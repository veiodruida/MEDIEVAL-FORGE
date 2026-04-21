"""Research orchestration runner (RESEARCH-04, RESEARCH-05, D-05..D-09, D-20, D-22..D-26).

run_research: producer task that orchestrates the full pipeline:
  load condados → build prompt → cache lookup → run_with_retry → validate ids → cache result

Emits SSE-format strings to asyncio.Queue[str | None]. Terminates with None sentinel.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..database import AsyncSessionLocal
from ..models import Project
from .llm import PROVIDERS, ResearchResult, run_with_retry, ResearchValidationError
from .llm.auth import resolve_credentials
from .llm.prompt import build_research_prompt
from .paths import project_dir
from .research_cache import compute_cache_key, get_cached, set_cached

logger = logging.getLogger(__name__)

# Provider → default model used in cache key (D-23).
PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "ollama": "qwen2.5:7b",
}


def _load_condados(project_path: Path) -> list[dict]:
    """Load condados from territories.geojson in the project's generated/ directory.

    Returns a list of dicts with id/name/lon/lat suitable for the prompt builder.
    """
    gj_path = project_path / "generated" / "territories.geojson"
    if not gj_path.exists():
        raise FileNotFoundError(f"territories.geojson not found at {gj_path}")
    data = json.loads(gj_path.read_text(encoding="utf-8"))
    condados: list[dict] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        cid = props.get("id") or props.get("osm_id")
        name = props.get("name", "")
        # Centroid: prefer explicit centroid prop; fall back to ring average.
        geom = feat.get("geometry", {})
        cx, cy = 0.0, 0.0
        if props.get("centroid"):
            cx, cy = props["centroid"]
        elif geom.get("type") == "Polygon" and geom.get("coordinates"):
            ring = geom["coordinates"][0]
            if ring:
                cx = sum(p[0] for p in ring) / len(ring)
                cy = sum(p[1] for p in ring) / len(ring)
        condados.append({"id": str(cid), "name": name, "lon": cx, "lat": cy})
    return condados


def validate_assignment_against_condados(
    result: ResearchResult,
    known_ids: set[str],
) -> None:
    """Raise ValueError if any condado_id in result is not in known_ids.

    D-09: Unknown condado_id from LLM is treated as validation error → retry loop re-prompts.
    Only validates referenced ids — partial assignment (LLM skips some condados) is allowed.
    """
    for assignment in result.condados_assignment:
        if assignment.condado_id not in known_ids:
            raise ValueError(
                f"LLM returned unknown condado_id: {assignment.condado_id!r} "
                f"(not in project's territory list)"
            )


async def run_research(
    project_id: str,
    provider_id: str,
    queue: asyncio.Queue[str | None],
    force_refresh: bool = False,
    db_session_factory: async_sessionmaker | None = None,
    app_state: Any = None,
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning (Pitfall 6).

    Orchestrates:
      1. Validate provider
      2. Load project metadata from DB
      3. Compute cache key; check cache (unless force_refresh)
      4. Load condados from territories.geojson
      5. Resolve credentials
      6. Build prompt + run_with_retry + validate condado ids
      7. Cache result
      8. Emit RESULT + DONE to queue
    """
    factory = db_session_factory or AsyncSessionLocal
    try:
        # Validate provider
        if provider_id not in PROVIDERS:
            await queue.put(f"data: ERROR: unknown provider {provider_id}\n\n")
            return
        provider = PROVIDERS[provider_id]
        model = PROVIDER_DEFAULT_MODEL.get(provider_id, provider_id)
        # Ollama: let the user override the model via app.state.credentials["ollama"]["model"]
        if provider_id == "ollama" and app_state is not None:
            session_ollama = (getattr(app_state, "credentials", {}) or {}).get("ollama") or {}
            if session_ollama.get("model"):
                model = session_ollama["model"]

        # Load project from DB
        async with factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                await queue.put("data: ERROR: project not found\n\n")
                return
            country_qid = project.country_qid
            period_start = project.period_start
            period_end = project.period_end
            country_name = project.name

        # Cache lookup
        cache_key = compute_cache_key(country_qid, period_start, period_end, provider_id, model)

        if not force_refresh:
            async with factory() as session:
                cached = await get_cached(session, cache_key)
            if cached is not None:
                await queue.put("data: cached\n\n")
                await queue.put(f"data: RESULT: {json.dumps(cached)}\n\n")
                await queue.put("data: DONE\n\n")
                return

        # Load condados from disk
        project_path = project_dir(project_id)
        condados = _load_condados(project_path)
        known_ids = {c["id"] for c in condados}
        prompt = build_research_prompt(country_name, period_start, period_end, condados)

        # Resolve credentials
        credentials = resolve_credentials(provider_id, app_state)
        if provider_id != "ollama" and not credentials:
            await queue.put(f"data: ERROR: no credentials for {provider_id}\n\n")
            return

        await queue.put(f"data: starting {provider_id} ({model})\n\n")

        # Wrap provider.research with condado-id validation so retry loop re-prompts
        # on unknown ids (D-09, T-3-08).
        class _ValidatingWrapper:
            """Thin wrapper that adds condado-id validation after each research call."""
            provider_id = provider.provider_id
            display_name = provider.display_name
            auth_methods = provider.auth_methods

            async def health_check(self, creds: dict | None):
                return await provider.health_check(creds)

            async def research(
                self, p: str, s: type, c: dict | None, q: asyncio.Queue | None
            ) -> ResearchResult:
                result = await provider.research(p, s, c, q)
                validate_assignment_against_condados(result, known_ids)
                return result

        try:
            result: ResearchResult = await run_with_retry(
                _ValidatingWrapper(), prompt, ResearchResult, credentials, queue, max_retries=3
            )
        except ResearchValidationError as e:
            # T-3-12: truncate error message to 200 chars; full trace goes to stderr only.
            await queue.put(f"data: ERROR: {e.last_error[:200]}\n\n")
            return

        # Cache the successful result
        payload = result.model_dump()
        async with factory() as session:
            await set_cached(
                session, cache_key, payload, provider_id, model,
                country_qid, period_start, period_end,
            )

        await queue.put(f"data: RESULT: {json.dumps(payload)}\n\n")
        await queue.put("data: DONE\n\n")

    except Exception as e:
        logger.exception("run_research failed")
        # T-3-12: truncate to 200 chars; credential fragments never leaked via SSE.
        await queue.put(f"data: ERROR: {type(e).__name__}: {str(e)[:200]}\n\n")
    finally:
        # Pitfall 6: sentinel ALWAYS emitted so SSE consumer exits cleanly.
        await queue.put(None)
