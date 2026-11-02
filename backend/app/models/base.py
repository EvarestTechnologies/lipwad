"""Contracts for the model client layer.

Every model call goes through here. Each role resolves to a provider config
(base URL, key, model ID) and every provider speaks the OpenAI-compatible
Chat Completions format, so the switch is configuration, not code.
"""

from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, SecretStr
from pydantic import Field as PydanticField

ProviderName = Literal["meta", "baseten", "modal", "fireworks"]


class Role(StrEnum):
    REASONING = "reasoning"
    TRIAGE = "triage"
    CODING = "coding"
    SEGMENTATION = "segmentation"
    VISION = "vision"
    TRANSCRIPTION = "transcription"


class ProviderConfig(BaseModel):
    """How to reach the provider serving one role."""

    role: Role
    provider: ProviderName
    base_url: str
    api_key: SecretStr
    model_id: str
    key_env_var: str  # named in the error when the key is missing


class ChatMessage(BaseModel):
    """One turn in a Chat Completions conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Messages to complete, plus the stub replay key."""

    messages: list[ChatMessage] = PydanticField(min_length=1)
    case_id: str | None = None  # stub replay key; also used for tracing


class ChatResponse(BaseModel):
    """Text completion with its provenance."""

    content: str
    model_id: str
    provider: str


class EmbeddingResponse(BaseModel):
    """Embedding vector with its provenance."""

    vector: list[float]
    model_id: str
    provider: str


class ModelClient(Protocol):
    """What every model client implements."""

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Complete a chat request."""
        ...

    def embed(self, text: str) -> EmbeddingResponse:
        """Embed a text for retrieval."""
        ...


class StubFixtureMissingError(KeyError):
    """The stub has no fixture for this case ID (and it never calls the network)."""


class MissingAPIKeyError(Exception):
    """A live provider was selected but its key is not configured."""


class ModelAPIError(Exception):
    """The provider returned an HTTP error or a malformed body."""
