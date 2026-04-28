"""Codex API endpoints (Etapa 9 — quick-260428-l0l).

POST /projects/{project_id}/codex          — start Codex run, stream SSE progress
GET  /projects/{project_id}/codex/cached  — return cached codex payload or 404
GET  /projects/{project_id}/codex/prompt  — return built codex prompt (manual flow)

Mirrors api/research.py wiring: in-memory aiosqlite session factory captured
from app.state._test_session_factory; runner spawned via asyncio.create_task and
cancelled in the SSE generator's finally block (T-3-09, Pitfall 6).
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import Project
from ..services.codex_cache import compute_codex_cache_key, get_codex_cached
from ..services.codex_runner import run_codex
from ..services.llm import PROVIDERS
from ..services.llm.model_routing import resolve_model
from ..services.llm.prompt import build_codex_prompt
from ..services.paths import is_valid_uuid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["codex"])


def _parse_focus(focus: str | None) -> list[str] | None:
    """Parse comma-separated focus query param into a list (or None when empty)."""
    if not focus:
        return None
    parts = [p.strip() for p in focus.split(",") if p.strip()]
    return parts or None


def _resolve_codex_model(provider: str, model_override: str | None) -> str:
    """Resolve the codex model id for cache key computation.

    Default: route via model_routing with task='codex_genealogy' (high tier).
    When the caller passes an explicit model, prefer that.
    """
    if model_override:
        return model_override
    try:
        return resolve_model(provider, "codex_genealogy", None)
    except ValueError:
        # Fallback for providers not in TASK_MODEL_TIERS (shouldn't happen for
        # canonical providers, but stay defensive).
        return provider


@router.post("/projects/{project_id}/codex")
async def trigger_codex(
    project_id: str,
    request: Request,
    provider: str = Query(...),
    force_refresh: bool = Query(False),
    focus: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Start a Codex run for the project and stream SSE progress.

    Returns 400 if project_id is not a valid UUID.
    Returns 404 if provider is unknown or project does not exist.
    Streams 'data: ...\n\n' events from run_codex, ending with 'data: DONE\n\n'.
    """
    # T-3-11: validate UUID before any DB or path access.
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")

    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    db_session_factory = getattr(
        request.app.state, "_test_session_factory", AsyncSessionLocal
    )
    focus_sections = _parse_focus(focus)

    async def stream():
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        task = asyncio.create_task(
            run_codex(
                project_id=project_id,
                provider_id=provider,
                queue=queue,
                force_refresh=force_refresh,
                focus_sections=focus_sections,
                app_state=request.app.state,
                db_session_factory=db_session_factory,
            )
        )
        try:
            while True:
                msg = await queue.get()
                if msg is None:
                    break
                yield msg
        finally:
            # T-3-09: cancel producer on client disconnect (Pitfall 6).
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/projects/{project_id}/codex/cached")
async def get_cached_codex(
    project_id: str,
    provider: str = Query(...),
    model: str | None = Query(None),
    focus: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return the cached codex payload as JSON, or 404 if not cached."""
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    actual_model = _resolve_codex_model(provider, model)
    focus_sections = _parse_focus(focus)
    key = compute_codex_cache_key(
        proj.country_qid, proj.period_start, proj.period_end,
        provider, actual_model, focus_sections,
    )
    cached = await get_codex_cached(db, key)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="No cached codex for this project/provider/model",
        )
    return JSONResponse(content=cached)


@router.get("/projects/{project_id}/codex/prompt")
async def get_codex_prompt(
    project_id: str,
    focus: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return the built codex prompt for the manual copy/paste flow."""
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    focus_sections = _parse_focus(focus)
    map_summary = (
        f"{project.name} ({project.period_start}-{project.period_end} AD)"
    )
    prompt = build_codex_prompt(
        project.name, project.period_start, project.period_end, map_summary,
        focus_sections=focus_sections,
    )
    return JSONResponse(content={"prompt": prompt})
