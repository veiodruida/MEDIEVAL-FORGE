"""Phase 2.1 GEO-01..04: rivers, topography, coastline, parishes via Overpass."""
from __future__ import annotations

import asyncio
from typing import Any, Callable

import httpx
from shapely.geometry import LineString, MultiLineString, mapping
from shapely.ops import linemerge as line_merge

from medieval_forge.services import overpass_client
from medieval_forge.services.ingest_osm import _relation_to_geojson_feature

BBox = tuple[float, float, float, float]  # (lon_min, lat_min, lon_max, lat_max) — geopandas convention


def _q_rivers(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> str:
    return (
        "[out:json][timeout:160];\n"
        "(\n"
        f'  way["waterway"="river"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
        f'  way["waterway"="stream"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
        ");\nout geom;\n"
    )


def _q_topography(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> str:
    return (
        "[out:json][timeout:160];\n"
        "(\n"
        f'  node["natural"="peak"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
        f'  way["natural"="ridge"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
        f'  way["natural"="cliff"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
        ");\nout geom;\n"
    )


def _q_coastline(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> str:
    return (
        "[out:json][timeout:160];\n"
        "(\n"
        f'  way["natural"="coastline"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
        ");\nout geom;\n"
    )


def _q_parishes(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> str:
    return (
        "[out:json][timeout:60][maxsize:33554432];\n"
        "(\n"
        f'  relation["boundary"="administrative"]["admin_level"="8"]'
        f'({lat_min},{lon_min},{lat_max},{lon_max});\n'
        ");\nout body qt;\n>;\nout skel qt;\n"
    )


async def fetch_rivers(
    bbox: BBox,
    queue: asyncio.Queue,
    *,
    stop_event: asyncio.Event | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, Any]:
    """GEO-01: Fetch rivers and streams via Overpass → FeatureCollection of LineStrings."""
    payload = await overpass_client.post_query(
        _q_rivers(*bbox), queue, client_factory, stop_event=stop_event
    )
    features = []
    for el in payload.get("elements", []):
        if el.get("type") != "way":
            continue
        geom_pts = el.get("geometry") or []
        coords = [(p["lon"], p["lat"]) for p in geom_pts if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue
        tags = el.get("tags", {})
        ww = tags.get("waterway")
        if ww not in ("river", "stream"):
            continue
        # T-02-01: only static frame in SSE — OSM names go into properties, never into logs.
        features.append({
            "type": "Feature",
            "properties": {
                "id": int(el["id"]),
                "waterway": ww,
                "name": tags.get("name") or None,
            },
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    return {"type": "FeatureCollection", "features": features}


async def fetch_topography(
    bbox: BBox,
    queue: asyncio.Queue,
    *,
    stop_event: asyncio.Event | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, Any]:
    """GEO-02: Fetch peaks (Point), ridges and cliffs (LineString) → FeatureCollection."""
    payload = await overpass_client.post_query(
        _q_topography(*bbox), queue, client_factory, stop_event=stop_event
    )
    features = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        natural = tags.get("natural")
        if natural not in ("peak", "ridge", "cliff"):
            continue
        ele_raw = tags.get("ele")
        try:
            ele = float(ele_raw) if ele_raw not in (None, "") else None
        except (ValueError, TypeError):
            ele = None
        props = {
            "id": int(el["id"]),
            "natural": natural,
            "name": tags.get("name") or None,
            "ele": ele,
        }
        if el.get("type") == "node":
            geom: dict[str, Any] = {
                "type": "Point",
                "coordinates": [el["lon"], el["lat"]],
            }
        elif el.get("type") == "way":
            pts = el.get("geometry") or []
            coords = [(p["lon"], p["lat"]) for p in pts if "lon" in p and "lat" in p]
            if len(coords) < 2:
                continue
            geom = {"type": "LineString", "coordinates": coords}
        else:
            continue
        features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


async def fetch_coastline(
    bbox: BBox,
    queue: asyncio.Queue,
    *,
    stop_event: asyncio.Event | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, Any]:
    """GEO-03: Fetch coastline ways, line_merge them, output as single MultiLineString feature.

    D-03: always MultiLineString (wrap when line_merge returns a LineString — Pitfall 2).
    T-02-01: only static log messages — raw OSM data goes into properties, never into SSE logs.
    """
    payload = await overpass_client.post_query(
        _q_coastline(*bbox), queue, client_factory, stop_event=stop_event
    )
    lines: list[LineString] = []
    for el in payload.get("elements", []):
        if el.get("type") != "way":
            continue
        pts = el.get("geometry") or []
        coords = [(p["lon"], p["lat"]) for p in pts if "lon" in p and "lat" in p]
        if len(coords) >= 2:
            lines.append(LineString(coords))

    if not lines:
        # T-02-01: static message only, no raw OSM data.
        await queue.put("data: AVISO: nenhum segmento de coastline retornado.\n\n")
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "MultiLineString", "coordinates": []},
            }],
        }

    merged = line_merge(MultiLineString(lines))
    # Pitfall 2: line_merge may return a single LineString — wrap to MultiLineString for contract.
    if merged.geom_type == "LineString":
        merged = MultiLineString([merged])
    feature = {"type": "Feature", "properties": {}, "geometry": mapping(merged)}
    return {"type": "FeatureCollection", "features": [feature]}


async def fetch_parishes(
    bbox: BBox,
    queue: asyncio.Queue,
    *,
    stop_event: asyncio.Event | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, Any]:
    """GEO-04: Fetch admin_level=8 relations → FeatureCollection of Polygon/MultiPolygon.

    D-04 graceful empty: if no results, write empty FeatureCollection + SSE log.
    """
    payload = await overpass_client.post_query(
        _q_parishes(*bbox), queue, client_factory, stop_event=stop_event
    )
    features = []
    for el in payload.get("elements", []):
        if el.get("type") != "relation":
            continue
        feat = _relation_to_geojson_feature(el)
        if feat is None:
            continue
        tags = el.get("tags", {})
        # Re-shape properties to the parish schema (D-04 contract): id/name/admin_level=8.
        feat["properties"] = {
            "id": int(el["id"]),
            "name": tags.get("name", ""),
            "admin_level": 8,
        }
        features.append(feat)

    if not features:
        # D-04 graceful empty.
        await queue.put("data: Sem parishes disponíveis para este bbox.\n\n")
    return {"type": "FeatureCollection", "features": features}
