"""Research orchestration runner (RESEARCH-04, RESEARCH-05, D-05..D-09, D-20, D-22..D-26).

run_research: producer task that orchestrates the full pipeline:
  load project → build prompt → cache lookup → run_with_retry → validate → cache result

Emits SSE-format strings to asyncio.Queue[str | None]. Terminates with None sentinel.

Architecture note: the LLM GENERATES condados (counties) freely from scratch at the
START of the historical period. No pre-supplied OSM condado list is needed for research.
OSM ingest is only used for the modern_map.png preview layer.
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
from .llm.model_routing import resolve_model
from .llm.prompt import build_research_prompt
from .research_cache import compute_cache_key, get_cached, set_cached

logger = logging.getLogger(__name__)

# Provider → default model used in cache key (D-23).
PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "ollama": "qwen2.5:7b",
}


def load_condados(project_path: Path) -> list[dict]:
    """Load condados from the project's geographic data.

    Source priority:
      1. ``raw/municipalities.geojson`` — OSM ingest output.
         Each polygon becomes one condado, ID = ``C_{osm_id}``.
      2. ``generated/territories.geojson`` — fallback for legacy projects.

    Note: this utility is kept for debugging/tooling but is NO LONGER called
    by the main research pipeline. The LLM now generates condados freely.
    It is still used by territory_builder as a last-resort fallback.

    Returns a list of dicts with id/name/lon/lat.
    Raises FileNotFoundError if neither geojson source is available.
    """
    raw_path = project_path / "raw" / "municipalities.geojson"
    territories_path = project_path / "generated" / "territories.geojson"

    if raw_path.exists():
        return _condados_from_municipalities(raw_path)
    if territories_path.exists():
        return _condados_from_territories(territories_path)
    raise FileNotFoundError(
        f"Neither {raw_path} nor {territories_path} exists — run OSM ingest first."
    )


def _polygon_centroid(geom: dict) -> tuple[float, float]:
    """Compute centroid (lon, lat) of a Polygon or MultiPolygon GeoJSON geometry."""
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon" and coords:
        ring = coords[0]
        if ring:
            return (
                sum(p[0] for p in ring) / len(ring),
                sum(p[1] for p in ring) / len(ring),
            )
    elif gtype == "MultiPolygon" and coords:
        biggest = max(coords, key=lambda poly: len(poly[0]) if poly and poly[0] else 0)
        ring = biggest[0] if biggest else []
        if ring:
            return (
                sum(p[0] for p in ring) / len(ring),
                sum(p[1] for p in ring) / len(ring),
            )
    return 0.0, 0.0


def _condados_from_municipalities(path: Path) -> list[dict]:
    """Convert raw OSM municipalities into condados (one per polygon feature)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    condados: list[dict] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        props = feat.get("properties", {}) or {}
        osm_id = props.get("osm_id")
        name = props.get("name") or f"OSM {osm_id}"
        cid = f"C_{osm_id}" if osm_id is not None else f"C_{len(condados)}"
        cx, cy = _polygon_centroid(geom)
        condados.append({"id": cid, "name": name, "lon": cx, "lat": cy})
    return condados


def _condados_from_territories(path: Path) -> list[dict]:
    """Fallback: read condados from generator output (post-Voronoi territories.geojson)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    condados: list[dict] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        cid = props.get("id") or props.get("osm_id")
        name = props.get("name", "")
        geom = feat.get("geometry", {})
        cx, cy = 0.0, 0.0
        if props.get("centroid"):
            cx, cy = props["centroid"]
        else:
            cx, cy = _polygon_centroid(geom)
        condados.append({"id": str(cid), "name": name, "lon": cx, "lat": cy})
    return condados


def validate_condados_self_consistency(result: ResearchResult) -> None:
    """Check internal referential integrity of the LLM-generated result.

    Validates:
    - Every duchy's kingdom_id references a key in result.kingdoms.
    - Every condado's kingdom_id references a key in result.kingdoms.
    - Every condado's duchy_id references a key in result.duchies.
    - Every barony key references a condado id in result.condados.

    Raises:
        ValueError: describing the first inconsistency found.
    """
    kingdom_ids = set(result.kingdoms.keys())
    duchy_ids = set(result.duchies.keys())
    condado_ids = {c.id for c in result.condados}

    for did, duchy in result.duchies.items():
        if duchy.kingdom_id not in kingdom_ids:
            raise ValueError(
                f"Duchy {did!r} references unknown kingdom_id: {duchy.kingdom_id!r}"
            )

    for condado in result.condados:
        if condado.kingdom_id not in kingdom_ids:
            raise ValueError(
                f"Condado {condado.id!r} references unknown kingdom_id: {condado.kingdom_id!r}"
            )
        if condado.duchy_id not in duchy_ids:
            raise ValueError(
                f"Condado {condado.id!r} references unknown duchy_id: {condado.duchy_id!r}"
            )

    for barony_key in result.baronies:
        if barony_key not in condado_ids:
            raise ValueError(
                f"baronies key {barony_key!r} does not match any condado id"
            )


async def run_research(
    project_id: str,
    provider_id: str,
    queue: asyncio.Queue[str | None],
    force_refresh: bool = False,
    db_session_factory: async_sessionmaker | None = None,
    app_state: Any = None,
    task_type: str | None = None,
    effort_override: str | None = None,
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning (Pitfall 6).

    Orchestrates:
      1. Validate provider
      2. Load project metadata from DB
      3. Compute cache key; check cache (unless force_refresh)
      4. Resolve credentials
      5. Build prompt (no condados list — LLM generates freely)
      6. run_with_retry + validate self-consistency
      7. Cache result
      8. Emit RESULT + DONE to queue

    Optional model-routing params (Etapa 4 — quick-260428-f9x):
      task_type:        When provided, the model is resolved via
                        ``model_routing.resolve_model(provider_id, task_type,
                        effort_override)`` instead of the legacy
                        PROVIDER_DEFAULT_MODEL lookup. Backward compatible:
                        when None, behavior is unchanged.
      effort_override:  Optional "low"|"medium"|"high"; when set, overrides
                        the per-task default effort tier. Only used when
                        ``task_type`` is also provided.
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

        # When a task_type is provided, route via model_routing (Etapa 4 — quick-260428-f9x).
        # Otherwise keep legacy PROVIDER_DEFAULT_MODEL behavior for backward compat
        # (all 216 prior tests call run_research without task_type).
        if task_type is not None:
            try:
                model = resolve_model(provider_id, task_type, effort_override)
            except ValueError as e:
                await queue.put(f"data: ERROR: {e}\n\n")
                return
            # Note: llamacpp returns the sentinel "(server-default)" — the
            # llamacpp provider adapter is responsible for handling it.

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
            bbox: tuple[float, float, float, float] | None = None
            if all(
                v is not None
                for v in (
                    project.bbox_lon_min,
                    project.bbox_lat_min,
                    project.bbox_lon_max,
                    project.bbox_lat_max,
                )
            ):
                bbox = (
                    project.bbox_lon_min,
                    project.bbox_lat_min,
                    project.bbox_lon_max,
                    project.bbox_lat_max,
                )

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

        # Build prompt — LLM generates condados freely, no pre-supplied list
        prompt = build_research_prompt(country_name, period_start, period_end, bbox)

        # Resolve credentials
        credentials = resolve_credentials(provider_id, app_state)
        if provider_id != "ollama" and not credentials:
            await queue.put(f"data: ERROR: no credentials for {provider_id}\n\n")
            return

        await queue.put(f"data: starting {provider_id} ({model})\n\n")

        # Wrap provider.research with self-consistency validation so retry loop
        # re-prompts when the LLM produces internally inconsistent ids.
        class _ValidatingWrapper:
            """Thin wrapper that adds self-consistency validation after each research call."""
            provider_id = provider.provider_id
            display_name = provider.display_name
            auth_methods = provider.auth_methods

            async def health_check(self, creds: dict | None):
                return await provider.health_check(creds)

            async def research(
                self, p: str, s: type, c: dict | None, q: asyncio.Queue | None
            ) -> ResearchResult:
                result = await provider.research(p, s, c, q)
                validate_condados_self_consistency(result)
                return result

        try:
            result: ResearchResult = await run_with_retry(
                _ValidatingWrapper(), prompt, ResearchResult, credentials, queue, max_retries=3
            )
        except ResearchValidationError as e:
            msg = e.last_error[:600].replace("\n", " ")
            await queue.put(f"data: ERROR: validação falhou após 3 tentativas — {msg}\n\n")
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
        await queue.put(f"data: ERROR: {type(e).__name__}: {str(e)[:200]}\n\n")
    finally:
        # Pitfall 6: sentinel ALWAYS emitted so SSE consumer exits cleanly.
        await queue.put(None)
