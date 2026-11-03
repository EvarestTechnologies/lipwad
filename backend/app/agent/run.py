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
from app.db.schemas import ActivityStep, Field, Lifecycle, Readiness, Upload
from app.hie.base import ClaimPatch, Confirmation, HieAdapter
from app.models import (
    ChatMessage,
    ChatRequest,
    ModelAPIError,
    ModelClient,
    StubFixtureMissingError,
)
from app.models.transcribe import Transcriber
from app.tools.intake import DocumentInput, extract_document
from app.tools.listen import NoteInput, transcribe_note

DOCUMENTS = ("claim_form", "invoice")
VOICE_NOTE = "voice_note.wav"

EXPLAIN_PROMPT = (
    "You write for a hospital claims clerk in Kenya who prepares claims for SHA. Given "
    "the extracted fields, the status and the findings, tell the clerk what to do next "
    "to get this claim paid. At most two short sentences, plain words, no field names "
    "in snake_case. You never give clinical advice, never suggest adding or upgrading "
    "services, and never tell the clerk to approve or pay a claim: SHA does that. "
    'Return JSON only: {"explanation_en": English text, "explanation_sw": the same in '
    "Kiswahili}."
)


def case_uploads(data_dir: Path, case_id: str) -> list[Upload]:
    uploads = [
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
    if (data_dir / case_id / VOICE_NOTE).exists():
        uploads.append(
            Upload(
                id=f"{case_id}-voice_note",
                claim_id=case_id,
                kind="audio",
                filename=VOICE_NOTE,
                path=str(data_dir / case_id / VOICE_NOTE),
            )
        )
    return uploads


class ClaimAgent:
    def __init__(
        self,
        vision: ModelClient,
        reasoning: ModelClient,
        hie: HieAdapter,
        transcriber: Transcriber | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transcriber = transcriber
        self._vision = vision
        self._reasoning = reasoning
        self._hie = hie
        self._clock = clock

    def run(self, session: Session, case_id: str, uploads: list[Upload]) -> None:
        claim = load_claim(session, case_id)
        if claim.lifecycle in (Lifecycle.SUBMITTED, Lifecycle.PAID):
            raise RescueError(f"{case_id} is already with SHA")
        if any(
            c.source_id.endswith("-claim_form_signed") for f in claim.fields for c in f.citations
        ):
            raise RescueError(f"{case_id} has a drafted rescue; resubmit it instead")
        known = {upload.id for upload in list_uploads(session, case_id)}
        fields: dict[str, Field] = {}
        retake: list[str] = []
        for upload in uploads:
            if upload.id not in known:
                save_upload(session, upload)
            if upload.kind == "audio":
                self._listen(session, case_id, upload, fields, retake)
                continue
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
                result.model,
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

    def _listen(self, session, case_id, upload, fields, retake) -> None:
        if self._transcriber is None:
            self._log(session, case_id, "read", "Voice note skipped: no transcriber", None, [])
            return
        try:
            result = transcribe_note(NoteInput(upload=upload, case_id=case_id), self._transcriber)
        except (ModelAPIError, StubFixtureMissingError) as error:
            self._log(session, case_id, "read", f"Voice note unavailable: {error}", None, [])
            return
        fields.update({field.name: field for field in result.fields})
        retake += result.retake_reasons
        heard = "; ".join(f'"{c.quote}"' for f in result.fields for c in f.citations)
        self._log(
            session,
            case_id,
            "read",
            f"Heard voice note: {len(result.fields)} cited values"
            + (f" ({heard})" if heard else "")
            + (f"; {'; '.join(result.retake_reasons)}" if result.retake_reasons else ""),
            result.model,
            [c for field in result.fields for c in field.citations],
        )

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
            text = f"{body['explanation_en']} | SW: {body['explanation_sw']}"
            self._log(session, claim.id, "decide", text, response.model_id, [])
        except (
            ModelAPIError,
            StubFixtureMissingError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            self._log(session, claim.id, "decide", f"Explanation unavailable: {error}", None, [])

    def rescue(self, session: Session, case_id: str, upload: Upload) -> dict:
        """Re-read a corrected page and redo the checks. Only evidence changes the claim."""
        claim = load_claim(session, case_id)
        if claim.lifecycle not in (Lifecycle.RETURNED, Lifecycle.REJECTED):
            raise RescueError(f"{case_id} is {claim.lifecycle.value}, not returned or rejected")
        reasons = [flag.code for flag in claim.flags if flag.code not in SETTLEMENT_FLAGS]
        if upload.id not in {item.id for item in list_uploads(session, case_id)}:
            save_upload(session, upload)
        result = extract_document(
            DocumentInput(upload=upload, case_id=case_id, kind="claim_form"),
            self._vision,
        )
        before = {field.name: field.value for field in claim.fields}
        fields = {field.name: field for field in claim.fields}
        changes = []
        for field in result.fields:
            if before.get(field.name) != field.value:
                changes.append(
                    {"field": field.name, "before": before.get(field.name), "after": field.value}
                )
                fields[field.name] = field
        practitioner = fields.get("practitioner_id")
        found = self._hie.lookup_practitioner(practitioner.value).found if practitioner else None
        facility = fields.get("facility_id")
        level = self._hie.lookup_facility(facility.value).level if facility else None
        flags = check(claim, Evidence(fields, result.retake_reasons, found, level), self._clock())
        claim = claim.model_copy(update={"fields": list(fields.values()), "flags": flags})
        claim = claim.model_copy(update={"readiness": _readiness(claim)})
        save_claim(session, claim)
        summary = (
            "; ".join(f"{c['field']}: {c['before']} -> {c['after']}" for c in changes)
            or "no changes"
        )
        self._log(
            session,
            case_id,
            "check",
            f"Rescue drafted from the corrected page: {summary}",
            result.model,
            [
                c
                for field in result.fields
                if field.name in {x["field"] for x in changes}
                for c in field.citations
            ],
        )
        return {"reason": reasons, "changes": changes}

    def resubmit(self, session: Session, case_id: str, confirmation: Confirmation) -> None:
        claim = load_claim(session, case_id)
        signed = f"{case_id}-claim_form_signed"
        corrections = [
            field
            for field in claim.fields
            if any(citation.source_id == signed for citation in field.citations)
        ]
        blocking = [flag.code for flag in claim.flags if flag.code not in SETTLEMENT_FLAGS]
        if not corrections or blocking:
            raise RescueError(f"{case_id} has no drafted fix or is still blocked: {blocking}")
        response = self._hie.edit_claim(claim.hie_id, ClaimPatch(corrections=corrections))
        claim = claim.model_copy(
            update={
                "lifecycle": response.lifecycle,
                "returned_at": response.outcome_at
                if response.lifecycle in (Lifecycle.RETURNED, Lifecycle.REJECTED)
                else claim.returned_at,
                "flags": [flag for flag in claim.flags if flag.code not in SETTLEMENT_FLAGS]
                if response.lifecycle is Lifecycle.SUBMITTED
                else claim.flags,
            }
        )
        claim = claim.model_copy(update={"readiness": _readiness(claim)})
        save_claim(session, claim)
        self._log(
            session,
            case_id,
            "hie",
            f"Resubmitted after confirmation by {confirmation.confirmed_by}; HIE outcome: "
            f"{response.outcome.value}",
            None,
            [],
        )

    def submit(self, session: Session, case_id: str, confirmation: Confirmation) -> None:
        claim = load_claim(session, case_id)
        if claim.readiness is not Readiness.GREEN or claim.lifecycle is not Lifecycle.DRAFT:
            raise RescueError(f"{case_id} is not a green draft")
        response = self._hie.submit_claim(claim, confirmation)
        claim = claim.model_copy(update={"lifecycle": response.lifecycle, "hie_id": response.id})
        if response.lifecycle in (Lifecycle.RETURNED, Lifecycle.REJECTED):
            claim = claim.model_copy(update={"returned_at": response.outcome_at})
        save_claim(session, claim)
        self._log(
            session,
            case_id,
            "hie",
            f"Submitted after confirmation by {confirmation.confirmed_by}; HIE outcome: "
            f"{response.outcome.value}",
            None,
            [],
        )

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


SETTLEMENT_FLAGS = {"resubmission_deadline_near", "claim_rejected"}


class RescueError(Exception):
    """The claim cannot be rescued or resubmitted in its current state."""


def signed_upload(data_dir: Path, case_id: str) -> Upload | None:
    path = data_dir / case_id / "claim_form_signed.png"
    if not path.exists():
        return None
    return Upload(
        id=f"{case_id}-claim_form_signed",
        claim_id=case_id,
        kind="image",
        filename="claim_form_signed.png",
        path=str(path),
    )


def _readiness(claim) -> Readiness:
    if any(flag.severity == "red" for flag in claim.flags):
        return Readiness.RED
    if claim.can_be_green:
        return Readiness.GREEN
    return Readiness.AMBER
