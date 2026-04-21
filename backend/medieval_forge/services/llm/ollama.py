"""Ollama local LLM provider adapter.

Implements LLMProvider Protocol using ollama Python client.
No auth required; healthcheck via GET localhost:11434/api/tags (D-13).
Research method will be fully implemented in Plan 03-03.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .base import NoAuth, HealthStatus

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"


class OllamaProvider:
    provider_id = "ollama"
    display_name = "Ollama (Local)"
    auth_methods = [NoAuth()]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    return HealthStatus(healthy=True, message="Ollama reachable")
                return HealthStatus(healthy=False, message=f"Ollama returned {resp.status_code}")
        except Exception as exc:
            return HealthStatus(healthy=False, message=f"Ollama unreachable: {exc}")

    async def research(
        self,
        prompt: str,
        schema: type,
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> Any:
        raise NotImplementedError("Ollama research not yet implemented — Plan 03-03")
