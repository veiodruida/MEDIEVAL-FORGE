"""Claude (Anthropic) LLM provider adapter.

Implements LLMProvider Protocol using AsyncAnthropic SDK.
Streaming via tool_use for structured JSON output (RESEARCH.md Pattern 3).
Research method will be fully implemented in Plan 03-03.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .base import ApiKeyAuth, CliAuth, HealthStatus


class ClaudeProvider:
    provider_id = "claude"
    display_name = "Claude (Anthropic)"
    auth_methods = [
        CliAuth(
            cli_command="claude",
            auth_file_path="~/.claude/.credentials.json",
        ),
        ApiKeyAuth(env_var="ANTHROPIC_API_KEY"),
    ]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        if not credentials:
            return HealthStatus(healthy=False, message="No credentials configured")
        return HealthStatus(healthy=True, message="Credentials present")

    async def research(
        self,
        prompt: str,
        schema: type,
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> Any:
        raise NotImplementedError("Claude research not yet implemented — Plan 03-03")
