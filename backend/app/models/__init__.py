"""One client layer for every model role, with a provider switch and stub."""

from app.models.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    MissingAPIKeyError,
    ModelAPIError,
    ModelClient,
    ProviderConfig,
    Role,
    StubFixtureMissingError,
)
from app.models.config import resolve_provider
from app.models.factory import create_client
from app.models.http import OpenAICompatibleClient
from app.models.stub import StubProvider

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "EmbeddingResponse",
    "MissingAPIKeyError",
    "ModelAPIError",
    "ModelClient",
    "OpenAICompatibleClient",
    "ProviderConfig",
    "Role",
    "StubFixtureMissingError",
    "StubProvider",
    "create_client",
    "resolve_provider",
]
