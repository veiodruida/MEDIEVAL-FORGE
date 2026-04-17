"""INGEST-04: SSE-streamed ingestion endpoint.

Per RESEARCH Pattern 3 — asyncio.Queue producer + SSE consumer.
T-PATH: project_id validated via is_valid_uuid before DB lookup.
T-DOS:  reject if project.status == 'generating' (anti-overlap).
"""
from __future__ import annotations

import asyncio
import logging

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import Project
from ..services.ingest_runner import run_ingest
from ..services.paths import is_valid_uuid, project_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["ingest"])


async def _sse_generator(
    project_id: str,
    source: str,
    country: str,
    session_factory,
    bbox: tuple[float, float, float, float] | None = None,
    clip_iso_codes: list[str] | None = None,
):
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    task = asyncio.create_task(
        run_ingest(
            project_id, source, country, queue, session_factory,
            bbox=bbox, clip_iso_codes=clip_iso_codes,
        )
    )
    try:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield msg
    finally:
        # Ensure the producer task is awaited so exceptions propagate to logs.
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


@router.get("/{project_id}/ingest-status")
async def ingest_status(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retorna informação sobre os dados geográficos já ingeridos neste projeto."""
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    geojson_path = project_dir(project_id) / "raw" / "municipalities.geojson"
    if not geojson_path.exists():
        return {"has_data": False, "feature_count": 0, "polygon_count": 0,
                "point_count": 0, "size_bytes": 0, "last_modified": None}

    stat = geojson_path.stat()
    with geojson_path.open(encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    polygon_types = {"Polygon", "MultiPolygon"}
    polygon_count = sum(1 for ft in features if ft.get("geometry", {}).get("type") in polygon_types)
    point_count = len(features) - polygon_count
    last_mod = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    return {
        "has_data": True,
        "feature_count": len(features),
        "polygon_count": polygon_count,
        "point_count": point_count,
        "size_bytes": stat.st_size,
        "last_modified": last_mod,
        "has_polygons": polygon_count > 0,
    }


@router.post("/{project_id}/ingest")
async def trigger_ingest(
    project_id: str,
    source: str = Query("wikidata", pattern="^(wikidata|osm)$"),
    country: str | None = Query(
        None,
        description="Override country code. For wikidata: QID (Q\\d+); for osm: ISO 3166-1 alpha-2.",
    ),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(
            status_code=400,
            detail="project_id must be a valid UUID",
        )
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if project.status == "generating":
        raise HTTPException(
            status_code=409,
            detail="project is currently generating; wait for that to finish",
        )

    if country:
        effective_country = country
    elif source == "osm":
        # OSM precisa de código ISO alpha-2; converte QID do projeto
        from ..services.countries import qid_to_iso
        try:
            effective_country = qid_to_iso(project.country_qid)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        effective_country = project.country_qid

    # Passar bbox do projeto para OSM (query por bbox é muito mais rápida)
    bbox: tuple[float, float, float, float] | None = None
    if source == "osm" and all(
        v is not None for v in [
            project.bbox_lat_min, project.bbox_lon_min,
            project.bbox_lat_max, project.bbox_lon_max,
        ]
    ):
        bbox = (
            project.bbox_lat_min,   # type: ignore[arg-type]
            project.bbox_lon_min,   # type: ignore[arg-type]
            project.bbox_lat_max,   # type: ignore[arg-type]
            project.bbox_lon_max,   # type: ignore[arg-type]
        )

    # Derivar clip_iso_codes do QID do projeto para clipping geográfico pós-bbox.
    # Só aplicável a OSM (Wikidata já filtra por QID nativamente).
    clip_iso_codes: list[str] | None = None
    if source == "osm" and bbox is not None:
        from ..services.countries import clip_iso_codes_for_qid
        clip_iso_codes = clip_iso_codes_for_qid(project.country_qid)
        if clip_iso_codes:
            logger.info(
                "ingest %s: will clip OSM features to countries %s",
                project_id, clip_iso_codes,
            )
        else:
            logger.warning(
                "ingest %s: country_qid=%r has no clip_iso_codes — "
                "cross-border features will NOT be filtered",
                project_id, project.country_qid,
            )

    return StreamingResponse(
        _sse_generator(
            project_id, source, effective_country, AsyncSessionLocal,
            bbox=bbox, clip_iso_codes=clip_iso_codes,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
