"""Phase 4 edit endpoints. Thin request/response layer over services/voronoi.py."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    MoveCapitalRequest, MoveCapitalResponse,
    MergeRequest, MergeResponse,
    SplitRequest, SplitResponse,
    ReshapeGeometryRequest,
    SaveSnapshotRequest,
    VertexHandle, VertexHandlesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_capitals(project_id: str) -> dict[str, tuple[float, float]]:
    """Read capital lon/lat from territory_metadata.json.

    territories.geojson stores only id/name/neighbors in feature properties;
    real lon/lat live in territory_metadata.json under condados[].
    Returns empty dict if metadata is missing — caller falls back to defaults.
    """
    from ..services.paths import project_dir
    try:
        meta_path = project_dir(project_id) / "generated" / "territory_metadata.json"
    except ValueError:
        return {}
    if not meta_path.exists():
        return {}
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    return {c["id"]: (c["lon"], c["lat"]) for c in metadata.get("condados", []) if "lon" in c and "lat" in c}


@router.post(
    "/projects/{project_id}/territories/{condado_id}/recalc",
    response_model=MoveCapitalResponse,
)
async def move_capital(
    project_id: str,
    condado_id: str,
    body: MoveCapitalRequest,
    persist: bool = True,
    session: AsyncSession = Depends(get_db),
) -> MoveCapitalResponse:
    """EDIT-01 + D-01: move capital, recalc Voronoi for moved condado + ridge-neighbors only."""
    from ..services import voronoi as voro_svc
    from ..services.territories_geojson import load_territories, save_territories

    territories = await load_territories(project_id)
    if condado_id not in territories:
        raise HTTPException(status_code=404, detail=f"condado {condado_id} not found")

    # Capital lon/lat live in territory_metadata.json, NOT in territories.geojson
    # properties. Without this merge, 91 of 92 seeds collapse to (0,0) and
    # scipy.Voronoi raises QhullError → 500 (regression discovered 2026-04-26 UAT).
    capitals = _load_capitals(project_id)

    # Build territory_data in the format voronoi.recalc_neighbors expects:
    # {"condados": [[id, name, lon, lat, duchy_id, baronies], ...]}
    territory_data = {
        "condados": [
            [
                cid,
                t.get("name", ""),
                *capitals.get(cid, (t.get("lon", 0.0), t.get("lat", 0.0))),
                t.get("duchy_id", ""),
                t.get("baronies", []),
            ]
            for cid, t in territories.items()
        ]
    }

    try:
        result = voro_svc.recalc_neighbors(condado_id, body.lon, body.lat, territory_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # QhullError, MemoryError, etc. — surface a clear message instead of a mute 500
        logger.exception("recalc_neighbors failed for project=%s condado=%s", project_id, condado_id)
        raise HTTPException(status_code=500, detail=f"recalc failed: {type(e).__name__}: {e}")

    updated_territories = result["updated_territories"]
    affected_ids = result["affected_ids"]

    if persist:
        # Update in-memory state: capital + updated geometries
        territories[condado_id]["lon"] = body.lon
        territories[condado_id]["lat"] = body.lat
        for aid, geom in updated_territories.items():
            if aid in territories:
                territories[aid]["geometry"] = geom
        await save_territories(project_id, territories)

    return MoveCapitalResponse(
        updated_territories=updated_territories,
        affected_ids=affected_ids,
    )


@router.post(
    "/projects/{project_id}/territories/merge",
    response_model=MergeResponse,
)
async def merge_territories_endpoint(
    project_id: str,
    body: MergeRequest,
    persist: bool = True,
    session: AsyncSession = Depends(get_db),
) -> MergeResponse:
    """EDIT-03 + D-03: merge N territories via unary_union."""
    from ..services import voronoi as voro_svc
    from ..services.territories_geojson import load_territories, save_territories

    if body.primary_id not in body.condado_ids:
        raise HTTPException(status_code=422, detail="primary_id must be in condado_ids")

    territories = await load_territories(project_id)
    missing = [cid for cid in body.condado_ids if cid not in territories]
    if missing:
        raise HTTPException(status_code=404, detail=f"condado(s) not found: {missing}")

    geometries = [territories[cid]["geometry"] for cid in body.condado_ids]

    try:
        result = voro_svc.merge_territories(geometries, body.primary_id, body.condado_ids)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    merged_geojson = result["merged_territory"]
    warning = result["warning"]
    removed_ids = [cid for cid in body.condado_ids if cid != body.primary_id]

    if persist:
        territories[body.primary_id]["geometry"] = merged_geojson
        for rid in removed_ids:
            territories.pop(rid, None)
        await save_territories(project_id, territories)

    return MergeResponse(
        merged_id=body.primary_id,
        merged_territory=merged_geojson,
        removed_ids=removed_ids,
        warning=warning,
    )


@router.post(
    "/projects/{project_id}/territories/{condado_id}/split",
    response_model=SplitResponse,
)
async def split_territory_endpoint(
    project_id: str,
    condado_id: str,
    body: SplitRequest,
    persist: bool = True,
    session: AsyncSession = Depends(get_db),
) -> SplitResponse:
    """EDIT-04 + D-04: split territory via shapely.ops.split."""
    from ..services import voronoi as voro_svc
    from ..services.territories_geojson import load_territories, save_territories

    territories = await load_territories(project_id)
    if condado_id not in territories:
        raise HTTPException(status_code=404, detail=f"condado {condado_id} not found")

    geometry = territories[condado_id]["geometry"]
    # cut_line is list[tuple[float, float]] -> convert to list[list[float]] for LineString
    cut_line = [list(pt) for pt in body.cut_line]

    try:
        result = voro_svc.split_territory(geometry, cut_line, condado_id)
    except ValueError as e:
        # Pitfall 4: must be 422, not 500. Frontend shows toast from detail.
        raise HTTPException(status_code=422, detail=str(e))

    new_a = result["new_territory_a"]
    new_b = result["new_territory_b"]

    # Override new_a id to match stored key: voronoi.py returns "{condado_id}_a"
    # but we keep the original territory on disk under its existing condado_id.
    # P05 frontend must reference the same id it sent to avoid 404 on next edit.
    new_a = {**new_a, "id": condado_id}

    if persist:
        territories[condado_id]["geometry"] = new_a["geometry"]
        new_b_id = new_b["id"]
        territories[new_b_id] = {
            **territories[condado_id],
            "geometry": new_b["geometry"],
            "id": new_b_id,
            "name": territories[condado_id].get("name", "") + " (split)",
        }
        await save_territories(project_id, territories)

    return SplitResponse(
        original_id=condado_id,
        new_territory_a=new_a,
        new_territory_b=new_b,
    )


@router.patch(
    "/projects/{project_id}/territories/{condado_id}/geometry",
)
async def reshape_geometry(
    project_id: str,
    condado_id: str,
    body: ReshapeGeometryRequest,
    persist: bool = True,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """EDIT-02: persist a client-reshaped polygon."""
    from ..services.territories_geojson import load_territories, save_territories
    from shapely.geometry import shape
    from shapely import is_valid

    territories = await load_territories(project_id)
    if condado_id not in territories:
        raise HTTPException(status_code=404, detail=f"condado {condado_id} not found")

    try:
        poly = shape(body.geometry)
        if not is_valid(poly):
            poly = poly.buffer(0)
            if not is_valid(poly):
                raise HTTPException(
                    status_code=422,
                    detail="reshaped polygon is invalid and could not be repaired",
                )

        if persist:
            territories[condado_id]["geometry"] = body.geometry
            await save_territories(project_id, territories)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "reshape_geometry failed for project=%s condado=%s",
            project_id, condado_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"reshape failed: {type(e).__name__}: {e}",
        )

    return {"condado_id": condado_id, "ok": True}


@router.post("/projects/{project_id}/geometry/save")
async def save_geometry_snapshot(
    project_id: str,
    body: SaveSnapshotRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """D-07 flush endpoint: atomically write the full geometry snapshot to disk."""
    from ..services.territories_geojson import load_territories, save_territories

    # Merge snapshot into existing feature dict (preserve non-geometry metadata)
    existing = await load_territories(project_id)
    merged: dict[str, dict] = {}
    for cid, geom in body.territories.items():
        base = existing.get(cid, {"id": cid})
        merged[cid] = {**base, "geometry": geom}
        if cid in body.capitals:
            lon, lat = body.capitals[cid]
            merged[cid]["lon"] = lon
            merged[cid]["lat"] = lat
    # Snapshot is authoritative: any id in existing but not in snapshot is dropped.
    await save_territories(project_id, merged)
    return {"ok": True, "count": len(merged)}


@router.get(
    "/projects/{project_id}/territories/{condado_id}/vertex-handles",
    response_model=VertexHandlesResponse,
)
async def vertex_handles(
    project_id: str,
    condado_id: str,
    target: int = 12,
    session: AsyncSession = Depends(get_db),
) -> VertexHandlesResponse:
    """D-02: return Douglas-Peucker decimated handle points with source_index mapping."""
    from ..services import voronoi as voro_svc
    from ..services.territories_geojson import load_territories
    from shapely.geometry import shape

    if target < 4 or target > 100:
        raise HTTPException(status_code=422, detail="target must be between 4 and 100")

    territories = await load_territories(project_id)
    if condado_id not in territories:
        raise HTTPException(status_code=404, detail=f"condado {condado_id} not found")

    geometry = territories[condado_id]["geometry"]
    poly = shape(geometry)
    if poly.geom_type != "Polygon":
        raise HTTPException(
            status_code=422,
            detail="vertex handles only supported on Polygon geometry",
        )

    decimated_geojson = voro_svc.decimate_polygon(geometry, target_vertices=target)
    decimated_poly = shape(decimated_geojson)
    decimated_coords = list(decimated_poly.exterior.coords)[:-1]  # drop closing duplicate

    # Map each decimated vertex to its nearest index in the ORIGINAL exterior ring
    original_coords = list(poly.exterior.coords)[:-1]
    handles: list[VertexHandle] = []
    for dx, dy in decimated_coords:
        best_idx = 0
        best_dist_sq = float("inf")
        for i, (ox, oy) in enumerate(original_coords):
            d_sq = (ox - dx) ** 2 + (oy - dy) ** 2
            if d_sq < best_dist_sq:
                best_dist_sq = d_sq
                best_idx = i
        handles.append(VertexHandle(lon=dx, lat=dy, source_index=best_idx))

    return VertexHandlesResponse(handles=handles)
