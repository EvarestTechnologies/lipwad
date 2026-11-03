"""Intake tool: read one photographed document into cited fields with Muse Spark vision.

Values the model cannot read, or reads with low confidence, become retake requests and
are never returned as fields.
"""

import base64
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.db.schemas import Citation, Field, Upload
from app.models import ChatMessage, ChatRequest, ModelClient

MIN_CONFIDENCE = 0.6
WHOLE_PAGE = [0.0, 0.0, 1.0, 1.0]

CLAIM_FORM_FIELDS = (
    "patient_name",
    "patient_ref",
    "visit_type",
    "admission_date",
    "discharge_date",
    "diagnosis",
    "practitioner_name",
    "practitioner_id",
    "facility_id",
)
REQUIRED_FIELDS = {"claim_form": ("patient_ref", "admission_date", "practitioner_id")}

DOCUMENT_PROMPTS = {
    "claim_form": (
        "You transcribe a photographed hospital claim form. Copy what is written; do not "
        "interpret, correct or add anything. Return JSON only: "
        '{"fields":[{"name":str,"value":str,"confidence":0-1,'
        '"bbox":[x0,y0,x1,y1] normalised 0-1 around the value,"quote":str}],'
        '"signature_present":bool,"signature_bbox":[x0,y0,x1,y1] around the signature line,'
        '"unreadable":[field names]}. '
        f"Field names: {', '.join(CLAIM_FORM_FIELDS)}. Dates as YYYY-MM-DD. "
        "Never guess: if a value is blurred or unclear, leave it out of fields and list "
        "its name in unreadable."
    ),
    "invoice": (
        "You transcribe a photographed hospital invoice. Copy what is written; do not "
        "interpret or add anything. Return JSON only: "
        '{"lines":[{"description":str,"amount":int,"bbox":[x0,y0,x1,y1]}],'
        '"total":{"amount":int,"bbox":[x0,y0,x1,y1]},'
        '"itemised":bool (true only if separate priced services are listed),'
        '"unreadable":[str]}. Amounts in Kenyan shillings without separators. '
        "Never guess: list anything unclear in unreadable."
    ),
}


class DocumentInput(BaseModel):
    upload: Upload
    case_id: str
    kind: Literal["claim_form", "invoice"]


class ExtractionResult(BaseModel):
    upload_id: str
    kind: Literal["claim_form", "invoice"]
    fields: list[Field]
    retake_reasons: list[str]
    model: str


def extract_document(document: DocumentInput, client: ModelClient) -> ExtractionResult:
    """Read one document into cited fields, or ask for a retake of what is unreadable."""
    encoded = base64.b64encode(Path(document.upload.path).read_bytes()).decode()
    request = ChatRequest(
        case_id=f"{document.case_id}/{Path(document.upload.filename).stem}",
        json_output=True,
        messages=[
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": DOCUMENT_PROMPTS[document.kind]},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                ],
            )
        ],
    )
    response = client.complete(request)
    try:
        data = _parse(response.content)
        result = (
            _claim_form(document, data)
            if document.kind == "claim_form"
            else _invoice(document, data)
        )
    except (ValueError, TypeError, AttributeError):
        result = ExtractionResult(
            upload_id=document.upload.id,
            kind=document.kind,
            fields=[],
            retake_reasons=[f"{document.kind} could not be read"],
            model="",
        )
    return result.model_copy(update={"model": response.model_id})


def _claim_form(document: DocumentInput, data: dict[str, Any]) -> ExtractionResult:
    upload_id = document.upload.id
    fields, retake = [], [f"{name} is unreadable" for name in data.get("unreadable", [])]
    for item in data.get("fields", []):
        name, raw = item.get("name"), item.get("value")
        if name not in CLAIM_FORM_FIELDS:
            continue
        value = str(raw).strip() if raw is not None else ""
        confidence = float(item.get("confidence") or 0)
        if not value or confidence < MIN_CONFIDENCE:
            retake.append(f"{name} is unclear")
            continue
        fields.append(
            _field(name, value, confidence, upload_id, item.get("bbox"), item.get("quote"))
        )
    read = {field.name for field in fields}
    for name in REQUIRED_FIELDS["claim_form"]:
        if name not in read and not any(reason.startswith(name) for reason in retake):
            retake.append(f"{name} is missing")
    signed = bool(data.get("signature_present"))
    fields.append(
        _field(
            "clinician_signature",
            "present" if signed else "absent",
            1.0,
            upload_id,
            data.get("signature_bbox"),
            None,
        )
    )
    return ExtractionResult(
        upload_id=upload_id, kind="claim_form", fields=fields, retake_reasons=retake, model=""
    )


def _invoice(document: DocumentInput, data: dict[str, Any]) -> ExtractionResult:
    upload_id = document.upload.id
    fields = [
        _field(
            f"invoice_line_{number}",
            f"{(line.get('description') or '').strip()}: KSh {_amount(line.get('amount'))}",
            1.0,
            upload_id,
            line.get("bbox"),
            line.get("description"),
        )
        for number, line in enumerate(data.get("lines", []), start=1)
    ]
    total = data.get("total") or {}
    if "amount" in total:
        fields.append(
            _field(
                "invoice_total",
                str(_amount(total["amount"])),
                1.0,
                upload_id,
                total.get("bbox"),
                None,
            )
        )
    lines = data.get("lines", [])
    fields.append(
        _field(
            "invoice_itemised",
            "yes" if data.get("itemised") and len(lines) > 1 else "no",
            1.0,
            upload_id,
            total.get("bbox") or (lines[0].get("bbox") if lines else None),
            None,
        )
    )
    retake = [f"{item} is unreadable" for item in data.get("unreadable", [])]
    return ExtractionResult(
        upload_id=upload_id, kind="invoice", fields=fields, retake_reasons=retake, model=""
    )


def _amount(value: Any) -> int:
    return int(str(value).replace(",", "").replace("KSh", "").strip())


def _field(
    name: str,
    value: str,
    confidence: float,
    upload_id: str,
    bbox: list[float] | None,
    quote: str | None,
) -> Field:
    citation = Citation(kind="image", source_id=upload_id, region=_region(bbox), quote=quote)
    return Field(name=name, value=value, confidence=confidence, citations=[citation])


def _region(bbox: list[float] | None) -> list[list[float]]:
    if not bbox or len(bbox) != 4:
        bbox = WHOLE_PAGE
    x0, y0, x1, y1 = (min(max(float(value), 0.0), 1.0) for value in bbox)
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _parse(content: str) -> dict[str, Any]:
    text = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data
