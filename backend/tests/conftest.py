"""Suite-wide guard: tests serve fixtures and mocks, never the network.

Connection attempts are refused; in-process socket pairs (as used by the API
test client) still work.
"""

import socket

import pytest


def _refuse_connect(self: socket.socket, *args: object, **kwargs: object) -> None:
    raise AssertionError("network access is forbidden in tests")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _refuse_connect)
