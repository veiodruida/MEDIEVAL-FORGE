"""Llama.cpp local provider (Phase 07.1, D-V3-04 rewrite under v3 patterns).

Template source: 87f8aab~1:backend/medieval_forge/services/llm/llamacpp.py (read-only
reference). Three v3 deviations applied per RESEARCH §Pattern 2:

1. base_url sourced from llamacpp_launcher.status() — not hardcoded DEFAULT_BASE_URL.
   The launcher owns the live server's auto-picked port; provider just calls.
   (review-fix #8: STRICT — no production localhost:8080 fallback)
2. health() returns Ollama-shape dict {ok, message, available_models} so the
   existing api/v3/research.py:/providers builder surfaces gguf listings.
   health_check(credentials) returns HealthStatus (Protocol compliance).
3. Drop v1 `model == "(server-default)"` sentinel logic — D-08 always passes an
   explicit model; the sentinel is dead code.

Threat model: subprocess.Popen spawning is the launcher's responsibility; this
provider only consumes the resulting base_url and streams research requests via
httpx. No untrusted input reaches a shell.

T-07.1-03-01 (SSRF): base_url sourced exclusively from llamacpp_launcher.status()
  (server-controlled, auto-picked port). v1's credentials["base_url"] user-supplied
  path is DROPPED on port per RESEARCH §Security.
T-07.1-03-02 (malformed JSON): raises LlamaCppProviderError on malformed SSE data:
  lines — no silent swallow.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from .base import HealthStatus, NoAuth
from .llamacpp_launcher import _resolve_binary, list_models, status
from .schemas import ResearchResult, parse_research_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a historical-research assistant. "
    "Return ONLY a JSON object matching the schema. No prose, no markdown."
)

# review-fix #8: NO module-level DEFAULT_BASE_URL constant.
# base_url is derived from launcher.status() at request time; idle launcher
# raises LlamaCppProviderError. Tests bypass via the `_test_only_base_url`
# instance attribute set by monkeypatch fixtures (never read from user input).


class LlamaCppProviderError(RuntimeError):
    """Raised when LlamaCppProvider cannot serve a request — e.g. no launcher
    state or malformed SSE payload. Distinct from launcher-level exceptions
    (LlamacppBinaryMissing etc.) so the router (plan 07.1-05) can map cleanly
    to HTTP 503/409/400.
    """


class LlamaCppProvider:
    """Llama.cpp local server provider — OpenAI-compatible API via httpx.

    Deviation #1: base_url from launcher.status() (review-fix #8 STRICT).
    Deviation #2: health() Ollama-shape dict {ok, message, available_models}.
    Deviation #3: no '(server-default)' sentinel — D-08 always passes explicit model.
    """

    provider_id = "llamacpp"
    display_name = "Llama.cpp (local)"
    auth_methods = [NoAuth()]

    async def health(self) -> dict:
        """Deviation #2: Ollama-shape dict {ok, message, available_models}.

        Probes /v1/models on the live server when launcher reports alive.
        Returns ok=False with PT-BR diagnostic message when binary missing
        or launcher idle. available_models is ALWAYS populated from the
        filesystem (D-07a list_models()) so the UI dropdown stays
        discoverable even when the server is not yet running.
        """
        available = list_models()
        binary = _resolve_binary()
        if binary is None:
            return {
                "ok": False,
                "message": "llama-server não encontrado no PATH (defina LLAMA_SERVER_BIN)",
                "available_models": available,
            }
        running = status()
        if running is None:
            return {
                "ok": False,
                "message": "Servidor llama-server não está ativo. Use 'Levantar servidor'.",
                "available_models": available,
            }
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{running['base_url']}/v1/models")
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "message": f"Unreachable: {exc}",
                "available_models": available,
            }
        ok = resp.status_code == 200
        return {
            "ok": ok,
            "message": (
                f"Reachable at {running['base_url']}"
                if ok
                else f"HTTP {resp.status_code}"
            ),
            "available_models": available,
        }

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        """Protocol-conforming wrapper around health().

        Uses HealthStatus.available_models (D-09 field added in plan 07.1-01).
        """
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
        """Stream OpenAI-compatible chat completion to queue.

        Deviation #1 (review-fix #8 — STRICT): base_url comes EXCLUSIVELY from
        launcher.status() when a live PID exists. If launcher is idle, raise
        LlamaCppProviderError — DO NOT silently target http://localhost:8080
        (SSRF / local-confusion hardening).

        The provider instance accepts an optional test-only `_test_only_base_url`
        attribute honored ONLY when explicitly set by pytest fixtures via monkeypatch;
        production callers leave it unset and the launcher state is canonical.

        Deviation #3: model must be provided in credentials['model'];
        v1's '(server-default)' sentinel is dropped.

        review-fix #7: streaming aggregator buffers across chunk boundaries.
        Malformed JSON in a data: line raises LlamaCppProviderError (typed).
        """
        # review-fix #8: test-only override path — only honored when explicitly
        # set by a test fixture (see test_llamacpp_provider.py monkeypatch sites).
        base_url = getattr(self, "_test_only_base_url", None)
        if base_url is None:
            running = status()
            if running is None:
                raise LlamaCppProviderError(
                    "no llama-server alive - call POST /llamacpp/launch first"
                )
            base_url = running["base_url"]

        model = (credentials or {}).get("model")
        if not model:
            raise ValueError(
                "LlamaCppProvider.research requires credentials['model'] — "
                "Deviation #3: '(server-default)' sentinel is dropped, D-08 "
                "always passes an explicit model."
            )

        body: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": True,
            "model": model,
        }

        if queue is not None:
            await queue.put(
                "data: "
                + json.dumps(
                    {
                        "event_type": "started",
                        "message": f"Aguardando llama.cpp em {base_url}...",
                    }
                )
                + "\n\n"
            )

        chunks: list[str] = []

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{base_url}/v1/chat/completions", json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError as exc:
                        # review-fix #7: typed error — no silent swallow
                        raise LlamaCppProviderError(
                            f"Malformed SSE JSON from llama-server: {payload!r}"
                        ) from exc
                    choices = obj.get("choices") or [{}]
                    delta = (choices[0].get("delta") or {}).get("content", "")
                    if delta:
                        chunks.append(delta)
                        if queue is not None:
                            await queue.put(f"data: {delta}\n\n")

        content = "".join(chunks)

        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)
