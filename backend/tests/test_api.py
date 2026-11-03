from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.run import ClaimAgent
from app.db.seed import DATA_DIR, load_cases, mock_script, register_submissions, seed_claims
from app.db.tables import Base
from app.hie.mock import MockHIE
from app.main import create_app
from app.models import Role, StubProvider
from app.models.transcribe import FixtureTranscriber
from app.services import Services
from app.tools.fixtures import load_fixtures
from tests.test_agent import FakeReasoning

CONFIRM = {"confirmed_by": "Clerk Achieng [demo]"}


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cases = load_cases()
    hie = MockHIE(script=mock_script(cases))
    register_submissions(hie, cases)
    with sessions() as session:
        seed_claims(session, cases)
        session.commit()
    fixtures = load_fixtures(DATA_DIR)
    agent = ClaimAgent(
        StubProvider(Role.VISION, fixtures), FakeReasoning(), hie, FixtureTranscriber(fixtures)
    )
    services = Services(sessions=sessions, agent=agent, hie=hie, data_dir=DATA_DIR)
    return TestClient(create_app(None, services))


def test_claims_are_listed(client: TestClient) -> None:
    ids = {claim["id"] for claim in client.get("/api/claims").json()}

    assert {"C01", "F05"} <= ids


def test_running_the_agent_returns_the_reviewed_claim(client: TestClient) -> None:
    body = client.post("/api/claims/F01/run").json()

    assert body["claim"]["readiness"] == "amber"
    assert [flag["code"] for flag in body["claim"]["flags"]] == ["signature_missing"]
    assert body["activity"]
    assert {upload["id"] for upload in body["uploads"]} == {"F01-claim_form", "F01-invoice"}


def test_upload_images_are_served(client: TestClient) -> None:
    client.post("/api/claims/C01/run")

    response = client.get("/api/uploads/C01-claim_form/image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_unknown_claim_is_404(client: TestClient) -> None:
    assert client.get("/api/claims/X99").status_code == 404


def test_submit_needs_a_named_confirmation(client: TestClient) -> None:
    client.post("/api/claims/C01/run")

    assert client.post("/api/claims/C01/submit", json={"confirmed_by": " "}).status_code == 422


def test_claim_that_is_not_green_cannot_be_submitted(client: TestClient) -> None:
    client.post("/api/claims/F01/run")

    assert client.post("/api/claims/F01/submit", json=CONFIRM).status_code == 409


def test_green_claim_is_submitted_after_confirmation(client: TestClient) -> None:
    client.post("/api/claims/C01/run")

    body = client.post("/api/claims/C01/submit", json=CONFIRM).json()

    assert body["claim"]["lifecycle"] == "submitted"
    assert body["claim"]["hie_id"] == "HIE-C01"
    assert any("Clerk Achieng" in step["text"] for step in body["activity"])


def test_rescue_drafts_the_fix_from_the_signed_page(client: TestClient) -> None:
    client.post("/api/claims/F05/run")

    draft = client.post("/api/claims/F05/rescue").json()

    assert draft["changes"] == [
        {"field": "clinician_signature", "before": "absent", "after": "present"}
    ]
    assert draft["reason"] == ["signature_missing"]


def test_rescued_claim_is_resubmitted_and_accepted(client: TestClient) -> None:
    client.post("/api/claims/F05/run")
    client.post("/api/claims/F05/rescue")

    body = client.post("/api/claims/F05/resubmit", json=CONFIRM).json()

    assert body["claim"]["lifecycle"] == "submitted"
    assert "signature_missing" not in [flag["code"] for flag in body["claim"]["flags"]]


def test_resubmit_without_a_drafted_fix_is_refused(client: TestClient) -> None:
    client.post("/api/claims/F05/run")

    assert client.post("/api/claims/F05/resubmit", json=CONFIRM).status_code == 409


def test_today_reports_money_at_risk_and_tasks(client: TestClient) -> None:
    for case_id in ("C01", "F01", "F05"):
        client.post(f"/api/claims/{case_id}/run")

    today = client.get("/api/today").json()

    assert today["at_risk_ksh"] > 0
    assert {task["claim_id"] for task in today["tasks"]} >= {"F01", "F05"}
    assert "C01" not in {task["claim_id"] for task in today["tasks"]}
    assert today["activity"]


def test_unused_paths_are_not_found(client: TestClient) -> None:
    assert client.get("/api/missing").status_code == 404


def test_data_dir_has_case_documents() -> None:
    assert Path(DATA_DIR, "F05", "claim_form_signed.png").exists()


def test_rules_catalogue_lists_placeholder_versions(client: TestClient) -> None:
    rules = client.get("/api/rules").json()

    assert {"id", "checks", "version", "source_registered"} <= set(rules[0])
    assert all(rule["version"] == "v[PLACEHOLDER]" for rule in rules)
    assert not any(rule["source_registered"] for rule in rules)


def test_today_feed_is_short(client: TestClient) -> None:
    for case_id in ("C01", "C02", "F01", "F02", "F03"):
        client.post(f"/api/claims/{case_id}/run")

    assert len(client.get("/api/today").json()["activity"]) == 8


def test_voice_notes_are_served_as_audio(client: TestClient) -> None:
    client.post("/api/claims/F06/run")
    response = client.get("/api/uploads/F06-voice_note/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"


def make_client(**options) -> tuple[TestClient, Services]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cases = load_cases()
    hie = MockHIE(script=mock_script(cases))
    register_submissions(hie, cases)
    with sessions() as session:
        seed_claims(session, cases)
        session.commit()
    fixtures = load_fixtures(DATA_DIR)
    agent = ClaimAgent(
        StubProvider(Role.VISION, fixtures), FakeReasoning(), hie, FixtureTranscriber(fixtures)
    )
    services = Services(sessions=sessions, agent=agent, hie=hie, data_dir=DATA_DIR, **options)
    return TestClient(create_app(None, services)), services


def test_a_claim_already_being_worked_on_is_refused_not_crashed() -> None:
    client, services = make_client()
    with services.claim_lock("F02"):
        response = client.post("/api/claims/F02/run")

    assert response.status_code == 409
    assert "already working" in response.json()["detail"]


def test_confirmer_names_are_capped(client: TestClient) -> None:
    client.post("/api/claims/C01/run")

    assert client.post("/api/claims/C01/submit", json={"confirmed_by": "A" * 81}).status_code == 422


def test_security_headers_are_set(client: TestClient) -> None:
    headers = client.get("/api/health").headers

    assert headers["x-frame-options"] == "DENY"
    assert headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["referrer-policy"] == "same-origin"


def test_paid_runs_stop_at_the_daily_limit(tmp_path) -> None:
    from app.services import RunBudget

    client, _ = make_client(budget=RunBudget(tmp_path / "usage.json", per_day=1))

    assert client.post("/api/claims/C01/run").status_code == 200
    blocked = client.post("/api/claims/C02/run")
    assert blocked.status_code == 429
    assert "today" in blocked.json()["detail"]


def test_demo_resets_itself_when_due(tmp_path) -> None:
    from app.services import DemoReset

    resets = []
    client, _ = make_client(
        demo_reset=DemoReset(tmp_path / "reset_at", every_hours=6, reset=lambda: resets.append(1))
    )
    client.get("/api/today")
    assert resets == [1]
    client.get("/api/today")
    assert resets == [1]


def test_a_draft_can_take_its_corrected_page_and_then_be_submitted(client: TestClient) -> None:
    client.post("/api/claims/F01/run")
    assert client.get("/api/claims/F01").json()["has_corrected_page"] is True

    draft = client.post("/api/claims/F01/rescue").json()
    claim = client.get("/api/claims/F01").json()["claim"]

    assert draft["changes"] == [
        {"field": "clinician_signature", "before": "absent", "after": "present"}
    ]
    assert claim["readiness"] == "green"
    assert client.post("/api/claims/F01/submit", json=CONFIRM).status_code == 200


def test_a_draft_cannot_be_resubmitted(client: TestClient) -> None:
    client.post("/api/claims/F01/run")
    client.post("/api/claims/F01/rescue")

    assert client.post("/api/claims/F01/resubmit", json=CONFIRM).status_code == 409


def test_claims_without_a_corrected_page_say_so(client: TestClient) -> None:
    assert client.get("/api/claims/F02").json()["has_corrected_page"] is False


def test_requests_that_cannot_run_do_not_spend_the_budget(tmp_path) -> None:
    from app.services import RunBudget

    client, _ = make_client(budget=RunBudget(tmp_path / "usage.json", per_day=1))
    client.post("/api/claims/C01/run")
    client.post("/api/claims/C01/submit", json=CONFIRM)

    assert client.post("/api/claims/NOPE/run").status_code == 404
    assert client.post("/api/claims/C01/run").status_code == 409
    assert client.post("/api/claims/F02/rescue").status_code == 409
    usage = (tmp_path / "usage.json").read_text()
    assert '"count": 1' in usage


def test_an_unreviewed_draft_cannot_take_a_corrected_page(client: TestClient) -> None:
    assert client.post("/api/claims/F01/rescue").status_code == 409


def test_a_corrected_draft_can_be_reviewed_again_with_its_signed_page(client: TestClient) -> None:
    client.post("/api/claims/F01/run")
    client.post("/api/claims/F01/rescue")

    response = client.post("/api/claims/F01/run")
    claim = response.json()["claim"]

    assert response.status_code == 200
    assert claim["readiness"] == "green"
    signature = next(f for f in claim["fields"] if f["name"] == "clinician_signature")
    assert signature["citations"][0]["source_id"] == "F01-claim_form_signed"


def test_pointless_paid_requests_are_refused_before_spending(tmp_path) -> None:
    from app.services import RunBudget

    client, _ = make_client(budget=RunBudget(tmp_path / "usage.json", per_day=3))
    client.post("/api/claims/F05/rescue")

    assert client.post("/api/claims/F05/rescue").status_code == 409
    assert client.post("/api/claims/F05/run").status_code == 409
    assert '"count": 1' in (tmp_path / "usage.json").read_text()
