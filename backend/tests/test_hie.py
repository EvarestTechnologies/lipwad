from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.db.schemas import Citation, Claim, Field, Lifecycle
from app.hie.base import (
    Adjudication,
    ClaimPatch,
    Confirmation,
    HieClaimNotFoundError,
    HieDuplicateClaimError,
    HieEditRefusedError,
)
from app.hie.factory import create_hie
from app.hie.mock import MockHIE, MockScript, ScriptedOutcome

NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
CONFIRMED = Confirmation(confirmed_by="clerk [demo]", confirmed_at=NOW)
RETURNED = ScriptedOutcome(outcome=Adjudication.RETURN, reasons=["signature_missing"])


def script(**outcomes: ScriptedOutcome) -> MockScript:
    return MockScript(
        outcomes=outcomes,
        practitioners={"PR-100": "Dr. Amani Otieno [demo]"},
        facilities={"FAC-4": 4},
        eligible_patients={"PT-1"},
    )


def hie(**outcomes: ScriptedOutcome) -> MockHIE:
    return MockHIE(script=script(**outcomes), clock=lambda: NOW)


def patch() -> ClaimPatch:
    citation = Citation(kind="image", source_id="upload-1", region=[[0.1, 0.2], [0.3, 0.4]])
    return ClaimPatch(
        corrections=[Field(name="signature", value="present", confidence=1, citations=[citation])]
    )


def test_eligibility_reflects_the_register() -> None:
    assert hie().check_eligibility("PT-1").eligible
    assert not hie().check_eligibility("PT-9").eligible


def test_registered_practitioner_is_found() -> None:
    result = hie().lookup_practitioner("PR-100")

    assert result.found
    assert result.name == "Dr. Amani Otieno [demo]"


def test_unregistered_practitioner_is_not_found() -> None:
    result = hie().lookup_practitioner("PR-404")

    assert not result.found
    assert result.name is None


def test_facility_lookup_reports_level() -> None:
    assert hie().lookup_facility("FAC-4").level == 4
    assert not hie().lookup_facility("FAC-9").found


def test_unscripted_claim_is_accepted() -> None:
    response = hie().submit_claim(Claim(id="C01"), CONFIRMED)

    assert response.resourceType == "ClaimResponse"
    assert response.outcome is Adjudication.ACCEPT
    assert response.error == []


def test_submission_requires_a_named_confirmer() -> None:
    with pytest.raises(ValidationError):
        Confirmation(confirmed_by=" ", confirmed_at=NOW)


@pytest.mark.parametrize("outcome", [Adjudication.RETURN, Adjudication.REJECT])
def test_scripted_outcome_carries_all_reasons(outcome: Adjudication) -> None:
    reasons = ["itemised_invoice_missing", "signature_missing"]
    system = hie(F09=ScriptedOutcome(outcome=outcome, reasons=reasons))

    assert system.submit_claim(Claim(id="F09"), CONFIRMED).error == reasons


def test_outcome_time_supports_day_thirteen_of_fourteen() -> None:
    system = hie(F05=RETURNED.model_copy(update={"days_since_outcome": 13}))

    response = system.submit_claim(Claim(id="F05"), CONFIRMED)

    assert response.outcome_at == NOW - timedelta(days=13)


@pytest.mark.parametrize(
    ("outcome", "lifecycle"),
    [
        (Adjudication.ACCEPT, Lifecycle.SUBMITTED),
        (Adjudication.RETURN, Lifecycle.RETURNED),
        (Adjudication.REJECT, Lifecycle.REJECTED),
    ],
)
def test_outcome_maps_to_claim_lifecycle(outcome: Adjudication, lifecycle: Lifecycle) -> None:
    system = hie(C01=ScriptedOutcome(outcome=outcome))

    assert system.submit_claim(Claim(id="C01"), CONFIRMED).lifecycle is lifecycle


def test_accepted_claim_can_settle_to_paid() -> None:
    system = hie()
    submitted = system.submit_claim(Claim(id="C01"), CONFIRMED)

    assert system.settle(submitted.id).lifecycle is Lifecycle.PAID


def test_status_matches_submission() -> None:
    system = hie(F05=RETURNED)
    submitted = system.submit_claim(Claim(id="F05"), CONFIRMED)

    assert system.get_claim_status(submitted.id) == submitted


def test_status_of_unknown_claim_raises() -> None:
    with pytest.raises(HieClaimNotFoundError):
        hie().get_claim_status("HIE-404")


def test_duplicate_submission_is_refused_and_keeps_state() -> None:
    system = hie(F09=RETURNED)
    submitted = system.submit_claim(Claim(id="F09"), CONFIRMED)

    with pytest.raises(HieDuplicateClaimError):
        system.submit_claim(Claim(id="F09"), CONFIRMED)
    assert system.get_claim_status(submitted.id) == submitted


def test_edit_accepts_the_claim_and_records_the_patch() -> None:
    system = hie(F09=RETURNED)
    submitted = system.submit_claim(Claim(id="F09"), CONFIRMED)

    edited = system.edit_claim(submitted.id, patch())

    assert edited.outcome is Adjudication.ACCEPT
    assert edited.error == []
    assert system.recorded_edits(submitted.id) == [patch()]


def test_failed_repair_can_be_scripted() -> None:
    still_returned = ScriptedOutcome(outcome=Adjudication.RETURN, reasons=["signature_missing"])
    system = hie(F09=RETURNED.model_copy(update={"after_edit": still_returned}))
    submitted = system.submit_claim(Claim(id="F09"), CONFIRMED)

    assert system.edit_claim(submitted.id, patch()).outcome is Adjudication.RETURN


def test_patch_needs_corrections_and_citations() -> None:
    with pytest.raises(ValidationError):
        ClaimPatch(corrections=[])
    with pytest.raises(ValidationError):
        ClaimPatch(corrections=[Field(name="signature", value="present", confidence=1)])


def test_accepted_claim_cannot_be_edited() -> None:
    system = hie()
    submitted = system.submit_claim(Claim(id="C01"), CONFIRMED)

    with pytest.raises(HieEditRefusedError):
        system.edit_claim(submitted.id, patch())


def test_edit_after_the_window_closes_is_refused() -> None:
    system = hie(F05=RETURNED.model_copy(update={"days_since_outcome": 15}))
    submitted = system.submit_claim(Claim(id="F05"), CONFIRMED)

    with pytest.raises(HieEditRefusedError):
        system.edit_claim(submitted.id, patch())


def test_editing_unknown_claim_raises() -> None:
    with pytest.raises(HieClaimNotFoundError):
        hie().edit_claim("HIE-404", patch())


def test_submitted_claims_survive_a_restart(tmp_path: Path) -> None:
    state = tmp_path / "hie.json"
    first = MockHIE(script=script(F09=RETURNED), state_path=state, clock=lambda: NOW)
    submitted = first.submit_claim(Claim(id="F09"), CONFIRMED)
    first.edit_claim(submitted.id, patch())

    restarted = MockHIE(script=script(F09=RETURNED), state_path=state, clock=lambda: NOW)

    assert restarted.get_claim_status(submitted.id).outcome is Adjudication.ACCEPT
    assert restarted.recorded_edits(submitted.id) == [patch()]


def test_factory_passes_the_script_to_the_mock() -> None:
    system = create_hie("mock", script=script())

    assert system.lookup_practitioner("PR-100").found


def test_factory_refuses_sandbox_until_it_exists() -> None:
    with pytest.raises(NotImplementedError):
        create_hie("sandbox")


def test_factory_refuses_unknown_mode() -> None:
    with pytest.raises(ValueError):
        create_hie("production")
