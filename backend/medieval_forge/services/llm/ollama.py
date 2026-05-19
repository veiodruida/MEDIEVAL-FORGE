"""OllamaProvider — AsyncClient + format=schema + D-13 defaults (Plan 07-04 Task 2).

Source: 07-RESEARCH.md §Pattern 4 (full code block) + REVIEWS fix #5 (2026-05-14).

D-13: qwen2.5:7b PREFERRED; ordered fallback per REVIEWS fix #5:
    MODEL_PREFERENCE_ORDER = [
        "qwen2.5:7b",
        "qwen2.5-coder:14b",
        "gemma4:26b",
        "deepseek-r1:14b",
    ]

The provider itself does NOT auto-select — selection logic lives in the frontend
ProviderSelector (Plan 09a) reading the `available_models` field returned by
`health()`. The provider accepts whatever model string the runner passes.

REVIEWS fix #5: `health()` returns `{ok, message, available_models: list[str]}`
so the `/providers` endpoint (Plan 07b) can surface installed models. Uses
`httpx.AsyncClient.get("/api/tags")` with a 3s `asyncio.wait_for` timeout
(Pitfall 5 + RESEARCH §Pattern 4).
"""
from __future__ import annotations

import asyncio
import json
import shutil

import httpx
from ollama import AsyncClient

from .base import HealthStatus, NoAuth

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"
FALLBACK_MODEL = "llama3.1:8b"

# REVIEWS fix #5 — ordered preference list (frontend-side; documented here for
# reference). When no preference matches, fall back to the first available
# model. When the preferred model is missing the UI surfaces a hint
# (`Modelo preferido qwen2.5:7b não encontrado — execute "ollama pull qwen2.5:7b"`).
MODEL_PREFERENCE_ORDER = [
    "qwen2.5:7b",
    "qwen2.5-coder:14b",
    "gemma4:26b",
    "deepseek-r1:14b",
]


class OllamaProvider:
    """Ollama provider — local model, format=schema JSON enforcement."""

    provider_id = "ollama"
    display_name = "Ollama (local)"
    auth_methods = [NoAuth()]

    async def health(self) -> dict:
        """Return health + available models via /api/tags.

        REVIEWS fix #5: surface available_models so the frontend ProviderSelector
        can pick a sensible default from the ordered preference list. No credential
        payload (Ollama needs none).

        T-07-04-06 mitigation: `asyncio.wait_for(..., timeout=3.0)` bounds the
        health-check; client `timeout=3.0` is a belt-and-suspenders defense.
        """
        try:
            async with httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=3.0) as client:
                resp = await asyncio.wait_for(client.get("/api/tags"), timeout=3.0)
                resp.raise_for_status()
                data = resp.json()
                models = [
                    m.get("name", "")
                    for m in data.get("models", [])
                    if m.get("name")
                ]
                return {
                    "ok": True,
                    "message": "Ollama reachable",
                    "available_models": models,
                }
        except asyncio.TimeoutError:
            return {
                "ok": False,
                "message": "Ollama unreachable (timeout after 3s)",
                "available_models": [],
            }
        except Exception:  # noqa: BLE001
            binary = shutil.which("ollama")
            if binary is None:
                msg = "Ollama não encontrado no PATH. Instale em https://ollama.com"
            else:
                msg = "Ollama instalado mas não está em execução. Abra o Ollama e aguarde."
            return {
                "ok": False,
                "message": msg,
                "available_models": [],
            }

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        """Protocol-conforming wrapper around health() returning HealthStatus.

        Plan 07b runner consumes `health()` directly (for available_models);
        Protocol consumers (LLMProvider) keep using `health_check`.
        """
        result = await self.health()
        return HealthStatus(healthy=result["ok"], message=result["message"])

    async def research(self, prompt, schema, credentials, queue):
        """Single-shot chat with format=schema JSON enforcement.

        The provider does NOT auto-fallback to a different model — the UI picks
        based on `available_models` (REVIEWS fix #5). Provider accepts whatever
        model string the runner passes via `credentials["model"]`.
        """
        client = AsyncClient(host=OLLAMA_HOST)
        model = (credentials or {}).get("model") or DEFAULT_MODEL
        if queue is not None:
            await queue.put(
                "data: "
                + json.dumps(
                    {
                        "event_type": "started",
                        "message": f"Aguardando Ollama ({model})...",
                    }
                )
                + "\n\n"
            )

        # Heartbeat task — blocking call may take 30-120s on local hw.
        async def heartbeat() -> None:
            elapsed = 0
            while queue is not None:
                await asyncio.sleep(3.0)
                elapsed += 3
                await queue.put(
                    "data: "
                    + json.dumps({"event_type": "heartbeat", "elapsed_s": elapsed})
                    + "\n\n"
                )

        hb_task = asyncio.create_task(heartbeat()) if queue is not None else None
        try:
            response = await client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format=schema.model_json_schema(),
                stream=False,
            )
        finally:
            if hb_task is not None:
                hb_task.cancel()
                try:
                    await hb_task
                except (asyncio.CancelledError, Exception):
                    pass

        content = response["message"]["content"]
        # Lenient parser (literal-port schemas.parse_research_json) handles
        # small-model tendency to add extra top-level keys.
        from .schemas import ResearchResult, parse_research_json

        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)
