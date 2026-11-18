from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.db.repository import add_audit, list_audit
from app.db.schemas import AuditEvent
from app.db.tables import Base
from tests.test_api import CONFIRM, make_client


def event(**overrides) -> AuditEvent:
    values = {
        "claim_id": "X",
        "at": datetime(2026, 11, 18, tzinfo=UTC),
        "actor": "lipwad",
        "action": "file_read",
        "detail": {"file": "claim_form.png"},
    }
    return AuditEvent(**{**values, **overrides})


def test_the_log_is_append_only() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_audit(session, event())
        session.commit()
        for statement in ("UPDATE audit_events SET actor = 'someone'", "DELETE FROM audit_events"):
            with pytest.raises(DatabaseError):
                session.execute(text(statement))
            session.rollback()
        assert [e.actor for e in list_audit(session, "X")] == ["lipwad"]


def history(client: TestClient, claim_id: str) -> list[dict]:
    return client.get(f"/api/claims/{claim_id}/audit").json()["events"]


def test_a_review_records_each_file_value_and_flag_with_its_source() -> None:
    client, _ = make_client()
    client.post("/api/claims/F10/run")
    events = history(client, "F10")
    actions = [e["action"] for e in events]

    assert {"file_read", "value_extracted", "flag_raised"} <= set(actions)
    read = next(e for e in events if e["action"] == "file_read")
    assert read["detail"]["file"] == "claim_form.png" and read["detail"]["model"]
    value = next(e for e in events if e["detail"].get("field") == "patient_ref")
    assert value["detail"]["value"] == "PT-014"
    assert value["detail"]["citations"][0]["source_id"] == "F10-claim_form"
    raised = {e["detail"]["code"]: e for e in events if e["action"] == "flag_raised"}
    assert set(raised) == {"discharge_summary_missing", "tariff_code_missing"}
    flag = raised["discharge_summary_missing"]
    assert flag["detail"]["rules"] == ["SHA-A-13.3.1-SUPPORTING-DOCS", "SHA-NEWS-3-DOCS"]


def test_history_runs_from_first_photo_to_the_person_who_confirmed() -> None:
    client, _ = make_client()
    client.post("/api/claims/C04/run")
    client.post("/api/claims/C04/submit", json=CONFIRM)
    events = history(client, "C04")

    assert events[0]["action"] == "file_read"
    confirmed = next(e for e in events if e["action"] == "claim_confirmed")
    assert confirmed["actor"] == CONFIRM["confirmed_by"]
    assert events[-1]["action"] == "submitted"


def test_a_corrected_page_records_the_flag_it_clears() -> None:
    client, _ = make_client()
    client.post("/api/claims/F01/run")
    client.post("/api/claims/F01/rescue")

    cleared = [e for e in history(client, "F01") if e["action"] == "flag_cleared"]
    assert [e["detail"]["code"] for e in cleared] == ["declaration_unsigned"]


def test_the_export_is_one_downloadable_file_per_claim() -> None:
    client, _ = make_client()
    client.post("/api/claims/F10/run")
    response = client.get("/api/claims/F10/audit")

    assert response.headers["content-disposition"] == (
        'attachment; filename="lipwad-audit-F10.json"'
    )
    assert response.json()["claim_id"] == "F10"
    assert client.get("/api/claims/NOPE/audit").status_code == 404


def test_old_explanations_are_hidden_and_kept_in_the_audit_as_superseded() -> None:
    from datetime import UTC, datetime, timedelta

    from app.agent.run import EXPLANATION_MISSING

    client, services = make_client(admin_key="k" * 32, demo=object())
    client.post("/api/claims/F03/run")
    shown = lambda: [a["text"] for a in client.get("/api/claims/F03").json()["activity"]]  # noqa: E731
    assert any(" | SW: " in text for text in shown())

    cutoff = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    response = client.post(
        "/api/demo/supersede-explanations",
        json={"before": cutoff},
        headers={"x-admin-key": "k" * 32},
    )

    assert response.json()["superseded"] >= 1
    assert not any(" | SW: " in text for text in shown())
    assert EXPLANATION_MISSING in shown()
    superseded = [e for e in history(client, "F03") if e["action"] == "explanation_superseded"]
    assert superseded and " | SW: " in superseded[0]["detail"]["text"]
    assert superseded[0]["detail"]["reason"]


def test_superseding_needs_the_admin_key() -> None:
    client, _ = make_client(admin_key="k" * 32, demo=object())

    assert (
        client.post(
            "/api/demo/supersede-explanations", json={"before": "2026-11-18T00:00:00+00:00"}
        ).status_code
        == 403
    )
