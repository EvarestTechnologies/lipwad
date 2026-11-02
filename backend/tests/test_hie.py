import pytest

from app.db.schemas import Claim
from app.hie.base import ClaimOutcome, ClaimStatus, HieClaimNotFoundError, HieEditRefusedError
from app.hie.factory import create_hie
from app.hie.mock import MockHIE


def hie(**outcomes: ClaimOutcome) -> MockHIE:
    return MockHIE(
        outcomes=outcomes,
        practitioners={"PR-100": "Dr. Amani Otieno [demo]"},
        facilities={"FAC-4": 4},
        eligible_patients={"PT-1"},
    )


def test_eligible_patient_is_reported_eligible() -> None:
    assert hie().check_eligibility("PT-1").eligible


def test_unknown_patient_is_not_eligible() -> None:
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


def test_unknown_facility_is_not_found() -> None:
    assert not hie().lookup_facility("FAC-9").found


def test_unscripted_claim_is_accepted() -> None:
    response = hie().submit_claim(Claim(id="C01"))

    assert response.resourceType == "ClaimResponse"
    assert response.status is ClaimStatus.ACCEPTED
    assert response.reason is None


@pytest.mark.parametrize("status", [ClaimStatus.RETURNED, ClaimStatus.REJECTED])
def test_scripted_outcome_carries_its_reason(status: ClaimStatus) -> None:
    system = hie(F09=ClaimOutcome(status=status, reason="itemised_invoice_missing"))

    response = system.submit_claim(Claim(id="F09"))

    assert response.status is status
    assert response.reason == "itemised_invoice_missing"


def test_status_matches_submission() -> None:
    system = hie(F05=ClaimOutcome(status=ClaimStatus.RETURNED, reason="signature_missing"))
    submitted = system.submit_claim(Claim(id="F05"))

    assert system.get_claim_status(submitted.id) == submitted


def test_status_of_unknown_claim_raises() -> None:
    with pytest.raises(HieClaimNotFoundError):
        hie().get_claim_status("HIE-404")


def test_editing_a_returned_claim_accepts_it_and_clears_the_reason() -> None:
    system = hie(F09=ClaimOutcome(status=ClaimStatus.REJECTED, reason="itemised_invoice_missing"))
    submitted = system.submit_claim(Claim(id="F09"))

    edited = system.edit_claim(submitted.id, {"invoice": "itemised"})

    assert edited.status is ClaimStatus.ACCEPTED
    assert edited.reason is None
    assert system.get_claim_status(submitted.id).status is ClaimStatus.ACCEPTED


def test_accepted_claim_cannot_be_edited() -> None:
    system = hie()
    submitted = system.submit_claim(Claim(id="C01"))

    with pytest.raises(HieEditRefusedError):
        system.edit_claim(submitted.id, {"invoice": "itemised"})


def test_editing_unknown_claim_raises() -> None:
    with pytest.raises(HieClaimNotFoundError):
        hie().edit_claim("HIE-404", {})


def test_factory_builds_the_mock() -> None:
    assert isinstance(create_hie("mock"), MockHIE)


def test_factory_refuses_sandbox_until_it_exists() -> None:
    with pytest.raises(NotImplementedError):
        create_hie("sandbox")


def test_factory_refuses_unknown_mode() -> None:
    with pytest.raises(ValueError):
        create_hie("production")
