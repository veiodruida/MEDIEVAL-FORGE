"""Tests for INGEST-01..04 and T-SSRF guards."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


# ---------- T-SSRF: validators reject malformed input ----------

def test_validate_qid_rejects_non_qid_strings():
    from medieval_forge.services.ingest_wikidata import validate_qid

    validate_qid("Q29")  # ok
    validate_qid("Q1234567")  # ok
    for bad in ["q29", "spain", "29", "Q", "../etc/passwd", "Q29; DROP TABLE"]:
        with pytest.raises(ValueError):
            validate_qid(bad)


def test_validate_iso_country_rejects_bad_format():
    from medieval_forge.services.ingest_osm import validate_iso_country

    validate_iso_country("ES")
    validate_iso_country("PT")
    for bad in ["es", "ESP", "E", "12", "../", "ES; DROP"]:
        with pytest.raises(ValueError):
            validate_iso_country(bad)


# ---------- INGEST-01: Wikidata pagination ----------

class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    """Yields a sequence of fake JSON payloads for successive .get() calls."""

    def __init__(self, payloads: list[dict[str, Any]]):
        self._payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if not self._payloads:
            return _FakeResponse({"results": {"bindings": []}})
        return _FakeResponse(self._payloads.pop(0))

    async def post(self, url, data=None):
        return _FakeResponse(self._payloads.pop(0) if self._payloads else {})


def _binding(qid_num: int):
    return {
        "item": {"value": f"http://www.wikidata.org/entity/Q{qid_num}"},
        "itemLabel": {"value": f"Place {qid_num}"},
        "lat": {"value": "40.0"},
        "lon": {"value": "-3.0"},
    }


async def test_wikidata_pagination():
    from medieval_forge.services.ingest_wikidata import fetch_municipalities

    # Two pages: first 500 items, second 200 items (terminates).
    page1 = {"results": {"bindings": [_binding(i) for i in range(500)]}}
    page2 = {"results": {"bindings": [_binding(500 + i) for i in range(200)]}}
    fake = _FakeClient([page1, page2])
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    result = await fetch_municipalities(
        "Q29", queue, page_size=500, client_factory=lambda: fake
    )

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 700
    # SSE messages: 2 "Fetching page" + 1 "complete" = 3 puts (plus possibly intermediate)
    assert queue.qsize() >= 3
    # Verify pagination params advanced.
    assert len(fake.calls) == 2
    assert "OFFSET 0" in fake.calls[0]["params"]["query"]
    assert "OFFSET 500" in fake.calls[1]["params"]["query"]
    # T-SSRF: query contains ONLY validated QID, never raw user input.
    assert "wd:Q29" in fake.calls[0]["params"]["query"]


# ---------- INGEST-02: OSM fallback ----------

# Helper: build an OSM-style relation dict from a list of way-member geometries.
def _osm_relation(
    rel_id: int,
    name: str,
    outer_ways: list[list[tuple[float, float]]],
    inner_ways: list[list[tuple[float, float]]] | None = None,
    admin_level: str = "6",
) -> dict:
    members = []
    for pts in outer_ways:
        members.append({
            "role": "outer",
            "geometry": [{"lon": x, "lat": y} for x, y in pts],
        })
    for pts in (inner_ways or []):
        members.append({
            "role": "inner",
            "geometry": [{"lon": x, "lat": y} for x, y in pts],
        })
    return {
        "type": "relation",
        "id": rel_id,
        "tags": {"name": name, "admin_level": admin_level, "boundary": "administrative"},
        "members": members,
    }


# Four outer ways forming a unit square (each way = one edge).
_SQUARE_OUTER_WAYS = [
    [(0.0, 0.0), (1.0, 0.0)],
    [(1.0, 0.0), (1.0, 1.0)],
    [(1.0, 1.0), (0.0, 1.0)],
    [(0.0, 1.0), (0.0, 0.0)],
]

# Four inner ways forming a small square hole (0.2–0.8 in both axes).
_HOLE_INNER_WAYS = [
    [(0.2, 0.2), (0.8, 0.2)],
    [(0.8, 0.2), (0.8, 0.8)],
    [(0.8, 0.8), (0.2, 0.8)],
    [(0.2, 0.8), (0.2, 0.2)],
]

# Two disjoint squares: [0,1]x[0,1] and [2,3]x[0,1].
_ISLAND_OUTER_WAYS = [
    # square A
    [(0.0, 0.0), (1.0, 0.0)],
    [(1.0, 0.0), (1.0, 1.0)],
    [(1.0, 1.0), (0.0, 1.0)],
    [(0.0, 1.0), (0.0, 0.0)],
    # square B
    [(2.0, 0.0), (3.0, 0.0)],
    [(3.0, 0.0), (3.0, 1.0)],
    [(3.0, 1.0), (2.0, 1.0)],
    [(2.0, 1.0), (2.0, 0.0)],
]


async def test_osm_fallback():
    """INGEST-02 end-to-end: single properly-closed outer ring produces one Polygon feature."""
    from medieval_forge.services.ingest_osm import fetch_municipalities

    # Single outer way that is already closed (first == last point).
    closed_way = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]
    overpass_payload = {
        "elements": [
            _osm_relation(1, "Province A", [closed_way], admin_level="8"),
            {"type": "node", "id": 2},  # filtered out
        ]
    }
    fake = _FakeClient([overpass_payload])
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    result = await fetch_municipalities("ES", queue, client_factory=lambda: fake)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    feat = result["features"][0]
    assert feat["geometry"]["type"] == "Polygon"
    assert feat["properties"]["name"] == "Province A"
    # Outer ring must be closed.
    ring = feat["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]


# ---------- _relation_to_geojson_feature unit tests ----------

def test_relation_simple_square():
    """Four outer ways forming one square → single Polygon, 1 outer ring."""
    from medieval_forge.services.ingest_osm import _relation_to_geojson_feature

    rel = _osm_relation(10, "Square", _SQUARE_OUTER_WAYS)
    feat = _relation_to_geojson_feature(rel)

    assert feat is not None
    assert feat["geometry"]["type"] == "Polygon"
    coords = feat["geometry"]["coordinates"]
    # Exactly one ring (outer), no holes.
    assert len(coords) == 1
    # Ring must be closed.
    assert coords[0][0] == coords[0][-1]
    # Basic area sanity: unit square ≈ 1.0 sq-deg.
    from shapely.geometry import shape
    poly = shape(feat["geometry"])
    assert abs(poly.area - 1.0) < 1e-6


def test_relation_with_hole():
    """Four outer + four inner ways → Polygon with 1 outer ring and 1 hole."""
    from medieval_forge.services.ingest_osm import _relation_to_geojson_feature

    rel = _osm_relation(20, "DonutSquare", _SQUARE_OUTER_WAYS, _HOLE_INNER_WAYS)
    feat = _relation_to_geojson_feature(rel)

    assert feat is not None
    assert feat["geometry"]["type"] == "Polygon"
    coords = feat["geometry"]["coordinates"]
    # Two rings: outer + one hole.
    assert len(coords) == 2
    # Both rings closed.
    assert coords[0][0] == coords[0][-1]
    assert coords[1][0] == coords[1][-1]
    # Area of donut is less than full square.
    from shapely.geometry import shape
    poly = shape(feat["geometry"])
    assert poly.area < 1.0
    assert poly.area > 0.0


def test_relation_multi_island():
    """Eight outer ways forming two disjoint squares → MultiPolygon with 2 parts."""
    from medieval_forge.services.ingest_osm import _relation_to_geojson_feature

    rel = _osm_relation(30, "Islands", _ISLAND_OUTER_WAYS)
    feat = _relation_to_geojson_feature(rel)

    assert feat is not None
    assert feat["geometry"]["type"] == "MultiPolygon"
    parts = feat["geometry"]["coordinates"]
    assert len(parts) == 2


def test_relation_malformed_returns_none(caplog):
    """Outer ways with a gap (don't close) → returns None and logs a warning."""
    import logging
    from medieval_forge.services.ingest_osm import _relation_to_geojson_feature

    # Three disconnected edges — no closing path, so polygonize yields nothing.
    broken_ways = [
        [(0.0, 0.0), (1.0, 0.0)],   # bottom
        [(1.0, 0.0), (1.0, 1.0)],   # right
        [(5.0, 5.0), (6.0, 5.0)],   # disconnected — leaves a gap
    ]
    rel = _osm_relation(40, "Broken", broken_ways)

    with caplog.at_level(logging.WARNING, logger="medieval_forge.services.ingest_osm"):
        result = _relation_to_geojson_feature(rel)

    assert result is None
    assert any("do not form closed ring" in r.message for r in caplog.records)


def test_relation_no_outer_returns_none():
    """Relation with only inner members and no outer ways → returns None."""
    from medieval_forge.services.ingest_osm import _relation_to_geojson_feature

    rel = _osm_relation(50, "NoOuter", outer_ways=[], inner_ways=_HOLE_INNER_WAYS)
    result = _relation_to_geojson_feature(rel)
    assert result is None


# ---------- Tasks 3 and 4 tests (stubs until implemented) ----------

async def test_geojson_written(tmp_path, monkeypatch):
    """run_ingest writes raw/municipalities.geojson and updates project.status (INGEST-03)."""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    from medieval_forge.models import Base, Project
    from medieval_forge.services import ingest_runner, ingest_wikidata
    from medieval_forge.services import paths as paths_mod

    # Redirect PROJECTS_ROOT to tmp_path.
    fake_root = tmp_path / "projects"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

    # Build a dedicated in-memory DB for this test.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    # Insert a project row.
    pid = "12345678-1234-4234-8234-123456789abc"
    async with sf() as session:
        session.add(Project(
            id=pid, name="ingest-test", country_qid="Q29",
            period_start=800, period_end=1000, status="created",
        ))
        await session.commit()

    # Stub the wikidata fetcher to avoid network calls.
    async def fake_fetch(country_qid, queue, page_size=500, *, client_factory=None):
        await queue.put("data: stub fetching...\n\n")
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"qid": "Q1", "label": "Stub"},
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            }],
        }
    monkeypatch.setattr(ingest_wikidata, "fetch_municipalities", fake_fetch)

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await ingest_runner.run_ingest(pid, "wikidata", "Q29", queue, db_session_factory=sf)

    # Verify file written.
    geojson_path = fake_root / pid / "raw" / "municipalities.geojson"
    assert geojson_path.exists()
    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1

    # Verify status updated in the dedicated engine.
    async with sf() as session:
        proj = await session.get(Project, pid)
        assert proj.status == "ingested"

    await engine.dispose()


async def test_sse_stream_invalid_uuid_returns_400(client):
    resp = await client.post("/api/projects/not-a-uuid/ingest?source=wikidata")
    assert resp.status_code == 400


async def test_sse_stream(client, tmp_path, monkeypatch):
    """Endpoint streams SSE messages from the runner queue end-to-end."""
    from medieval_forge.services import ingest_wikidata
    from medieval_forge.services import paths as paths_mod

    # Isolate filesystem.
    fake_root = tmp_path / "projects"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

    # Stub the network fetch.
    async def fake_fetch(country_qid, queue, page_size=500, *, client_factory=None):
        await queue.put("data: stub page 1\n\n")
        await queue.put("data: stub page 2\n\n")
        return {"type": "FeatureCollection", "features": []}
    monkeypatch.setattr(ingest_wikidata, "fetch_municipalities", fake_fetch)

    created = (await client.post("/api/projects", json={
        "name": "sse",
        "country_qid": "Q29",
        "period_start": 800,
        "period_end": 1000,
    })).json()
    pid = created["id"]

    # Stream the SSE response and collect events.
    async with client.stream("POST", f"/api/projects/{pid}/ingest?source=wikidata") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body_chunks: list[str] = []
        async for chunk in resp.aiter_text():
            body_chunks.append(chunk)
    full_body = "".join(body_chunks)
    # Verify expected event substrings (the producer emits Starting, stub page 1/2, Wrote, DONE).
    assert "Starting wikidata ingest" in full_body
    assert "stub page 1" in full_body
    assert "stub page 2" in full_body
    assert "DONE" in full_body
