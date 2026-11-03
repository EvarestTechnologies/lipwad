from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import AwareDatetime, BaseModel

from app.agent.rules import RULE_VERSION, RULES
from app.agent.run import RescueError, case_uploads, signed_upload
from app.db.repository import list_activity, list_uploads, load_claim
from app.db.schemas import Lifecycle, NonBlank, Readiness
from app.db.tables import ClaimRow, UploadRow
from app.hie.base import Confirmation, HieDuplicateClaimError, HieEditRefusedError
from app.services import Services

ACTIONS = {
    "signature_missing": "Ask the clinician to sign, then snap the signed page",
    "itemised_invoice_missing": "Snap the itemised invoice",
    "service_type_inconsistent": "Correct the service type to match the documents",
    "practitioner_not_found": "Confirm the practitioner's registration number",
    "service_outside_facility_level": "Check the service against this facility's level",
    "retake_required": "Retake the photo in better light",
    "resubmission_deadline_near": "Fix and resubmit before the window closes",
    "claim_rejected": "Review the rejection and resubmit",
}

TODAY_FEED = 8


class ConfirmBody(BaseModel):
    confirmed_by: NonBlank


def router(services: Services) -> APIRouter:
    api = APIRouter()

    def detail(session, claim_id: str) -> dict:
        claim = load_claim(session, claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
        return {
            "claim": claim.model_dump(mode="json"),
            "uploads": [upload.model_dump() for upload in list_uploads(session, claim_id)],
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
            detail(session, claim_id)
            uploads = case_uploads(services.data_dir, claim_id)
            try:
                services.agent.run(session, claim_id, uploads)
            except RescueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.commit()
            return detail(session, claim_id)

    @api.post("/claims/{claim_id}/submit")
    def submit(claim_id: str, body: ConfirmBody) -> dict:
        with services.sessions() as session:
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
            detail(session, claim_id)
            upload = signed_upload(services.data_dir, claim_id)
            if upload is None:
                raise HTTPException(status_code=409, detail="no corrected page to read")
            try:
                draft = services.agent.rescue(session, claim_id, upload)
            except RescueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.commit()
            return draft

    @api.post("/claims/{claim_id}/resubmit")
    def resubmit(claim_id: str, body: ConfirmBody) -> dict:
        with services.sessions() as session:
            detail(session, claim_id)
            try:
                services.agent.resubmit(session, claim_id, _confirmation(body))
            except (RescueError, HieEditRefusedError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            session.commit()
            return detail(session, claim_id)

    @api.get("/uploads/{upload_id}/image")
    def image(upload_id: str) -> FileResponse:
        with services.sessions() as session:
            row = session.get(UploadRow, upload_id)
            if row is None:
                raise HTTPException(status_code=404)
            return FileResponse(row.path, media_type="image/png")

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

    return api


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
