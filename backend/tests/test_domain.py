from datetime import date, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.repository import load_claim, save_claim
from app.db.schemas import Citation, Claim, Field, Flag, Lifecycle
from app.db.tables import Base


def image_citation() -> Citation:
    return Citation(
        kind="image",
        source_id="upload-1",
        region=[[0.1, 0.2], [0.4, 0.2], [0.4, 0.3]],
        page=2,
        quote="Admitted 12/10/2026",
    )


def field(citations: list[Citation] | None = None) -> Field:
    return Field(
        name="admission_date", value="2026-10-12", confidence=0.93, citations=citations or []
    )


def test_image_citation_requires_region() -> None:
    with pytest.raises(ValidationError):
        Citation(kind="image", source_id="upload-1")


def test_image_region_must_be_normalised() -> None:
    with pytest.raises(ValidationError):
        Citation(kind="image", source_id="upload-1", region=[[10.0, 0.2], [0.4, 0.2]])


def test_audio_citation_requires_increasing_timestamps() -> None:
    with pytest.raises(ValidationError):
        Citation(kind="audio", source_id="upload-2", t_start=9.0, t_end=4.0)


def test_audio_citation_requires_timestamps() -> None:
    with pytest.raises(ValidationError):
        Citation(kind="audio", source_id="upload-2")


def test_rule_citation_requires_version() -> None:
    with pytest.raises(ValidationError):
        Citation(kind="rule", source_id="SHA-BEN-01")


def test_uncited_field_blocks_green() -> None:
    claim = Claim(id="claim-1", fields=[field()])

    assert claim.uncited_field_names == ["admission_date"]
    assert not claim.can_be_green


def test_uncited_coded_line_blocks_green() -> None:
    line = Field(name="diagnosis_code", value="X00", confidence=0.8, citations=[])
    claim = Claim(id="claim-1", fields=[field([image_citation()])], coded_lines=[line])

    assert claim.uncited_field_names == ["diagnosis_code"]
    assert not claim.can_be_green


def test_open_flag_blocks_green() -> None:
    flag = Flag(code="signature_missing", severity="amber", citations=[image_citation()])
    claim = Claim(id="claim-1", fields=[field([image_citation()])], flags=[flag])

    assert not claim.can_be_green


def test_fully_cited_claim_without_flags_can_be_green() -> None:
    assert Claim(id="claim-1", fields=[field([image_citation()])]).can_be_green


def test_submission_deadline_is_seven_days_after_discharge() -> None:
    claim = Claim(id="claim-1", discharge_date=date(2026, 10, 12))

    assert claim.submission_deadline == date(2026, 10, 19)


def test_resubmission_deadline_is_fourteen_days_after_return() -> None:
    claim = Claim(id="claim-1", returned_at=datetime(2026, 10, 1, 9, 30))

    assert claim.resubmission_deadline == datetime(2026, 10, 15, 9, 30)


def test_deadlines_are_absent_without_their_start_date() -> None:
    claim = Claim(id="claim-1")

    assert claim.submission_deadline is None
    assert claim.resubmission_deadline is None


def test_claim_round_trip_preserves_citations_exactly() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audio = Citation(kind="audio", source_id="upload-2", t_start=3.5, t_end=7.25, quote="alilazwa")
    rule = Citation(kind="rule", source_id="SHA-BEN-01", rule_version="v[PLACEHOLDER]")
    claim = Claim(
        id="claim-1",
        lifecycle=Lifecycle.RETURNED,
        discharge_date=date(2026, 10, 12),
        returned_at=datetime(2026, 10, 14, 8, 0),
        fields=[field([image_citation(), audio])],
        coded_lines=[Field(name="service_code", value="X00", confidence=0.7, citations=[rule])],
        flags=[Flag(code="invoice_not_itemised", severity="amber", citations=[image_citation()])],
    )

    with Session(engine) as session:
        save_claim(session, claim)
        session.commit()

    with Session(engine) as session:
        assert load_claim(session, "claim-1") == claim


def test_loading_unknown_claim_returns_none() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        assert load_claim(session, "missing") is None
