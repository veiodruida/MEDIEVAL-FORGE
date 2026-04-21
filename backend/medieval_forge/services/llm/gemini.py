"""Google Gemini LLM provider adapter.

Implements LLMProvider Protocol using google-genai async client.
JSON mode via response_mime_type="application/json" + response_schema (RESEARCH.md).
Research method will be fully implemented in Plan 03-03.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .base import ApiKeyAuth, OAuthAuth, HealthStatus

GEMINI_SCOPES = ["https://www.googleapis.com/auth/generative-language.retriever"]


class GeminiProvider:
    provider_id = "gemini"
    display_name = "Gemini (Google)"
    auth_methods = [
        ApiKeyAuth(env_var="GOOGLE_API_KEY"),
        OAuthAuth(
            authorize_url="https://accounts.google.com/o/oauth2/auth",
            scopes=GEMINI_SCOPES,
        ),
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
        raise NotImplementedError("Gemini research not yet implemented — Plan 03-03")
