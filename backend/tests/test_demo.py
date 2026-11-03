from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.agent.run import ClaimAgent, case_uploads
from app.db.repository import load_claim
from app.db.seed import DATA_DIR, load_cases, mock_script, seed_database
from app.hie.mock import MockHIE
from app.main import create_app
from app.models import Role, StubProvider
from app.models.transcribe import FixtureTranscriber
from app.services import DemoState, Services
from app.tools.fixtures import load_fixtures
from tests.test_agent import FakeReasoning


def build(tmp_path: Path, now: list[datetime]):
    url = f"sqlite:///{tmp_path / 'lipwad.db'}"
    state = tmp_path / "hie_state.json"
    seed_database(url, state)
    demo = DemoState(url, state, tmp_path / "baseline", clock=lambda: now[0])
    hie = MockHIE(script=mock_script(load_cases()), state_path=state)
    fixtures = load_fixtures(DATA_DIR)
    agent = ClaimAgent(
        StubProvider(Role.VISION, fixtures), FakeReasoning(), hie, FixtureTranscriber(fixtures)
    )
    return demo, sessionmaker(demo.engine), agent, hie


def test_restore_brings_back_the_snapshot_with_deadlines_moved_forward(tmp_path: Path) -> None:
    now = [datetime.now(UTC)]
    demo, sessions, agent, hie = build(tmp_path, now)
    with sessions() as session:
        agent.run(session, "C01", case_uploads(DATA_DIR, "C01"))
        session.commit()
        deadline = load_claim(session, "F05").resubmission_deadline
    demo.snapshot()
    with sessions() as session:
        agent.run(session, "C02", case_uploads(DATA_DIR, "C02"))
        session.commit()

    now[0] += timedelta(days=3)
    demo.restore(hie)

    with sessions() as session:
        assert load_claim(session, "C01").readiness is not None
        assert load_claim(session, "C02").readiness is None
        moved = load_claim(session, "F05").resubmission_deadline
    assert abs((moved - deadline) - timedelta(days=3)) < timedelta(seconds=5)
    f05 = next(c for c in hie._claims.values() if c.outcome.value == "return")
    assert now[0] - timedelta(days=14) < f05.outcome_at < now[0] - timedelta(days=12)


def test_restore_without_a_snapshot_reseeds(tmp_path: Path) -> None:
    now = [datetime.now(UTC)]
    demo, sessions, agent, hie = build(tmp_path, now)
    with sessions() as session:
        agent.run(session, "C01", case_uploads(DATA_DIR, "C01"))
        session.commit()

    demo.restore(hie)

    with sessions() as session:
        assert load_claim(session, "C01").readiness is None


def test_snapshot_endpoint_needs_the_admin_key(tmp_path: Path) -> None:
    now = [datetime.now(UTC)]
    demo, sessions, agent, hie = build(tmp_path, now)
    services = Services(
        sessions=sessions, agent=agent, hie=hie, data_dir=DATA_DIR, demo=demo, admin_key="k" * 32
    )
    client = TestClient(create_app(None, services))

    assert client.post("/api/demo/snapshot").status_code == 403
    assert client.post("/api/demo/snapshot", headers={"x-admin-key": "wrong"}).status_code == 403
    assert client.post("/api/demo/snapshot", headers={"x-admin-key": "k" * 32}).status_code == 200
    assert (tmp_path / "baseline" / "lipwad.db").exists()


def test_snapshot_endpoint_is_absent_without_a_key(tmp_path: Path) -> None:
    now = [datetime.now(UTC)]
    demo, sessions, agent, hie = build(tmp_path, now)
    services = Services(sessions=sessions, agent=agent, hie=hie, data_dir=DATA_DIR, demo=demo)

    assert TestClient(create_app(None, services)).post("/api/demo/snapshot").status_code == 404
