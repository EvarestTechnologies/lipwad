"""Wires the database, agent, HIE and model clients from the environment."""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agent.run import ClaimAgent
from app.db.seed import DATA_DIR, load_cases, mock_script
from app.db.tables import Base
from app.hie.factory import create_hie
from app.hie.mock import MockHIE
from app.models import Role, create_client
from app.models.transcribe import create_transcriber
from app.tools.fixtures import load_fixtures


@dataclass
class Services:
    sessions: sessionmaker[Session]
    agent: ClaimAgent
    hie: MockHIE
    data_dir: Path


def build_services() -> Services:
    engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///./lipwad.db"))
    Base.metadata.create_all(engine)
    state = Path(os.environ.get("HIE_STATE_PATH", "./hie_state.json"))
    hie = create_hie(
        os.environ.get("HIE_MODE", "mock"), script=mock_script(load_cases()), state_path=state
    )
    fixtures = load_fixtures(DATA_DIR)
    agent = ClaimAgent(
        create_client(Role.VISION, fixtures=fixtures),
        create_client(Role.REASONING),
        hie,
        create_transcriber(fixtures=fixtures),
    )
    return Services(sessions=sessionmaker(engine), agent=agent, hie=hie, data_dir=DATA_DIR)
