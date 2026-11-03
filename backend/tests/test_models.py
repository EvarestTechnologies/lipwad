"""Model client layer: role resolution, partner fallback, stub replay, no network."""

import hashlib
import json
import socket

import httpx
import pytest

from app.models import (
    ChatMessage,
    ChatRequest,
    MissingAPIKeyError,
    ModelAPIError,
    OpenAICompatibleClient,
    Role,
    StubFixtureMissingError,
    StubProvider,
    create_client,
    resolve_provider,
)

META_KEY = "meta-key [demo]"
BASETEN_KEY = "baseten-key [demo]"
GLIMMER_URL = "https://modal.example/glimmer"
FIREWORKS_MODEL = "accounts/fireworks/models/coding [demo]"


def message(text: str = "review claim C01") -> ChatMessage:
    return ChatMessage(role="user", content=text)


def request(case_id: str | None = "C01") -> ChatRequest:
    return ChatRequest(messages=[message()], case_id=case_id)


def test_reasoning_resolves_to_baseten_when_configured() -> None:
    env = {"BASETEN_API_KEY": BASETEN_KEY, "META_MODEL_API_KEY": META_KEY}

    config = resolve_provider(Role.REASONING, env)

    assert config.provider == "baseten"
    assert config.base_url == "https://inference.baseten.co/v1"
    assert config.model_id == "meta-models/muse-spark-open-1026"
    assert config.api_key.get_secret_value() == BASETEN_KEY


def test_triage_resolves_to_modal_glimmer_when_configured() -> None:
    env = {
        "MODAL_GLIMMER_ENDPOINT_URL": GLIMMER_URL,
        "MODAL_GLIMMER_API_KEY": "glimmer-key [demo]",
        "META_MODEL_API_KEY": META_KEY,
    }

    config = resolve_provider(Role.TRIAGE, env)

    assert config.provider == "modal"
    assert config.base_url == GLIMMER_URL
    assert config.model_id == "muse-glimmer"


def test_coding_resolves_to_fireworks_when_configured() -> None:
    env = {
        "FIREWORKS_API_KEY": "fireworks-key [demo]",
        "FIREWORKS_CODING_MODEL": FIREWORKS_MODEL,
        "META_MODEL_API_KEY": META_KEY,
    }

    config = resolve_provider(Role.CODING, env)

    assert config.provider == "fireworks"
    assert config.base_url == "https://api.fireworks.ai/inference/v1"
    assert config.model_id == FIREWORKS_MODEL


@pytest.mark.parametrize(
    ("role", "model_id"),
    [
        (Role.SEGMENTATION, "sam-3.1"),
        (Role.VISION, "muse-spark-1.3"),
        (Role.TRANSCRIPTION, "muse-voice-transcribe-1.0"),
    ],
)
def test_meta_roles_resolve_to_the_meta_model_api(role: Role, model_id: str) -> None:
    config = resolve_provider(role, {"META_MODEL_API_KEY": META_KEY})

    assert config.provider == "meta"
    assert config.base_url == "https://api.meta.ai/v1"
    assert config.model_id == model_id
    assert config.api_key.get_secret_value() == META_KEY


def test_custom_meta_base_url_is_honoured() -> None:
    env = {"META_MODEL_API_KEY": META_KEY, "META_MODEL_API_BASE_URL": "https://meta.example/v1"}

    assert resolve_provider(Role.VISION, env).base_url == "https://meta.example/v1"


@pytest.mark.parametrize(
    ("role", "env"),
    [
        (Role.REASONING, {"META_MODEL_API_KEY": META_KEY}),
        (Role.REASONING, {"BASETEN_API_KEY": "   ", "META_MODEL_API_KEY": META_KEY}),
        (Role.TRIAGE, {"META_MODEL_API_KEY": META_KEY}),
        (
            Role.TRIAGE,
            {"MODAL_GLIMMER_ENDPOINT_URL": "   ", "META_MODEL_API_KEY": META_KEY},
        ),
        (Role.CODING, {"META_MODEL_API_KEY": META_KEY}),
        (
            Role.CODING,
            {"FIREWORKS_API_KEY": "key", "META_MODEL_API_KEY": META_KEY},
        ),
    ],
)
def test_partner_roles_fall_back_to_meta_when_unconfigured(role: Role, env: dict[str, str]) -> None:
    config = resolve_provider(role, env)

    assert config.provider == "meta"
    assert config.base_url == "https://api.meta.ai/v1"
    assert config.model_id == "muse-spark-1.3"


def stub(role: Role = Role.REASONING) -> StubProvider:
    return StubProvider(
        role,
        fixtures={
            "C01": "draft claim for C01",
            "reasoning:F05": "reasoning fix for F05",
            "F05": "generic fix for F05",
        },
    )


def test_stub_replays_the_fixture_for_the_case_id() -> None:
    response = stub().complete(request("C01"))

    assert response.content == "draft claim for C01"
    assert response.provider == "stub"


def test_stub_prefers_the_role_specific_fixture() -> None:
    assert stub(Role.REASONING).complete(request("F05")).content == "reasoning fix for F05"
    assert stub(Role.TRIAGE).complete(request("F05")).content == "generic fix for F05"


def test_stub_replay_is_deterministic() -> None:
    first = stub().complete(request("C01"))
    second = stub().complete(request("C01"))

    assert first == second


def test_stub_without_a_fixture_raises() -> None:
    with pytest.raises(StubFixtureMissingError, match="F99"):
        stub().complete(request("F99"))


def test_stub_without_a_case_id_raises() -> None:
    with pytest.raises(StubFixtureMissingError, match="case_id"):
        stub().complete(request(None))


def test_stub_embedding_is_deterministic_and_bounded() -> None:
    first = stub().embed("admission date 2026-10-12")
    second = stub().embed("admission date 2026-10-12")

    assert first.vector == second.vector
    assert len(first.vector) == 8
    assert all(-1 <= value <= 1 for value in first.vector)
    assert first.provider == "stub"


def test_stub_embedding_differs_per_text() -> None:
    assert stub().embed("alpha").vector != stub().embed("beta").vector


def test_factory_returns_the_stub_in_stub_mode() -> None:
    client = create_client(Role.REASONING, env={"MODEL_PROVIDER_MODE": "stub"})

    assert isinstance(client, StubProvider)


def test_factory_returns_a_live_client_by_default() -> None:
    client = create_client(Role.REASONING, env={"BASETEN_API_KEY": BASETEN_KEY})

    assert isinstance(client, OpenAICompatibleClient)


def test_factory_refuses_unknown_mode() -> None:
    with pytest.raises(ValueError, match="MODEL_PROVIDER_MODE"):
        create_client(Role.REASONING, env={"MODEL_PROVIDER_MODE": "sandbox"})


def test_live_client_without_a_key_names_the_missing_variable() -> None:
    with pytest.raises(MissingAPIKeyError, match="META_MODEL_API_KEY"):
        create_client(Role.VISION, env={})


def test_stub_makes_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in tests")

    monkeypatch.setattr(socket, "socket", refuse)

    assert stub().complete(request("C01")).content == "draft claim for C01"
    assert len(stub().embed("admission date").vector) == 8


def live_client(handler: httpx.MockTransport) -> OpenAICompatibleClient:
    config = resolve_provider(Role.REASONING, {"BASETEN_API_KEY": BASETEN_KEY})
    return OpenAICompatibleClient(config, transport=handler)


def test_live_client_posts_openai_compatible_chat_completions() -> None:
    seen: dict[str, object] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["path"] = http_request.url.path
        seen["authorization"] = http_request.headers["authorization"]
        seen["body"] = http_request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "judged green"}}]})

    response = live_client(httpx.MockTransport(handler)).complete(request("C01"))

    assert seen["path"] == "/v1/chat/completions"
    assert seen["authorization"] == f"Bearer {BASETEN_KEY}"
    assert '"model":"meta-models/muse-spark-open-1026"' in str(seen["body"]).replace(" ", "")
    assert '"role":"user"' in str(seen["body"]).replace(" ", "")
    assert response.content == "judged green"
    assert response.model_id == "meta-models/muse-spark-open-1026"
    assert response.provider == "baseten"


def test_live_client_tolerates_a_trailing_slash_on_the_base_url() -> None:
    seen: dict[str, object] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["path"] = http_request.url.path
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    env = {"BASETEN_API_KEY": BASETEN_KEY, "BASETEN_BASE_URL": "https://baseten.example/v1/"}
    config = resolve_provider(Role.REASONING, env)
    OpenAICompatibleClient(config, transport=httpx.MockTransport(handler)).complete(request())

    assert seen["path"] == "/v1/chat/completions"


@pytest.mark.parametrize("status", [400, 401, 429, 500])
def test_live_client_maps_http_errors(status: int) -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "denied"})

    with pytest.raises(ModelAPIError, match=str(status)):
        live_client(httpx.MockTransport(handler)).complete(request())


def test_live_client_rejects_a_malformed_body() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(ModelAPIError, match="malformed"):
        live_client(httpx.MockTransport(handler)).complete(request())


def test_live_client_posts_openai_compatible_embeddings() -> None:
    seen: dict[str, object] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["path"] = http_request.url.path
        return httpx.Response(200, json={"data": [{"embedding": [0.1, -0.2]}]})

    response = live_client(httpx.MockTransport(handler)).embed("admission date")

    assert seen["path"] == "/v1/embeddings"
    assert response.vector == [0.1, -0.2]
    assert response.provider == "baseten"


def test_stub_embedding_matches_the_documented_construction() -> None:
    digest = hashlib.sha256(b"alpha").digest()
    expected = [(byte - 128) / 128 for byte in digest[:8]]

    assert stub().embed("alpha").vector == expected


def test_modal_account_token_is_never_used_as_an_endpoint_key() -> None:
    env = {
        "MODAL_GLIMMER_ENDPOINT_URL": GLIMMER_URL,
        "MODAL_TOKEN_SECRET": "account-secret [demo]",
        "META_MODEL_API_KEY": META_KEY,
    }

    config = resolve_provider(Role.TRIAGE, env)

    assert config.provider == "meta"
    assert "account-secret" not in config.api_key.get_secret_value()


def test_reasoning_fallback_to_meta_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        resolve_provider(Role.REASONING, {"META_MODEL_API_KEY": META_KEY})

    assert "BASETEN_API_KEY" in caplog.text


def test_messages_can_carry_image_and_audio_parts() -> None:
    message = ChatMessage(
        role="user",
        content=[
            {"type": "text", "text": "Extract the admission date."},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}},
        ],
    )

    assert message.model_dump()["content"][1]["type"] == "image_url"


def test_missing_fixture_is_not_mistaken_for_a_missing_key() -> None:
    assert not issubclass(StubFixtureMissingError, LookupError)


def test_json_output_requests_a_json_object() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    client = create_client(
        Role.VISION,
        env={"META_MODEL_API_KEY": META_KEY},
        transport=httpx.MockTransport(handler),
    )
    client.complete(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")], json_output=True)
    )

    assert seen["response_format"] == {"type": "json_object"}
