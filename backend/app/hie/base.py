"""HIE adapter contract. Every implementation returns these FHIR-shaped responses.

ClaimResponse follows FHIR in keeping `status` for the resource and the adjudication
result in `outcome` and `error`. The shapes have not yet been checked against DHA
sandbox responses, so SandboxHIE may need a translation step.
"""

from enum import StrEnum
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, field_validator
from pydantic import Field as PydanticField

from app.db.schemas import Claim, Field, Lifecycle, NonBlank

RESUBMISSION_DAYS = 14


class Adjudication(StrEnum):
    ACCEPT = "accept"
    RETURN = "return"
    REJECT = "reject"
    PAID = "paid"


LIFECYCLE_FOR = {
    Adjudication.ACCEPT: Lifecycle.SUBMITTED,
    Adjudication.RETURN: Lifecycle.RETURNED,
    Adjudication.REJECT: Lifecycle.REJECTED,
    Adjudication.PAID: Lifecycle.PAID,
}


class ClaimResponse(BaseModel):
    resourceType: Literal["ClaimResponse"] = "ClaimResponse"
    id: str
    status: Literal["active"] = "active"
    outcome: Adjudication
    error: list[str] = PydanticField(default_factory=list)
    outcome_at: AwareDatetime

    @property
    def lifecycle(self) -> Lifecycle:
        return LIFECYCLE_FOR[self.outcome]


class Confirmation(BaseModel):
    """Who approved a submission. Required by every submit."""

    confirmed_by: NonBlank
    confirmed_at: AwareDatetime


class ClaimPatch(BaseModel):
    """Corrections sent on a resubmission. Each one keeps its evidence."""

    corrections: list[Field] = PydanticField(min_length=1)

    @field_validator("corrections")
    @classmethod
    def corrections_are_cited(cls, corrections: list[Field]) -> list[Field]:
        if any(not item.citations for item in corrections):
            raise ValueError("every correction must carry a citation")
        return corrections


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


class HieDuplicateClaimError(Exception):
    """The claim was already submitted; corrections go through edit_claim."""


class HieEditRefusedError(Exception):
    """The claim cannot be edited, because of its state or an expired window."""


class HieAdapter(Protocol):
    def check_eligibility(self, patient_ref: str) -> Eligibility: ...

    def lookup_practitioner(self, practitioner_id: str) -> PractitionerLookup: ...

    def lookup_facility(self, facility_id: str) -> FacilityLookup: ...

    def submit_claim(self, claim: Claim, confirmation: Confirmation) -> ClaimResponse: ...

    def get_claim_status(self, hie_id: str) -> ClaimResponse: ...

    def edit_claim(self, hie_id: str, patch: ClaimPatch) -> ClaimResponse: ...
