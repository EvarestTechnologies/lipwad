"""Deterministic stub provider. Replays fixtures by case ID, never network."""

import hashlib
from collections.abc import Mapping

from app.models.base import (
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    Role,
    StubFixtureMissingError,
)

STUB_EMBEDDING_DIM = 8


class StubProvider:
    """Serve canned fixtures in tests. A role-specific fixture wins over a
    generic one: `reasoning:F05` beats `F05` for the reasoning role."""

    def __init__(self, role: Role, fixtures: Mapping[str, str] | None = None) -> None:
        self._role = role
        self._fixtures = dict(fixtures or {})

    @property
    def role(self) -> Role:
        return self._role

    def complete(self, request: ChatRequest) -> ChatResponse:
        if not request.case_id:
            raise StubFixtureMissingError("stub replay needs a case_id")
        keys = (f"{self._role.value}:{request.case_id}", request.case_id)
        for key in keys:
            if key in self._fixtures:
                return ChatResponse(content=self._fixtures[key], model_id="stub", provider="stub")
        raise StubFixtureMissingError(
            f"no stub fixture for case {request.case_id!r} (role {self._role.value})"
        )

    def embed(self, text: str) -> EmbeddingResponse:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [(byte - 128) / 128 for byte in digest[:STUB_EMBEDDING_DIM]]
        return EmbeddingResponse(vector=vector, model_id="stub", provider="stub")
