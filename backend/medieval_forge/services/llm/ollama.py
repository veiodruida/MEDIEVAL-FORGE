"""OllamaProvider — Local Ollama via async client with format='json'.

D-19: No auth required for local Ollama instance.
Uses qwen2.5:7b as default model; format='json' enforces JSON output.
"""
from __future__ import annotations

import asyncio
import json

from ollama import AsyncClient
from pydantic import BaseModel

from .base import HealthStatus, LLMProvider, NoAuth

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"


class OllamaProvider:
    provider_id = "ollama"
    display_name = "Ollama (local)"
    auth_methods = [NoAuth()]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        try:
            client = AsyncClient(host=OLLAMA_HOST)
            await asyncio.wait_for(client.list(), timeout=3.0)
            return HealthStatus(healthy=True, message=f"Reachable at {OLLAMA_HOST}")
        except asyncio.TimeoutError:
            return HealthStatus(healthy=False, message="Unreachable: timeout after 3s")
        except Exception as exc:
            return HealthStatus(healthy=False, message=f"Unreachable: {exc}")

    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel:
        client = AsyncClient(host=OLLAMA_HOST)
        # Pick the model: user-selected via credentials > DEFAULT_MODEL.
        model = (credentials or {}).get("model") or DEFAULT_MODEL
        if queue is not None:
            await queue.put(f"data: Aguardando Ollama ({model})...\n\n")
        response = await client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            stream=False,
        )
        content = response["message"]["content"]
        return schema.model_validate_json(content)
