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

        # Ollama.chat(stream=False) is a single blocking call that can take 30-120s
        # on local hardware. Emit a heartbeat every 3s so the user sees activity.
        async def heartbeat() -> None:
            elapsed = 0
            while queue is not None:
                await asyncio.sleep(3.0)
                elapsed += 3
                await queue.put(f"data: ainda processando... ({elapsed}s)\n\n")

        hb_task = asyncio.create_task(heartbeat()) if queue is not None else None
        try:
            response = await client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                stream=False,
            )
        finally:
            if hb_task is not None:
                hb_task.cancel()
                try:
                    await hb_task
                except (asyncio.CancelledError, Exception):
                    pass

        if queue is not None:
            await queue.put("data: resposta recebida, validando JSON...\n\n")
        content = response["message"]["content"]
        # Use lenient parser so small local models that add extra top-level keys
        # (common with qwen2.5:7b, llama3.2:3b) can still succeed if core shape is right.
        from .schemas import parse_research_json, ResearchResult
        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)
