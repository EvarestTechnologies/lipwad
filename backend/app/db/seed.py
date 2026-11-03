"""Loads the synthetic cases into the database and the mock HIE.

Ground truth is never copied into claim fields: only the agent may produce those, with
citations. Seeding creates the claim record and any scripted HIE history.
"""

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.repository import save_claim
from app.db.schemas import Claim
from app.db.tables import Base, ClaimRow
from app.hie.base import (
    LIFECYCLE_FOR,
    Adjudication,
    Confirmation,
    HieClaimNotFoundError,
)
from app.hie.mock import MockHIE, MockScript, ScriptedOutcome

DATA_DIR = Path(__file__).parents[3] / "data" / "synthetic"
DEMO_CRITICAL_CASES = {"C01", "C02", "C03", "F01", "F02", "F03", "F04", "F05"}
REGISTERED_PRACTITIONER_NAME = "Dr. Amani Otieno [demo]"


class GroundTruth(BaseModel):
    case_id: str
    facility_level: int
    facility_id: str
    patient_ref: str
    practitioner_id: str
    practitioner_registered: bool
    service_type: Literal["outpatient", "inpatient", "maternity"]
    date_of_service: date
    expected_status: Literal["green", "amber", "red"]
    expected_reasons: list[str]
    fields: dict[str, str]
    codes: list[str]
    mock_hie_outcome: Adjudication
    mock_hie_reasons: list[str] = []
    days_since_outcome: int | None = None

    @property
    def was_submitted(self) -> bool:
        return self.days_since_outcome is not None


def load_cases(data_dir: Path = DATA_DIR) -> list[GroundTruth]:
    return [
        GroundTruth.model_validate_json(path.read_text())
        for path in sorted(data_dir.glob("*/ground_truth.json"))
    ]


def mock_script(cases: list[GroundTruth]) -> MockScript:
    return MockScript(
        outcomes={
            case.case_id: ScriptedOutcome(
                outcome=case.mock_hie_outcome,
                reasons=case.mock_hie_reasons,
                days_since_outcome=case.days_since_outcome or 0,
            )
            for case in cases
        },
        practitioners={
            case.practitioner_id: REGISTERED_PRACTITIONER_NAME
            for case in cases
            if case.practitioner_registered
        },
        facilities={case.facility_id: case.facility_level for case in cases},
        eligible_patients={case.patient_ref for case in cases},
    )


def register_submissions(hie: MockHIE, cases: list[GroundTruth]) -> None:
    """Give the mock the history behind claims seeded as already submitted."""
    confirmation = Confirmation(confirmed_by="seed [demo]", confirmed_at=datetime.now(UTC))
    for case in cases:
        if not case.was_submitted:
            continue
        try:
            hie.get_claim_status(f"HIE-{case.case_id}")
        except HieClaimNotFoundError:
            hie.submit_claim(Claim(id=case.case_id), confirmation)


def seed_claims(session: Session, cases: list[GroundTruth]) -> None:
    for case in cases:
        if session.get(ClaimRow, case.case_id) is None:
            save_claim(session, _claim(case))


def _claim(case: GroundTruth) -> Claim:
    discharged = date.fromisoformat(case.fields["discharge_date"])
    if not case.was_submitted:
        return Claim(id=case.case_id, discharge_date=discharged)
    return Claim(
        id=case.case_id,
        lifecycle=LIFECYCLE_FOR[case.mock_hie_outcome],
        hie_id=f"HIE-{case.case_id}",
        discharge_date=discharged,
        returned_at=datetime.now(UTC) - timedelta(days=case.days_since_outcome),
    )


def seed_database(database_url: str, hie_state_path: Path) -> int:
    """Seed claims and the mock HIE together, so their histories always agree.

    Claims already submitted are recreated on every run with a fresh return time, so
    the F05 countdown starts at day 13 whenever the demo is reseeded.
    """
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    cases = load_cases()
    with Session(engine) as session:
        for case in cases:
            row = session.get(ClaimRow, case.case_id)
            if row is not None and case.was_submitted:
                session.delete(row)
        session.flush()
        seed_claims(session, cases)
        session.commit()
    hie_state_path.unlink(missing_ok=True)
    register_submissions(MockHIE(script=mock_script(cases), state_path=hie_state_path), cases)
    return len(cases)


def main() -> None:
    count = seed_database(
        os.environ.get("DATABASE_URL", "sqlite:///./lipwad.db"),
        Path(os.environ.get("HIE_STATE_PATH", "./hie_state.json")),
    )
    print(f"Seeded {count} synthetic cases")


if __name__ == "__main__":
    main()
