"""In-memory HIE with scripted outcomes for the synthetic cases."""

from app.db.schemas import Claim
from app.hie.base import (
    ClaimOutcome,
    ClaimResponse,
    ClaimStatus,
    Eligibility,
    FacilityLookup,
    HieClaimNotFoundError,
    HieEditRefusedError,
    PractitionerLookup,
)


class MockHIE:
    def __init__(
        self,
        outcomes: dict[str, ClaimOutcome] | None = None,
        practitioners: dict[str, str] | None = None,
        facilities: dict[str, int] | None = None,
        eligible_patients: set[str] | None = None,
    ) -> None:
        self._outcomes = outcomes or {}
        self._practitioners = practitioners or {}
        self._facilities = facilities or {}
        self._eligible_patients = eligible_patients or set()
        self._claims: dict[str, ClaimResponse] = {}

    def check_eligibility(self, patient_ref: str) -> Eligibility:
        return Eligibility(patient_ref=patient_ref, eligible=patient_ref in self._eligible_patients)

    def lookup_practitioner(self, practitioner_id: str) -> PractitionerLookup:
        name = self._practitioners.get(practitioner_id)
        return PractitionerLookup(id=practitioner_id, found=name is not None, name=name)

    def lookup_facility(self, facility_id: str) -> FacilityLookup:
        level = self._facilities.get(facility_id)
        return FacilityLookup(id=facility_id, found=level is not None, level=level)

    def submit_claim(self, claim: Claim) -> ClaimResponse:
        outcome = self._outcomes.get(claim.id, ClaimOutcome(status=ClaimStatus.ACCEPTED))
        response = ClaimResponse(id=f"HIE-{claim.id}", **outcome.model_dump())
        self._claims[response.id] = response
        return response

    def get_claim_status(self, hie_id: str) -> ClaimResponse:
        if hie_id not in self._claims:
            raise HieClaimNotFoundError(hie_id)
        return self._claims[hie_id]

    def edit_claim(self, hie_id: str, patch: dict[str, str]) -> ClaimResponse:
        current = self.get_claim_status(hie_id)
        if current.status is ClaimStatus.ACCEPTED:
            raise HieEditRefusedError(f"{hie_id} is already accepted")
        edited = ClaimResponse(id=hie_id, status=ClaimStatus.ACCEPTED)
        self._claims[hie_id] = edited
        return edited
