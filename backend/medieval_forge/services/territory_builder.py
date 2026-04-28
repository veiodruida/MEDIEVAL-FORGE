"""territory_builder: assemble generator input from DB cache.

This is the single source of truth for building the `territory_data` dict
consumed by `services.generator.run_generation`. It replaces the previous
flow where the frontend posted a hardcoded template to /generate.

Precedence (per QUICK-260426-q3v):
  1. Latest ResearchCache row matching (project.country_qid, period_start, period_end)
     — picked across ALL providers/models, newest `created_at` wins.

The research payload now carries condados with their own coordinates (the LLM
generates them freely). No geojson centroid file is needed to assemble territory_data.

If no cache row exists, the public entry point returns None and the caller
(api/generate.py) decides how to surface the 422 to the user.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Project, ResearchCache

logger = logging.getLogger(__name__)


async def select_latest_cache_row(
    session: AsyncSession,
    country_qid: str,
    period_start: int,
    period_end: int,
) -> ResearchCache | None:
    """Return the most-recently-created ResearchCache row for the given tuple.

    Across multiple providers/models for the same (country_qid, period_start,
    period_end), the row with the latest `created_at` wins.
    """
    stmt = (
        select(ResearchCache)
        .where(
            ResearchCache.country_qid == country_qid,
            ResearchCache.period_start == period_start,
            ResearchCache.period_end == period_end,
        )
        .order_by(ResearchCache.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def assemble_territory_data(research_payload: dict[str, Any]) -> dict[str, Any]:
    """Build the generator-ready territory_data dict from a cached research payload.

    Output shape (consumed by services.generator._inject_territory_module):
        {
            "kingdoms": dict[str, str],          # id -> display name
            "duchies":  dict[str, Any],          # id -> Duchy-like
            "condados": list[tuple],             # (id, name, lon, lat, duchy_id, baronies)
        }
    where each barony entry is `(name, lon, lat)`.

    Condado coordinates come from the research payload itself — the LLM generates
    condados with their centroids. No external geojson centroid source is needed.
    """
    condados_raw: list[dict[str, Any]] = research_payload.get("condados", [])
    baronies_by_id: dict[str, list[dict[str, Any]]] = research_payload.get("baronies", {}) or {}

    condados: list[tuple] = []
    for c in condados_raw:
        cid = c["id"]
        baronies_raw = baronies_by_id.get(cid, []) or []
        baronies: list[tuple] = [
            (b["name"], float(b["lon"]), float(b["lat"]))
            for b in baronies_raw
        ]
        condados.append((
            cid,
            c["name"],
            float(c["lon"]),
            float(c["lat"]),
            c.get("duchy_id"),
            baronies,
        ))

    return {
        "kingdoms": research_payload.get("kingdoms", {}),
        "duchies": research_payload.get("duchies", {}),
        "condados": condados,
    }


async def build_territory_data_from_cache(
    session: AsyncSession,
    project: Project,
    project_path: Path | None = None,  # kept for API compat; no longer used
) -> dict[str, Any] | None:
    """Public entry point: return a generator-ready territory_data dict, or None on cache miss.

    Cache key is derived from the project row (never from the request body),
    so a malicious client cannot redirect the cache lookup to another
    project's research (T-q3v-04 mitigation).

    Returns:
        Assembled territory_data dict on cache hit; None if no
        ResearchCache row exists for the project's tuple.
    """
    row = await select_latest_cache_row(
        session,
        project.country_qid,
        project.period_start,
        project.period_end,
    )
    if row is None:
        return None

    territory_data = assemble_territory_data(row.payload)
    logger.info(
        "territory_builder: assembled territory_data from cache "
        "(provider=%s model=%s, %d condados) for project=%s",
        row.provider,
        row.model,
        len(territory_data["condados"]),
        project.id,
    )
    return territory_data
