from datetime import UTC, datetime

from app.agent.rules import Evidence, check
from app.db.schemas import Citation, Claim, Field

CITE = [Citation(kind="image", source_id="u", region=[[0.1, 0.1], [0.2, 0.2]])]


def field(name: str, value: str) -> Field:
    return Field(name=name, value=value, confidence=1, citations=CITE)


def codes(**values: str) -> set[str]:
    fields = {name: field(name, value) for name, value in values.items()}
    flags = check(Claim(id="X"), Evidence(fields, [], True, 2), datetime(2026, 11, 3, tzinfo=UTC))
    return {flag.code for flag in flags}


def test_clinic_visit_is_not_mistaken_for_inpatient() -> None:
    assert "service_outside_facility_level" not in codes(visit_type="Day clinic")


def test_bedside_service_is_not_mistaken_for_bed_days() -> None:
    assert "service_type_inconsistent" not in codes(
        visit_type="Outpatient", invoice_line_1="Bedside ultrasound: KSh 2000"
    )


def test_bed_days_on_an_outpatient_visit_are_flagged() -> None:
    assert "service_type_inconsistent" in codes(
        visit_type="Outpatient", invoice_line_1="Bed days x2: KSh 6000"
    )


def test_voice_and_form_dates_that_disagree_are_flagged_with_both_sources() -> None:
    spoken = Field(
        name="voice_admission_date",
        value="2026-10-11",
        confidence=1,
        citations=[Citation(kind="audio", source_id="note", t_start=5.6, t_end=10.3)],
    )
    fields = {
        "admission_date": field("admission_date", "2026-10-12"),
        "voice_admission_date": spoken,
    }
    flags = check(Claim(id="X"), Evidence(fields, [], True, 3), datetime(2026, 11, 3, tzinfo=UTC))
    flag = next(flag for flag in flags if flag.code == "admission_date_mismatch")

    assert flag.severity == "amber"
    assert {c.kind for c in flag.citations} == {"image", "audio", "rule"}


def test_matching_voice_and_form_dates_are_not_flagged() -> None:
    assert "admission_date_mismatch" not in codes(
        admission_date="2026-10-12", voice_admission_date="2026-10-12"
    )
