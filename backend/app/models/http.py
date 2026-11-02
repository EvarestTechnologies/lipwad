"""Live provider client. Every provider speaks the OpenAI-compatible format, so
one client serves all roles: POST `{base_url}/chat/completions` and
`{base_url}/embeddings` with a Bearer key."""

from typing import Any

import httpx

from app.models.base import (
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    ModelAPIError,
    ProviderConfig,
)


class OpenAICompatibleClient:
    def __init__(
        self,
        config: ProviderConfig,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._config = config
        self._transport = transport
        self._timeout = timeout

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def complete(self, request: ChatRequest) -> ChatResponse:
        payload = {
            "model": self._config.model_id,
            "messages": [item.model_dump() for item in request.messages],
        }
        data = self._post("chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelAPIError(f"malformed chat response from {self._config.provider}") from exc
        if not isinstance(content, str):
            raise ModelAPIError(f"malformed chat response from {self._config.provider}")
        return ChatResponse(
            content=content, model_id=self._config.model_id, provider=self._config.provider
        )

    def embed(self, text: str) -> EmbeddingResponse:
        data = self._post("embeddings", {"model": self._config.model_id, "input": text})
        try:
            vector = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelAPIError(
                f"malformed embedding response from {self._config.provider}"
            ) from exc
        if not isinstance(vector, list) or not all(
            isinstance(item, (int, float)) for item in vector
        ):
            raise ModelAPIError(f"malformed embedding response from {self._config.provider}")
        return EmbeddingResponse(
            vector=[float(item) for item in vector],
            model_id=self._config.model_id,
            provider=self._config.provider,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}/{path}"
        headers = {"Authorization": f"Bearer {self._config.api_key.get_secret_value()}"}
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise ModelAPIError(f"{self._config.provider} request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ModelAPIError(
                f"{self._config.provider} returned HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ModelAPIError(f"malformed JSON response from {self._config.provider}") from exc
        if not isinstance(data, dict):
            raise ModelAPIError(f"malformed response from {self._config.provider}")
        return data
