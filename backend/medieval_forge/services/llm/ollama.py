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
        """Stream chat completion with format=schema JSON enforcement.

        UAT 2026-05-22 — switched from a single blocking `chat(stream=False)`
        to `stream=True`. The user reported "Quero ver o output do modelo bem
        como o seu processamento". Each delta chunk is forwarded to the SSE
        queue as a `token` envelope so the dialog can render the model's
        output as it streams. The full content is reassembled and validated
        against the schema once `done=True` arrives.

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

        content_parts: list[str] = []
        loop = asyncio.get_event_loop()
        start_t = loop.time()
        hb_task: asyncio.Task | None = None
        first_token_arrived = False

        async def _heartbeat() -> None:
            # Fire one heartbeat right away so the dialog leaves the
            # "(aguardando primeiro token…)" placeholder within the first
            # frame — without this the first signal arrives 2s later and
            # users on slow models thought the request was stuck.
            if queue is not None:
                await queue.put(
                    "data: "
                    + json.dumps(
                        {
                            "event_type": "progress",
                            "message": "Conectando a Ollama…",
                        }
                    )
                    + "\n\n"
                )
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
                                "message": f"Ollama carregando modelo / processando prompt… ({elapsed:.0f}s)",
                            }
                        )
                        + "\n\n"
                    )

        if queue is not None:
            hb_task = asyncio.create_task(_heartbeat())

        # UAT 2026-05-23 (round 3) — user reported Ollama "ficou parado".
        # Forcing num_ctx=32768 + num_gpu=999 with a 7B model + 8GB VRAM
        # blows the KV cache (~8GB at 32k ctx) and the daemon either
        # crashes silently (Ollama Desktop swallows the stderr) or hangs
        # waiting for memory the OS can't deliver. Drop the aggressive
        # overrides — let Ollama use the model's modelfile defaults and
        # auto-pick GPU layers based on free VRAM. We KEEP `num_predict`
        # because output truncation is the only setting the server can't
        # reasonably auto-tune (model authors don't ship a sensible
        # default for our 15-25k JSON output).
        try:
            async for chunk in await client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format=schema.model_json_schema(),
                stream=True,
                options={"num_predict": 24576},
            ):
                msg = chunk.get("message") if isinstance(chunk, dict) else None
                delta = ""
                if isinstance(msg, dict):
                    delta = msg.get("content", "") or ""
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
                if isinstance(chunk, dict) and chunk.get("done"):
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
        # Lenient parser (literal-port schemas.parse_research_json) handles
        # small-model tendency to add extra top-level keys.
        from .schemas import ResearchResult, parse_research_json

        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)
