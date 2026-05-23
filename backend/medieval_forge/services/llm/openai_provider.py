"""OpenAIProvider — direct OpenAI Chat Completions for users with own keys.

UAT 2026-05-23 — added alongside OpenRouter so users with a direct
OpenAI API key (no aggregator) can still use the research flow. Same
streaming + heartbeat shape as `OpenRouterProvider`; the only delta is
the base URL and the credential env var.

Free tier: OpenAI does NOT offer a permanent free tier (trial credits
only). Users who want a no-cost cloud option should use OpenRouter
(`*:free` models) or Gemini (AI Studio free quota).
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from .base import ApiKeyAuth, HealthStatus
from .schemas import ResearchResult, parse_research_json

OPENAI_BASE = "https://api.openai.com/v1"
SYSTEM_PROMPT = (
    "You are a historical-research assistant. "
    "Return ONLY a JSON object matching the schema. No prose, no markdown."
)
RECOMMENDED_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]


class OpenAIProviderError(RuntimeError):
    """Raised on missing key or malformed SSE response."""


class OpenAIProvider:
    """Direct OpenAI Chat Completions provider."""

    provider_id = "openai"
    display_name = "OpenAI (paid)"
    auth_methods = [
        ApiKeyAuth(env_var="OPENAI_API_KEY"),
        ApiKeyAuth(env_var=None),
    ]

    @staticmethod
    def _resolve_key(credentials: dict | None) -> str | None:
        if credentials and credentials.get("key"):
            return credentials["key"]
        return os.getenv("OPENAI_API_KEY") or None

    @staticmethod
    def _headers(key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async def health(self) -> dict:
        key = self._resolve_key(credentials=None)
        if not key:
            return {
                "ok": False,
                "message": (
                    "Sem chave de API. Cole sua OPENAI_API_KEY em "
                    "Configurações ou importe um .env."
                ),
                "available_models": list(RECOMMENDED_MODELS),
            }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{OPENAI_BASE}/models", headers=self._headers(key)
                )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "message": f"OpenAI inalcançável: {exc}",
                "available_models": list(RECOMMENDED_MODELS),
            }
        if resp.status_code == 401:
            return {
                "ok": False,
                "message": "Chave inválida (HTTP 401). Verifique sua OPENAI_API_KEY.",
                "available_models": list(RECOMMENDED_MODELS),
            }
        if resp.status_code != 200:
            return {
                "ok": False,
                "message": f"HTTP {resp.status_code} ao consultar /models",
                "available_models": list(RECOMMENDED_MODELS),
            }
        data = resp.json()
        models = sorted(
            m.get("id", "") for m in (data.get("data") or []) if m.get("id")
        )
        # Prefer chat-completion models; the /models endpoint returns
        # everything (whisper, embeddings, etc.) which would clutter the UI.
        chat_models = [m for m in models if any(p in m for p in ("gpt-", "o1-", "o3-"))]
        return {
            "ok": True,
            "message": f"Conectado a OpenAI ({len(chat_models)} modelos)",
            "available_models": chat_models or models,
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
        key = self._resolve_key(credentials)
        if not key:
            raise OpenAIProviderError(
                "OpenAIProvider sem chave — configure OPENAI_API_KEY ou cole em Configurações."
            )
        model = (credentials or {}).get("model")
        if not model:
            raise OpenAIProviderError("OpenAIProvider requer credentials['model'].")

        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": True,
            "max_tokens": 16384,
        }

        if queue is not None:
            await queue.put(
                "data: "
                + json.dumps({"event_type": "started", "message": f"Conectando OpenAI ({model})…"})
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
                                "message": f"OpenAI processando prompt… ({elapsed:.0f}s)",
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
                    f"{OPENAI_BASE}/chat/completions",
                    json=body,
                    headers=self._headers(key),
                ) as resp:
                    if resp.status_code == 401:
                        raise OpenAIProviderError(
                            "OpenAI recusou a chave (HTTP 401). Atualize a credencial."
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
                            raise OpenAIProviderError(
                                f"OpenAI retornou linha SSE malformada: {payload!r}"
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
                                    + json.dumps({"event_type": "token", "text": delta})
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
            raise OpenAIProviderError(
                "OpenAI stream sem conteúdo"
                + (" (no finish_reason)" if not finished else "")
            )

        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)


__all__ = ["OpenAIProvider", "OpenAIProviderError", "RECOMMENDED_MODELS"]
