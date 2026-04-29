"""Phase 2.1 terrain ingestion API. Plans 02-05 each replace ONE stub.

File-ownership convention (so Plans 02-05 can run in parallel without conflicts):
  - Plan 02 owns /overpass + /stop implementation (this plan)
  - Plan 03 owns _hydrosheds_handler implementation
  - Plan 04 owns _dem_handler implementation
  - Plan 05 owns _ridges_handler implementation
  - This module's outer shape (router, route paths) is fixed by Plan 01.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from medieval_forge.services.paths import is_valid_uuid
from medieval_forge.services.ingest_terrain import runner as terrain_runner

router = APIRouter(prefix="/projects/{project_id}/terrain", tags=["terrain"])


async def _stream_from_queue(queue: asyncio.Queue):
    """Consume queue until None sentinel, yielding SSE strings."""
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


@router.post("/overpass")
async def post_overpass_terrain(project_id: str) -> StreamingResponse:
    """Plan 02: rivers + peaks + coast + parishes via Overpass.

    T-02-02 / T-PATH: project_id is UUID-validated before use.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="invalid project_id")
    queue: asyncio.Queue = asyncio.Queue()
    stop_event = terrain_runner.register_stop_event(project_id, "overpass")
    asyncio.create_task(
        terrain_runner.run_terrain_overpass(project_id, queue, stop_event=stop_event)
    )
    return StreamingResponse(_stream_from_queue(queue), media_type="text/event-stream")


@router.post("/hydrosheds")
async def post_hydrosheds_basins(project_id: str) -> StreamingResponse:
    """Plan 03: HydroSHEDS lv6 basin polygons clipped to bbox → raw/basins.geojson.

    T-03-01: project_id validated via is_valid_uuid before use.
    Shapefile path is constructed via importlib.resources in hydrosheds.py — no user input.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="invalid project_id")
    queue: asyncio.Queue = asyncio.Queue()
    stop_event = terrain_runner.register_stop_event(project_id, "hydrosheds")
    asyncio.create_task(
        terrain_runner.run_terrain_hydrosheds(project_id, queue, stop_event=stop_event)
    )
    return StreamingResponse(_stream_from_queue(queue), media_type="text/event-stream")


@router.post("/dem")
async def post_dem(project_id: str) -> StreamingResponse:
    """Plan 04: Copernicus DEM 90m mosaic."""
    raise HTTPException(status_code=501, detail="Plan 04 stub — DEM not yet implemented")


@router.post("/ridges")
async def post_ridges(project_id: str, sensitivity: str = "med") -> StreamingResponse:
    """Plan 05: DEM-derived ridges (low/med/high sensitivity)."""
    raise HTTPException(status_code=501, detail="Plan 05 stub — ridges not yet implemented")


@router.post("/stop")
async def post_stop_terrain(project_id: str, step: str) -> dict:
    """Cancel currently-running step.

    T-02-02: project_id is UUID-validated; step is whitelisted;
    stop_event is keyed on (project_id, step) — cannot cancel another project's run.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="invalid project_id")
    if step not in {"overpass", "hydrosheds", "dem", "ridges"}:
        raise HTTPException(status_code=400, detail=f"invalid step: {step}")
    ev = terrain_runner.get_stop_event(project_id, step)
    if ev is None:
        return {"status": "no-active-step"}
    ev.set()
    return {"status": "stopping", "project_id": project_id, "step": step}
