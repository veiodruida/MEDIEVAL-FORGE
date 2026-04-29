"""Wave 0 RED tests for bbox backfill in ingest_runner (Plan 02.1-01, Task 0).

These tests MUST fail until Task 2 adds _backfill_bbox to ingest_runner.py.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from shapely.geometry import mapping
from shapely.geometry import box as _shp_box
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_polygon_feature(minx: float, miny: float, maxx: float, maxy: float) -> dict[str, Any]:
    """Return a GeoJSON Feature wrapping a rectangular Shapely polygon."""
    poly = _shp_box(minx, miny, maxx, maxy)
    return {
        "type": "Feature",
        "properties": {},
        "geometry": dict(mapping(poly)),
    }


def _make_feature_collection(*features: dict[str, Any]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_writes_bbox_to_project(sample_project, tmp_raw_dir, monkeypatch):
    """After a successful OSM ingest the project.bbox_* columns are populated."""
    from medieval_forge.services import ingest_runner

    project_id, factory = sample_project
    pid_raw, raw_dir = tmp_raw_dir

    # Build a FeatureCollection with 2 known polygons.
    feat1 = _make_polygon_feature(-1.2, 46.4, -1.1, 46.5)
    feat2 = _make_polygon_feature(-1.1, 46.45, -1.0, 46.6)
    fc = _make_feature_collection(feat1, feat2)

    expected_union = unary_union([
        _shp_box(-1.2, 46.4, -1.1, 46.5),
        _shp_box(-1.1, 46.45, -1.0, 46.6),
    ])
    exp_minx, exp_miny, exp_maxx, exp_maxy = expected_union.bounds

    # Stub the OSM fetcher to return our FeatureCollection.
    async def _fake_fetch(*args, **kwargs):
        return fc

    monkeypatch.setattr(ingest_runner.ingest_osm, "fetch_municipalities", _fake_fetch)

    # Override project_id from tmp_raw_dir — use the one from sample_project instead,
    # so the DB row exists; also ensure the raw dir exists under that project_id.
    import uuid as _uuid
    from medieval_forge.services import paths as _paths
    _paths.ensure_project_dirs(project_id)

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    stop = asyncio.Event()

    await ingest_runner.run_ingest(
        project_id=project_id,
        source="osm",
        country="FR",
        queue=queue,
        db_session_factory=factory,
        stop_event=stop,
    )

    # Drain queue
    while not queue.empty():
        queue.get_nowait()

    # Reload project from DB
    from sqlalchemy.ext.asyncio import AsyncSession
    async with factory() as session:
        from medieval_forge.models import Project
        proj = await session.get(Project, project_id)

    assert proj is not None
    assert proj.bbox_lon_min == pytest.approx(exp_minx)
    assert proj.bbox_lon_max == pytest.approx(exp_maxx)
    assert proj.bbox_lat_min == pytest.approx(exp_miny)
    assert proj.bbox_lat_max == pytest.approx(exp_maxy)


@pytest.mark.asyncio
async def test_run_ingest_skips_bbox_when_no_features(sample_project, monkeypatch):
    """Empty FeatureCollection leaves project.bbox_* as None."""
    from medieval_forge.services import ingest_runner

    project_id, factory = sample_project

    async def _fake_fetch(*args, **kwargs):
        return {"type": "FeatureCollection", "features": []}

    monkeypatch.setattr(ingest_runner.ingest_osm, "fetch_municipalities", _fake_fetch)

    from medieval_forge.services import paths as _paths
    _paths.ensure_project_dirs(project_id)

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await ingest_runner.run_ingest(
        project_id=project_id,
        source="osm",
        country="FR",
        queue=queue,
        db_session_factory=factory,
    )

    while not queue.empty():
        queue.get_nowait()

    async with factory() as session:
        from medieval_forge.models import Project
        proj = await session.get(Project, project_id)

    assert proj is not None
    assert proj.bbox_lon_min is None
    assert proj.bbox_lon_max is None
    assert proj.bbox_lat_min is None
    assert proj.bbox_lat_max is None


@pytest.mark.asyncio
async def test_run_ingest_skips_bbox_on_cancellation(sample_project, monkeypatch):
    """When CancelledError is raised (stop_event), bbox is NOT written to the project."""
    from medieval_forge.services import ingest_runner

    project_id, factory = sample_project

    stop = asyncio.Event()

    async def _fake_fetch(*args, **kwargs):
        # Simulate stop_event being set inside the fetcher
        stop.set()
        raise asyncio.CancelledError("ingest stopped by user")

    monkeypatch.setattr(ingest_runner.ingest_osm, "fetch_municipalities", _fake_fetch)

    from medieval_forge.services import paths as _paths
    _paths.ensure_project_dirs(project_id)

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await ingest_runner.run_ingest(
        project_id=project_id,
        source="osm",
        country="FR",
        queue=queue,
        db_session_factory=factory,
        stop_event=stop,
    )

    while not queue.empty():
        queue.get_nowait()

    async with factory() as session:
        from medieval_forge.models import Project
        proj = await session.get(Project, project_id)

    assert proj is not None
    assert proj.bbox_lon_min is None, "bbox must NOT be written when ingestion is cancelled"
    assert proj.bbox_lon_max is None
    assert proj.bbox_lat_min is None
    assert proj.bbox_lat_max is None
