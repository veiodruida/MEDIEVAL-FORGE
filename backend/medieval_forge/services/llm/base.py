"""LLMProvider Protocol + auth methods + health-check shape (NEW v3, Phase 07 D-01).

Design template: v1 87f8aab~1:base.py. v3 simplification:
- 2-provider MVP (Claude + Ollama) per D-05.
- OAuthAuth dropped (deferred to v3.1 backlog; see 07-RESEARCH.md §Deferred).
- @runtime_checkable so isinstance() works on duck-typed adapters.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class HealthStatus(BaseModel):
    """Result of a provider's health_check() — `healthy` plus a UI-rendered message."""

    healthy: bool
    message: str = ""


class ApiKeyAuth(BaseModel):
    """API-key auth. `env_var=None` signals dialog-paste flow (payload persists to DB)."""

    type: str = "api_key"
    env_var: str | None = None


class CliAuth(BaseModel):
    """CLI-piggyback auth (e.g., reading `~/.claude/.credentials.json` from Claude Code)."""

    type: str = "cli"
    cli_command: str
    auth_file_path: str


class NoAuth(BaseModel):
    """No-auth (e.g., local Ollama at http://localhost:11434)."""

    type: str = "none"


# OAuthAuth intentionally NOT included — deferred to v3.1 per 07-RESEARCH §Deferred.
AuthMethod = ApiKeyAuth | CliAuth | NoAuth


@runtime_checkable
class LLMProvider(Protocol):
    """Plugin-registry contract for an LLM adapter.

    Implementations supply:
    - identity (`provider_id`, `display_name`),
    - declared auth methods (`auth_methods`),
    - an async `health_check` returning `HealthStatus`,
    - an async `research` that streams events into the provided queue.
    """

    provider_id: str
    display_name: str
    auth_methods: list[AuthMethod]

    async def health_check(self, credentials: dict | None) -> HealthStatus: ...

    async def research(
        self,
        prompt: str,
        schema: Any,
        credentials: dict | None,
        queue: Any,
    ) -> Any: ...
