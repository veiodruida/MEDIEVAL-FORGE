"""OpenAIProvider — GPT-4o via AsyncOpenAI with json_schema response format.

D-21: Uses response_format=json_schema + stream=True for structured output.
"""
from __future__ import annotations

import asyncio
import os

from openai import AsyncOpenAI
from pydantic import BaseModel

from .base import ApiKeyAuth, HealthStatus, LLMProvider

SYSTEM_PROMPT = "You are a historical-research assistant. Return JSON matching the schema."


class OpenAIProvider:
    provider_id = "openai"
    display_name = "OpenAI (GPT-4o)"
    auth_methods = [
        ApiKeyAuth(env_var="OPENAI_API_KEY"),
        ApiKeyAuth(env_var=None),
    ]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        key = (credentials or {}).get("key") or os.getenv("OPENAI_API_KEY")
        return HealthStatus(
            healthy=bool(key),
            message="API key present" if key else "No OPENAI_API_KEY",
        )

    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel:
        key = (credentials or {}).get("key") or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("No OpenAI credentials available")
        client = AsyncOpenAI(api_key=key)
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "research_result",
                    "schema": schema.model_json_schema(),
                    "strict": True,
                },
            },
            stream=True,
        )
        chunks: list[str] = []
        async for chunk in stream:
            delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            if delta:
                chunks.append(delta)
                if queue is not None:
                    await queue.put(f"data: {delta}\n\n")
        return schema.model_validate_json("".join(chunks))
