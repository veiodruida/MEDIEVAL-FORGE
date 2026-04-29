"""Phase 2.1 terrain ingestion API. Each endpoint is a stub here — Plans 02-05 each replace ONE stub.

File-ownership convention (so Plans 02-05 can run in parallel without conflicts):
  - Plan 02 owns _overpass_handler implementation
  - Plan 03 owns _hydrosheds_handler implementation
  - Plan 04 owns _dem_handler implementation
  - Plan 05 owns _ridges_handler implementation
  - This module's outer shape (router, route paths) is fixed by Plan 01.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/projects/{project_id}/terrain", tags=["terrain"])


@router.post("/overpass")
async def post_overpass_terrain(project_id: str) -> StreamingResponse:
    """Plan 02: rivers + peaks + coast + parishes via Overpass."""
    raise HTTPException(status_code=501, detail="Plan 02 stub — overpass terrain not yet implemented")


@router.post("/hydrosheds")
async def post_hydrosheds_basins(project_id: str) -> StreamingResponse:
    """Plan 03: HydroSHEDS lv6 basin polygons clipped to bbox."""
    raise HTTPException(status_code=501, detail="Plan 03 stub — hydrosheds not yet implemented")


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
    """Cancel currently-running step. Plans 02-05 each register their stop_event in a shared dict.

    T-01-04 mitigation: scope stop to (project_id, step) — never global.
    """
    raise HTTPException(status_code=501, detail="Stop endpoint stub — wired by Plan 02 first")
