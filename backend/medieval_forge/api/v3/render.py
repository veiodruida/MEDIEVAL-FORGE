"""v3 SSE render endpoint trio (D-04, D-13, D-14).

POST   /api/v3/projects/{id}/render          → 202 + {run_id, affected_stages, status}
GET    /api/v3/projects/{id}/render/stream   → SSE stream (stage_start/done/cancel/done)
POST   /api/v3/projects/{id}/render/cancel   → 200 {status: cancel_requested}
GET    /api/v3/projects/{id}/stage/{name}.png → 200 PNG of cached stage array (allowlist)

Reuses _RUN_QUEUES/_RUN_TASKS from _run_state.py for cross-router 409 (D-04 single-flight).
Builds a fresh cfg from load_region(project.region_key) on every call via dataclasses.replace
(D-18 — never mutates the cached singleton; RESEARCH Pitfall 9 / T-05-04-04).

Security mitigations (threat register T-04-02-01 through T-04-02-06):
  T-04-02-01: is_run_alive() checks both generate + render slots (DoS 409 gate)
  T-04-02-02: Pydantic Field(ge=, le=) + extra=forbid rejects out-of-bounds/unknown
  T-04-02-04: cache_put only on success; StageCancelled leaves cache unchanged
  T-04-02-05: only exc.__class__.__name__ in error events (no paths/PII)
  T-04-02-06: stage_name validated against allowlist (no FS traversal — dict lookup only)
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import numpy as np
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import AsyncSessionLocal, get_db
from ...models import Project
from ...services.paths import is_valid_uuid, project_dir
from ...services.pipeline import run_pipeline_incremental
from ...services.pipeline.cache import cache_get
from ...services.pipeline.cleanup import StageCancelled
from ...services.pipeline.region_loader import load_region
from ._run_state import (
    _RUN_QUEUES, _RUN_TASKS, _RUN_STOP_EVENTS, _RUN_KIND, is_run_alive,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v3/projects", tags=["v3-render"])


# ---------------------------------------------------------------------------
# Request / response models (ASVS V5 input validation)
# ---------------------------------------------------------------------------

class CfgOverrides(BaseModel):
    """D-05 slider bounds + ASVS V5 input validation. Reject out-of-bounds with 422."""
    smooth_sigma: Optional[float] = Field(default=None, ge=3.0, le=4.5)
    median_passes: Optional[int] = Field(default=None, ge=1, le=12)
    fragment_min_px: Optional[int] = Field(default=None, ge=0, le=2000)
    blob_merge_px: Optional[int] = Field(default=None, ge=0, le=500)

    model_config = {"extra": "forbid"}  # ASVS V5: reject unknown slider fields


class RenderRequest(BaseModel):
    cfg_overrides: CfgOverrides = Field(default_factory=CfgOverrides)
    # stage_view is client-only (Pitfall 8). Accepted but NOT used for token
    # derivation — it does not affect which stages recompute.
    stage_view: Optional[str] = None
    # D-23 + T-08-02-01: branch_id scopes the stage cache; validated pattern
    # prevents path-traversal or injection via branch name.
    branch_id: str = Field(default="main", pattern=r"^[a-zA-Z0-9_-]{1,255}$")

    model_config = {"extra": "forbid"}  # ASVS V5: reject unknown top-level fields


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _emit(queue: asyncio.Queue, event_type: str, stage: Optional[str],
          message: str = "", progress: Optional[float] = None,
          token: Optional[str] = None) -> None:
    """Push structured SSE envelope into the queue (sync, safe via call_soon_threadsafe)."""
    payload = {
        "event_type": event_type,
        "stage": stage,
        "message": message,
        "progress": progress,
        "token": token,
    }
    queue.put_nowait(f"data: {json.dumps(payload)}\n\n")


# ---------------------------------------------------------------------------
# Producer task
# ---------------------------------------------------------------------------

async def _render_producer(
    project_id: str,
    region_key: str,
    overrides: dict,
    queue: asyncio.Queue,
    sf,
    branch_id: str = "main",
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning.

    region_key is fetched at the endpoint (project.region_key) and passed in
    as a plain string — do NOT call db.get(Project) inside the producer thread.
    cfg is built via dataclasses.replace(load_region(region_key), ...) — never
    mutates the cached singleton (RESEARCH Pitfall 9 / T-05-04-04).

    On StageCancelled:
      - Emits stage_cancel per affected stage, carrying prior_token in message (D-13)
      - Cache is NOT updated (atomicity invariant: cache_put only fires on success)
    """
    stop_event = threading.Event()
    _RUN_STOP_EVENTS[project_id] = stop_event

    # Track affected stages via closure list updated by on_stage bridge.
    # This reflects what actually completed (not the return value, which is
    # unavailable inside the except block on StageCancelled — advisor item 2).
    completed_stages: list[str] = []

    try:
        _emit(queue, "started", None, f"Render iniciado para projeto {project_id}", 0.0)

        # AFTER (immutable per-call copy — RESEARCH Pitfall 9 / T-05-04-04):
        # load_region returns a cached singleton; replace() builds a fresh copy.
        cfg = replace(
            load_region(region_key),
            output_dir=str(project_dir(project_id) / "output"),
            stop_event=stop_event,
            branch_id=branch_id,
        )

        # Apply validated overrides from slider.
        # Mutates the LOCAL cfg copy — safe because replace() already gave us
        # a fresh instance; the cached singleton is untouched (RESEARCH line 800-803).
        for k, v in overrides.items():
            if v is not None:
                setattr(cfg, k, v)

        loop = asyncio.get_running_loop()

        # Wire on_stage to both SSE queue AND completed_stages tracker
        def _on_stage_tracking(stage: str, evt: str) -> None:
            if evt == "done":
                completed_stages.append(stage)
            loop.call_soon_threadsafe(_emit, queue, f"stage_{evt}", stage, "OK", None, None)

        cfg.on_stage = _on_stage_tracking

        affected = await asyncio.to_thread(
            run_pipeline_incremental, cfg, project_id,
        )

        # D-19 cache-bust: bump updated_at so CanvasViewer's cacheVersion changes
        # and the browser fetches the newly written visual_condado.png.
        # Mirror of _set_status_and_bump_updated_at in generate.py.
        async with AsyncSessionLocal() as session:
            proj = await session.get(Project, project_id)
            if proj is not None:
                proj.updated_at = datetime.now(timezone.utc)
                await session.commit()

        _emit(queue, "done", None, f"OK affected={','.join(affected)}", 1.0)

    except StageCancelled as exc:
        # D-13: emit stage_cancel per completed stage + the cancelled stage,
        # carrying prior_token in message so frontend can revert the canvas.
        cancelled_and_completed = list(dict.fromkeys(completed_stages + [exc.stage_name]))
        for stage in cancelled_and_completed:
            entry = cache_get(project_id, branch_id, stage)
            prior_tok = (entry.prior_token if (entry and entry.prior_token) else "") or ""
            _emit(queue, "stage_cancel", stage, prior_tok, None, prior_tok)
        _emit(queue, "done", None, "cancelled", 1.0)

    except Exception as exc:  # noqa: BLE001
        # T-04-02-05: only class name — no paths or PII in SSE
        logger.exception("v3 render failed for project %s", project_id)
        _emit(queue, "error", None, exc.__class__.__name__, None)

    finally:
        await queue.put(None)  # terminal sentinel — MUST stay before evictions
        _RUN_STOP_EVENTS.pop(project_id, None)
        _RUN_KIND.pop(project_id, None)
        _RUN_QUEUES.pop(project_id, None)   # WR-02 fix: prevent late-subscriber hang
        _RUN_TASKS.pop(project_id, None)    # WR-02 fix: prevent stale task reference


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{project_id}/render", status_code=202)
async def trigger_render(
    project_id: str,
    body: RenderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Schedule an incremental render run; return 202 + run_id immediately.

    D-04: cross-router 409 if /generate or /render is alive for the same project.
    D-18: fresh cfg from load_region(project.region_key) via dataclasses.replace
          per call (producer task owns it; cached singleton never mutated).
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Cross-router single-flight gate (D-04, T-04-02-01)
    alive_kind = is_run_alive(project_id)
    if alive_kind is not None:
        raise HTTPException(
            status_code=409,
            detail=f"project is already {alive_kind}; subscribe to /{alive_kind}/stream",
        )

    # Fetch region_key here (endpoint has the project row) — do NOT query DB
    # again inside the producer thread.
    region_key = project.region_key

    queue: asyncio.Queue = asyncio.Queue()
    _RUN_QUEUES[project_id] = queue
    _RUN_KIND[project_id] = "render"  # set BEFORE task creation (race guard)

    overrides = body.cfg_overrides.model_dump(exclude_none=True)
    task = asyncio.create_task(
        _render_producer(project_id, region_key, overrides, queue, AsyncSessionLocal,
                         branch_id=body.branch_id),
    )
    _RUN_TASKS[project_id] = task

    run_id = str(uuid.uuid4())
    return {"run_id": run_id, "status": "scheduled", "kind": "render"}


@router.get("/{project_id}/render/stream")
async def stream_render(project_id: str) -> StreamingResponse:
    """Drain the per-project render SSE queue until the None sentinel.

    Subscribe immediately after `/render` returns 202; the queue is evicted in
    the producer's `finally` block once the run completes (the eviction
    follows `put(None)` to prevent late-subscriber hangs). Late subscribers —
    after the producer pops `_RUN_QUEUES[project_id]` — receive 404.

    WR-04 (Plan 05 review): there is a narrow race window between sentinel
    emission and queue eviction. A client subscribing in that window will
    get the queue, drain the `None` sentinel immediately, and see an
    empty-but-completed stream. The frontend MUST treat this case
    identically to a 404 (the run is finished either way).
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    queue = _RUN_QUEUES.get(project_id)
    if queue is None:
        raise HTTPException(
            status_code=404,
            detail="no active render run; POST /render first",
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


@router.post("/{project_id}/render/cancel", status_code=200)
async def cancel_render(project_id: str) -> dict:
    """Set the stop_event for the alive render task (D-14 cooperative cancel).

    The worker thread's split functions check stop_event between passes and
    raise StageCancelled within ~one median pass (~0.2–0.5 s at default cfg).
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    stop_event = _RUN_STOP_EVENTS.get(project_id)
    if stop_event is None:
        raise HTTPException(
            status_code=404,
            detail="no active render run to cancel",
        )
    stop_event.set()
    return {"status": "cancel_requested"}


# Stage name allowlist (T-04-02-06: prevent path traversal via stage_name param)
_VALID_STAGE_NAMES = frozenset({
    "landmask", "voronoi-raw", "cleanup", "smooth", "render-final"
})

# Map UI radio name → _STAGE_CACHE key (D-10 viz mapping)
_STAGE_CACHE_KEY = {
    "landmask": "landmask",
    "voronoi-raw": "voronoi",
    "cleanup": "merge",      # post-merge is the final cleanup output
    "smooth": "smooth",
    "render-final": "merge", # for render-final, frontend uses /artifacts; we fallback to merge
}


@router.get("/{project_id}/stage/{stage_name}.png")
async def get_stage_raster(project_id: str, stage_name: str) -> Response:
    """Phase 04 stage-view endpoint (D-09/D-10/D-11).

    Visualization only — does NOT trigger pipeline recomputation (Pitfall 8).
    Returns a colorized PNG of the cached stage array.

    T-04-02-06: stage_name validated against 5-entry allowlist; no FS access —
    reads from _STAGE_CACHE dict by key only.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    if stage_name not in _VALID_STAGE_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown stage_name '{stage_name}'; valid: {sorted(_VALID_STAGE_NAMES)}",
        )

    cache_stage = _STAGE_CACHE_KEY[stage_name]
    entry = cache_get(project_id, "main", cache_stage)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"stage '{cache_stage}' not in cache; run /render or /generate first",
        )

    img_bytes = _array_to_png(entry.array, stage_name)
    return Response(content=img_bytes, media_type="image/png")


# Tab20 palette (matplotlib values, hardcoded — Pitfall A3 fallback: no matplotlib dep)
_TAB20 = np.array([
    [31, 119, 180], [174, 199, 232], [255, 127, 14], [255, 187, 120],
    [44, 160, 44], [152, 223, 138], [214, 39, 40], [255, 152, 150],
    [148, 103, 189], [197, 176, 213], [140, 86, 75], [196, 156, 148],
    [227, 119, 194], [247, 182, 210], [127, 127, 127], [199, 199, 199],
    [188, 189, 34], [219, 219, 141], [23, 190, 207], [158, 218, 229],
], dtype=np.uint8)


def _array_to_png(arr: np.ndarray, stage_name: str) -> bytes:
    """Hand-rolled tab20 colormap. bool/landmask → grayscale; int → 20-color cycle."""
    if arr.dtype == np.bool_ or stage_name == "landmask":
        img = Image.fromarray((arr.astype(np.uint8) * 255), mode="L")
    else:
        h, w = arr.shape
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        valid = arr >= 0
        idx = (arr[valid] % 20).astype(int)
        rgb[valid] = _TAB20[idx]
        img = Image.fromarray(rgb, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


__all__ = ["router"]
