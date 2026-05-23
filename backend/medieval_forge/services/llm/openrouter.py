"""OpenRouterProvider — cloud LLM aggregator with free + paid tiers.

UAT 2026-05-23 — user asked for additional cloud providers beyond
Anthropic. OpenRouter is the highest-leverage addition: a single API key
unlocks hundreds of models from every major lab (OpenAI, Anthropic,
Google, Meta, DeepSeek, Mistral, …) AND a "free tier" of throttled
models you can use without paying (suffix `:free`).

API surface mirrors OpenAI:
  - POST https://openrouter.ai/api/v1/chat/completions
  - GET  https://openrouter.ai/api/v1/models

Auth chain (resolved INSIDE the provider, same shape as Claude):
  1. credentials["key"]            — dialog paste OR `.env` import (Plan 01)
  2. OPENROUTER_API_KEY env        — local override / CI
  3. None                          — provider raises RuntimeError

Streaming + heartbeat parity with LlamaCppProvider: forward each
`delta.content` chunk as a `token` SSE envelope, fire `progress`
heartbeats every 2s until the first token lands. Break on
`finish_reason != null` or the `[DONE]` sentinel (whichever lands
first).
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from .base import ApiKeyAuth, HealthStatus
from .schemas import ResearchResult, parse_research_json

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
SYSTEM_PROMPT = (
    "You are a historical-research assistant. "
    "Return ONLY a JSON object matching the schema. No prose, no markdown."
)
# Free models on OpenRouter advertise the `:free` suffix in their slug.
# We ship a short shortlist of strong free models so first-run users get
# a sensible default without browsing the full catalog.
RECOMMENDED_FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-r1:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]


class OpenRouterProviderError(RuntimeError):
    """Raised on malformed SSE data or unauthenticated request."""


class OpenRouterProvider:
    """OpenRouter cloud aggregator — OpenAI-compatible streaming."""

    provider_id = "openrouter"
    display_name = "OpenRouter (free + paid)"
    auth_methods = [
        ApiKeyAuth(env_var="OPENROUTER_API_KEY"),
        ApiKeyAuth(env_var=None),  # dialog paste / .env import → DB
    ]

    @staticmethod
    def _resolve_key(credentials: dict | None) -> str | None:
        if credentials and credentials.get("key"):
            return credentials["key"]
        env = os.getenv("OPENROUTER_API_KEY")
        return env or None

    @staticmethod
    def _headers(key: str) -> dict[str, str]:
        # Referer + Title are optional but encouraged by OpenRouter docs so
        # the model usage shows up under our app in their dashboard. We use
        # generic strings; no PII leaks.
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/medieval-forge",
            "X-Title": "Medieval Forge",
        }

    async def health(self) -> dict:
        """Probe /models with the resolved key — returns Ollama-shape dict.

        When no key is configured we return ok=False but STILL populate
        `available_models` with our shortlist so the UI dropdown stays
        usable; the user then sees the unhealthy badge + actionable
        message ("Configure uma chave OPENROUTER_API_KEY").
        """
        key = self._resolve_key(credentials=None)
        if not key:
            return {
                "ok": False,
                "message": (
                    "Sem chave de API. Cole sua OPENROUTER_API_KEY em "
                    "Configurações ou importe um .env."
                ),
                "available_models": list(RECOMMENDED_FREE_MODELS),
            }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{OPENROUTER_BASE}/models", headers=self._headers(key)
                )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "message": f"OpenRouter inalcançável: {exc}",
                "available_models": list(RECOMMENDED_FREE_MODELS),
            }
        if resp.status_code == 401:
            return {
                "ok": False,
                "message": "Chave inválida (HTTP 401). Verifique sua OPENROUTER_API_KEY.",
                "available_models": list(RECOMMENDED_FREE_MODELS),
            }
        if resp.status_code != 200:
            return {
                "ok": False,
                "message": f"HTTP {resp.status_code} ao consultar /models",
                "available_models": list(RECOMMENDED_FREE_MODELS),
            }
        try:
            data = resp.json()
        except ValueError:
            return {
                "ok": False,
                "message": "OpenRouter retornou body não-JSON",
                "available_models": list(RECOMMENDED_FREE_MODELS),
            }
        models = []
        for m in data.get("data", []) or []:
            mid = m.get("id")
            if isinstance(mid, str):
                models.append(mid)
        # Surface free models first (UI badges them); keep deterministic.
        models.sort(key=lambda m: (":free" not in m, m))
        return {
            "ok": True,
            "message": f"Conectado a OpenRouter ({len(models)} modelos)",
            "available_models": models,
        }

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        result = await self.health()
        return HealthStatus(
            healthy=result["ok"],
            message=result["message"],
            available_models=result.get("available_models"),
        )

    async def research(
        self,
        prompt: str,
        schema: Any,
        credentials: dict | None,
        queue: asyncio.Queue,
    ) -> Any:
        """Stream OpenAI-compatible chat completion through OpenRouter."""
        key = self._resolve_key(credentials)
        if not key:
            raise OpenRouterProviderError(
                "OpenRouterProvider sem chave — configure OPENROUTER_API_KEY "
                "ou cole a chave em Configurações."
            )
        model = (credentials or {}).get("model")
        if not model:
            raise OpenRouterProviderError(
                "OpenRouterProvider requer credentials['model']."
            )

        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": True,
            "max_tokens": 24576,
        }

        if queue is not None:
            await queue.put(
                "data: "
                + json.dumps(
                    {
                        "event_type": "started",
                        "message": f"Conectando OpenRouter ({model})…",
                    }
                )
                + "\n\n"
            )

        loop = asyncio.get_event_loop()
        start_t = loop.time()
        first_token_arrived = False

        async def _heartbeat() -> None:
            while not first_token_arrived:
                await asyncio.sleep(2.0)
                if first_token_arrived:
                    return
                elapsed = loop.time() - start_t
                if queue is not None:
                    await queue.put(
                        "data: "
                        + json.dumps(
                            {
                                "event_type": "progress",
                                "message": f"OpenRouter processando prompt… ({elapsed:.0f}s)",
                            }
                        )
                        + "\n\n"
                    )

        hb_task: asyncio.Task | None = (
            asyncio.create_task(_heartbeat()) if queue is not None else None
        )

        timeout = httpx.Timeout(connect=15.0, read=60.0, write=60.0, pool=15.0)
        content_parts: list[str] = []
        finished = False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{OPENROUTER_BASE}/chat/completions",
                    json=body,
                    headers=self._headers(key),
                ) as resp:
                    if resp.status_code == 401:
                        raise OpenRouterProviderError(
                            "OpenRouter recusou a chave (HTTP 401). Atualize a credencial."
                        )
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if not payload:
                            continue
                        if payload == "[DONE]":
                            finished = True
                            break
                        try:
                            obj = json.loads(payload)
                        except json.JSONDecodeError as exc:
                            raise OpenRouterProviderError(
                                f"OpenRouter retornou linha SSE malformada: {payload!r}"
                            ) from exc
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        first = choices[0] or {}
                        delta = (first.get("delta") or {}).get("content", "") or ""
                        if delta:
                            if not first_token_arrived:
                                first_token_arrived = True
                            content_parts.append(delta)
                            if queue is not None:
                                await queue.put(
                                    "data: "
                                    + json.dumps(
                                        {"event_type": "token", "text": delta}
                                    )
                                    + "\n\n"
                                )
                        if first.get("finish_reason"):
                            finished = True
                            break
        finally:
            first_token_arrived = True
            if hb_task is not None:
                hb_task.cancel()
                try:
                    await hb_task
                except (asyncio.CancelledError, Exception):
                    pass

        content = "".join(content_parts)
        if not content:
            raise OpenRouterProviderError(
                "OpenRouter stream sem conteúdo"
                + (" (no finish_reason)" if not finished else "")
            )

        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)


__all__ = ["OpenRouterProvider", "OpenRouterProviderError", "RECOMMENDED_FREE_MODELS"]
