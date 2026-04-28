"""Codex orchestration runner (Etapa 9 — quick-260428-l0l).

run_codex: producer task that orchestrates the Codex narrative pipeline:
  load project → build prompt → cache lookup → run_with_retry → cache result

Mirrors research_runner.run_research's queue-producer + sentinel-finally semantics
(Pitfall 6). Emits SSE-format strings to asyncio.Queue[str | None] and ALWAYS
terminates with None.

Differences from run_research:
  - Uses CodexResult schema (12 categories, no cross-ref validation in Etapa 9).
  - Uses build_codex_prompt with optional focus_sections.
  - Caches into codex_cache table (separate from research_cache).
  - Default task_type="codex_genealogy" routes to the high-effort model tier.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..database import AsyncSessionLocal
from ..models import Project
from .codex_cache import compute_codex_cache_key, get_codex_cached, set_codex_cached
from .llm import PROVIDERS, ResearchValidationError, run_with_retry
from .llm.auth import resolve_credentials
from .llm.model_routing import resolve_model
from .llm.prompt import build_codex_prompt
from .llm.schemas import CodexResult
from .research_runner import PROVIDER_DEFAULT_MODEL

logger = logging.getLogger(__name__)


async def run_codex(
    project_id: str,
    provider_id: str,
    queue: asyncio.Queue[str | None],
    *,
    force_refresh: bool = False,
    focus_sections: list[str] | None = None,
    db_session_factory: async_sessionmaker | None = None,
    app_state: Any = None,
    task_type: str | None = "codex_genealogy",
    effort_override: str | None = None,
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning (Pitfall 6).

    Orchestrates:
      1. Validate provider
      2. Resolve model (via model_routing when task_type given, else PROVIDER_DEFAULT_MODEL)
      3. Load project metadata from DB
      4. Compute codex cache key; check cache (unless force_refresh)
      5. Resolve credentials
      6. Build prompt + run_with_retry against CodexResult
      7. Cache result
      8. Emit RESULT + DONE to queue
    """
    factory = db_session_factory or AsyncSessionLocal
    try:
        # --- 1. Validate provider ---
        if provider_id not in PROVIDERS:
            await queue.put(f"data: ERROR: unknown provider {provider_id}\n\n")
            return
        provider = PROVIDERS[provider_id]

        # --- 2. Resolve model ---
        if task_type is not None:
            try:
                model = resolve_model(provider_id, task_type, effort_override)
            except ValueError as e:
                await queue.put(f"data: ERROR: {e}\n\n")
                return
        else:
            model = PROVIDER_DEFAULT_MODEL.get(provider_id, provider_id)
        # Ollama: allow user-selected local model override.
        if provider_id == "ollama" and app_state is not None:
            session_ollama = (getattr(app_state, "credentials", {}) or {}).get("ollama") or {}
            if session_ollama.get("model"):
                model = session_ollama["model"]

        # --- 3. Load project from DB ---
        async with factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                await queue.put("data: ERROR: project not found\n\n")
                return
            country_qid = project.country_qid
            period_start = project.period_start
            period_end = project.period_end
            country_name = project.name

        # --- 4. Cache lookup ---
        cache_key = compute_codex_cache_key(
            country_qid, period_start, period_end, provider_id, model, focus_sections,
        )

        if not force_refresh:
            async with factory() as session:
                cached = await get_codex_cached(session, cache_key)
            if cached is not None:
                await queue.put("data: cached\n\n")
                await queue.put(f"data: RESULT: {json.dumps(cached)}\n\n")
                await queue.put("data: DONE\n\n")
                return

        # --- 5. Resolve credentials ---
        credentials = resolve_credentials(provider_id, app_state)
        if provider_id != "ollama" and not credentials:
            await queue.put(f"data: ERROR: no credentials for {provider_id}\n\n")
            return

        # --- 6. Build prompt + run with retry ---
        map_summary = f"{country_name} ({period_start}-{period_end} AD)"
        prompt = build_codex_prompt(
            country_name, period_start, period_end, map_summary,
            focus_sections=focus_sections,
        )

        await queue.put(f"data: starting {provider_id} ({model})\n\n")

        try:
            result = await run_with_retry(
                provider, prompt, CodexResult, credentials, queue, max_retries=3,
            )
        except ResearchValidationError as e:
            msg = e.last_error[:600].replace("\n", " ")
            await queue.put(f"data: ERROR: validação falhou após 3 tentativas — {msg}\n\n")
            return

        # --- 7. Cache the result ---
        payload = result.model_dump()
        async with factory() as session:
            await set_codex_cached(
                session, cache_key, payload, provider_id, model,
                country_qid, period_start, period_end,
                focus_sections=focus_sections,
            )

        # --- 8. Emit RESULT + DONE ---
        await queue.put(f"data: RESULT: {json.dumps(payload)}\n\n")
        await queue.put("data: DONE\n\n")

    except Exception as e:
        logger.exception("run_codex failed")
        await queue.put(f"data: ERROR: {type(e).__name__}: {str(e)[:200]}\n\n")
    finally:
        # Pitfall 6: sentinel ALWAYS emitted so SSE consumer exits cleanly.
        await queue.put(None)
