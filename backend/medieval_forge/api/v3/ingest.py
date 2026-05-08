"""v3 SSE ingest endpoint — wraps services/pipeline/adapters.build_dataset_from_osm (D-14).

Mirrors api/ingest.py:_sse_generator pattern: asyncio.Queue producer,
StreamingResponse consumer, terminal None sentinel, per-(project_id) stop_event.

Phase 02 scope: adapter-only — this endpoint does NOT call run_pipeline.
Phase 03/04 will extend it.

The legacy /api/projects/{id}/ingest endpoint (api/ingest.py) STAYS mounted —
both coexist until Phase 03 deletes the v1 stepper + v1 router together.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...database import AsyncSessionLocal, get_db
from ...models import Project
from ...services.countries import clip_iso_codes_for_qid
from ...services.paths import is_valid_uuid
from ...services.pipeline.adapters.osm import build_dataset_from_osm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v3/projects", tags=["v3-ingest"])

# T-02-04-04: per-(project_id, step) stop_event registry. Phase 02 only has
# one step ("osm"), so the scoping is just project_id; we still use a tuple
# key for symmetry with services/ingest_terrain/runner.py's pattern.
_STOP_EVENTS: dict[tuple[str, str], asyncio.Event] = {}


def _register_stop_event(project_id: str, step: str = "osm") -> asyncio.Event:
    ev = asyncio.Event()
    _STOP_EVENTS[(project_id, step)] = ev
    return ev


def _clear_stop_event(project_id: str, step: str = "osm") -> None:
    _STOP_EVENTS.pop((project_id, step), None)


async def _set_status(
    project_id: str,
    status: str,
    session_factory: async_sessionmaker,
) -> None:
    """Mirror of services/ingest_runner._set_status."""
    async with session_factory() as session:
        proj = await session.get(Project, project_id)
        if proj is not None:
            proj.status = status
            await session.commit()


async def _adapter_producer(
    project_id: str,
    bbox: tuple[float, float, float, float],
    iso_codes: list[str],
    queue: asyncio.Queue[str | None],
    session_factory: async_sessionmaker,
    stop_event: asyncio.Event,
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning (mirrors run_ingest)."""
    try:
        await queue.put(f"data: Iniciando ingestão v3 para projeto {project_id}...\n\n")
        await build_dataset_from_osm(
            project_id, bbox, iso_codes, queue,
            stop_event=stop_event,
        )
        await _set_status(project_id, "ingested", session_factory)
        await queue.put("data: DONE\n\n")
    except asyncio.CancelledError:
        logger.info("v3 ingest cancelled for project %s", project_id)
        await queue.put("data: Cancelado pelo usuário.\n\n")
        try:
            await _set_status(project_id, "error_ingesting", session_factory)
        except Exception:  # noqa: BLE001
            logger.exception("failed to update status after cancellation")
    except Exception as exc:  # noqa: BLE001 — top of producer task
        logger.exception("v3 ingest failed for project %s", project_id)
        # T-02-04-05: only emit exception class name in SSE; full repr to logger only.
        await queue.put(f"data: ERROR: {exc.__class__.__name__}\n\n")
        try:
            await _set_status(project_id, "error_ingesting", session_factory)
        except Exception:  # noqa: BLE001
            logger.exception("failed to update status to error_ingesting")
    finally:
        await queue.put(None)


async def _v3_sse_generator(
    project_id: str,
    bbox: tuple[float, float, float, float],
    iso_codes: list[str],
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    stop_event = _register_stop_event(project_id)
    task = asyncio.create_task(
        _adapter_producer(project_id, bbox, iso_codes, queue, AsyncSessionLocal, stop_event)
    )
    try:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield msg
    finally:
        stop_event.set()
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _clear_stop_event(project_id)


@router.get("/{project_id}/ingest")
async def trigger_v3_ingest(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """v3 ingest — wraps build_dataset_from_osm and streams progress as SSE (D-14).

    T-02-04-01 (Spoofing/Tampering): is_valid_uuid before any DB lookup.
    T-02-04-02 (DoS — anti-overlap): 409 if project.status == 'generating'.
    T-02-04-03 (DoS — bbox sanity): adapter validates bbox span ≤ 30°/axis;
                                    400 here if project has no bbox at all.

    Test seam: _v3_sse_generator and _adapter_producer reference the
    module-level AsyncSessionLocal directly. Tests use
    `monkeypatch.setattr(v3_ingest_mod, "AsyncSessionLocal", in_memory_factory)`
    (matches Plan 02 Task 1 PROJECTS_ROOT pattern; mirrors v1 api/ingest.py).
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if project.status == "generating":
        raise HTTPException(
            status_code=409,
            detail="project is currently generating; wait for that to finish",
        )

    bbox_fields = (
        project.bbox_lat_min, project.bbox_lon_min,
        project.bbox_lat_max, project.bbox_lon_max,
    )
    if any(v is None for v in bbox_fields):
        raise HTTPException(
            status_code=400,
            detail="project has no bbox — set bbox_lat_min/lon_min/lat_max/lon_max first",
        )

    bbox: tuple[float, float, float, float] = (
        float(project.bbox_lat_min),  # type: ignore[arg-type]
        float(project.bbox_lon_min),  # type: ignore[arg-type]
        float(project.bbox_lat_max),  # type: ignore[arg-type]
        float(project.bbox_lon_max),  # type: ignore[arg-type]
    )

    iso_codes = clip_iso_codes_for_qid(project.country_qid) or []
    if not iso_codes:
        raise HTTPException(
            status_code=400,
            detail=f"no clip_iso_codes for country_qid={project.country_qid!r}",
        )

    return StreamingResponse(
        _v3_sse_generator(project_id, bbox, iso_codes),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


__all__ = ["router"]
