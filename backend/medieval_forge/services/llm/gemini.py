"""GeminiProvider — Gemini 2.0 Flash via google-genai async client.

D-22: Uses response_mime_type='application/json' + response_schema for structured output.
Pitfall 2: Uses `from google import genai` (google-genai), NOT google.generativeai (deprecated).
Pitfall 3: No tools combined with response_mime_type (mutually exclusive in Gemini API).
"""
from __future__ import annotations

import asyncio
import os

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel

from .base import ApiKeyAuth, HealthStatus, LLMProvider, OAuthAuth


class GeminiProvider:
    provider_id = "gemini"
    display_name = "Gemini (Google)"
    auth_methods = [
        ApiKeyAuth(env_var="GOOGLE_API_KEY"),
        OAuthAuth(scopes=["https://www.googleapis.com/auth/generative-language.retriever"]),
        ApiKeyAuth(env_var=None),
    ]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        key = (
            (credentials or {}).get("api_key")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        token = (credentials or {}).get("access_token")
        has_cred = bool(key or token)
        return HealthStatus(
            healthy=has_cred,
            message="Credential present" if has_cred else "No GOOGLE_API_KEY/OAuth token",
        )

    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel:
        credentials = credentials or {}
        api_key = (
            credentials.get("api_key")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        token = credentials.get("access_token")
        if token:
            client = genai.Client(
                http_options={"headers": {"Authorization": f"Bearer {token}"}}
            )
        elif api_key:
            client = genai.Client(api_key=api_key)
        else:
            raise ValueError("No Gemini credentials available")
        # NOTE: We intentionally do NOT pass response_schema here. Gemini's
        # structured-output mode rejects any JSON Schema containing
        # `additionalProperties`, which Pydantic always emits for dict[str, X]
        # fields (kingdoms, duchies, baronies). Instead we rely on:
        #   - response_mime_type="application/json" (plain-JSON output mode)
        #   - explicit OUTPUT_FORMAT_SPEC in the prompt
        #   - Pydantic validation on our side (the retry loop catches errors)
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        )
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=config,
        )
        if queue is not None:
            await queue.put(f"data: Gemini respondeu ({len(response.text)} chars)\n\n")
        from .schemas import parse_research_json, ResearchResult
        if schema is ResearchResult:
            return parse_research_json(response.text)
        return schema.model_validate_json(response.text)
