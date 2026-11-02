"""Map each model role to its provider config.

Partner providers serve the roles they were chosen for; anything else, and
any partner role whose credentials are missing, falls back to the Meta Model
API. Resolution is pure configuration: it never touches the network and never
raises for a missing key. Key enforcement happens in the factory.
"""

import os
from collections.abc import Mapping

from pydantic import SecretStr

from app.models.base import ProviderConfig, Role

META_BASE_URL = "https://api.meta.ai/v1"
BASETEN_BASE_URL = "https://inference.baseten.co/v1"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"

BASETEN_REASONING_MODEL = "meta-models/muse-spark-open-1026"
MODAL_GLIMMER_MODEL = "muse-glimmer"

META_MODEL_FOR = {
    Role.REASONING: "muse-spark",
    Role.TRIAGE: "muse-spark",
    Role.CODING: "muse-spark",
    Role.SEGMENTATION: "sam-3.1",
    Role.VISION: "muse-spark",
    Role.TRANSCRIPTION: "muse-voice-transcribe",
}


def _present(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _value(settings: Mapping[str, str], name: str, default: str) -> str:
    return _present(settings.get(name)) or default


def _meta(role: Role, settings: Mapping[str, str]) -> ProviderConfig:
    return ProviderConfig(
        role=role,
        provider="meta",
        base_url=_value(settings, "META_MODEL_API_BASE_URL", META_BASE_URL),
        api_key=SecretStr(_present(settings.get("META_MODEL_API_KEY")) or ""),
        model_id=META_MODEL_FOR[role],
        key_env_var="META_MODEL_API_KEY",
    )


def resolve_provider(role: Role, env: Mapping[str, str] | None = None) -> ProviderConfig:
    """Return the provider config for a role, falling back to Meta when needed."""
    settings = dict(os.environ) if env is None else dict(env)
    if role is Role.REASONING:
        key = _present(settings.get("BASETEN_API_KEY"))
        if key is None:
            return _meta(role, settings)
        return ProviderConfig(
            role=role,
            provider="baseten",
            base_url=_value(settings, "BASETEN_BASE_URL", BASETEN_BASE_URL),
            api_key=SecretStr(key),
            model_id=_value(settings, "BASETEN_MODEL", BASETEN_REASONING_MODEL),
            key_env_var="BASETEN_API_KEY",
        )
    if role is Role.TRIAGE:
        endpoint = _present(settings.get("MODAL_GLIMMER_ENDPOINT_URL"))
        secret = _present(settings.get("MODAL_TOKEN_SECRET"))
        if endpoint is None or secret is None:
            return _meta(role, settings)
        return ProviderConfig(
            role=role,
            provider="modal",
            base_url=endpoint,
            api_key=SecretStr(secret),
            model_id=_value(settings, "MODAL_GLIMMER_MODEL", MODAL_GLIMMER_MODEL),
            key_env_var="MODAL_TOKEN_SECRET",
        )
    if role is Role.CODING:
        key = _present(settings.get("FIREWORKS_API_KEY"))
        model = _present(settings.get("FIREWORKS_CODING_MODEL"))
        if key is None or model is None:
            return _meta(role, settings)
        return ProviderConfig(
            role=role,
            provider="fireworks",
            base_url=_value(settings, "FIREWORKS_BASE_URL", FIREWORKS_BASE_URL),
            api_key=SecretStr(key),
            model_id=model,
            key_env_var="FIREWORKS_API_KEY",
        )
    return _meta(role, settings)
