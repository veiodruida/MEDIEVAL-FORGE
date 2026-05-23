"""GeminiProvider — Google AI Studio (free tier).

UAT 2026-05-23 — Gemini gives the best free-tier ceiling of the major
cloud labs (60 req/min on flash models, no card required at AI Studio).
We hit the v1beta generative-language REST API directly so we don't
need the heavyweight `google-genai` SDK as a dependency.

API shape differs from OpenAI:
  - POST .../v1beta/models/{model}:streamGenerateContent?key=<API_KEY>
  - SSE-ish: returns a JSON array of `GenerateContentResponse` chunks.
  - Content: `candidates[0].content.parts[0].text`.
  - Auth: `?key=` query string OR `x-goog-api-key` header (we use the header).

Tier note: AI Studio free quota is generous but rate-limited per
minute; paid usage routes through Vertex AI (different endpoint we do
NOT support here — users wanting Vertex should hit OpenRouter instead).
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from .base import ApiKeyAuth, HealthStatus
from .schemas import ResearchResult, parse_research_json

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
SYSTEM_INSTRUCTION = (
    "You are a historical-research assistant. "
    "Return ONLY a JSON object matching the schema. No prose, no markdown."
)
RECOMMENDED_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


class GeminiProviderError(RuntimeError):
    """Raised on missing key, HTTP error, or malformed chunk."""


class GeminiProvider:
    """Google AI Studio Gemini provider — free tier friendly."""

    provider_id = "gemini"
    display_name = "Google Gemini (free tier)"
    auth_methods = [
        ApiKeyAuth(env_var="GOOGLE_API_KEY"),
        ApiKeyAuth(env_var="GEMINI_API_KEY"),
        ApiKeyAuth(env_var=None),
    ]

    @staticmethod
    def _resolve_key(credentials: dict | None) -> str | None:
        if credentials and credentials.get("key"):
            return credentials["key"]
        return (
            os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or None
        )

    @staticmethod
    def _headers(key: str) -> dict[str, str]:
        return {
            "x-goog-api-key": key,
            "Content-Type": "application/json",
        }

    async def health(self, credentials: dict | None = None) -> dict:
        key = self._resolve_key(credentials)
        if not key:
            return {
                "ok": False,
                "message": (
                    "Sem chave de API. Cole sua GOOGLE_API_KEY (AI Studio) em "
                    "Configurações ou importe um .env."
                ),
                "available_models": list(RECOMMENDED_MODELS),
            }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{GEMINI_BASE}/models", headers=self._headers(key)
                )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "message": f"Gemini inalcançável: {exc}",
                "available_models": list(RECOMMENDED_MODELS),
            }
        if resp.status_code in (401, 403):
            return {
                "ok": False,
                "message": f"Chave rejeitada (HTTP {resp.status_code}).",
                "available_models": list(RECOMMENDED_MODELS),
            }
        if resp.status_code != 200:
            return {
                "ok": False,
                "message": f"HTTP {resp.status_code} ao consultar /models",
                "available_models": list(RECOMMENDED_MODELS),
            }
        data = resp.json()
        models = []
        for m in data.get("models", []) or []:
            name = m.get("name", "")
            if not name.startswith("models/"):
                continue
            short = name.removeprefix("models/")
            methods = m.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
            # UAT 2026-05-23 — Google's /models endpoint returns dozens of
            # internal preview / experimental / non-chat models (vision-only,
            # embedding-only, "antigravity-preview-*" research releases) that
            # streamGenerateContent rejects with 429 / 404. Keep only the
            # documented public Gemini families (`gemini-1.5-*` / `gemini-2.*`
            # / `gemini-pro` / `gemini-flash`) so the dropdown matches what
            # the user finds in AI Studio docs.
            if not short.startswith("gemini-"):
                continue
            # Skip preview / experimental qualifiers that frequently 429.
            if any(tag in short for tag in ("antigravity", "preview-tts", "audio")):
                continue
            models.append(short)
        # Stable order: pro families first, then flash, then numeric tail.
        def _rank(m: str) -> tuple[int, str]:
            if "pro" in m:
                return (0, m)
            if "flash" in m:
                return (1, m)
            return (2, m)
        models.sort(key=_rank)
        return {
            "ok": True,
            "message": f"Conectado a Gemini ({len(models)} modelos)",
            "available_models": models or list(RECOMMENDED_MODELS),
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
            raise GeminiProviderError(
                "GeminiProvider sem chave — configure GOOGLE_API_KEY ou cole em Configurações."
            )
        model = (credentials or {}).get("model")
        if not model:
            raise GeminiProviderError("GeminiProvider requer credentials['model'].")

        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 8192,
            },
        }

        if queue is not None:
            await queue.put(
                "data: "
                + json.dumps({"event_type": "started", "message": f"Conectando Gemini ({model})…"})
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
                                "message": f"Gemini processando prompt… ({elapsed:.0f}s)",
                            }
                        )
                        + "\n\n"
                    )

        hb_task: asyncio.Task | None = (
            asyncio.create_task(_heartbeat()) if queue is not None else None
        )

        url = f"{GEMINI_BASE}/models/{model}:streamGenerateContent?alt=sse"
        timeout = httpx.Timeout(connect=15.0, read=60.0, write=60.0, pool=15.0)
        content_parts: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", url, json=body, headers=self._headers(key)
                ) as resp:
                    if resp.status_code in (401, 403):
                        raise GeminiProviderError(
                            f"Gemini recusou a chave (HTTP {resp.status_code})."
                        )
                    if resp.status_code == 429:
                        body_bytes = await resp.aread()
                        raise GeminiProviderError(
                            "Gemini HTTP 429 — quota AI Studio esgotada. "
                            "Aguarde até o reset da janela (~1min para flash, "
                            "~1h para pro) ou troque para outro provider. "
                            f"Upstream: {body_bytes.decode('utf-8','replace')[:200]}"
                        )
                    if resp.status_code >= 400:
                        body_bytes = await resp.aread()
                        raise GeminiProviderError(
                            f"Gemini HTTP {resp.status_code}: "
                            f"{body_bytes.decode('utf-8','replace')[:300]}"
                        )
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if not payload:
                            continue
                        try:
                            obj = json.loads(payload)
                        except json.JSONDecodeError as exc:
                            raise GeminiProviderError(
                                f"Gemini retornou linha SSE malformada: {payload!r}"
                            ) from exc
                        candidates = obj.get("candidates") or []
                        if not candidates:
                            continue
                        cand = candidates[0] or {}
                        cnt = cand.get("content") or {}
                        for part in cnt.get("parts") or []:
                            text = part.get("text", "") or ""
                            if text:
                                if not first_token_arrived:
                                    first_token_arrived = True
                                content_parts.append(text)
                                if queue is not None:
                                    await queue.put(
                                        "data: "
                                        + json.dumps({"event_type": "token", "text": text})
                                        + "\n\n"
                                    )
                        if cand.get("finishReason"):
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
            raise GeminiProviderError("Gemini stream sem conteúdo")

        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)


__all__ = ["GeminiProvider", "GeminiProviderError", "RECOMMENDED_MODELS"]
