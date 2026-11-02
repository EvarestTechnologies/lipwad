"""HIE adapter contract. Every implementation returns these FHIR-shaped responses."""

from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel

from app.db.schemas import Claim


class ClaimStatus(StrEnum):
    ACCEPTED = "accepted"
    RETURNED = "returned"
    REJECTED = "rejected"


class ClaimOutcome(BaseModel):
    status: ClaimStatus
    reason: str | None = None


class ClaimResponse(ClaimOutcome):
    resourceType: Literal["ClaimResponse"] = "ClaimResponse"
    id: str


class Eligibility(BaseModel):
    resourceType: Literal["CoverageEligibilityResponse"] = "CoverageEligibilityResponse"
    patient_ref: str
    eligible: bool


class PractitionerLookup(BaseModel):
    resourceType: Literal["Practitioner"] = "Practitioner"
    id: str
    found: bool
    name: str | None = None


class FacilityLookup(BaseModel):
    resourceType: Literal["Organization"] = "Organization"
    id: str
    found: bool
    level: int | None = None


class HieClaimNotFoundError(Exception):
    """The HIE has no claim with this ID."""


class HieEditRefusedError(Exception):
    """The claim is not in a state that allows editing."""


class HieAdapter(Protocol):
    def check_eligibility(self, patient_ref: str) -> Eligibility: ...

    def lookup_practitioner(self, practitioner_id: str) -> PractitionerLookup: ...

    def lookup_facility(self, facility_id: str) -> FacilityLookup: ...

    def submit_claim(self, claim: Claim) -> ClaimResponse: ...

    def get_claim_status(self, hie_id: str) -> ClaimResponse: ...

    def edit_claim(self, hie_id: str, patch: dict[str, str]) -> ClaimResponse: ...
