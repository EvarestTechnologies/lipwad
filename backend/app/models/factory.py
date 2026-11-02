"""Build the model client for a role.

`MODEL_PROVIDER_MODE=stub` (as in CI) serves fixtures without network;
anything else resolves the live provider and requires its key.
"""

import os
from collections.abc import Mapping

import httpx

from app.models.base import MissingAPIKeyError, ModelClient, Role
from app.models.config import resolve_provider
from app.models.http import OpenAICompatibleClient
from app.models.stub import StubProvider


def create_client(
    role: Role,
    *,
    env: Mapping[str, str] | None = None,
    fixtures: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ModelClient:
    settings = dict(os.environ) if env is None else dict(env)
    mode = (settings.get("MODEL_PROVIDER_MODE") or "live").strip().lower()
    if mode == "stub":
        return StubProvider(role, fixtures)
    if mode != "live":
        raise ValueError(f"unknown MODEL_PROVIDER_MODE: {settings.get('MODEL_PROVIDER_MODE')!r}")
    config = resolve_provider(role, settings)
    if not config.api_key.get_secret_value().strip():
        raise MissingAPIKeyError(
            f"{config.key_env_var} is not set; "
            f"configure the {config.provider} provider for the {role.value} role "
            "or run with MODEL_PROVIDER_MODE=stub"
        )
    return OpenAICompatibleClient(config, transport=transport)
