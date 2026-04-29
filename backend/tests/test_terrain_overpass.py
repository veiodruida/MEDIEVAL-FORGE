"""Phase 2.1 Plan 02 — RED tests for 4 Overpass terrain fetchers + runner SSE.

Wave 0: tests must FAIL (ImportError) until overpass_terrain.py and runner.py are created.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import respx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medieval_forge.models import Base, Project
from medieval_forge.services import overpass_client

# These imports must fail at collection time — that's the RED state.
from medieval_forge.services.ingest_terrain.overpass_terrain import (
    fetch_rivers,
    fetch_topography,
    fetch_coastline,
    fetch_parishes,
)
from medieval_forge.services.ingest_terrain.runner import run_terrain_overpass


FIXTURES_DIR = Path(__file__).parent / "fixtures"

SAMPLE_BBOX = (-1.2, 46.4, -1.0, 46.6)  # (lon_min, lat_min, lon_max, lat_max)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / "responses_recorded" / f"{name}.json").read_text())


def _mock_all_endpoints(respx_mock, payload: dict) -> None:
    """Register the given payload on all 3 OVERPASS_ENDPOINTS."""
    for ep in overpass_client.OVERPASS_ENDPOINTS:
        respx_mock.post(ep).mock(return_value=httpx.Response(200, json=payload))


# ---------------------------------------------------------------------------
# Composed fixture: in-memory DB + tmp_raw_dir for runner tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def terrain_env(monkeypatch, tmp_path):
    """Yield (project_id, raw_dir, session_factory) with bbox populated and
    PROJECTS_ROOT monkeypatched to tmp_path.
    """
    from medieval_forge.services import paths

    monkeypatch.setattr(paths, "PROJECTS_ROOT", tmp_path / "projects")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create a project with bbox populated (simulating end-of-phase-1 backfill).
    import uuid as _uuid
    pid = str(_uuid.uuid4())
    async with factory() as session:
        proj = Project(
            id=pid,
            name="Terrain Test",
            country_qid="Q142",
            period_start=800,
            period_end=900,
        )
        proj.bbox_lon_min = -1.2
        proj.bbox_lat_min = 46.4
        proj.bbox_lon_max = -1.0
        proj.bbox_lat_max = 46.6
        session.add(proj)
        await session.commit()

    dirs = paths.ensure_project_dirs(pid)
    yield pid, dirs["raw"], factory

    await engine.dispose()


# ---------------------------------------------------------------------------
# rivers (GEO-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_rivers_returns_feature_collection(respx_mock):
    payload = load_fixture("overpass_rivers")
    _mock_all_endpoints(respx_mock, payload)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    result = await fetch_rivers(SAMPLE_BBOX, queue, stop_event=stop)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 2


@pytest.mark.asyncio
async def test_fetch_rivers_property_schema(respx_mock):
    payload = load_fixture("overpass_rivers")
    _mock_all_endpoints(respx_mock, payload)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    result = await fetch_rivers(SAMPLE_BBOX, queue, stop_event=stop)

    for feat in result["features"]:
        props = feat["properties"]
        assert set(props.keys()) == {"id", "waterway", "name"}
        assert props["waterway"] in {"river", "stream"}
        assert isinstance(props["id"], int)

    # The river (id=42) should have name "Lay"; the stream (id=43) has no name.
    by_id = {f["properties"]["id"]: f["properties"] for f in result["features"]}
    assert by_id[42]["name"] == "Lay"
    assert by_id[43]["name"] is None


@pytest.mark.asyncio
async def test_fetch_rivers_geometry_is_linestring(respx_mock):
    payload = load_fixture("overpass_rivers")
    _mock_all_endpoints(respx_mock, payload)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    result = await fetch_rivers(SAMPLE_BBOX, queue, stop_event=stop)

    for feat in result["features"]:
        assert feat["geometry"]["type"] == "LineString"


# ---------------------------------------------------------------------------
# topography (GEO-02)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_topography_includes_peak_with_elevation(respx_mock):
    payload = load_fixture("overpass_topography")
    _mock_all_endpoints(respx_mock, payload)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    result = await fetch_topography(SAMPLE_BBOX, queue, stop_event=stop)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1

    feat = result["features"][0]
    props = feat["properties"]
    assert props["natural"] == "peak"
    assert props["name"] == "Mont Test"
    assert props["ele"] == 234.0
    assert isinstance(props["ele"], float)
    assert props["id"] == 100
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [-1.05, 46.5]


# ---------------------------------------------------------------------------
# coastline (GEO-03)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_coastline_returns_single_multilinestring_feature(respx_mock):
    """Contract: even when line_merge produces a single LineString, wrap to MultiLineString."""
    payload = load_fixture("overpass_coast")
    _mock_all_endpoints(respx_mock, payload)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    result = await fetch_coastline(SAMPLE_BBOX, queue, stop_event=stop)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    feat = result["features"][0]
    # Pitfall 2: must be MultiLineString (not LineString) even when only 1 way.
    assert feat["geometry"]["type"] == "MultiLineString"
    assert feat["properties"] == {}


# ---------------------------------------------------------------------------
# parishes (GEO-04)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_parishes_returns_empty_when_no_results(respx_mock):
    """Empty Overpass response → empty FeatureCollection."""
    payload = load_fixture("overpass_parishes")  # elements: []
    _mock_all_endpoints(respx_mock, payload)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    result = await fetch_parishes(SAMPLE_BBOX, queue, stop_event=stop)

    assert result == {"type": "FeatureCollection", "features": []}


@pytest.mark.asyncio
async def test_fetch_parishes_emits_graceful_log_on_empty(respx_mock):
    """D-04: SSE log must contain 'Sem parishes' when no results."""
    payload = load_fixture("overpass_parishes")
    _mock_all_endpoints(respx_mock, payload)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    await fetch_parishes(SAMPLE_BBOX, queue, stop_event=stop)

    # Drain the queue and look for the graceful-empty message.
    messages = []
    while not queue.empty():
        msg = queue.get_nowait()
        if msg is not None:
            messages.append(msg)

    assert any("Sem parishes" in m for m in messages), (
        f"Expected 'Sem parishes' in SSE messages, got: {messages}"
    )


# ---------------------------------------------------------------------------
# runner SSE (GEO-08 foundation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_terrain_overpass_writes_four_files(terrain_env, respx_mock):
    """Runner writes rivers/topography/coastline/parishes.geojson to raw_dir."""
    project_id, raw_dir, factory = terrain_env

    _mock_all_endpoints(respx_mock, load_fixture("overpass_rivers"))
    # Since all endpoints share the same mock, the first fixture (rivers) responds.
    # We need each call to respond with the appropriate fixture.
    # Clear and re-register with per-call routing using side_effect.
    respx_mock.reset()

    call_index = [0]
    fixtures_in_order = [
        load_fixture("overpass_rivers"),
        load_fixture("overpass_topography"),
        load_fixture("overpass_coast"),
        load_fixture("overpass_parishes"),
    ]

    def _side_effect(request):
        idx = call_index[0] % len(fixtures_in_order)
        call_index[0] += 1
        return httpx.Response(200, json=fixtures_in_order[idx])

    for ep in overpass_client.OVERPASS_ENDPOINTS:
        respx_mock.post(ep).mock(side_effect=_side_effect)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    await run_terrain_overpass(
        project_id, queue, stop_event=stop, db_session_factory=factory
    )

    assert (raw_dir / "rivers.geojson").exists()
    assert (raw_dir / "topography.geojson").exists()
    assert (raw_dir / "coastline.geojson").exists()
    assert (raw_dir / "parishes.geojson").exists()

    for fname in ["rivers.geojson", "topography.geojson", "coastline.geojson", "parishes.geojson"]:
        data = json.loads((raw_dir / fname).read_text())
        assert data["type"] == "FeatureCollection"


@pytest.mark.asyncio
async def test_run_terrain_overpass_atomic_writes_no_tmp_left(terrain_env, respx_mock):
    """After successful run, no *.geojson.tmp files should remain in raw_dir."""
    project_id, raw_dir, factory = terrain_env

    respx_mock.reset()
    call_index = [0]
    fixtures_in_order = [
        load_fixture("overpass_rivers"),
        load_fixture("overpass_topography"),
        load_fixture("overpass_coast"),
        load_fixture("overpass_parishes"),
    ]

    def _side_effect(request):
        idx = call_index[0] % len(fixtures_in_order)
        call_index[0] += 1
        return httpx.Response(200, json=fixtures_in_order[idx])

    for ep in overpass_client.OVERPASS_ENDPOINTS:
        respx_mock.post(ep).mock(side_effect=_side_effect)

    queue = asyncio.Queue()
    stop = asyncio.Event()
    await run_terrain_overpass(
        project_id, queue, stop_event=stop, db_session_factory=factory
    )

    tmp_files = list(raw_dir.glob("*.geojson.tmp"))
    assert tmp_files == [], f"Unexpected .tmp files remaining: {tmp_files}"


@pytest.mark.asyncio
async def test_run_terrain_overpass_honors_stop_event(terrain_env):
    """stop_event set before run → no files written + 'Cancelado' message in queue."""
    project_id, raw_dir, factory = terrain_env

    queue = asyncio.Queue()
    stop = asyncio.Event()
    stop.set()  # Set BEFORE calling run

    await run_terrain_overpass(
        project_id, queue, stop_event=stop, db_session_factory=factory
    )

    # No files should have been written.
    assert not (raw_dir / "rivers.geojson").exists()
    assert not (raw_dir / "topography.geojson").exists()
    assert not (raw_dir / "coastline.geojson").exists()
    assert not (raw_dir / "parishes.geojson").exists()

    # Queue must contain the cancellation message.
    messages = []
    while not queue.empty():
        msg = queue.get_nowait()
        if msg is not None:
            messages.append(msg)

    assert any("Cancelado" in m for m in messages), (
        f"Expected 'Cancelado' message, got: {messages}"
    )
