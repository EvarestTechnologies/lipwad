"""HIE stand-in with scripted outcomes for the synthetic cases.

Submitted claims are kept in a JSON file when `state_path` is set, so they survive a
container restart alongside the claims stored in the database.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel
from pydantic import Field as PydanticField

from app.db.schemas import Claim
from app.hie.base import (
    RESUBMISSION_DAYS,
    Adjudication,
    ClaimPatch,
    ClaimResponse,
    Confirmation,
    Eligibility,
    FacilityLookup,
    HieClaimNotFoundError,
    HieDuplicateClaimError,
    HieEditRefusedError,
    PractitionerLookup,
)


class ScriptedOutcome(BaseModel):
    outcome: Adjudication = Adjudication.ACCEPT
    reasons: list[str] = PydanticField(default_factory=list)
    days_since_outcome: int = 0
    after_edit: "ScriptedOutcome | None" = None


class MockScript(BaseModel):
    outcomes: dict[str, ScriptedOutcome] = PydanticField(default_factory=dict)
    practitioners: dict[str, str] = PydanticField(default_factory=dict)
    facilities: dict[str, int] = PydanticField(default_factory=dict)
    eligible_patients: set[str] = PydanticField(default_factory=set)


def _now() -> datetime:
    return datetime.now(UTC)


class MockHIE:
    def __init__(
        self,
        script: MockScript | None = None,
        state_path: Path | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._script = script or MockScript()
        self._state_path = state_path
        self._clock = clock
        self._claims: dict[str, ClaimResponse] = {}
        self._edits: dict[str, list[ClaimPatch]] = {}
        if state_path and state_path.exists():
            stored = json.loads(state_path.read_text())
            self._claims = {
                key: ClaimResponse.model_validate(value) for key, value in stored["claims"].items()
            }
            self._edits = {
                key: [ClaimPatch.model_validate(item) for item in value]
                for key, value in stored["edits"].items()
            }

    def check_eligibility(self, patient_ref: str) -> Eligibility:
        eligible = patient_ref in self._script.eligible_patients
        return Eligibility(patient_ref=patient_ref, eligible=eligible)

    def lookup_practitioner(self, practitioner_id: str) -> PractitionerLookup:
        name = self._script.practitioners.get(practitioner_id)
        return PractitionerLookup(id=practitioner_id, found=name is not None, name=name)

    def lookup_facility(self, facility_id: str) -> FacilityLookup:
        level = self._script.facilities.get(facility_id)
        return FacilityLookup(id=facility_id, found=level is not None, level=level)

    def submit_claim(self, claim: Claim, confirmation: Confirmation) -> ClaimResponse:
        hie_id = f"HIE-{claim.id}"
        if hie_id in self._claims:
            raise HieDuplicateClaimError(hie_id)
        scripted = self._script.outcomes.get(claim.id, ScriptedOutcome())
        return self._record(hie_id, scripted)

    def get_claim_status(self, hie_id: str) -> ClaimResponse:
        if hie_id not in self._claims:
            raise HieClaimNotFoundError(hie_id)
        return self._claims[hie_id]

    def edit_claim(self, hie_id: str, patch: ClaimPatch) -> ClaimResponse:
        current = self.get_claim_status(hie_id)
        if current.outcome not in (Adjudication.RETURN, Adjudication.REJECT):
            raise HieEditRefusedError(f"{hie_id} is {current.outcome}")
        if self._clock() > current.outcome_at + timedelta(days=RESUBMISSION_DAYS):
            raise HieEditRefusedError(f"{hie_id}: resubmission window has closed")
        self._edits.setdefault(hie_id, []).append(patch)
        claim_id = hie_id.removeprefix("HIE-")
        scripted = self._script.outcomes.get(claim_id, ScriptedOutcome())
        return self._record(hie_id, scripted.after_edit or ScriptedOutcome())

    def recorded_edits(self, hie_id: str) -> list[ClaimPatch]:
        return list(self._edits.get(hie_id, []))

    def settle(self, hie_id: str) -> ClaimResponse:
        """Mark an accepted claim as paid, standing in for SHA's later payment."""
        if self.get_claim_status(hie_id).outcome is not Adjudication.ACCEPT:
            raise HieEditRefusedError(f"{hie_id} is not accepted")
        return self._record(hie_id, ScriptedOutcome(outcome=Adjudication.PAID))

    def _record(self, hie_id: str, scripted: ScriptedOutcome) -> ClaimResponse:
        response = ClaimResponse(
            id=hie_id,
            outcome=scripted.outcome,
            error=scripted.reasons,
            outcome_at=self._clock() - timedelta(days=scripted.days_since_outcome),
        )
        self._claims[hie_id] = response
        self._persist()
        return response

    def _persist(self) -> None:
        if self._state_path is None:
            return
        self._state_path.write_text(
            json.dumps(
                {
                    "claims": {
                        key: value.model_dump(mode="json") for key, value in self._claims.items()
                    },
                    "edits": {
                        key: [
                            item.model_dump(mode="json", exclude_computed_fields=True)
                            for item in value
                        ]
                        for key, value in self._edits.items()
                    },
                }
            )
        )
