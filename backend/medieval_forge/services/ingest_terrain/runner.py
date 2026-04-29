"""SSE orchestrator for Phase 2.1 terrain steps + (project_id, step) stop_event registry.

T-01-04 mitigation: stop_events are scoped by (project_id, step) tuple, not global.

Deviation from plan spec: db_session_factory parameter added (mirrors ingest_runner.run_ingest)
so tests can inject an in-memory DB session. Rule 3 auto-fix — without it, _resolve_bbox
always uses production AsyncSessionLocal and cannot be unit-tested.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from medieval_forge.models import Project
from medieval_forge.database import AsyncSessionLocal
from medieval_forge.services.paths import ensure_project_dirs
from medieval_forge.services.ingest_runner import _write_geojson_atomic
from medieval_forge.services.ingest_terrain import overpass_terrain
from medieval_forge.services.ingest_terrain import hydrosheds as _hydrosheds

logger = logging.getLogger(__name__)

# (project_id, step) -> asyncio.Event. step ∈ {"overpass","hydrosheds","dem","ridges"}.
_STOP_EVENTS: dict[tuple[str, str], asyncio.Event] = {}


def register_stop_event(project_id: str, step: str) -> asyncio.Event:
    ev = asyncio.Event()
    _STOP_EVENTS[(project_id, step)] = ev
    return ev


def get_stop_event(project_id: str, step: str) -> asyncio.Event | None:
    return _STOP_EVENTS.get((project_id, step))


def clear_stop_event(project_id: str, step: str) -> None:
    _STOP_EVENTS.pop((project_id, step), None)


async def _resolve_bbox(
    project_id: str,
    queue: asyncio.Queue,
    session_factory: async_sessionmaker,
) -> tuple[float, float, float, float] | None:
    """Read (lon_min, lat_min, lon_max, lat_max) from Project row. None if missing."""
    async with session_factory() as session:
        proj = await session.get(Project, project_id)
        if proj is None or proj.bbox_lon_min is None:
            await queue.put(
                "data: ERROR: project bbox não definido — execute Fase 1 "
                "(ingestão de municípios) primeiro.\n\n"
            )
            return None
        return (
            proj.bbox_lon_min,
            proj.bbox_lat_min,
            proj.bbox_lon_max,
            proj.bbox_lat_max,
        )


def _maybe_split_bbox(
    bbox: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """D-21: split bboxes >30° in any axis into halves recursively."""
    lon_min, lat_min, lon_max, lat_max = bbox
    if (lon_max - lon_min) <= 30 and (lat_max - lat_min) <= 30:
        return [bbox]
    # split on longest axis
    if (lon_max - lon_min) >= (lat_max - lat_min):
        mid = (lon_min + lon_max) / 2
        return _maybe_split_bbox((lon_min, lat_min, mid, lat_max)) + _maybe_split_bbox(
            (mid, lat_min, lon_max, lat_max)
        )
    else:
        mid = (lat_min + lat_max) / 2
        return _maybe_split_bbox((lon_min, lat_min, lon_max, mid)) + _maybe_split_bbox(
            (lon_min, mid, lon_max, lat_max)
        )


def _merge_feature_collections(fcs: list[dict]) -> dict:
    feats = []
    for fc in fcs:
        feats.extend(fc.get("features", []))
    return {"type": "FeatureCollection", "features": feats}


async def run_terrain_overpass(
    project_id: str,
    queue: asyncio.Queue,
    *,
    stop_event: asyncio.Event | None = None,
    db_session_factory: async_sessionmaker | None = None,
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning.

    db_session_factory: injected for testing (mirrors ingest_runner.run_ingest).
    Defaults to production AsyncSessionLocal when None.
    """
    factory = db_session_factory or AsyncSessionLocal
    if stop_event is None:
        stop_event = register_stop_event(project_id, "overpass")
    try:
        # Deviation from plan spec: check stop_event BEFORE _resolve_bbox so
        # test_run_terrain_overpass_honors_stop_event sees "Cancelado" message.
        # (Advisor correction: Rule 3 auto-fix.)
        if stop_event.is_set():
            raise asyncio.CancelledError("ingest stopped by user")

        bbox = await _resolve_bbox(project_id, queue, factory)
        if bbox is None:
            return
        await queue.put(f"data: bbox: {bbox}\n\n")
        sub_bboxes = _maybe_split_bbox(bbox)
        if len(sub_bboxes) > 1:
            await queue.put(
                f"data: bbox grande — dividido em {len(sub_bboxes)} sub-áreas (D-21).\n\n"
            )
        raw_dir = ensure_project_dirs(project_id)["raw"]

        for step_name, fetcher, out_file in [
            ("rios",       overpass_terrain.fetch_rivers,     "rivers.geojson"),
            ("topografia", overpass_terrain.fetch_topography, "topography.geojson"),
            ("costa",      overpass_terrain.fetch_coastline,  "coastline.geojson"),
            ("freguesias", overpass_terrain.fetch_parishes,   "parishes.geojson"),
        ]:
            if stop_event.is_set():
                raise asyncio.CancelledError("ingest stopped by user")
            await queue.put(f"data: === {step_name} ===\n\n")
            fcs = []
            for sub in sub_bboxes:
                fcs.append(await fetcher(sub, queue, stop_event=stop_event))
            merged = _merge_feature_collections(fcs)
            _write_geojson_atomic(raw_dir / out_file, merged)
            await queue.put(
                f"data: {step_name}: {len(merged['features'])} features → {out_file}\n\n"
            )
        await queue.put("data: DONE\n\n")
    except asyncio.CancelledError:
        await queue.put("data: Cancelado pelo usuário.\n\n")
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_terrain_overpass failed")
        # T-02-05: only emit exception class name in SSE; full repr to logs.
        await queue.put(f"data: ERROR: {exc.__class__.__name__}\n\n")
    finally:
        clear_stop_event(project_id, "overpass")
        await queue.put(None)


async def run_terrain_hydrosheds(
    project_id: str,
    queue: asyncio.Queue,
    *,
    stop_event: asyncio.Event | None = None,
    db_session_factory: async_sessionmaker | None = None,
) -> None:
    """Producer task: clip HydroSHEDS lv6 basins to project bbox, write raw/basins.geojson.

    db_session_factory: injected for testing (mirrors run_terrain_overpass pattern).
    Defaults to production AsyncSessionLocal when None.

    T-03-03 mitigation: geopandas.read_file with bbox= filters at GDAL layer;
    asyncio.to_thread keeps the event loop free during the blocking call.
    """
    factory = db_session_factory or AsyncSessionLocal
    if stop_event is None:
        stop_event = register_stop_event(project_id, "hydrosheds")
    try:
        if stop_event.is_set():
            raise asyncio.CancelledError("ingest stopped by user")

        bbox = await _resolve_bbox(project_id, queue, factory)
        if bbox is None:
            return
        await queue.put(f"data: bbox: {bbox}\n\n")
        raw_dir = ensure_project_dirs(project_id)["raw"]
        fc = await _hydrosheds.fetch_basins(bbox, queue, stop_event=stop_event)
        _write_geojson_atomic(raw_dir / "basins.geojson", fc)
        await queue.put(f"data: bacias: {len(fc['features'])} features → basins.geojson\n\n")
        await queue.put("data: DONE\n\n")
    except asyncio.CancelledError:
        await queue.put("data: Cancelado pelo usuário.\n\n")
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_terrain_hydrosheds failed")
        await queue.put(f"data: ERROR: {exc.__class__.__name__}\n\n")
    finally:
        clear_stop_event(project_id, "hydrosheds")
        await queue.put(None)
