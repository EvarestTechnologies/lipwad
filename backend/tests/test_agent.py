import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.run import ClaimAgent, case_uploads, signed_upload
from app.db.repository import list_activity, load_claim
from app.db.schemas import Readiness
from app.db.seed import load_cases, mock_script, register_submissions, seed_claims
from app.db.tables import Base
from app.hie.mock import MockHIE
from app.models import ChatResponse, Role, StubProvider
from app.models.transcribe import FixtureTranscriber
from app.tools.fixtures import load_fixtures

DATA_DIR = Path(__file__).parents[2] / "data" / "synthetic"
CASES = {case.case_id: case for case in load_cases(DATA_DIR)}
GATE = sorted(CASES)


class FakeReasoning:
    """Stands in for Muse Spark Open; records what the agent asked it."""

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        body = {
            "explanation_en": "Explanation [demo]",
            "explanation_sw": "Maelezo [demo]",
        }
        return ChatResponse(content=json.dumps(body), model_id="fake", provider="fake")


def run(case_id: str):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    hie = MockHIE(script=mock_script(list(CASES.values())))
    register_submissions(hie, list(CASES.values()))
    reasoning = FakeReasoning()
    agent = ClaimAgent(
        vision=StubProvider(Role.VISION, load_fixtures(DATA_DIR)),
        reasoning=reasoning,
        hie=hie,
        transcriber=FixtureTranscriber(load_fixtures(DATA_DIR)),
    )
    with Session(engine) as session:
        seed_claims(session, list(CASES.values()))
        agent.run(session, case_id, case_uploads(DATA_DIR, case_id))
        session.commit()
        return load_claim(session, case_id), list_activity(session, case_id), reasoning


@pytest.mark.parametrize("case_id", GATE)
def test_case_reaches_its_expected_status_and_reasons(case_id: str) -> None:
    claim, _, _ = run(case_id)
    expected = CASES[case_id]

    assert claim.readiness == Readiness(expected.expected_status)
    assert set(expected.expected_reasons) <= {flag.code for flag in claim.flags}


@pytest.mark.parametrize("case_id", GATE)
def test_every_flag_and_field_is_cited(case_id: str) -> None:
    claim, _, _ = run(case_id)

    assert all(flag.citations for flag in claim.flags)
    assert claim.uncited_field_names == []


def test_rule_flags_cite_a_rule_and_its_version() -> None:
    claim, _, _ = run("F01")
    flag = next(flag for flag in claim.flags if flag.code == "declaration_unsigned")

    assert any(c.kind == "rule" and c.rule_version for c in flag.citations)
    assert any(c.kind == "image" for c in flag.citations)


def test_green_claim_has_coded_lines() -> None:
    claim, _, _ = run("C01")

    assert claim.coded_lines
    assert claim.can_be_green


def test_reasoning_model_is_consulted_and_its_trace_logged() -> None:
    _, activity, reasoning = run("F02")

    assert reasoning.requests
    assert any(step.model == "fake" for step in activity)


def test_activity_records_each_agent_step() -> None:
    _, activity, _ = run("F04")
    text = " ".join(step.text for step in activity)

    assert "claim_form" in text and "registry" in text.lower()


def test_rescued_claim_cannot_be_rerun_and_lose_its_fix() -> None:
    from app.agent.run import RescueError, signed_upload

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    hie = MockHIE(script=mock_script(list(CASES.values())))
    register_submissions(hie, list(CASES.values()))
    agent = ClaimAgent(StubProvider(Role.VISION, load_fixtures(DATA_DIR)), FakeReasoning(), hie)
    with Session(engine) as session:
        seed_claims(session, list(CASES.values()))
        agent.run(session, "F05", case_uploads(DATA_DIR, "F05"))
        agent.rescue(session, "F05", signed_upload(DATA_DIR, "F05"))
        with pytest.raises(RescueError):
            agent.run(session, "F05", case_uploads(DATA_DIR, "F05"))


def test_rescue_only_replaces_fields_that_changed() -> None:
    from app.agent.run import signed_upload

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    hie = MockHIE(script=mock_script(list(CASES.values())))
    register_submissions(hie, list(CASES.values()))
    agent = ClaimAgent(StubProvider(Role.VISION, load_fixtures(DATA_DIR)), FakeReasoning(), hie)
    with Session(engine) as session:
        seed_claims(session, list(CASES.values()))
        agent.run(session, "F05", case_uploads(DATA_DIR, "F05"))
        agent.rescue(session, "F05", signed_upload(DATA_DIR, "F05"))
        claim = load_claim(session, "F05")

    signed = [
        field.name
        for field in claim.fields
        if any(c.source_id == "F05-claim_form_signed" for c in field.citations)
    ]
    assert signed == ["declaration_signature"]


def test_activity_names_the_model_that_did_the_work() -> None:
    _, activity, _ = run("C01")

    assert all(step.model != "muse-spark-1.3" for step in activity if step.kind == "read")
    assert any(step.model == "stub" for step in activity if step.kind == "read")


@pytest.mark.parametrize("case_id", GATE)
def test_every_cited_rule_is_in_the_catalogue(case_id: str) -> None:
    from app.agent.rules import RULES

    claim, _, _ = run(case_id)
    cited = {
        c.source_id
        for item in [*claim.flags, *claim.coded_lines]
        for c in item.citations
        if c.kind == "rule"
    }

    assert cited <= set(RULES)


def test_explanation_is_logged_english_first_then_kiswahili() -> None:
    _, activity, reasoning = run("F01")
    step = next(step for step in activity if step.model == "fake")
    prompt = reasoning.requests[0].messages[0].content

    assert step.text == "Explanation [demo] | SW: Maelezo [demo]"
    assert "hospital claims clerk" in prompt and "approve" in prompt


def test_voice_note_is_heard_and_logged_with_its_model() -> None:
    claim, activity, _ = run("F06")
    spoken = next(f for f in claim.fields if f.name == "voice_admission_date")

    assert spoken.citations[0].kind == "audio"
    assert any("voice note" in step.text.lower() and step.model for step in activity)


class Broken:
    def transcribe(self, audio_path: str, case_id: str):
        from app.models import ModelAPIError

        raise ModelAPIError("unreadable audio")


def test_unreadable_voice_note_blocks_green_with_a_re_record_request() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    hie = MockHIE(script=mock_script(list(CASES.values())))
    agent = ClaimAgent(
        vision=StubProvider(Role.VISION, load_fixtures(DATA_DIR)),
        reasoning=FakeReasoning(),
        hie=hie,
        transcriber=Broken(),
    )
    with Session(engine) as session:
        seed_claims(session, list(CASES.values()))
        agent.run(session, "F06", case_uploads(DATA_DIR, "F06"))
        claim = load_claim(session, "F06")

    codes = {flag.code for flag in claim.flags}
    assert "voice_note_unclear" in codes and "retake_required" not in codes
    assert claim.readiness == Readiness.AMBER


def test_read_steps_count_values_in_plain_english() -> None:
    _, activity, _ = run("F06")

    assert any(step.text.startswith("Heard voice note: 1 cited value ") for step in activity)
    assert not any("1 cited values" in step.text for step in activity)


def test_a_corrected_page_keeps_flags_about_other_evidence() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    hie = MockHIE(script=mock_script(list(CASES.values())))
    fixtures = load_fixtures(DATA_DIR)
    fixtures["vision:F06/claim_form_signed"] = fixtures["vision:F01/claim_form_signed"]
    agent = ClaimAgent(
        vision=StubProvider(Role.VISION, fixtures),
        reasoning=FakeReasoning(),
        hie=hie,
        transcriber=Broken(),
    )
    with Session(engine) as session:
        seed_claims(session, list(CASES.values()))
        uploads = case_uploads(DATA_DIR, "F06")
        agent.run(session, "F06", uploads)
        page = signed_upload(DATA_DIR, "F01").model_copy(
            update={"claim_id": "F06", "id": "F06-claim_form_signed"}
        )
        agent.rescue(session, "F06", page)
        claim = load_claim(session, "F06")

    assert "voice_note_unclear" in {flag.code for flag in claim.flags}
    assert claim.readiness != Readiness.GREEN


def test_f10_names_the_missing_discharge_summary_and_cites_part_a() -> None:
    claim, _, _ = run("F10")
    flag = next(f for f in claim.flags if f.code == "discharge_summary_missing")

    assert claim.readiness == Readiness.AMBER
    assert {c.source_id for c in flag.citations} == {
        "SHA-A-13.3.1-SUPPORTING-DOCS",
        "SHA-NEWS-3-DOCS",
    }


def test_the_clean_inpatient_claim_reads_a_signed_discharge_summary() -> None:
    claim, _, _ = run("C04")
    signature = next(f for f in claim.fields if f.name == "discharge_summary_signature")

    assert claim.readiness == Readiness.GREEN
    assert signature.value == "present"
    assert signature.citations[0].source_id == "C04-discharge_summary"


def test_the_clean_claim_has_tariff_codes_and_no_note() -> None:
    claim, _, _ = run("C04")
    codes = next(f for f in claim.fields if f.name == "invoice_tariff_codes")

    assert codes.value == "all"
    assert claim.flags == []


def test_f10_still_notes_its_missing_tariff_codes() -> None:
    claim, _, _ = run("F10")

    assert "tariff_code_missing" in {f.code for f in claim.flags}


def explain_payload(case_id: str) -> dict:
    _, _, reasoning = run(case_id)
    return json.loads(reasoning.requests[-1].messages[-1].content)


def test_the_explanation_model_sees_only_the_status_and_lipwads_own_steps() -> None:
    from app.agent.steps import FIX_STEPS

    payload = explain_payload("F10")

    assert set(payload) == {"status", "steps"}
    assert payload["steps"] == [FIX_STEPS["discharge_summary_missing"]]


def test_notes_never_become_steps_and_a_clean_claim_has_none() -> None:
    assert explain_payload("C01") == {"status": "green", "steps": []}


def test_no_step_names_a_value_or_asks_to_change_a_charge_or_code() -> None:
    import re

    from app.agent.steps import FIX_STEPS

    for step in FIX_STEPS.values():
        assert not re.search(r"\d{4}-\d{2}|KSh|\bremove\b|\btariff code", step, re.I), step
