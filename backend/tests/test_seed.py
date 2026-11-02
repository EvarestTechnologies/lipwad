from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.repository import load_claim
from app.db.schemas import Lifecycle
from app.db.seed import (
    DEMO_CRITICAL_CASES,
    GroundTruth,
    load_cases,
    mock_script,
    register_submissions,
    seed_claims,
)
from app.db.tables import Base, ClaimRow
from app.hie.base import Adjudication
from app.hie.mock import MockHIE

DATA_DIR = Path(__file__).parents[2] / "data" / "synthetic"


def engine():
    db = create_engine("sqlite://")
    Base.metadata.create_all(db)
    return db


def test_every_demo_critical_case_exists() -> None:
    assert DEMO_CRITICAL_CASES <= {case.case_id for case in load_cases(DATA_DIR)}


@pytest.mark.parametrize("case", load_cases(DATA_DIR), ids=lambda case: case.case_id)
def test_case_matches_its_directory_and_is_labelled_synthetic(case: GroundTruth) -> None:
    assert (DATA_DIR / case.case_id / "ground_truth.json").exists()
    assert "[demo]" in case.fields["patient_name"]


def test_expected_statuses_match_the_data_spec() -> None:
    cases = {case.case_id: case for case in load_cases(DATA_DIR)}

    assert cases["C01"].expected_status == "green"
    assert cases["F01"].expected_reasons == ["signature_missing"]
    assert cases["F02"].expected_reasons == ["itemised_invoice_missing"]
    assert cases["F03"].expected_status == "red"
    assert cases["F04"].expected_status == "red"
    assert cases["F05"].expected_status == "amber"


def test_invalid_case_is_rejected(tmp_path: Path) -> None:
    case_dir = tmp_path / "X01"
    case_dir.mkdir()
    (case_dir / "ground_truth.json").write_text('{"case_id": "X01"}')

    with pytest.raises(ValueError):
        load_cases(tmp_path)


def test_seeding_is_idempotent() -> None:
    db = engine()
    cases = load_cases(DATA_DIR)

    with Session(db) as session:
        seed_claims(session, cases)
        seed_claims(session, cases)
        session.commit()
        assert session.scalar(select(func.count()).select_from(ClaimRow)) == len(cases)


def test_seeded_rescue_case_is_returned_on_day_thirteen() -> None:
    db = engine()
    cases = load_cases(DATA_DIR)

    with Session(db) as session:
        seed_claims(session, cases)
        session.commit()
        claim = load_claim(session, "F05")

    assert claim.lifecycle is Lifecycle.RETURNED
    assert claim.hie_id == "HIE-F05"
    assert claim.resubmission_deadline is not None


def test_seeded_fields_are_not_trusted_without_evidence() -> None:
    db = engine()

    with Session(db) as session:
        seed_claims(session, load_cases(DATA_DIR))
        session.commit()
        assert load_claim(session, "C01").fields == []


def test_mock_script_knows_clean_practitioner_and_not_the_f04_one() -> None:
    cases = {case.case_id: case for case in load_cases(DATA_DIR)}
    hie = MockHIE(script=mock_script(list(cases.values())))

    assert hie.lookup_practitioner(cases["C01"].practitioner_id).found
    assert not hie.lookup_practitioner(cases["F04"].practitioner_id).found


def test_mock_script_registers_facility_level_and_patient() -> None:
    cases = {case.case_id: case for case in load_cases(DATA_DIR)}
    hie = MockHIE(script=mock_script(list(cases.values())))

    assert hie.lookup_facility(cases["C01"].facility_id).level == 3
    assert hie.check_eligibility(cases["C01"].patient_ref).eligible


def test_mock_script_carries_scripted_rejection() -> None:
    script = mock_script(load_cases(DATA_DIR))

    assert script.outcomes["F09"].outcome is Adjudication.REJECT
    assert script.outcomes["F09"].reasons


def test_seeded_submissions_are_known_to_the_mock() -> None:
    cases = load_cases(DATA_DIR)
    hie = MockHIE(script=mock_script(cases))

    register_submissions(hie, cases)
    register_submissions(hie, cases)

    assert hie.get_claim_status("HIE-F05").outcome is Adjudication.RETURN
    assert hie.get_claim_status("HIE-F05").error == ["signature_missing"]
    assert hie.get_claim_status("HIE-F09").outcome is Adjudication.REJECT
