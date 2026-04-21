"""OpenAI LLM provider adapter.

Implements LLMProvider Protocol using AsyncOpenAI SDK.
JSON mode via response_format={"type": "json_schema"} (RESEARCH.md).
Research method will be fully implemented in Plan 03-03.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .base import ApiKeyAuth, HealthStatus


class OpenAIProvider:
    provider_id = "openai"
    display_name = "OpenAI (GPT)"
    auth_methods = [
        ApiKeyAuth(env_var="OPENAI_API_KEY"),
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
        raise NotImplementedError("OpenAI research not yet implemented — Plan 03-03")
