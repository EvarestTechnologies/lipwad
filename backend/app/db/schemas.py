"""Domain types shared by the tools, the agent and the API."""

import math
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, StringConstraints, computed_field, model_validator
from pydantic import Field as PydanticField

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

SUBMISSION_WINDOW = timedelta(days=7)
RESUBMISSION_WINDOW = timedelta(days=14)


class Lifecycle(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    REJECTED = "rejected"
    PAID = "paid"


class Readiness(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class Citation(BaseModel):
    kind: Literal["image", "audio", "rule"]
    source_id: NonBlank
    region: list[list[float]] | None = None
    page: int | None = None
    t_start: float | None = None
    t_end: float | None = None
    rule_version: str | None = None
    quote: str | None = None

    @model_validator(mode="after")
    def locates_its_source(self) -> "Citation":
        if self.kind == "image":
            self._require_normalised_region()
        elif self.kind == "audio":
            self._require_time_span()
        elif not (self.rule_version and self.rule_version.strip()):
            raise ValueError("rule citation requires rule_version")
        return self

    def _require_normalised_region(self) -> None:
        if not self.region:
            raise ValueError("image citation requires region")
        if any(len(point) != 2 for point in self.region):
            raise ValueError("region points must be [x, y] pairs")
        coordinates = [value for point in self.region for value in point]
        if not all(0 <= value <= 1 for value in coordinates):
            raise ValueError("region coordinates must be normalised to 0-1")

    def _require_time_span(self) -> None:
        if self.t_start is None or self.t_end is None:
            raise ValueError("audio citation requires t_start and t_end")
        if not (math.isfinite(self.t_start) and math.isfinite(self.t_end)):
            raise ValueError("audio citation requires finite timestamps")
        if not 0 <= self.t_start < self.t_end:
            raise ValueError("audio citation requires 0 <= t_start < t_end")


class Field(BaseModel):
    name: str
    value: str
    confidence: float = PydanticField(ge=0, le=1)
    citations: list[Citation] = PydanticField(default_factory=list)
    confirmed_by: str | None = None


class Flag(BaseModel):
    code: str
    severity: Literal["amber", "red"]
    citations: list[Citation] = PydanticField(default_factory=list)


class Upload(BaseModel):
    id: str
    claim_id: str
    kind: Literal["image", "audio"]
    filename: str
    path: str


class Claim(BaseModel):
    id: str
    version: int = 0
    lifecycle: Lifecycle = Lifecycle.DRAFT
    readiness: Readiness | None = None
    hie_id: str | None = None
    discharge_date: date | None = None
    returned_at: AwareDatetime | None = None  # set when the HIE returns or rejects the claim
    fields: list[Field] = PydanticField(default_factory=list)
    coded_lines: list[Field] = PydanticField(default_factory=list)
    flags: list[Flag] = PydanticField(default_factory=list)

    @computed_field
    @property
    def uncited_field_names(self) -> list[str]:
        return [item.name for item in self.fields + self.coded_lines if not item.citations]

    @computed_field
    @property
    def can_be_green(self) -> bool:
        has_evidence = bool(self.fields and self.coded_lines)
        return has_evidence and not self.uncited_field_names and not self.flags

    @computed_field
    @property
    def submission_deadline(self) -> date | None:
        if self.lifecycle is not Lifecycle.DRAFT or self.discharge_date is None:
            return None
        return self.discharge_date + SUBMISSION_WINDOW

    @computed_field
    @property
    def resubmission_deadline(self) -> datetime | None:
        if self.lifecycle not in (Lifecycle.RETURNED, Lifecycle.REJECTED):
            return None
        return self.returned_at + RESUBMISSION_WINDOW if self.returned_at else None


class ActivityStep(BaseModel):
    """One thing the agent did, shown in the Today feed."""

    claim_id: str
    at: AwareDatetime
    kind: Literal["read", "check", "decide", "hie", "human"]
    text: str
    model: str | None = None
    citations: list[Citation] = PydanticField(default_factory=list)
