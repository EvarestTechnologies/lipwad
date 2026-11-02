"""Domain types shared by the tools, the agent and the API."""

from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, model_validator
from pydantic import Field as PydanticField

SUBMISSION_WINDOW = timedelta(days=7)
RESUBMISSION_WINDOW = timedelta(days=14)


class Lifecycle(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    REJECTED = "rejected"
    PAID = "paid"


class Citation(BaseModel):
    kind: Literal["image", "audio", "rule"]
    source_id: str
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
        elif not self.rule_version:
            raise ValueError("rule citation requires rule_version")
        return self

    def _require_normalised_region(self) -> None:
        if not self.region:
            raise ValueError("image citation requires region")
        coordinates = [value for point in self.region for value in point]
        if any(value < 0 or value > 1 for value in coordinates):
            raise ValueError("region coordinates must be normalised to 0-1")

    def _require_time_span(self) -> None:
        if self.t_start is None or self.t_end is None:
            raise ValueError("audio citation requires t_start and t_end")
        if self.t_start >= self.t_end:
            raise ValueError("audio citation requires t_start before t_end")


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
    lifecycle: Lifecycle = Lifecycle.DRAFT
    discharge_date: date | None = None
    returned_at: datetime | None = None
    fields: list[Field] = PydanticField(default_factory=list)
    coded_lines: list[Field] = PydanticField(default_factory=list)
    flags: list[Flag] = PydanticField(default_factory=list)

    @property
    def uncited_field_names(self) -> list[str]:
        return [item.name for item in self.fields + self.coded_lines if not item.citations]

    @property
    def can_be_green(self) -> bool:
        return not self.uncited_field_names and not self.flags

    @property
    def submission_deadline(self) -> date | None:
        return self.discharge_date + SUBMISSION_WINDOW if self.discharge_date else None

    @property
    def resubmission_deadline(self) -> datetime | None:
        return self.returned_at + RESUBMISSION_WINDOW if self.returned_at else None
