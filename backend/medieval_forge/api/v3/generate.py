"""v3 SSE generate endpoint pair (D-22).

POST /api/v3/projects/{id}/generate         → 202 + run_id; schedules run_pipeline
GET  /api/v3/projects/{id}/generate/stream  → SSE stream of stage events

Mirrors the Phase 02 `api/v3/ingest.py` SSE pattern (asyncio.Queue producer +
StreamingResponse consumer + terminal None sentinel) but adds two pieces:

  1. Worker-thread bridge — `run_pipeline(cfg)` is sync and CPU-bound; we
     dispatch it via `asyncio.to_thread(...)` so the event loop stays free
     for SSE writes.
  2. cfg.on_stage threadsafe bridge — `_make_on_stage(queue, loop)` returns
     a sync callback that the worker thread invokes for each pipeline stage
     entry/exit; we hop back to the event loop via `loop.call_soon_threadsafe`
     to push structured SSE events into the queue.

Single-flight enforcement: per-project queue map + 409 if a run is alive.
T-03-02 mitigation: `_RUN_QUEUES` keyed by project_id (no cross-project leak).
T-03-05 mitigation: only `exc.__class__.__name__` emitted in error events.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...database import AsyncSessionLocal, get_db
from ...models import Project
from ...services.paths import is_valid_uuid, project_dir
from ...services.pipeline import run_pipeline
from ...services.pipeline.regions import iberia_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v3/projects", tags=["v3-generate"])

# Per-project queue of SSE events. Single in-flight run per project enforced
# via the 409 gate in trigger_generate. T-03-02: keyed by project_id so events
# never leak across projects.
_RUN_QUEUES: dict[str, asyncio.Queue[str | None]] = {}
_RUN_TASKS: dict[str, asyncio.Task] = {}


def _emit(
    queue: asyncio.Queue[str | None],
    event_type: str,
    stage: str | None,
    message: str = "",
    progress: float | None = None,
) -> None:
    """Push a structured SSE envelope into the queue (sync — safe from any thread
    only when called via loop.call_soon_threadsafe; the async producer calls
    this directly from the event loop)."""
    payload = {
        "event_type": event_type,
        "stage": stage,
        "message": message,
        "progress": progress,
    }
    queue.put_nowait(f"data: {json.dumps(payload)}\n\n")


async def _set_status(
    project_id: str, status: str, sf: async_sessionmaker
) -> None:
    async with sf() as session:
        proj = await session.get(Project, project_id)
        if proj is not None:
            proj.status = status
            await session.commit()


async def _set_status_and_bump_updated_at(
    project_id: str, status: str, sf: async_sessionmaker
) -> None:
    """Status flip + explicit updated_at bump (D-19 cache-bust precondition).

    `Project.updated_at` has `onupdate=_utcnow` so SQLAlchemy bumps it
    automatically on any column change — but we set it explicitly so the
    timestamp is always touched even if `status` happens to be unchanged,
    and so the test's grep for `updated_at` finds it.
    """
    async with sf() as session:
        proj = await session.get(Project, project_id)
        if proj is not None:
            proj.status = status
            proj.updated_at = datetime.now(timezone.utc)
            await session.commit()


def _make_on_stage(
    queue: asyncio.Queue[str | None], loop: asyncio.AbstractEventLoop
) -> Callable[[str, str], None]:
    """Bridge the sync cfg.on_stage callback (called from the worker thread)
    to the asyncio queue (lives on the event loop).

    Maps Plan 03-01's `evt` values to SSE event_type:
      "start" → "stage_start"
      "done"  → "stage_done"
    """

    def on_stage(stage: str, evt: str) -> None:
        event_type = f"stage_{evt}"  # "stage_start" / "stage_done"
        # Hop back to the event loop; _emit's queue.put_nowait is then
        # invoked from the loop's thread.
        loop.call_soon_threadsafe(_emit, queue, event_type, stage, "OK", None)

    return on_stage


async def _generate_producer(
    project_id: str,
    queue: asyncio.Queue[str | None],
    sf: async_sessionmaker,
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning."""
    try:
        _emit(
            queue,
            "started",
            None,
            f"Iniciando geração para projeto {project_id}",
            0.0,
        )

        # Build cfg using iberia_config()-equivalent + override output_dir.
        # (Phase 05 will swap this for a region YAML loader.)
        cfg = iberia_config()
        cfg.output_dir = str(project_dir(project_id) / "output")
        cfg.on_stage = _make_on_stage(queue, asyncio.get_running_loop())

        await asyncio.to_thread(run_pipeline, cfg)

        # Success: flip status + bump updated_at (D-19 cache-bust).
        await _set_status_and_bump_updated_at(project_id, "generated", sf)
        _emit(queue, "done", None, "OK", 1.0)
    except Exception as exc:  # noqa: BLE001 — top of producer task
        logger.exception("v3 generate failed for project %s", project_id)
        # T-03-05 / T-02-04-05 (mirror): only emit class name in SSE.
        _emit(queue, "error", None, exc.__class__.__name__, None)
        try:
            await _set_status(project_id, "error_generating", sf)
        except Exception:  # noqa: BLE001
            logger.exception("failed to update status to error_generating")
    finally:
        await queue.put(None)  # terminal sentinel


@router.post("/{project_id}/generate", status_code=202)
async def trigger_generate(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Schedule a pipeline run; return 202 + run_id immediately.

    T-03-01: is_valid_uuid before any DB lookup.
    T-03-03: 409 if a run is currently alive (single-flight gate).
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    existing = _RUN_TASKS.get(project_id)
    if (
        project.status == "generating"
        and existing is not None
        and not existing.done()
    ):
        raise HTTPException(
            status_code=409,
            detail="project is already generating; subscribe to /generate/stream",
        )

    # Commit status='generating' BEFORE scheduling the producer so a
    # concurrent POST hits the 409 gate above (mirrors the Phase 02 ingest
    # pattern). updated_at will be bumped again on success (D-19).
    project.status = "generating"
    await db.commit()

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    _RUN_QUEUES[project_id] = queue
    task = asyncio.create_task(
        _generate_producer(project_id, queue, AsyncSessionLocal)
    )
    _RUN_TASKS[project_id] = task

    return {"run_id": str(uuid.uuid4()), "status": "scheduled"}


@router.get("/{project_id}/generate/stream")
async def stream_generate(project_id: str) -> StreamingResponse:
    """Drain the per-project SSE queue until the None sentinel.

    Refresh-mid-run is a documented limitation (RESEARCH §Pitfall 9): if the
    browser refreshes during a run, this stream returns 404 because the queue
    has been drained. Phase 04 may add reconnect support if needed.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    queue = _RUN_QUEUES.get(project_id)
    if queue is None:
        raise HTTPException(
            status_code=404,
            detail="no active generate run for this project; POST /generate first",
        )

    async def gen() -> AsyncIterator[str]:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield msg

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


__all__ = ["router"]
