"""INGEST-01: Wikidata SPARQL paginated municipality fetcher.

DEPRECATED (Etapa 12, 2026-04-28): Wikidata is now a SECONDARY ingestion path,
retained only as a points-only fallback when OSM fails for a given bounding box.
The recommended flow is OSM (see ingest_osm.py) which provides real polygons.
The frontend hides this provider behind an "Avançado" (Advanced) disclosure in
Step 1 of ProjectDetail. Do NOT promote this back to a primary CTA without
revisiting the points-only / no-polygons UX limitation that produces all-blue
maps downstream.

T-SSRF mitigation: validate_qid enforces ^Q\\d+$ before composing the query;
endpoint URL is a hardcoded constant — never assembled from user input.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Callable

import httpx

WIKIDATA_ENDPOINT: str = "https://query.wikidata.org/sparql"
USER_AGENT: str = (
    "MedievalForge/0.1 (https://github.com/user/medieval-forge; "
    "local map authoring tool)"
)
QID_RE: re.Pattern[str] = re.compile(r"^Q\d+$")

_PAGE_TIMEOUT_S: float = 70.0  # Wikidata hard limit is 60s; client timeout ~70s


def validate_qid(value: str) -> str:
    """Raise ValueError if `value` is not a Wikidata QID (`Q` followed by digits)."""
    if not isinstance(value, str) or not QID_RE.match(value):
        raise ValueError(f"invalid Wikidata QID: {value!r} (expected pattern ^Q\\d+$)")
    return value


def _parse_qid_list(country_qid: str) -> list[str]:
    """Parse a comma-separated QID string into a validated list.

    Supports both single QIDs ("Q45") and multi-country presets ("Q29,Q45").
    """
    qids = [q.strip() for q in country_qid.split(",") if q.strip()]
    if not qids:
        raise ValueError(f"empty QID list: {country_qid!r}")
    for q in qids:
        validate_qid(q)
    return qids


def _build_query(country_qids: list[str], limit: int, offset: int) -> str:
    # VALUES clause supports both single and multi-country queries safely.
    # Each QID has already been validated by _parse_qid_list.
    values = " ".join(f"wd:{q}" for q in country_qids)
    return f"""
    SELECT ?item ?itemLabel ?lat ?lon WHERE {{
      VALUES ?country {{ {values} }}
      ?item wdt:P31/wdt:P279* wd:Q15284 .
      ?item wdt:P17 ?country .
      ?item wdt:P625 ?coords .
      BIND(geof:latitude(?coords) AS ?lat)
      BIND(geof:longitude(?coords) AS ?lon)
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
    OFFSET {offset}
    """


def _binding_to_feature(b: dict[str, Any]) -> dict[str, Any]:
    qid_url = b.get("item", {}).get("value", "")
    qid = qid_url.rsplit("/", 1)[-1] if qid_url else ""
    label = b.get("itemLabel", {}).get("value", "")
    lat = float(b.get("lat", {}).get("value", "nan"))
    lon = float(b.get("lon", {}).get("value", "nan"))
    return {
        "type": "Feature",
        "properties": {"qid": qid, "label": label},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


async def fetch_municipalities(
    country_qid: str,
    queue: asyncio.Queue[str | None],
    page_size: int = 500,
    *,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> dict[str, Any]:
    """Paginate SPARQL; return GeoJSON FeatureCollection.

    T-SSRF: every QID in country_qid is validated before query composition.
    Supports comma-separated multi-country presets (e.g. "Q29,Q45" for Iberia).
    """
    qids = _parse_qid_list(country_qid)
    if page_size < 1 or page_size > 1000:
        raise ValueError("page_size must be between 1 and 1000")

    features: list[dict[str, Any]] = []
    offset = 0

    def _factory() -> httpx.AsyncClient:
        if client_factory is not None:
            return client_factory()
        return httpx.AsyncClient(timeout=_PAGE_TIMEOUT_S)

    async with _factory() as client:
        while True:
            await queue.put(
                f"data: Fetching Wikidata page offset={offset} "
                f"(running total={len(features)})...\n\n"
            )
            query = _build_query(qids, page_size, offset)
            resp = await client.get(
                WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/sparql-results+json",
                },
            )
            resp.raise_for_status()
            bindings = resp.json().get("results", {}).get("bindings", [])
            features.extend(_binding_to_feature(b) for b in bindings)
            if len(bindings) < page_size:
                break
            offset += page_size

    await queue.put(
        f"data: Wikidata fetch complete: {len(features)} features.\n\n"
    )
    return {"type": "FeatureCollection", "features": features}
