"""The claim agent: read the documents, verify them, check the rules, explain the result.

Vision and registry lookups gather cited evidence, deterministic checks decide the
status, and Muse Spark Open explains the outcome in English and Kiswahili. The model
never sets the status, so it cannot turn a blocked claim green.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.agent.rules import Evidence, check, rule
from app.db.repository import add_activity, list_uploads, load_claim, save_claim, save_upload
from app.db.schemas import ActivityStep, Field, Readiness, Upload
from app.hie.base import HieAdapter
from app.models import ChatMessage, ChatRequest, ModelAPIError, ModelClient
from app.tools.intake import DocumentInput, extract_document

DOCUMENTS = ("claim_form", "invoice")

EXPLAIN_PROMPT = (
    "You explain a hospital insurance claim review to a claims clerk. You never give "
    "clinical advice and never suggest adding or upgrading services. Given the extracted "
    "fields and the findings, return JSON only: "
    '{"summary": one sentence on what was checked, '
    '"explanation_en": what the clerk must do next in plain English, '
    '"explanation_sw": the same in Kiswahili}.'
)


def case_uploads(data_dir: Path, case_id: str) -> list[Upload]:
    return [
        Upload(
            id=f"{case_id}-{kind}",
            claim_id=case_id,
            kind="image",
            filename=f"{kind}.png",
            path=str(data_dir / case_id / f"{kind}.png"),
        )
        for kind in DOCUMENTS
        if (data_dir / case_id / f"{kind}.png").exists()
    ]


class ClaimAgent:
    def __init__(
        self,
        vision: ModelClient,
        reasoning: ModelClient,
        hie: HieAdapter,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._vision = vision
        self._reasoning = reasoning
        self._hie = hie
        self._clock = clock

    def run(self, session: Session, case_id: str, uploads: list[Upload]) -> None:
        claim = load_claim(session, case_id)
        known = {upload.id for upload in list_uploads(session, case_id)}
        fields: dict[str, Field] = {}
        retake: list[str] = []
        for upload in uploads:
            if upload.id not in known:
                save_upload(session, upload)
            kind = upload.filename.removesuffix(".png")
            result = extract_document(
                DocumentInput(upload=upload, case_id=case_id, kind=kind), self._vision
            )
            fields.update({field.name: field for field in result.fields})
            retake += result.retake_reasons
            self._log(
                session,
                case_id,
                "read",
                f"Read {kind}: {len(result.fields)} cited values"
                + (
                    f"; retake needed ({'; '.join(result.retake_reasons)})"
                    if result.retake_reasons
                    else ""
                ),
                "muse-spark-1.3",
                [c for field in result.fields[:3] for c in field.citations],
            )

        practitioner = fields.get("practitioner_id")
        found = self._hie.lookup_practitioner(practitioner.value).found if practitioner else None
        facility = fields.get("facility_id")
        level = self._hie.lookup_facility(facility.value).level if facility else None
        if practitioner:
            self._log(
                session,
                case_id,
                "check",
                f"Practitioner registry: {practitioner.value} "
                + ("found" if found else "not found"),
                None,
                practitioner.citations,
            )

        flags = check(claim, Evidence(fields, retake, found, level), self._clock())
        coded = []
        if "diagnosis" in fields:
            coded.append(
                Field(
                    name="service_code",
                    value="PLACEHOLDER-001",
                    confidence=fields["diagnosis"].confidence,
                    citations=[*fields["diagnosis"].citations, rule("TERM-PLACEHOLDER")],
                )
            )
        claim = claim.model_copy(
            update={"fields": list(fields.values()), "coded_lines": coded, "flags": flags}
        )
        readiness = _readiness(claim)
        claim = claim.model_copy(update={"readiness": readiness})
        save_claim(session, claim)
        reasons = ", ".join(flag.code for flag in flags) or "none"
        self._log(
            session,
            case_id,
            "decide",
            f"Status {readiness.value}; reasons: {reasons}",
            None,
            [c for flag in flags for c in flag.citations],
        )
        self._explain(session, claim)

    def _explain(self, session: Session, claim) -> None:
        payload = {
            "fields": {field.name: field.value for field in claim.fields},
            "status": claim.readiness.value,
            "findings": [flag.code for flag in claim.flags],
        }
        request = ChatRequest(
            case_id=claim.id,
            json_output=True,
            messages=[
                ChatMessage(role="system", content=EXPLAIN_PROMPT),
                ChatMessage(role="user", content=json.dumps(payload)),
            ],
        )
        try:
            response = self._reasoning.complete(request)
            body = json.loads(response.content)
            text = f"{body['summary']} {body['explanation_en']} | SW: {body['explanation_sw']}"
            self._log(session, claim.id, "decide", text, response.model_id, [])
        except (ModelAPIError, ValueError, KeyError) as error:
            self._log(session, claim.id, "decide", f"Explanation unavailable: {error}", None, [])

    def _log(self, session, claim_id, kind, text, model, citations) -> None:
        add_activity(
            session,
            ActivityStep(
                claim_id=claim_id,
                at=self._clock(),
                kind=kind,
                text=text,
                model=model,
                citations=citations,
            ),
        )


def _readiness(claim) -> Readiness:
    if any(flag.severity == "red" for flag in claim.flags):
        return Readiness.RED
    if claim.can_be_green:
        return Readiness.GREEN
    return Readiness.AMBER
