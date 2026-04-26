"""territory_builder: assemble generator input from DB cache + territories.geojson.

This is the single source of truth for building the `territory_data` dict
consumed by `services.generator.run_generation`. It replaces the previous
flow where the frontend posted a hardcoded template to /generate (which
caused orphan bug #4: a 4-condado template overrode the 91-condado cached
research).

Precedence (per QUICK-260426-q3v):
  1. Latest ResearchCache row matching (project.country_qid, period_start, period_end)
     — picked across ALL providers/models, newest `created_at` wins.
  2. Centroids/names from generated/territories.geojson (via research_runner.load_condados).

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
from .research_runner import load_condados

logger = logging.getLogger(__name__)


async def select_latest_cache_row(
    session: AsyncSession,
    country_qid: str,
    period_start: int,
    period_end: int,
) -> ResearchCache | None:
    """Return the most-recently-created ResearchCache row for the given tuple.

    Across multiple providers/models for the same (country_qid, period_start,
    period_end), the row with the latest `created_at` wins. This is
    deterministic and observable: the user can see which provider was used
    via the returned row's `provider`/`model` fields.
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


def assemble_territory_data(
    research_payload: dict[str, Any],
    condados_centroids: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the generator-ready territory_data dict from a cached payload + centroids.

    Output shape (consumed by services.generator._inject_territory_module):
        {
            "kingdoms": dict[str, str],          # id -> display name
            "duchies":  dict[str, Any],          # id -> Duchy-like
            "condados": list[tuple],             # (id, name, lon, lat, duchy_id, baronies)
        }
    where each barony entry is `(name, lon, lat)`.

    Centroids without an assignment are still emitted with `duchy_id=None`
    and an empty barony list — the generator only requires the tuple shape,
    so unassigned territories render as un-attributed condados rather than
    silently disappearing.

    Raises:
        ValueError: if any condado_id appearing in
            research_payload["condados_assignment"] is not present in
            condados_centroids (defensive — mirrors
            research_runner.validate_assignment_against_condados).
    """
    centroids_by_id: dict[str, dict[str, Any]] = {c["id"]: c for c in condados_centroids}
    known_ids = set(centroids_by_id.keys())

    # Build assignment lookup: condado_id -> duchy_id
    assignment_by_id: dict[str, str] = {}
    unknown_ids: list[str] = []
    for assignment in research_payload.get("condados_assignment", []):
        cid = assignment["condado_id"]
        if cid not in known_ids:
            unknown_ids.append(cid)
        else:
            assignment_by_id[cid] = assignment["duchy_id"]

    if unknown_ids:
        raise ValueError(
            f"Research payload references condado_id(s) absent from territories.geojson: "
            f"{sorted(unknown_ids)!r}"
        )

    baronies_by_id: dict[str, list[dict[str, Any]]] = research_payload.get("baronies", {}) or {}

    condados: list[tuple] = []
    for centroid in condados_centroids:
        cid = centroid["id"]
        duchy_id = assignment_by_id.get(cid)  # None if unassigned
        baronies_raw = baronies_by_id.get(cid, []) or []
        baronies: list[tuple] = [
            (b["name"], float(b["lon"]), float(b["lat"]))
            for b in baronies_raw
        ]
        condados.append((
            cid,
            centroid["name"],
            float(centroid["lon"]),
            float(centroid["lat"]),
            duchy_id,
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
    project_path: Path,
) -> dict[str, Any] | None:
    """Public entry point: return a generator-ready territory_data dict, or None on cache miss.

    Cache key is derived from the project row (never from the request body),
    so a malicious client cannot redirect the cache lookup to another
    project's research (T-q3v-04 mitigation).

    Returns:
        Assembled territory_data dict on cache hit; None if no
        ResearchCache row exists for the project's tuple. The caller
        decides how to surface a cache miss (typically a 422).
    """
    row = await select_latest_cache_row(
        session,
        project.country_qid,
        project.period_start,
        project.period_end,
    )
    if row is None:
        return None

    centroids = load_condados(project_path)
    territory_data = assemble_territory_data(row.payload, centroids)
    logger.info(
        "territory_builder: assembled territory_data from cache "
        "(provider=%s model=%s, %d condados, %d centroids) for project=%s",
        row.provider,
        row.model,
        len(territory_data["condados"]),
        len(centroids),
        project.id,
    )
    return territory_data
