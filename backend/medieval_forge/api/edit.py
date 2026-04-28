"""Phase 4 edit endpoints. Thin request/response layer over services/voronoi.py."""
from __future__ import annotations

import json
import logging
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Project
from ..services.project_meta import touch_project
from shapely.geometry import Point

from ..schemas import (
    MoveCapitalRequest, MoveCapitalResponse,
    MergeRequest, MergeResponse,
    SplitRequest, SplitResponse,
    ReshapeGeometryRequest,
    SaveSnapshotRequest,
    VertexHandle, VertexHandlesResponse,
    PaintTerrainRequest, PaintTerrainResponse,
    EditAssignmentsRequest,
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

    # qlo-01: load land mask + bbox from project's generated/ artifacts so
    # recalc_neighbors can clip Voronoi cells to the actual land area
    # (matches generation-time behavior; previously cells could extend into
    # the ocean and edge cells were silently dropped).
    land_mask = None
    bbox = None
    try:
        from ..services.paths import project_dir
        generated_dir = project_dir(project_id) / "generated"
        land_mask, bbox = voro_svc.load_land_mask_and_bbox(generated_dir)
    except ValueError:
        # Non-UUID project_id (test path) — no clipping
        pass
    if land_mask is None and bbox is None:
        logger.info(
            "move_capital: no land_mask/bbox for project=%s — recalc unclipped",
            project_id,
        )

    try:
        result = voro_svc.recalc_neighbors(
            condado_id, body.lon, body.lat, territory_data,
            land_mask=land_mask,
            bbox=bbox,
        )
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
        await touch_project(session, project_id)
        await session.commit()

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
        await touch_project(session, project_id)
        await session.commit()

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
        await touch_project(session, project_id)
        await session.commit()

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
            await touch_project(session, project_id)
            await session.commit()
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
    await touch_project(session, project_id)
    await session.commit()
    return {"ok": True, "count": len(merged)}


@router.post(
    "/projects/{project_id}/edit/paint-terrain",
    response_model=PaintTerrainResponse,
)
async def paint_terrain(
    project_id: str,
    body: PaintTerrainRequest,
    session: AsyncSession = Depends(get_db),
) -> PaintTerrainResponse:
    """EDIT-05: assign terrain_type to territories whose centroids fall on land.

    Ocean centroids (per land_mask.contains) and unknown territory_ids land in
    skipped_ids. Persists terrain_type into territories.geojson properties for
    painted_ids only.

    Security: filters territory_ids to known_ids for THIS project before any
    geometry lookup (T-5-01 — prevents cross-project injection).
    Pydantic Literal rejects invalid terrain_type values with 422 (T-5-02).
    """
    from ..services import voronoi as voro_svc
    from ..services.territories_geojson import load_territories, save_territories
    from ..services.paths import project_dir

    territories = await load_territories(project_id)
    if not territories:
        # No project data — every requested id is unknown, all skipped
        return PaintTerrainResponse(painted_ids=[], skipped_ids=list(body.territory_ids))

    # Security guard (T-5-01): filter ids to those known for THIS project
    # before any geometry lookup — prevents arbitrary ID injection.
    known_ids = set(territories.keys())

    # Reuse generation-time land mask (Shapely geometry in lon/lat space)
    land_mask = None
    try:
        generated_dir = project_dir(project_id) / "generated"
        land_mask, _ = voro_svc.load_land_mask_and_bbox(generated_dir)
    except ValueError:
        # Non-UUID project_id (test path) — treat as no land mask clipping
        pass

    painted_ids: list[str] = []
    skipped_ids: list[str] = []
    for tid in body.territory_ids:
        if tid not in known_ids:
            skipped_ids.append(tid)
            continue
        t = territories[tid]
        lon = t.get("lon")
        lat = t.get("lat")
        if lon is None or lat is None:
            skipped_ids.append(tid)
            continue
        if land_mask is not None and not land_mask.contains(Point(lon, lat)):
            skipped_ids.append(tid)
            continue
        # Apply terrain type
        t["terrain_type"] = body.terrain_type
        painted_ids.append(tid)

    if painted_ids:
        await save_territories(project_id, territories)
        await touch_project(session, project_id)
        await session.commit()

    return PaintTerrainResponse(painted_ids=painted_ids, skipped_ids=skipped_ids)


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


# ==================== Etapa 8 (quick-260428-h1t): PATCH research/assignments ====================


@router.patch("/projects/{project_id}/research/assignments")
async def patch_research_assignments(
    project_id: str,
    body: EditAssignmentsRequest,
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Edit barony→condado assignments and/or condado metadata after research.

    Persists the edited payload back to the SAME ResearchCache row (overwrite-in-place),
    so subsequent /generate calls consume the edits via territory_builder.

    Errors:
      400: invalid project_id, unknown barony id(s), unknown duchy_id, validation failure
      404: project not found
      409: no research cache, cache predates barony_assignments schema, baronies.geojson missing
    """
    from ..services.paths import is_valid_uuid, project_dir
    from ..services.research_cache import set_cached
    from ..services.territory_builder import select_latest_cache_row
    from ..services.llm.schemas import MapResearchResult

    # 1. Validate project_id
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")

    # 2. Load Project
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 3. Load latest cache row
    row = await select_latest_cache_row(
        session, project.country_qid, project.period_start, project.period_end,
    )
    if row is None:
        raise HTTPException(status_code=409, detail="No research cache to edit")
    if "barony_assignments" not in row.payload:
        raise HTTPException(
            status_code=409,
            detail="Cache row predates barony_assignments schema",
        )

    # 4. Load baronies.geojson
    baronies_path = project_dir(project_id) / "raw" / "baronies.geojson"
    if not baronies_path.exists():
        raise HTTPException(status_code=409, detail="baronies.geojson missing")
    baronies_geojson = json.loads(baronies_path.read_text(encoding="utf-8"))
    valid_barony_ids: set[str] = set()
    for feature in baronies_geojson.get("features", []) or []:
        props = feature.get("properties", {}) or {}
        bid = props.get("id")
        if bid is not None:
            valid_barony_ids.add(bid)

    # 5. Deep-copy payload (NO mutation until step 10)
    payload = deepcopy(row.payload)

    # 6. Apply condado_renames FIRST
    if body.condado_renames:
        condados_by_id: dict[str, dict] = {c["id"]: c for c in payload.get("condados", [])}
        duchies: dict = payload.get("duchies", {}) or {}

        for cid, rename in body.condado_renames.items():
            if cid in condados_by_id:
                # Patch existing condado
                cond = condados_by_id[cid]
                if rename.name is not None:
                    cond["name"] = rename.name
                if rename.duchy_id is not None:
                    if rename.duchy_id not in duchies:
                        raise HTTPException(
                            status_code=400,
                            detail=f"unknown duchy_id: {rename.duchy_id!r}",
                        )
                    cond["duchy_id"] = rename.duchy_id
                    # Re-derive kingdom_id from new duchy
                    cond["kingdom_id"] = duchies[rename.duchy_id]["kingdom_id"]
            else:
                # Append new condado — duchy_id required
                if rename.duchy_id is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"new condado {cid!r} requires duchy_id",
                    )
                if rename.duchy_id not in duchies:
                    raise HTTPException(
                        status_code=400,
                        detail=f"unknown duchy_id: {rename.duchy_id!r}",
                    )
                kingdom_id = duchies[rename.duchy_id]["kingdom_id"]
                payload["condados"].append({
                    "id": cid,
                    "name": rename.name or cid,
                    "kingdom_id": kingdom_id,
                    "duchy_id": rename.duchy_id,
                })

    # 7. Apply barony_assignments delta
    if body.barony_assignments:
        existing_assignments: dict = payload.setdefault("barony_assignments", {})
        existing_assignments.update(body.barony_assignments)

    # 8. Validate every barony_id in FINAL assignments exists
    final_assignments: dict = payload.get("barony_assignments", {}) or {}
    unknown_baronies = sorted(
        bid for bid in final_assignments.keys() if bid not in valid_barony_ids
    )
    if unknown_baronies:
        raise HTTPException(
            status_code=400,
            detail=f"unknown barony id(s): {unknown_baronies}",
        )

    # 9. Re-parse through MapResearchResult (cross-ref invariant)
    try:
        MapResearchResult.model_validate(payload)
    except PydValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)[:600])

    # 10. Persist via set_cached (overwrite-in-place using same cache_key_hash)
    await set_cached(
        session,
        row.cache_key_hash,
        payload,
        row.provider,
        row.model,
        row.country_qid,
        row.period_start,
        row.period_end,
    )
    await touch_project(session, project_id)
    await session.commit()

    return JSONResponse({"result": payload})
