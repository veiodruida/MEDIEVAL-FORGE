"""territory_builder: assemble generator input from DB cache.

This is the single source of truth for building the `territory_data` dict
consumed by `services.generator.run_generation`. It replaces the previous
flow where the frontend posted a hardcoded template to /generate.

Precedence (per QUICK-260426-q3v):
  1. Latest ResearchCache row matching (project.country_qid, period_start, period_end)
     — picked across ALL providers/models, newest `created_at` wins.

Two aggregation paths coexist (both produce the same final tuple shape consumed
by ``services.generator``):

* Legacy ``assemble_territory_data`` — research payload carries condados with
  their own LLM-invented coordinates and an embedded ``baronies`` dict
  (pre-Etapa 7 schema). Kept untouched for backwards compatibility.

* New ``assemble_territory_data_from_baronies`` (Etapa 7 / master plan H.7) —
  consumes a ``MapResearchResult``-shaped payload (condados WITHOUT coords +
  ``barony_assignments``) and the baronies GeoJSON ``FeatureCollection``
  produced by ``baronies_builder``. Each condado's centroid is the arithmetic
  mean of its member-barony centroids (CK3-style: baronies are organic OSM
  geometry, condados are political aggregations).

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


def assemble_territory_data_from_baronies(
    map_research_payload: dict[str, Any],
    baronies_geojson: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate baronies into condados using ``barony_assignments`` (Etapa 7 / master plan H.7).

    This is the CK3-style path: baronies are organic OSM polygons (built by
    ``baronies_builder.build_baronies_from_osm``) and condados are political
    aggregations. Each condado's centroid is the **arithmetic mean** of its
    member-barony centroids — no LLM-invented coords. This closes the geometry
    gap that produced the "erro 0" IndexError described in master plan H.1.

    Inputs:
        map_research_payload: ``MapResearchResult``-shaped dict (Etapa 3
            schema) — keys ``kingdoms`` (dict[str, str]), ``duchies``
            (dict[str, Duchy-like]), ``condados`` (list of dicts with
            ``id``, ``name``, ``kingdom_id``, ``duchy_id`` — NO lon/lat),
            ``barony_assignments`` (dict[barony_id -> condado_id]).
        baronies_geojson: ``FeatureCollection`` from ``baronies_builder``.
            Each feature has ``properties.id`` (e.g. ``B_{osm_id}``),
            ``properties.name``, ``properties.centroid`` ([lon, lat]).

    Output (identical contract to ``assemble_territory_data``):
        {
            "kingdoms": dict[str, str],
            "duchies":  dict[str, Any],
            "condados": list[tuple],   # (id, name, lon, lat, duchy_id, baronies)
                                        # baronies = list[(name, lon, lat)]
        }

    Raises:
        ValueError: if any ``barony_id`` in ``barony_assignments`` is missing
            from ``baronies_geojson`` (ingestion mismatch — defensive),
            naming the offending id(s) sorted.
        ValueError: if any condado has zero baronies assigned to it (would
            otherwise crash ``map_generator`` with the "erro 0" IndexError),
            naming the empty condado_id(s) sorted.

    See ``assemble_territory_data`` for the legacy embedded-coords path
    (kept for backwards compat with pre-Etapa-7 ResearchResult schemas).
    """
    # O(1) lookup index by barony id.
    features = baronies_geojson.get("features", []) or []
    baronies_by_id: dict[str, dict[str, Any]] = {}
    for feature in features:
        props = feature.get("properties", {}) or {}
        bid = props.get("id")
        if bid is not None:
            baronies_by_id[bid] = feature

    barony_assignments: dict[str, str] = (
        map_research_payload.get("barony_assignments", {}) or {}
    )

    # Defensive: collect ALL missing barony ids referenced by assignments,
    # then raise once with a sorted list naming them.
    missing_ids = sorted(
        bid for bid in barony_assignments.keys() if bid not in baronies_by_id
    )
    if missing_ids:
        raise ValueError(
            "barony_assignments reference unknown barony id(s) "
            f"missing from baronies geojson: {missing_ids}"
        )

    condados_raw: list[dict[str, Any]] = map_research_payload.get("condados", []) or []

    # For each condado, gather the (barony_id) keys whose assignment value
    # equals its id, preserving insertion order of barony_assignments
    # (Python dicts preserve insertion order — deterministic).
    assigned_by_condado: dict[str, list[str]] = {c["id"]: [] for c in condados_raw}
    for barony_id, condado_id in barony_assignments.items():
        # Note: assignments to unknown condado_ids are silently allowed here
        # — they simply don't contribute to any condado. Cross-ref validation
        # is the responsibility of validate_barony_assignments (Etapa 6).
        if condado_id in assigned_by_condado:
            assigned_by_condado[condado_id].append(barony_id)

    empty_condados = sorted(
        cid for cid, members in assigned_by_condado.items() if not members
    )
    if empty_condados:
        raise ValueError(
            "condado(s) have zero baronies assigned (would crash map_generator "
            f"with empty baronies=[]): {empty_condados}"
        )

    condados: list[tuple] = []
    for c in condados_raw:
        cid = c["id"]
        member_ids = assigned_by_condado[cid]
        member_features = [baronies_by_id[bid] for bid in member_ids]

        baronies_list: list[tuple] = []
        lons: list[float] = []
        lats: list[float] = []
        for feat in member_features:
            props = feat.get("properties", {}) or {}
            centroid = props.get("centroid") or [0.0, 0.0]
            lon = float(centroid[0])
            lat = float(centroid[1])
            baronies_list.append((props.get("name"), lon, lat))
            lons.append(lon)
            lats.append(lat)

        mean_lon = sum(lons) / len(lons)
        mean_lat = sum(lats) / len(lats)

        condados.append((
            cid,
            c["name"],
            mean_lon,
            mean_lat,
            c.get("duchy_id"),
            baronies_list,
        ))

    return {
        "kingdoms": map_research_payload.get("kingdoms", {}),
        "duchies": map_research_payload.get("duchies", {}),
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
