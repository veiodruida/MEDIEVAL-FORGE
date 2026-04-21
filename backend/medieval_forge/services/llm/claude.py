"""ClaudeProvider — Anthropic claude-sonnet-4-6 via AsyncAnthropic streaming.

D-10: Auth priority: CliAuth (claude CLI session) > ApiKeyAuth (env var) > ApiKeyAuth (dialog).
D-19/D-20: Uses tool_use JSON mode with submit_research tool for structured output.
"""
from __future__ import annotations

import asyncio
import os

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from .base import ApiKeyAuth, CliAuth, HealthStatus, LLMProvider

SYSTEM_PROMPT = (
    "You are a historical-research assistant. Given a country and period, "
    "return the political hierarchy as JSON via the submit_research tool."
)


class ClaudeProvider:
    provider_id = "claude"
    display_name = "Claude (Anthropic)"
    auth_methods = [
        CliAuth(cli_command="claude", auth_file_path="~/.claude/.credentials.json"),
        ApiKeyAuth(env_var="ANTHROPIC_API_KEY"),
        ApiKeyAuth(env_var=None),
    ]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        key = (credentials or {}).get("key") or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            return HealthStatus(healthy=False, message="No ANTHROPIC_API_KEY or session key")
        return HealthStatus(healthy=True, message="API key present")

    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel:
        key = (credentials or {}).get("key") or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("No Anthropic credentials available")
        client = AsyncAnthropic(api_key=key)
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {
                    "name": "submit_research",
                    "description": "Submit structured research result",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "submit_research"},
        ) as stream:
            async for text in stream.text_stream:
                if queue is not None and text:
                    await queue.put(f"data: {text}\n\n")
            final = await stream.get_final_message()
        tool_block = next(
            b for b in final.content if getattr(b, "type", None) == "tool_use"
        )
        return schema.model_validate(tool_block.input)
