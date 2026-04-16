"""INGEST-02: OSM Overpass municipality fetcher (admin_level=8).

T-SSRF: validate_iso_country enforces 2-letter uppercase ISO 3166-1 code.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Callable

import httpx

OVERPASS_ENDPOINT: str = "https://overpass-api.de/api/interpreter"
ISO_RE: re.Pattern[str] = re.compile(r"^[A-Z]{2}$")
_TIMEOUT_S: float = 130.0  # Overpass internal timeout 120s; client 130s


def validate_iso_country(value: str) -> str:
    if not isinstance(value, str) or not ISO_RE.match(value):
        raise ValueError(
            f"invalid ISO 3166-1 alpha-2 country code: {value!r} "
            "(expected pattern ^[A-Z]{2}$)"
        )
    return value


def _build_query(country_iso: str, admin_level: int = 8) -> str:
    return f"""
    [out:json][timeout:120];
    area["ISO3166-1"="{country_iso}"]->.country;
    (
      relation["admin_level"="{admin_level}"]["boundary"="administrative"](area.country);
    );
    out geom;
    """


def _relation_to_geojson_feature(rel: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an OSM relation with geometry into a GeoJSON Polygon/MultiPolygon feature.

    Outer/inner classification: each member.role == "outer" forms a ring of
    a polygon; "inner" rings are holes. This is a minimal conversion adequate
    for Phase 1 (Plan 06 / Phase 6 polish may swap in osm2geojson if needed).
    """
    members = rel.get("members", [])
    outers: list[list[list[float]]] = []
    inners: list[list[list[float]]] = []
    for m in members:
        geom = m.get("geometry") or []
        if not geom:
            continue
        ring = [[pt["lon"], pt["lat"]] for pt in geom if "lon" in pt and "lat" in pt]
        if len(ring) < 3:
            continue
        # Close ring if not already closed.
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        role = m.get("role", "")
        if role == "outer":
            outers.append(ring)
        elif role == "inner":
            inners.append(ring)
    if not outers:
        return None

    tags = rel.get("tags", {})
    if len(outers) == 1:
        coords = [outers[0]] + inners
        geometry = {"type": "Polygon", "coordinates": coords}
    else:
        # Naive: each outer is its own polygon; ignore inner-to-outer assignment
        # for Phase 1. Phase 6 polish can reassign inners by point-in-polygon.
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [[o] for o in outers],
        }
    return {
        "type": "Feature",
        "properties": {
            "osm_id": rel.get("id"),
            "name": tags.get("name", ""),
            "admin_level": tags.get("admin_level", ""),
        },
        "geometry": geometry,
    }


async def fetch_municipalities(
    country_iso: str,
    queue: asyncio.Queue[str | None],
    *,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, Any]:
    validate_iso_country(country_iso)

    def _factory() -> httpx.AsyncClient:
        if client_factory is not None:
            return client_factory()
        return httpx.AsyncClient(timeout=_TIMEOUT_S)

    query = _build_query(country_iso)
    await queue.put("data: Querying OSM Overpass API (this may take ~2 min)...\n\n")
    async with _factory() as client:
        resp = await client.post(OVERPASS_ENDPOINT, data={"data": query})
        resp.raise_for_status()
        payload = resp.json()

    features: list[dict[str, Any]] = []
    for el in payload.get("elements", []):
        if el.get("type") != "relation":
            continue
        feat = _relation_to_geojson_feature(el)
        if feat is not None:
            features.append(feat)
    await queue.put(
        f"data: OSM fetch complete: {len(features)} features.\n\n"
    )
    return {"type": "FeatureCollection", "features": features}
