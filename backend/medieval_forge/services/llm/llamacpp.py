"""LlamaCppProvider — local llama-server via OpenAI-compatible /v1/chat/completions.

Etapa 5 (hazy-hatching-abelson) / quick-260428-fjc.

llama.cpp's `llama-server` exposes an OpenAI-compatible REST API. Unlike
OpenAIProvider (which uses the openai SDK and requires an API key), this
provider talks directly via httpx with no auth and serves whatever model the
local server was launched with (sentinel "(server-default)" — see Etapa 4
model_routing.py). When the resolver returns the sentinel, we omit the `model`
field from the request body.

Pattern mirrors OpenAIProvider's streaming flow but uses httpx + manual SSE parsing
since llama-server is not OpenAI-SDK-compatible at the auth/handshake layer.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from pydantic import BaseModel

from .base import HealthStatus, NoAuth

DEFAULT_BASE_URL = "http://localhost:8080"
SYSTEM_PROMPT = (
    "You are a historical-research assistant. "
    "Return ONLY a JSON object matching the schema. No prose, no markdown."
)


class LlamaCppProvider:
    provider_id = "llamacpp"
    display_name = "Llama.cpp (local)"
    auth_methods = [NoAuth()]
    DEFAULT_BASE_URL = DEFAULT_BASE_URL

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        """GET {base_url}/v1/models — never raise, always return HealthStatus."""
        base_url = (credentials or {}).get("base_url") or DEFAULT_BASE_URL
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{base_url}/v1/models")
                if r.status_code == 200:
                    return HealthStatus(healthy=True, message=f"Reachable at {base_url}")
                return HealthStatus(
                    healthy=False, message=f"HTTP {r.status_code} at {base_url}"
                )
        except asyncio.TimeoutError:
            return HealthStatus(healthy=False, message=f"Unreachable: timeout at {base_url}")
        except Exception as exc:
            return HealthStatus(healthy=False, message=f"Unreachable: {exc}")

    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel:
        """POST {base_url}/v1/chat/completions with stream=True; collect SSE deltas."""
        creds = credentials or {}
        base_url = creds.get("base_url") or DEFAULT_BASE_URL
        model = creds.get("model")  # may be None or "(server-default)"

        body: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": True,
        }
        # Etapa 4: sentinel "(server-default)" means "let llama-server use whatever
        # model it was launched with" — do NOT send `model` in that case.
        if model and model != "(server-default)":
            body["model"] = model

        if queue is not None:
            await queue.put(f"data: Aguardando llama.cpp em {base_url}...\n\n")

        chunks: list[str] = []
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{base_url}/v1/chat/completions", json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:") :].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or [{}]
                    delta = (choices[0].get("delta") or {}).get("content", "")
                    if delta:
                        chunks.append(delta)
                        if queue is not None:
                            await queue.put(f"data: {delta}\n\n")

        content = "".join(chunks)
        # Lenient parser for ResearchResult (matches Ollama pattern); strict for others.
        from .schemas import ResearchResult, parse_research_json

        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)
