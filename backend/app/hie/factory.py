from app.hie.base import HieAdapter
from app.hie.mock import MockHIE


def create_hie(mode: str) -> HieAdapter:
    if mode == "mock":
        return MockHIE()
    if mode == "sandbox":
        raise NotImplementedError("SandboxHIE needs DHA credentials and is a stretch item")
    raise ValueError(f"unknown HIE_MODE: {mode}")
