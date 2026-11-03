import hmac
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import AwareDatetime, BaseModel, StringConstraints
from sqlalchemy.exc import IntegrityError

from app.agent.rules import RULE_VERSION, RULES
from app.agent.run import RescueError, case_uploads, signed_upload
from app.db.repository import StaleClaimError, list_activity, list_uploads, load_claim
from app.db.schemas import Lifecycle, Readiness
from app.db.tables import ClaimRow, UploadRow
from app.hie.base import Confirmation, HieDuplicateClaimError, HieEditRefusedError
from app.services import ClaimBusyError, Services

ACTIONS = {
    "signature_missing": "Ask the clinician to sign, then snap the signed page",
    "itemised_invoice_missing": "Snap the itemised invoice",
    "service_type_inconsistent": "Correct the service type to match the documents",
    "practitioner_not_found": "Confirm the practitioner's registration number",
    "service_outside_facility_level": "Check the service against this facility's level",
    "retake_required": "Retake the photo in better light",
    "resubmission_deadline_near": "Fix and resubmit before the window closes",
    "claim_rejected": "Review the rejection and resubmit",
    "admission_date_mismatch": "Confirm the admission date with the ward and correct it",
    "voice_note_unclear": "Record the voice note again somewhere quiet",
}

TODAY_FEED = 8


PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
BUDGET_SPENT = (
    "Lipwad has used today's demo allowance of model runs. Everything already reviewed "
    "can still be opened; new reviews resume tomorrow."
)


class ConfirmBody(BaseModel):
    confirmed_by: PersonName


def router(services: Services) -> APIRouter:
    api = APIRouter(dependencies=[Depends(services.maybe_reset)])
    admin = APIRouter()

    @contextmanager
    def working_on(claim_id: str, paid: bool = False):
        """One request per claim at a time; paid runs also draw on the daily budget."""
        try:
            with services.claim_lock(claim_id):
                if paid and services.budget is not None and not services.budget.spend():
                    raise HTTPException(status_code=429, detail=BUDGET_SPENT)
                yield
        except ClaimBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (StaleClaimError, IntegrityError) as error:
            raise HTTPException(
                status_code=409, detail="The claim changed while Lipwad was working; try again"
            ) from error

    def detail(session, claim_id: str) -> dict:
        claim = load_claim(session, claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
        return {
            "claim": claim.model_dump(mode="json"),
            "uploads": [upload.model_dump() for upload in list_uploads(session, claim_id)],
            "has_corrected_page": signed_upload(services.data_dir, claim_id) is not None,
            "activity": [
                step.model_dump(mode="json") for step in reversed(list_activity(session, claim_id))
            ],
        }

    @api.get("/claims")
    def claims() -> list[dict]:
        with services.sessions() as session:
            ids = session.query(ClaimRow.id).order_by(ClaimRow.id).all()
            return [_summary(load_claim(session, claim_id)) for (claim_id,) in ids]

    @api.get("/claims/{claim_id}")
    def claim(claim_id: str) -> dict:
        with services.sessions() as session:
            return detail(session, claim_id)

    @api.post("/claims/{claim_id}/run")
    def run(claim_id: str) -> dict:
        with services.sessions() as session:
            claim = detail(session, claim_id)["claim"]
            if _with_sha(claim):
                raise HTTPException(status_code=409, detail=f"{claim_id} is already with SHA")
            if _corrected(claim) and claim["lifecycle"] != Lifecycle.DRAFT.value:
                raise HTTPException(
                    status_code=409, detail=f"{claim_id} has a drafted fix; resubmit it"
                )
        with services.sessions() as session, working_on(claim_id, paid=True):
            uploads = case_uploads(services.data_dir, claim_id)
            try:
                services.agent.run(session, claim_id, uploads)
            except RescueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.commit()
            return detail(session, claim_id)

    @api.post("/claims/{claim_id}/submit")
    def submit(claim_id: str, body: ConfirmBody) -> dict:
        with services.sessions() as session, working_on(claim_id):
            detail(session, claim_id)
            try:
                services.agent.submit(session, claim_id, _confirmation(body))
            except (RescueError, HieDuplicateClaimError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.commit()
            return detail(session, claim_id)

    @api.post("/claims/{claim_id}/rescue")
    def rescue(claim_id: str) -> dict:
        with services.sessions() as session:
            claim = detail(session, claim_id)["claim"]
            if _with_sha(claim):
                raise HTTPException(status_code=409, detail=f"{claim_id} is already with SHA")
            if _corrected(claim):
                raise HTTPException(
                    status_code=409, detail=f"{claim_id} already has its corrected page"
                )
            if claim["lifecycle"] == Lifecycle.DRAFT.value and claim["readiness"] is None:
                raise HTTPException(
                    status_code=409, detail=f"Review {claim_id} before adding a corrected page"
                )
            upload = signed_upload(services.data_dir, claim_id)
            if upload is None:
                raise HTTPException(status_code=409, detail="no corrected page to read")
        with services.sessions() as session, working_on(claim_id, paid=True):
            try:
                draft = services.agent.rescue(session, claim_id, upload)
            except RescueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.commit()
            return draft

    @api.post("/claims/{claim_id}/resubmit")
    def resubmit(claim_id: str, body: ConfirmBody) -> dict:
        with services.sessions() as session, working_on(claim_id):
            detail(session, claim_id)
            try:
                services.agent.resubmit(session, claim_id, _confirmation(body))
            except (RescueError, HieEditRefusedError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.commit()
            return detail(session, claim_id)

    @api.get("/uploads/{upload_id}/image")
    @api.get("/uploads/{upload_id}/file")
    def upload_file(upload_id: str) -> FileResponse:
        with services.sessions() as session:
            row = session.get(UploadRow, upload_id)
            if row is None:
                raise HTTPException(status_code=404)
            media = "audio/wav" if row.path.endswith(".wav") else "image/png"
            return FileResponse(row.path, media_type=media)

    @admin.post("/demo/snapshot", include_in_schema=False)
    def snapshot(x_admin_key: Annotated[str | None, Header()] = None) -> dict:
        """Save the current demo as the state the scheduled reset restores."""
        if not services.admin_key or services.demo is None:
            raise HTTPException(status_code=404)
        if not x_admin_key or not hmac.compare_digest(x_admin_key, services.admin_key):
            raise HTTPException(status_code=403)
        services.demo.snapshot()
        return {"ok": True}

    @api.get("/rules")
    def rules() -> list[dict]:
        return [
            {"id": rule_id, "checks": checks, "version": RULE_VERSION, "source_registered": False}
            for rule_id, checks in RULES.items()
        ]

    @api.get("/today")
    def today() -> dict:
        with services.sessions() as session:
            ids = [claim_id for (claim_id,) in session.query(ClaimRow.id).all()]
            summaries = [_summary(load_claim(session, claim_id)) for claim_id in ids]
            tasks = [{**item, "claim_id": item["id"]} for item in summaries if item["reasons"]]
            return {
                "at_risk_ksh": sum(item["amount_ksh"] or 0 for item in tasks),
                "tasks": sorted(tasks, key=lambda item: item["deadline"] or "9999"),
                "activity": [
                    step.model_dump(mode="json")
                    for step in reversed(list_activity(session, latest=TODAY_FEED))
                ],
            }

    outer = APIRouter()
    outer.include_router(api)
    outer.include_router(admin)
    return outer


def _with_sha(claim: dict) -> bool:
    return claim["lifecycle"] in (Lifecycle.SUBMITTED.value, Lifecycle.PAID.value)


def _corrected(claim: dict) -> bool:
    return any(
        citation["source_id"].endswith("-claim_form_signed")
        for field in claim["fields"]
        for citation in field["citations"]
    )


def _confirmation(body: ConfirmBody) -> Confirmation:
    from datetime import UTC, datetime

    return Confirmation(confirmed_by=body.confirmed_by, confirmed_at=datetime.now(UTC))


def _summary(claim) -> dict:
    values = {field.name: field.value for field in claim.fields}
    amount = values.get("invoice_total")
    deadline: AwareDatetime | None = claim.resubmission_deadline
    reasons = [flag.code for flag in claim.flags]
    return {
        "id": claim.id,
        "patient_name": values.get("patient_name"),
        "readiness": claim.readiness.value if claim.readiness else None,
        "lifecycle": claim.lifecycle.value,
        "reasons": reasons,
        "actions": [ACTIONS.get(code, code) for code in reasons],
        "amount_ksh": int(amount) if amount and amount.isdigit() else None,
        "deadline": deadline.isoformat() if deadline else None,
        "rescue": claim.lifecycle in (Lifecycle.RETURNED, Lifecycle.REJECTED),
        "ready": claim.readiness is Readiness.GREEN,
    }
