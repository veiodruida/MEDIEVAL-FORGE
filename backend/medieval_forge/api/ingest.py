"""INGEST-04: SSE-streamed ingestion endpoint.

Per RESEARCH Pattern 3 — asyncio.Queue producer + SSE consumer.
T-PATH: project_id validated via is_valid_uuid before DB lookup.
T-DOS:  reject if project.status == 'generating' (anti-overlap).
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import Project
from ..services.ingest_runner import run_ingest
from ..services.paths import is_valid_uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["ingest"])


async def _sse_generator(
    project_id: str,
    source: str,
    country: str,
    session_factory,
):
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    task = asyncio.create_task(
        run_ingest(project_id, source, country, queue, session_factory)
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

    effective_country = country or project.country_qid

    return StreamingResponse(
        _sse_generator(project_id, source, effective_country, AsyncSessionLocal),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
