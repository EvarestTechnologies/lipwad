from datetime import UTC, datetime, timedelta

import pytest

from app.agent.rules import RULES, Evidence, check, rule
from app.db.schemas import Citation, Claim, Field, Lifecycle

CITE = [Citation(kind="image", source_id="u", region=[[0.1, 0.1], [0.2, 0.2]])]
NOW = datetime(2026, 11, 3, tzinfo=UTC)


def field(name: str, value: str) -> Field:
    return Field(name=name, value=value, confidence=1, citations=CITE)


def flags_for(claim: Claim | None = None, **values: str):
    fields = {name: field(name, value) for name, value in values.items()}
    return check(claim or Claim(id="X"), Evidence(fields, [], True), NOW)


def codes(**values: str) -> set[str]:
    return {flag.code for flag in flags_for(**values)}


def rules_cited(flag) -> set[str]:
    return {c.source_id for c in flag.citations if c.kind == "rule"}


def test_every_rule_names_its_source_status_and_exact_quote() -> None:
    for rule_id, source in RULES.items():
        assert source.status in {"final", "news", "lipwad"}, rule_id
        assert source.quote and source.title and source.issuer, rule_id
        if source.status != "lipwad":
            assert source.url.startswith("https://"), rule_id
            assert source.clause, rule_id


def test_rule_citations_carry_the_version_and_quote() -> None:
    citation = rule("SHA-A-13.5.2-RESUBMIT-14D")

    assert citation.rule_version == "Part A, 16 Oct 2026"
    assert citation.quote.startswith("The Healthcare Provider shall correct and resubmit")


def test_nothing_in_the_catalogue_is_a_placeholder() -> None:
    marker = "PLACE" + "HOLDER"  # spelled out so a repo-wide grep for the word stays clean
    assert not any(marker in f"{key}{value}".upper() for key, value in RULES.items())


def test_unknown_rule_is_refused() -> None:
    with pytest.raises(KeyError):
        rule("SHA-MADE-UP")


def test_bedside_service_is_not_mistaken_for_bed_days() -> None:
    assert "service_type_inconsistent" not in codes(
        visit_type="Outpatient", invoice_line_1="Bedside ultrasound: KSh 2000"
    )


def test_bed_days_on_an_outpatient_visit_cite_the_accuracy_clause() -> None:
    flags = flags_for(visit_type="Outpatient", invoice_line_1="Bed days x2: KSh 6000")
    flag = next(f for f in flags if f.code == "service_type_inconsistent")

    assert rules_cited(flag) == {"SHA-A-13.1.2-ACCURATE"}


def test_facility_level_is_not_checked_until_fund_rules_are_built() -> None:
    assert "service_outside_facility_level" not in codes(visit_type="Inpatient")


@pytest.mark.parametrize(
    ("field_name", "code"),
    [
        ("physician_details", "physician_details_missing"),
        ("declaration_signature", "declaration_unsigned"),
        ("facility_stamp", "facility_stamp_missing"),
    ],
)
def test_each_missing_form_3_item_cites_form_3(field_name: str, code: str) -> None:
    flag = flags_for(**{field_name: "absent"})[0]

    assert flag.code == code and flag.severity == "amber"
    assert rules_cited(flag) == {"SHI-FORM3-FIELDS"}


def test_form_3_is_not_cited_for_a_clinician_signature() -> None:
    assert flags_for(clinician_signature="absent") == []


def test_invoice_lines_without_tariff_codes_are_a_note_not_a_block() -> None:
    flag = flags_for(invoice_tariff_codes="none")[0]

    assert (flag.code, flag.severity) == ("tariff_code_missing", "note")
    assert rules_cited(flag) == {"SHA-A-13.3.1-SUPPORTING-DOCS"}
    assert "tariff_code_missing" not in codes(invoice_tariff_codes="all")


def test_a_note_does_not_stop_a_claim_from_going_green() -> None:
    from app.db.schemas import Flag

    claim = Claim(
        id="X",
        fields=[field("patient_ref", "PT-1")],
        coded_lines=[field("service_code", "not coded")],
        flags=[Flag(code="tariff_code_missing", severity="note", citations=CITE)],
    )
    assert claim.can_be_green


def test_the_schedule_entry_is_marked_as_a_summary_not_a_quote() -> None:
    assert RULES["SHI-SCHED-INPATIENT-LEVEL"].quote_kind == "summary"
    assert all(
        source.quote_kind == "verbatim"
        for rule_id, source in RULES.items()
        if rule_id != "SHI-SCHED-INPATIENT-LEVEL"
    )


def test_the_coding_note_never_promises_to_assign_codes() -> None:
    assert RULES["LIPWAD-CODING-PENDING"].quote == (
        "Lipwad does not check service or diagnosis codes yet. It never assigns or suggests codes."
    )


def test_invoice_without_items_cites_supporting_documents() -> None:
    flag = flags_for(invoice_itemised="no")[0]

    assert rules_cited(flag) == {"SHA-A-13.3.1-SUPPORTING-DOCS"}


def test_unregistered_practitioner_cites_the_licensing_warranty() -> None:
    fields = {"practitioner_id": field("practitioner_id", "PR-999")}
    flag = check(Claim(id="X"), Evidence(fields, [], False), NOW)[0]

    assert flag.code == "practitioner_not_found"
    assert rules_cited(flag) == {"SHA-A-13.4.3-LICENSED"}


def test_a_sent_back_claim_near_its_deadline_cites_clause_13_5_2() -> None:
    claim = Claim(id="X", lifecycle=Lifecycle.RETURNED, returned_at=NOW - timedelta(days=13))
    flag = next(f for f in flags_for(claim) if f.code == "resubmission_deadline_near")

    assert rules_cited(flag) == {"SHA-A-13.5.2-RESUBMIT-14D"}


def test_a_rejected_claim_cites_the_review_window_not_resubmission() -> None:
    claim = Claim(id="X", lifecycle=Lifecycle.REJECTED, returned_at=NOW - timedelta(days=1))
    flag = next(f for f in flags_for(claim) if f.code == "claim_rejected")

    assert rules_cited(flag) == {"SHA-A-13.8.1-REVIEW-7WD"}


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
    flags = check(Claim(id="X"), Evidence(fields, [], True), NOW)
    flag = next(flag for flag in flags if flag.code == "admission_date_mismatch")

    assert flag.severity == "amber"
    assert {c.kind for c in flag.citations} == {"image", "audio", "rule"}
    assert rules_cited(flag) == {"SHA-A-13.1.2-ACCURATE"}


def test_matching_voice_and_form_dates_are_not_flagged() -> None:
    assert "admission_date_mismatch" not in codes(
        admission_date="2026-10-12", voice_admission_date="2026-10-12"
    )


def test_an_unclear_voice_note_asks_for_a_new_recording_not_a_photo() -> None:
    note = Citation(kind="audio", source_id="F06-voice_note", t_start=0, t_end=22.2)
    flags = check(Claim(id="X"), Evidence({}, [], True, voice_retake=note), NOW)

    assert [f.code for f in flags] == ["voice_note_unclear"]
    assert flags[0].citations[0] == note
    assert rules_cited(flags[0]) == {"LIPWAD-EVIDENCE-QUALITY"}


def test_a_missing_discharge_summary_is_named_and_cites_part_a() -> None:
    evidence = Evidence({}, [], True, documents_present={"CLAIM_FORM", "INVOICE"})
    flags = check(Claim(id="X"), evidence, NOW)

    assert [f.code for f in flags] == ["discharge_summary_missing"]
    assert rules_cited(flags[0]) == {"SHA-A-13.3.1-SUPPORTING-DOCS", "SHA-NEWS-3-DOCS"}


def test_documents_are_not_judged_when_none_were_listed() -> None:
    assert flags_for() == []


def test_an_unsigned_inpatient_discharge_summary_cites_part_b2() -> None:
    flags = flags_for(visit_type="Inpatient", discharge_summary_signature="absent")
    flag = next(f for f in flags if f.code == "discharge_summary_unsigned")

    assert rules_cited(flag) == {"SHA-B2-SHIF-DOCS"}
    assert any(c.kind == "image" for c in flag.citations)


def test_an_outpatient_discharge_summary_signature_is_not_required() -> None:
    assert "discharge_summary_unsigned" not in codes(
        visit_type="Outpatient", discharge_summary_signature="absent"
    )


def test_a_voice_segment_needing_review_is_flagged_with_its_seconds() -> None:
    segment = Citation(kind="audio", source_id="F11-voice_note", t_start=6.5, t_end=14)
    flags = check(Claim(id="X"), Evidence({}, [], True, voice_review=[segment]), NOW)

    assert [f.code for f in flags] == ["voice_needs_review"]
    assert flags[0].citations[0] == segment
    assert rules_cited(flags[0]) == {"LIPWAD-EVIDENCE-QUALITY"}
