"""INGEST-02: OSM Overpass municipality fetcher (admin_level=6 — concelhos/municípios).

Estratégia de query:
- Se bbox fornecida: query por bounding box (muito mais rápido, evita timeout 504)
- Se só ISO fornecido: query por área de país (fallback, pode ser lento para países grandes)

Country clipping:
- Quando clip_iso_codes fornecido, carrega o polígono soberano de cada ISO via
  Natural Earth Admin 0 (1:50m, vendored em data/ne_50m_admin_0_countries.geojson).
- União dos polígonos → filtra municípios cujo representative_point está dentro.
- Substitui a query Overpass admin_level=2 anterior, que sofria com 406/504/timeouts
  e exigia hardcode de fallbacks por país (não escalava).

Retry: tenta até 3 endpoints públicos do Overpass em sequência (apenas para a
fetch de admin_level=6, que precisa de dados live).
T-SSRF: validate_iso_country enforces 2-letter uppercase ISO 3166-1 code.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Callable

import httpx
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping
from shapely.ops import linemerge, polygonize, unary_union

from . import country_boundaries, overpass_client

log = logging.getLogger(__name__)

# OVERPASS_ENDPOINTS moved to overpass_client.py per D-02.
# Re-exported here for backward compatibility with existing callers.
OVERPASS_ENDPOINTS = overpass_client.OVERPASS_ENDPOINTS

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


async def _fetch_country_polygon(
    country_iso: str,
    queue: asyncio.Queue[str | None],
    client_factory: Callable[[], httpx.AsyncClient] | None = None,  # noqa: ARG001 — kept for API compat
) -> Polygon | MultiPolygon | None:
    """Carrega o polígono soberano de um país via Natural Earth Admin 0 (vendored).

    Substitui a query Overpass admin_level=2 anterior — NE é offline,
    determinístico, ~1km de precisão, e cobre 234 países sem hardcoding.
    Mantém assinatura `async` (+ `client_factory` ignorado) para compatibilidade
    com chamadores que esperam coroutine.
    """
    poly = country_boundaries.get_country_polygon(country_iso)
    if poly is None:
        await queue.put(
            f"data: AVISO: Sem polígono Natural Earth para {country_iso} — este país não será clipado.\n\n"
        )
        log.warning("country boundary: %r not in Natural Earth dataset", country_iso)
        return None

    await queue.put(
        f"data: Polígono Natural Earth carregado para {country_iso} ({poly.geom_type}).\n\n"
    )
    log.info("country boundary loaded from NE for %s: %s", country_iso, poly.geom_type)
    return poly


# Buffer applied to the country union before clipping. NE 1:50m has a coastline
# precision around 1–2 km; coastal municipalities (Lisboa, Funchal, Ponta Delgada)
# fall ~400 m–2 km outside the polygon and would be wrongly dropped without it.
# 0.025 deg ≈ 2.7 km — large enough to absorb NE's coastal error, small enough
# that it doesn't bleed across real borders (Strait of Gibraltar is 14 km wide;
# the Pyrenees crest is dozens of km from any major French commune).
_COUNTRY_BUFFER_DEG: float = 0.025


def _clip_features_to_countries(
    features: list[dict[str, Any]],
    country_polys: list[Polygon | MultiPolygon],
) -> list[dict[str, Any]]:
    """Filtra features mantendo apenas aquelas cujo representative_point está
    dentro da união dos polígonos de país (com buffer costeiro).

    Um feature sem geometria polygon (ex: Point) é sempre mantido — não há
    como testá-lo espacialmente sem coordenadas de área.
    """
    if not country_polys:
        return features

    country_union = unary_union(country_polys).buffer(_COUNTRY_BUFFER_DEG)
    kept: list[dict[str, Any]] = []
    removed = 0

    for feat in features:
        geom_type = feat.get("geometry", {}).get("type", "")
        if geom_type not in {"Polygon", "MultiPolygon"}:
            # Pontos / outras geometrias — manter sem testar
            kept.append(feat)
            continue

        try:
            from shapely.geometry import shape as _shape
            shp = _shape(feat["geometry"])
            pt = shp.representative_point()
            if country_union.contains(pt):
                kept.append(feat)
            else:
                removed += 1
                name = feat.get("properties", {}).get("name", "?")
                log.debug("clipped out feature outside country union: %s", name)
        except Exception as exc:
            log.warning("country clip: error testing feature, keeping it: %s", exc)
            kept.append(feat)

    if removed:
        log.info(
            "country clipping removed %d features outside target countries (%d kept)",
            removed, len(kept),
        )
    return kept


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
    *,
    stop_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    """Thin wrapper — delegates to overpass_client.post_query (D-02)."""
    return await overpass_client.post_query(
        query, queue, client_factory, stop_event=stop_event
    )


async def fetch_municipalities(
    country_iso: str,
    queue: asyncio.Queue[str | None],
    *,
    bbox: tuple[float, float, float, float] | None = None,
    clip_iso_codes: list[str] | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
    stop_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    """Busca municípios OSM e retorna GeoJSON FeatureCollection.

    Args:
        country_iso: Código ISO alpha-2 (usado apenas se bbox=None e clip_iso_codes=None).
        queue: Fila SSE para mensagens de progresso.
        bbox: (lat_min, lon_min, lat_max, lon_max) — se fornecido, usa query
              por bounding box (muito mais rápido que por país).
        clip_iso_codes: Lista de códigos ISO alpha-2 a usar para country clipping.
              Quando fornecido, busca os polígonos de fronteira soberana de cada
              país e filtra features cujo representative_point está fora da união.
              Exemplo: ["ES", "PT"] para Ibéria.
              Se None e bbox fornecido, sem clipping (avisa no SSE).
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

    payload = await _post_query(query, queue, client_factory, stop_event=stop_event)

    features: list[dict[str, Any]] = []
    for el in payload.get("elements", []):
        if el.get("type") != "relation":
            continue
        feat = _relation_to_geojson_feature(el)
        if feat is not None:
            features.append(feat)

    await queue.put(f"data: OSM: {len(features)} municípios/regiões encontrados.\n\n")

    # Country clipping: remove features outside the target country polygon(s).
    if clip_iso_codes:
        await queue.put(
            f"data: Clipping geográfico para países: {', '.join(clip_iso_codes)}...\n\n"
        )
        valid_isos: list[str] = []
        for iso in clip_iso_codes:
            try:
                validate_iso_country(iso)
                valid_isos.append(iso)
            except ValueError as exc:
                log.warning("clip_iso_codes: invalid ISO %r skipped: %s", iso, exc)

        country_polys: list[Polygon | MultiPolygon] = []
        for iso in valid_isos:
            poly = await _fetch_country_polygon(iso, queue, client_factory)
            if poly is not None:
                country_polys.append(poly)

        # _fetch_country_polygon reads from the bundled Natural Earth dataset,
        # so country_polys is fully resolved without any network dependency.
        if country_polys:
            before = len(features)
            features = _clip_features_to_countries(features, country_polys)
            after = len(features)
            await queue.put(
                f"data: Clipping: {before - after} features removidas fora dos países alvo "
                f"({after} restantes).\n\n"
            )
        else:
            await queue.put(
                "data: AVISO: Polígonos de fronteira não encontrados — clipping ignorado.\n\n"
            )
    elif bbox is not None:
        await queue.put(
            "data: AVISO: bbox sem clip_iso_codes — features de países vizinhos podem aparecer.\n\n"
        )

    return {"type": "FeatureCollection", "features": features}
