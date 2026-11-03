import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.run import ClaimAgent, case_uploads
from app.db.repository import list_activity, load_claim
from app.db.schemas import Readiness
from app.db.seed import load_cases, mock_script, register_submissions, seed_claims
from app.db.tables import Base
from app.hie.mock import MockHIE
from app.models import ChatResponse, Role, StubProvider
from app.tools.fixtures import load_fixtures

DATA_DIR = Path(__file__).parents[2] / "data" / "synthetic"
CASES = {case.case_id: case for case in load_cases(DATA_DIR)}
GATE = ["C01", "C02", "C03", "F01", "F02", "F03", "F04", "F05", "F07", "F08", "F09"]


class FakeReasoning:
    """Stands in for Muse Spark Open; records what the agent asked it."""

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        body = {
            "summary": "Checked the claim against its documents.",
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
        vision=StubProvider(Role.VISION, load_fixtures(DATA_DIR)), reasoning=reasoning, hie=hie
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
    flag = next(flag for flag in claim.flags if flag.code == "signature_missing")

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
    assert signed == ["clinician_signature"]


def test_activity_names_the_model_that_did_the_work() -> None:
    _, activity, _ = run("C01")

    assert all(step.model != "muse-spark-1.3" for step in activity if step.kind == "read")
    assert any(step.model == "stub" for step in activity if step.kind == "read")
