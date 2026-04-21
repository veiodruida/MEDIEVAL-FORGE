"""LLMProvider Protocol, AuthMethod tagged union, HealthStatus.

D-02/D-03: Each provider implements LLMProvider Protocol with a typed auth_methods list.
"""
from __future__ import annotations

import asyncio
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class HealthStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    healthy: bool
    message: str = ""


class ApiKeyAuth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["api_key"] = "api_key"
    env_var: str | None = None  # None = dialog-paste-only fallback


class OAuthAuth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["oauth"] = "oauth"
    authorize_url: str | None = None  # None until /oauth/start computes it
    scopes: list[str] = []


class CliAuth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["cli"] = "cli"
    cli_command: str          # e.g., "claude"
    auth_file_path: str       # e.g., "~/.claude/.credentials.json"


class NoAuth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["none"] = "none"


AuthMethod = ApiKeyAuth | OAuthAuth | CliAuth | NoAuth


@runtime_checkable
class LLMProvider(Protocol):
    provider_id: str
    display_name: str
    auth_methods: list[AuthMethod]

    async def health_check(self, credentials: dict | None) -> HealthStatus: ...

    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel: ...
