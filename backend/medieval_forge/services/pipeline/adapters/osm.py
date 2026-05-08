"""OSM adapter: wrap ingest_osm.fetch_municipalities + split-by-ISO partition (D-05).

Implements ROADMAP-02#3 "wrap, don't rewrite". The split-by-ISO step is NEW
logic (the existing _clip_features_to_countries is a union filter, not a
partition — see RESEARCH Pitfall 4).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

import httpx
from shapely.geometry import shape as shapely_shape

from medieval_forge.services.country_boundaries import get_country_polygon
from medieval_forge.services.ingest_osm import fetch_municipalities  # D-05: wrap
from medieval_forge.services.pipeline.contracts import ProjectDataset

from .base import project_inputs_dir, _write_geojson_atomic

log = logging.getLogger(__name__)

# 0.025 deg buffer around country polygons — matches ingest_osm._COUNTRY_BUFFER_DEG;
# absorbs Natural Earth coastline imprecision (~1-2 km) so that coastal
# municipalities (Lisboa, Funchal) aren't dropped at the partition step.
_COUNTRY_BUFFER_DEG: float = 0.025

# Per-ISO OSM admin_level map. The vendored fixture cardinality is at the
# concelho/municipio tier, NOT the v1 default of admin_level=6:
#   PT concelho ≈ admin_level=7 (~278 features in the vendored
#     pt_concelhos_wgs84.geojson)
#   ES municipio ≈ admin_level=8 (~3000+ features in the vendored
#     es-atlas municipalities)
# v1 fetch_municipalities defaulted to admin_level=6 (PT distrito + ES
# provincia), which on first live-snapshot capture returned only 18+50
# features and broke the parity test (Plan 02-03 Rule 1 deviation).
_ADMIN_LEVEL_BY_ISO: dict[str, int] = {"PT": 7, "ES": 8}
# Fallback for any future ISO not explicitly mapped (matches v1 default).
_DEFAULT_ADMIN_LEVEL: int = 6

# D-13: vendored mountain_river_data.json path (Phase 02 stub passthrough).
# Anchored to repo root via parents[5] from this file:
#   adapters/osm.py -> adapters/ -> pipeline/ -> services/ -> medieval_forge/ -> backend/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_VENDORED_MOUNTAIN_RIVER = _REPO_ROOT / "data" / "regions" / "iberia_868" / "inputs" / "mountain_river_data.json"


def _validate_bbox(bbox: tuple) -> None:
    """T-DOS / T-SSRF: bbox must be 4 floats; lat/lon order valid; span ≤ 30°/axis."""
    if not isinstance(bbox, tuple) or len(bbox) != 4:
        raise ValueError(f"bbox must be a 4-tuple of floats, got {bbox!r}")
    try:
        lat_min, lon_min, lat_max, lon_max = (float(x) for x in bbox)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bbox elements must be numeric, got {bbox!r}") from exc
    if lat_min >= lat_max or lon_min >= lon_max:
        raise ValueError(f"bbox has zero/negative span: {bbox!r}")
    if (lat_max - lat_min) > 30 or (lon_max - lon_min) > 30:
        raise ValueError(f"bbox exceeds 30° per axis (DoS guard): {bbox!r}")


def _split_by_iso(
    fc: dict[str, Any],
    iso_codes: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Partition fc.features by representative-point-in-buffered-country-polygon.

    Returns {iso: [features]} for each iso in iso_codes. Features whose
    representative_point falls outside ALL polygons are dropped.

    Uses representative_point (guaranteed inside the geometry) rather than
    centroid (can fall outside concave shapes — Pitfall A3).
    """
    result: dict[str, list[dict[str, Any]]] = {iso: [] for iso in iso_codes}

    # Build (iso, buffered_polygon) tuples. Skip ISOs not in Natural Earth.
    polys: list[tuple[str, Any]] = []
    for iso in iso_codes:
        poly = get_country_polygon(iso)
        if poly is None:
            log.warning(
                "split_by_iso: no Natural Earth polygon for %s — features routed to %s will be empty",
                iso, iso,
            )
            continue
        polys.append((iso, poly.buffer(_COUNTRY_BUFFER_DEG)))

    for feat in fc.get("features", []):
        geom = feat.get("geometry") or {}
        gt = geom.get("type", "")
        if gt not in ("Polygon", "MultiPolygon"):
            continue  # only polygon features participate in country routing
        try:
            shp = shapely_shape(geom)
            rp = shp.representative_point()
        except Exception as exc:  # noqa: BLE001 — bad geometry; log + skip
            log.warning("split_by_iso: bad geometry, dropping feature: %s", exc)
            continue
        for iso, buffered in polys:
            if buffered.contains(rp):
                result[iso].append(feat)
                break  # first match wins; ISO order matters for border features

    return result


async def build_dataset_from_osm(
    project_id: str,
    bbox: tuple[float, float, float, float],
    iso_codes: list[str],
    queue: asyncio.Queue[str | None],
    *,
    stop_event: asyncio.Event | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> ProjectDataset:
    """Live OSM → ProjectDataset (D-01, D-05, D-07, D-13).

    For Iberia 868: pass iso_codes=["PT", "ES"] (clip_iso_codes_for_qid("Q29,Q45")).

    Steps:
      1. Validate inputs (T-PATH project_id; T-DOS bbox).
      2. Wrap ingest_osm.fetch_municipalities (D-05: wrap, don't rewrite).
      3. Split combined FC into per-ISO lists (NEW logic).
      4. Write each per-ISO FC atomically to projects/<uuid>/inputs/<iso>_*.geojson (D-07).
      5. Return ProjectDataset with the two written .geojson paths +
         vendored mountain_river_data.json (D-13 stub passthrough).
    """
    _validate_bbox(bbox)
    inputs_dir = project_inputs_dir(project_id)  # raises ValueError if project_id is not UUID

    if "PT" not in iso_codes or "ES" not in iso_codes:
        raise ValueError(
            f"Phase 02 supports Iberia 868 only — iso_codes must include PT and ES, got {iso_codes!r}"
        )

    # Step 1: wrap fetch_municipalities ONCE PER ISO using the per-ISO admin_level
    # (PT=7 concelho, ES=8 municipio). v1's single-call admin_level=6 default
    # returned PT distritos + ES provincias — the wrong cardinality tier and
    # the cause of the Plan 02-03 Rule 1 deviation.
    combined_features: list[dict[str, Any]] = []
    for iso in iso_codes:
        admin_level = _ADMIN_LEVEL_BY_ISO.get(iso, _DEFAULT_ADMIN_LEVEL)
        await queue.put(
            f"data: Adapter: fetching OSM municipalities for {iso} "
            f"(bbox={bbox}, admin_level={admin_level})...\n\n"
        )
        per_iso_fc = await fetch_municipalities(
            country_iso=iso,
            queue=queue,
            bbox=bbox,
            clip_iso_codes=[iso],  # narrow the bbox return to this ISO only
            client_factory=client_factory,
            stop_event=stop_event,
            admin_level=admin_level,
        )
        per_iso_features = per_iso_fc.get("features", [])
        await queue.put(
            f"data: Adapter: {iso} (admin_level={admin_level}) returned "
            f"{len(per_iso_features)} features.\n\n"
        )
        combined_features.extend(per_iso_features)

    combined_fc = {"type": "FeatureCollection", "features": combined_features}

    # Step 2: split-by-ISO over the combined per-ISO results. Defensive — even
    # though clip_iso_codes already filtered each call, _split_by_iso re-routes
    # any cross-border features to the canonical ISO and keeps the partition
    # logic in one place for future ISOs that may share a bbox span.
    by_iso = _split_by_iso(combined_fc, iso_codes)
    pt_count = len(by_iso["PT"])
    es_count = len(by_iso["ES"])
    await queue.put(f"data: Adapter: split-by-ISO → PT={pt_count}, ES={es_count}.\n\n")

    # Step 3: write atomically (D-07).
    pt_path = inputs_dir / "pt_concelhos_live.geojson"
    es_path = inputs_dir / "es_municipalities_live.geojson"
    _write_geojson_atomic(pt_path, {"type": "FeatureCollection", "features": by_iso["PT"]})
    _write_geojson_atomic(es_path, {"type": "FeatureCollection", "features": by_iso["ES"]})
    await queue.put(
        f"data: Adapter: wrote {pt_path.name} ({pt_count}) + {es_path.name} ({es_count}).\n\n"
    )

    return ProjectDataset(
        pt_geojson=pt_path,
        es_input=es_path,
        mountain_river_json=_VENDORED_MOUNTAIN_RIVER,  # D-13 stub passthrough
    )


__all__ = ["build_dataset_from_osm", "_split_by_iso"]
