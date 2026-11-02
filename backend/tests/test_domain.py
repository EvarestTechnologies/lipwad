from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db.repository import (
    StaleClaimError,
    list_uploads,
    load_claim,
    save_claim,
    save_upload,
)
from app.db.schemas import Citation, Claim, Field, Flag, Lifecycle, Readiness, Upload
from app.db.tables import Base, CitationRow


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


def coded_line() -> Field:
    rule = Citation(kind="rule", source_id="SHA-BEN-01", rule_version="v[PLACEHOLDER]")
    return Field(name="service_code", value="X00", confidence=0.8, citations=[rule])


def database():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    return engine


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "image", "source_id": "u", "region": [[]]},
        {"kind": "image", "source_id": "u", "region": [[0.1], [0.2, 0.3, 0.4]]},
        {"kind": "image", "source_id": "u", "region": [[float("nan"), 0.1]]},
        {"kind": "image", "source_id": "", "region": [[0.1, 0.2]]},
        {"kind": "audio", "source_id": "u", "t_start": -5.0, "t_end": 1.0},
        {"kind": "audio", "source_id": "u", "t_start": float("nan"), "t_end": 1.0},
        {"kind": "audio", "source_id": "u", "t_start": 1.0, "t_end": float("inf")},
        {"kind": "rule", "source_id": "SHA-BEN-01", "rule_version": " "},
    ],
)
def test_citation_that_cannot_locate_its_source_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        Citation(**kwargs)


def test_claim_without_evidence_cannot_be_green() -> None:
    assert not Claim(id="claim-1").can_be_green


def test_claim_without_coded_lines_cannot_be_green() -> None:
    assert not Claim(id="claim-1", fields=[field([image_citation()])]).can_be_green


def test_derived_values_are_serialised() -> None:
    dumped = Claim(id="claim-1").model_dump()

    assert {"can_be_green", "uncited_field_names"} <= dumped.keys()
    assert {"submission_deadline", "resubmission_deadline"} <= dumped.keys()


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
    claim = Claim(id="claim-1", fields=[field([image_citation()])], coded_lines=[coded_line()])

    assert claim.can_be_green


def test_submission_deadline_is_seven_days_after_discharge() -> None:
    claim = Claim(id="claim-1", discharge_date=date(2026, 10, 12))

    assert claim.submission_deadline == date(2026, 10, 19)


@pytest.mark.parametrize("lifecycle", [Lifecycle.RETURNED, Lifecycle.REJECTED])
def test_resubmission_deadline_is_fourteen_days_after_return(lifecycle: Lifecycle) -> None:
    returned = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
    claim = Claim(id="claim-1", lifecycle=lifecycle, returned_at=returned)

    assert claim.resubmission_deadline == datetime(2026, 10, 15, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("lifecycle", [Lifecycle.SUBMITTED, Lifecycle.PAID])
def test_settled_claim_has_no_resubmission_deadline(lifecycle: Lifecycle) -> None:
    claim = Claim(id="claim-1", lifecycle=lifecycle, returned_at=datetime(2026, 10, 1, tzinfo=UTC))

    assert claim.resubmission_deadline is None


def test_submitted_claim_has_no_submission_deadline() -> None:
    claim = Claim(id="claim-1", lifecycle=Lifecycle.SUBMITTED, discharge_date=date(2026, 10, 12))

    assert claim.submission_deadline is None


def test_naive_return_time_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Claim(id="claim-1", returned_at=datetime(2026, 10, 1, 9, 30))


def test_deadlines_are_absent_without_their_start_date() -> None:
    claim = Claim(id="claim-1")

    assert claim.submission_deadline is None
    assert claim.resubmission_deadline is None


def full_claim() -> Claim:
    audio = Citation(kind="audio", source_id="upload-2", t_start=3.5, t_end=7.25, quote="alilazwa")
    return Claim(
        id="claim-1",
        lifecycle=Lifecycle.RETURNED,
        readiness=Readiness.AMBER,
        hie_id="HIE-123",
        discharge_date=date(2026, 10, 12),
        returned_at=datetime(2026, 10, 14, 8, 0, tzinfo=timezone(timedelta(hours=3))),
        fields=[field([image_citation(), audio])],
        coded_lines=[coded_line()],
        flags=[Flag(code="invoice_not_itemised", severity="amber", citations=[image_citation()])],
    )


def test_claim_round_trip_preserves_citations_exactly() -> None:
    engine = database()
    with Session(engine) as session:
        saved = save_claim(session, full_claim())
        session.commit()

    with Session(engine) as session:
        assert load_claim(session, "claim-1") == saved


def test_saving_increments_version() -> None:
    with Session(database()) as session:
        assert save_claim(session, full_claim()).version == 1


def test_stale_save_is_refused_and_keeps_the_confirmation() -> None:
    engine = database()
    with Session(engine) as session:
        original = save_claim(session, full_claim())
        session.commit()

    with Session(engine) as session:
        confirmed = original.model_copy(deep=True)
        confirmed.fields[0].confirmed_by = "clerk"
        save_claim(session, confirmed)
        session.commit()

    with Session(engine) as session:
        with pytest.raises(StaleClaimError):
            save_claim(session, original)
        session.rollback()

    with Session(engine) as session:
        assert load_claim(session, "claim-1").fields[0].confirmed_by == "clerk"


def test_updating_a_claim_with_uploads_replaces_children_only() -> None:
    engine = database()
    upload = Upload(
        id="upload-1", claim_id="claim-1", kind="image", filename="a.jpg", path="uploads/a.jpg"
    )
    with Session(engine) as session:
        saved = save_claim(session, full_claim())
        save_upload(session, upload)
        session.commit()

    updated = saved.model_copy(update={"flags": []})
    with Session(engine) as session:
        save_claim(session, updated)
        session.commit()

    with Session(engine) as session:
        assert load_claim(session, "claim-1").flags == []
        assert list_uploads(session, "claim-1") == [upload]
        flag_citations = select(CitationRow).where(CitationRow.flag_id.is_not(None))
        assert session.scalars(flag_citations).all() == []


def test_loading_unknown_claim_returns_none() -> None:
    with Session(database()) as session:
        assert load_claim(session, "missing") is None
