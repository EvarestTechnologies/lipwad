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
    agent = ClaimAgent(StubProvider(Role.VISION, load_fixtures(DATA_DIR)), FakeReasoning(), hie)
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
