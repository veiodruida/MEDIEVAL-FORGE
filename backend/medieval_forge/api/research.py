"""Research API endpoints (RESEARCH-05, D-05, D-17).

POST /projects/{project_id}/research  — start research run, stream SSE progress
GET  /projects/{project_id}/research/cached  — return cached result as JSON (404 if none)
GET  /projects/{project_id}/research/prompt  — return built research prompt (manual flow)
POST /projects/{project_id}/research/manual  — submit pasted LLM JSON response (manual flow)

SSE shape mirrors api/ingest.py: asyncio.Queue producer + StreamingResponse consumer.
T-PATH: is_valid_uuid check before any DB or filesystem access (T-3-11).
T-DOS: task.cancel() in SSE generator finally block (T-3-09, Pitfall 6).
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import Project
from ..services.llm import PROVIDERS
from ..services.llm.parse import ResearchParseError, parse_research_json
from ..services.llm.prompt import build_research_prompt
from ..services.paths import is_valid_uuid, project_dir
from ..services.research_cache import compute_cache_key, get_cached, set_cached
from ..services.research_runner import (
    PROVIDER_DEFAULT_MODEL,
    load_condados,
    run_research,
    validate_assignment_against_condados,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])


@router.post("/projects/{project_id}/research")
async def trigger_research(
    project_id: str,
    request: Request,
    provider: str = Query(...),
    force_refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Start an LLM research run for the project and stream SSE progress.

    Returns 400 if project_id is not a valid UUID.
    Returns 404 if provider is unknown or project does not exist.
    Streams 'data: ...\n\n' events from run_research, ending with 'data: DONE\n\n'.
    """
    # T-3-11: validate UUID before any DB or path access
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")

    # Validate provider up front (fast 404 before streaming starts)
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    # Validate project exists (404 before streaming starts) — uses injected session
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Capture the session factory: tests inject via app.state._test_session_factory
    # so the runner uses the same in-memory DB; production falls back to AsyncSessionLocal.
    db_session_factory = getattr(
        request.app.state, "_test_session_factory", AsyncSessionLocal
    )

    async def stream():
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        task = asyncio.create_task(
            run_research(
                project_id=project_id,
                provider_id=provider,
                queue=queue,
                force_refresh=force_refresh,
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
            # T-3-09: cancel producer on client disconnect (Pitfall 6)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/projects/{project_id}/research/cached")
async def get_cached_research(
    project_id: str,
    provider: str = Query(...),
    model: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return the cached research result as JSON, or 404 if not cached."""
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    actual_model = model or PROVIDER_DEFAULT_MODEL.get(provider, provider)
    key = compute_cache_key(
        proj.country_qid, proj.period_start, proj.period_end, provider, actual_model
    )
    cached = await get_cached(db, key)

    if cached is None:
        raise HTTPException(status_code=404, detail="No cached result for this project/provider/model")
    return JSONResponse(content=cached)


# ---------------------------------------------------------------------------
# Manual (copy/paste) flow — RESEARCH-manual
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/research/prompt")
async def get_research_prompt(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return the built research prompt string for the manual copy/paste flow.

    Returns 400 if project_id is not a valid UUID.
    Returns 404 if project does not exist.
    Returns 409 if territories.geojson has not been generated yet.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        condados = load_condados(project_dir(project_id))
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    prompt = build_research_prompt(
        project.name, project.period_start, project.period_end, condados
    )
    return JSONResponse(content={"prompt": prompt})


class ManualResponseBody(BaseModel):
    content: str


@router.post("/projects/{project_id}/research/manual")
async def submit_manual_research(
    project_id: str,
    body: ManualResponseBody,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Accept a pasted LLM JSON response, validate it, and cache it.

    Returns 400 if project_id is invalid, JSON is malformed, or condado_ids unknown.
    Returns 404 if project does not exist.
    Returns 409 if territories.geojson has not been generated yet.
    On success: returns {"result": <ResearchResult>} and writes a cache row
    keyed with provider="manual", model="manual".
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        result = parse_research_json(body.content)
    except ResearchParseError as e:
        # T-security: log only the parse error type, never the raw pasted content
        logger.debug("Manual research parse error for project %s: %s", project_id, type(e).__name__)
        raise HTTPException(status_code=400, detail=str(e))

    try:
        condados = load_condados(project_dir(project_id))
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))

    known_ids = {c["id"] for c in condados}
    try:
        validate_assignment_against_condados(result, known_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    payload = result.model_dump()
    cache_key = compute_cache_key(
        project.country_qid, project.period_start, project.period_end, "manual", "manual"
    )
    await set_cached(
        db, cache_key, payload, "manual", "manual",
        project.country_qid, project.period_start, project.period_end,
    )
    return JSONResponse(content={"result": payload})
