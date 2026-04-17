"""INGEST-02: OSM Overpass municipality fetcher (admin_level=6 — concelhos/municípios).

Estratégia de query:
- Se bbox fornecida: query por bounding box (muito mais rápido, evita timeout 504)
- Se só ISO fornecido: query por área de país (fallback, pode ser lento para países grandes)

Retry: tenta até 3 endpoints públicos do Overpass em sequência.
T-SSRF: validate_iso_country enforces 2-letter uppercase ISO 3166-1 code.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Callable

import httpx
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping
from shapely.ops import linemerge, polygonize

log = logging.getLogger(__name__)

# Endpoints públicos do Overpass API em ordem de preferência
OVERPASS_ENDPOINTS: list[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

ISO_RE: re.Pattern[str] = re.compile(r"^[A-Z]{2}$")
_TIMEOUT_S: float = 180.0  # aumentado para 3 min


def validate_iso_country(value: str) -> str:
    if not isinstance(value, str) or not ISO_RE.match(value):
        raise ValueError(
            f"invalid ISO 3166-1 alpha-2 country code: {value!r} "
            "(expected pattern ^[A-Z]{2}$)"
        )
    return value


def _build_bbox_query(
    lat_min: float, lon_min: float, lat_max: float, lon_max: float,
    admin_level: int = 6,
) -> str:
    """Query por bounding box — mais rápida e confiável que por país.

    Usa bbox no elemento (não global) para garantir que `out geom;` inclui
    a geometria completa dos membros, mesmo os que cruzam a fronteira do bbox.
    """
    return (
        f"[out:json][timeout:160];\n"
        f"(\n"
        f'  relation["admin_level"="{admin_level}"]["boundary"="administrative"]'
        f"({lat_min},{lon_min},{lat_max},{lon_max});\n"
        f");\n"
        f"out geom;\n"
    )


def _build_country_query(country_iso: str, admin_level: int = 6) -> str:
    """Query por código de país ISO — fallback quando não há bbox."""
    return (
        f'[out:json][timeout:160];\n'
        f'area["ISO3166-1"="{country_iso}"]->.country;\n'
        f'(\n'
        f'  relation["admin_level"="{admin_level}"]["boundary"="administrative"]'
        f'(area.country);\n'
        f');\n'
        f"out geom;\n"
    )


def _relation_to_geojson_feature(rel: dict[str, Any]) -> dict[str, Any] | None:
    """Converte relação OSM com geometria para Feature GeoJSON Polygon/MultiPolygon.

    Algoritmo correto para relações multipolygon do OSM:
    1. Coleta todos os ways outer/inner como LineStrings.
    2. Usa shapely.ops.linemerge + polygonize para montar anéis fechados.
    3. Associa cada anel inner ao outer que o contém.
    4. Emite Polygon (um outer) ou MultiPolygon (múltiplos outers disjuntos).

    Retorna None se não houver outer ways ou se as geometrias forem malformadas
    (e.g. gaps que impedem o polygonize de fechar o anel).
    """
    members = rel.get("members", [])
    outer_lines: list[LineString] = []
    inner_lines: list[LineString] = []

    for m in members:
        geom = m.get("geometry") or []
        pts = [(pt["lon"], pt["lat"]) for pt in geom if "lon" in pt and "lat" in pt]
        if len(pts) < 2:
            continue
        ls = LineString(pts)
        role = m.get("role", "")
        if role == "outer":
            outer_lines.append(ls)
        elif role == "inner":
            inner_lines.append(ls)

    if not outer_lines:
        return None

    tags = rel.get("tags", {})
    osm_id = rel.get("id")
    name = tags.get("name", "")

    # Stitch outer ways into closed rings, then polygonize.
    # Pass the list directly to linemerge — unary_union collapses a single
    # LineString to a bare geometry that linemerge cannot handle.
    outer_merged = linemerge(outer_lines)
    outer_polys = list(polygonize(outer_merged))
    if not outer_polys:
        log.warning(
            "osm relation id=%s name=%r: outer ways do not form closed ring(s) — skipped",
            osm_id, name,
        )
        return None

    # Stitch inner ways the same way.
    inner_polys: list[Polygon] = []
    if inner_lines:
        inner_merged = linemerge(inner_lines)
        inner_polys = list(polygonize(inner_merged))

    # Pair each inner to its containing outer, build final Polygon objects.
    final: list[Polygon] = []
    for op in outer_polys:
        holes = [
            list(ip.exterior.coords)
            for ip in inner_polys
            if op.contains(ip.representative_point())
        ]
        final.append(Polygon(op.exterior.coords, holes))

    if len(final) == 1:
        geometry: dict[str, Any] = mapping(final[0])
    else:
        geometry = mapping(MultiPolygon(final))

    return {
        "type": "Feature",
        "properties": {
            "osm_id": osm_id,
            "name": name,
            "admin_level": tags.get("admin_level", ""),
        },
        "geometry": geometry,
    }


async def _post_query(
    query: str,
    queue: asyncio.Queue[str | None],
    client_factory: Callable[[], httpx.AsyncClient] | None,
) -> dict[str, Any]:
    """Tenta cada endpoint Overpass em sequência até um responder sem erro 5xx."""
    def _factory() -> httpx.AsyncClient:
        if client_factory is not None:
            return client_factory()
        return httpx.AsyncClient(timeout=_TIMEOUT_S)

    last_exc: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        await queue.put(f"data: Tentando endpoint: {endpoint}...\n\n")
        try:
            async with _factory() as client:
                resp = await client.post(endpoint, data={"data": query})
                if resp.status_code >= 500:
                    await queue.put(
                        f"data: Endpoint retornou {resp.status_code}, tentando próximo...\n\n"
                    )
                    last_exc = httpx.HTTPStatusError(
                        f"Server error {resp.status_code}", request=resp.request, response=resp
                    )
                    continue
                resp.raise_for_status()
                return resp.json()
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            await queue.put(f"data: Endpoint falhou ({exc.__class__.__name__}), tentando próximo...\n\n")
            last_exc = exc
            continue

    raise last_exc or RuntimeError("Todos os endpoints Overpass falharam")


async def fetch_municipalities(
    country_iso: str,
    queue: asyncio.Queue[str | None],
    *,
    bbox: tuple[float, float, float, float] | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, Any]:
    """Busca municípios OSM e retorna GeoJSON FeatureCollection.

    Args:
        country_iso: Código ISO alpha-2 (usado apenas se bbox=None).
        queue: Fila SSE para mensagens de progresso.
        bbox: (lat_min, lon_min, lat_max, lon_max) — se fornecido, usa query
              por bounding box (muito mais rápido que por país).
        client_factory: Fábrica de cliente HTTP (para testes).
    """
    if bbox is not None:
        lat_min, lon_min, lat_max, lon_max = bbox
        await queue.put(
            f"data: Consultando OSM por área ({lat_min:.2f},{lon_min:.2f} → "
            f"{lat_max:.2f},{lon_max:.2f}) — mais rápido que por país...\n\n"
        )
        query = _build_bbox_query(lat_min, lon_min, lat_max, lon_max)
    else:
        validate_iso_country(country_iso)
        await queue.put(
            f"data: Consultando OSM Overpass por país ({country_iso})... "
            f"Pode demorar até 3 min para países grandes.\n\n"
        )
        query = _build_country_query(country_iso)

    payload = await _post_query(query, queue, client_factory)

    features: list[dict[str, Any]] = []
    for el in payload.get("elements", []):
        if el.get("type") != "relation":
            continue
        feat = _relation_to_geojson_feature(el)
        if feat is not None:
            features.append(feat)

    await queue.put(f"data: OSM: {len(features)} municípios/regiões encontrados.\n\n")
    return {"type": "FeatureCollection", "features": features}
