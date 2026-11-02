from pathlib import Path

from app.hie.base import HieAdapter
from app.hie.mock import MockHIE, MockScript


def create_hie(
    mode: str, script: MockScript | None = None, state_path: Path | None = None
) -> HieAdapter:
    if mode == "mock":
        return MockHIE(script=script, state_path=state_path)
    if mode == "sandbox":
        raise NotImplementedError("SandboxHIE needs DHA credentials and is a stretch item")
    raise ValueError(f"unknown HIE_MODE: {mode}")
