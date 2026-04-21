"""Base types for the LLM adapter layer.

Defines the LLMProvider Protocol, AuthMethod tagged union, and HealthStatus.
Source: CONTEXT.md D-02 / D-03 and RESEARCH.md Pattern 1.
"""
from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class HealthStatus(BaseModel):
    healthy: bool
    message: str = ""


class ApiKeyAuth(BaseModel):
    type: str = "api_key"
    env_var: str | None = None


class OAuthAuth(BaseModel):
    type: str = "oauth"
    authorize_url: str = ""
    scopes: list[str] = []


class CliAuth(BaseModel):
    type: str = "cli"
    cli_command: str = ""
    auth_file_path: str = ""


class NoAuth(BaseModel):
    type: str = "none"


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
