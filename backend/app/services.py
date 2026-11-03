"""Wires the database, agent, HIE and model clients from the environment.

Also holds the guards a public demo needs: a daily cap on paid model runs, one
worker per claim at a time, and a demo that restores itself on a schedule.
"""

import json
import os
import shutil
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.run import ClaimAgent
from app.db.seed import DATA_DIR, load_cases, mock_script, seed_database
from app.db.tables import ActivityRow, Base, ClaimRow
from app.hie.factory import create_hie
from app.hie.mock import MockHIE
from app.models import Role, create_client
from app.models.transcribe import create_transcriber
from app.tools.fixtures import load_fixtures


def _now() -> datetime:
    return datetime.now(UTC)


class ClaimBusyError(Exception):
    """Another request is already working on this claim."""


@dataclass
class RunBudget:
    """Caps paid agent runs per UTC day; the count is kept in a small JSON file."""

    path: Path
    per_day: int
    clock: Callable[[], datetime] = _now
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def spend(self) -> bool:
        with self._lock:
            today = self.clock().date().isoformat()
            try:
                usage = json.loads(self.path.read_text())
            except (OSError, ValueError):
                usage = {}
            count = usage.get("count", 0) if usage.get("date") == today else 0
            if count >= self.per_day:
                return False
            self.path.write_text(json.dumps({"date": today, "count": count + 1}))
            return True


@dataclass
class DemoReset:
    """Calls `reset` when the marker file is missing or older than `every_hours`."""

    marker: Path
    every_hours: float
    reset: Callable[[], None]
    clock: Callable[[], datetime] = _now
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def maybe(self) -> None:
        with self._lock:
            now = self.clock()
            try:
                last = datetime.fromisoformat(self.marker.read_text().strip())
            except (OSError, ValueError):
                last = None
            if last is not None and now - last < timedelta(hours=self.every_hours):
                return
            self.reset()
            self.marker.write_text(now.isoformat())


class DemoState:
    """Snapshots the demo database and HIE state, and restores them with time moved on.

    A restore shifts every stored time by the time since the snapshot, so a claim that
    was on day 13 of its resubmission window is still on day 13 after the restore.
    Without a snapshot, a restore reseeds the synthetic cases.
    """

    def __init__(
        self,
        database_url: str,
        hie_state_path: Path,
        baseline_dir: Path,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.engine: Engine = create_engine(database_url)
        self._url = database_url
        self._state = hie_state_path
        self._baseline = baseline_dir
        self._clock = clock

    def snapshot(self) -> None:
        self._baseline.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(self._baseline / "lipwad.db")
        try:
            with self.engine.connect() as connection:
                connection.connection.driver_connection.backup(target)
        finally:
            target.close()
        if self._state.exists():
            shutil.copyfile(self._state, self._baseline / "hie_state.json")
        (self._baseline / "taken_at").write_text(self._clock().isoformat())

    def restore(self, hie: MockHIE) -> None:
        saved = self._baseline / "lipwad.db"
        if not saved.exists():
            Base.metadata.drop_all(self.engine)
            seed_database(self._url, self._state)
            hie.reload()
            return
        source = sqlite3.connect(saved)
        try:
            with self.engine.connect() as connection:
                source.backup(connection.connection.driver_connection)
        finally:
            source.close()
        if (self._baseline / "hie_state.json").exists():
            shutil.copyfile(self._baseline / "hie_state.json", self._state)
        taken = datetime.fromisoformat((self._baseline / "taken_at").read_text().strip())
        offset = self._clock() - taken
        with Session(self.engine) as session:
            for row in session.scalars(select(ClaimRow).where(ClaimRow.returned_at.is_not(None))):
                row.returned_at = row.returned_at + offset
            for row in session.scalars(select(ActivityRow)):
                row.at = row.at + offset
            session.commit()
        hie.reload()
        hie.shift(offset)


@dataclass
class Services:
    sessions: sessionmaker[Session]
    agent: ClaimAgent
    hie: MockHIE
    data_dir: Path
    budget: RunBudget | None = None
    demo_reset: DemoReset | None = None
    demo: DemoState | None = None
    admin_key: str | None = None
    _locks: dict[str, threading.Lock] = field(default_factory=dict, repr=False)
    _guard: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @contextmanager
    def claim_lock(self, claim_id: str) -> Iterator[None]:
        """Hold the claim for one request; a second request at the same time is refused."""
        with self._guard:
            lock = self._locks.setdefault(claim_id, threading.Lock())
        if not lock.acquire(blocking=False):
            raise ClaimBusyError(f"Lipwad is already working on {claim_id}; try again shortly")
        try:
            yield
        finally:
            lock.release()


def build_services() -> Services:
    url = os.environ.get("DATABASE_URL", "sqlite:///./lipwad.db")
    state = Path(os.environ.get("HIE_STATE_PATH", "./hie_state.json"))
    data = state.parent
    demo = DemoState(url, state, data / "baseline")
    Base.metadata.create_all(demo.engine)
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
    per_day = int(os.environ.get("LIPWAD_DAILY_RUNS") or 0)
    every = float(os.environ.get("LIPWAD_DEMO_RESET_HOURS") or 0)
    return Services(
        sessions=sessionmaker(demo.engine),
        agent=agent,
        hie=hie,
        data_dir=DATA_DIR,
        budget=RunBudget(data / "usage.json", per_day) if per_day else None,
        demo_reset=DemoReset(data / "demo_reset_at", every, lambda: demo.restore(hie))
        if every
        else None,
        demo=demo,
        admin_key=(os.environ.get("LIPWAD_ADMIN_KEY") or "").strip() or None,
    )
