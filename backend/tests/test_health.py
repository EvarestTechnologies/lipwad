from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_service_status() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class Reasoning:
    def __init__(self, fail: bool) -> None:
        self.fail, self.calls = fail, 0

    def complete(self, request):
        from app.models import ChatResponse, ModelAPIError

        self.calls += 1
        if self.fail:
            raise ModelAPIError("baseten returned HTTP 400: model version is deactivated")
        return ChatResponse(content='{"ok": true}', model_id="muse-spark-1.3", provider="meta")


def probe_client(fail: bool, now=None):
    from datetime import UTC, datetime

    from app.services import ReasoningProbe
    from tests.test_api import make_client

    model = Reasoning(fail)
    probe = ReasoningProbe(model, clock=now or (lambda: datetime(2026, 11, 18, tzinfo=UTC)))
    client, _ = make_client(reasoning_probe=probe)
    return client, model


def test_reasoning_health_names_the_working_provider() -> None:
    client, _ = probe_client(fail=False)
    response = client.get("/api/health/reasoning")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["provider"] == "meta"


def test_a_failing_reasoning_provider_makes_the_health_check_fail() -> None:
    client, _ = probe_client(fail=True)
    response = client.get("/api/health/reasoning")

    assert response.status_code == 503
    assert "deactivated" in response.json()["error"]


def test_the_probe_is_cached_so_health_checks_cannot_run_up_costs() -> None:
    from datetime import UTC, datetime, timedelta

    now = [datetime(2026, 11, 18, tzinfo=UTC)]
    client, model = probe_client(fail=False, now=lambda: now[0])
    for _ in range(5):
        client.get("/api/health/reasoning")
    assert model.calls == 1
    now[0] += timedelta(minutes=11)
    client.get("/api/health/reasoning")
    assert model.calls == 2
