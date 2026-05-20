"""v3 research SSE endpoints + providers/health + overlay (Plan 07-07b Task 2).

Three router objects in this module (mounted by main.py under /api):

1. `router`       — prefix `/v3/research`
   - POST /start
   - GET  /stream/{run_id}
   - POST /stop/{run_id}
   - GET  /providers (REVIEWS fix #5: surfaces Ollama available_models)
   - GET  /health    (alias)

2. `overlay_router` — prefix `/v3/projects`
   - GET /{project_id}/research/overlay
     Returns {exists, covered_condado_ids, meta} per BLOCKER 2 + REVIEWS
     fix #2. `meta` carries BOTH generated_at and applied_at so Plan 09b
     microcopy can disambiguate cache-hit reuse from fresh-generation.

The runner state lives in `services/research/runner.py`. `run_id` here is the
project_id by convention (mirrors api/v3/generate.py — one alive run per
project).

T-07-07b-01 mitigation: /providers builder NEVER returns `payload` or `key`
fields. Only `{provider_id, display_name, healthy, message, configured,
available_models?}`.

T-07-07b-08 mitigation: overlay endpoint trims raw meta sidecar to UI-bound
subset `{provider, model, generated_at, applied_at}` — prompt_digest /
schema_version / country / period stay internal.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, conint, model_validator

from ...services.llm.registry import PROVIDERS
from ...services.paths import is_valid_uuid, project_dir
from ...services.research.runner import (
    SingleFlightError,
    _RUN_QUEUES,
    get_last_terminal,
    get_stream,
    start_research,
    stop_research,
)
from ...database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# CRITICAL: prefix is /v3/research; main.py adds /api at mount time.
router = APIRouter(prefix="/v3/research", tags=["v3-research"])

# Overlay endpoint lives under /v3/projects/{id}/research/overlay so it shares
# the project-scoped URL space with /generate, /render, /export.
overlay_router = APIRouter(prefix="/v3/projects", tags=["v3-research"])


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------
class StartResearchBody(BaseModel):
    """POST /start body — opaque payload validated by the runner.

    D-01 (Phase 07.1): period_start/end are AD positive integers in [1, 2100].
    D-02 (Phase 07.1): period_start <= period_end (equality allowed for snapshot
    queries like "Iberia exactly at 868 AD").
    D-04c (Phase 07.1): atomic swap — no transitional string period field.

    `project_id` doubles as the run_id (mirrors api/v3/generate.py — one alive
    run per project). `condado_ids` is the authoritative pipeline list (Plan 06
    matcher consumes it for defense-in-depth filtering).
    """

    project_id: str
    provider: str
    model: str
    country_qid: str
    period_start: conint(ge=1, le=2100)  # type: ignore[valid-type]  # D-01
    period_end: conint(ge=1, le=2100)    # type: ignore[valid-type]  # D-01
    condado_ids: list[str]
    force_refresh: bool = False

    @model_validator(mode="after")
    def _validate_period_range(self) -> "StartResearchBody":
        if self.period_start > self.period_end:  # D-02: <= allowed
            raise ValueError(
                f"period_start ({self.period_start}) must be <= "
                f"period_end ({self.period_end})"
            )
        return self


# ---------------------------------------------------------------------------
# POST /start  — schedule a research run
# ---------------------------------------------------------------------------
@router.post("/start")
async def post_start(body: StartResearchBody) -> dict:
    """Schedule a research run. Returns 202-equivalent JSON with run_id.

    T-07-07b-02 mitigation: is_valid_uuid before any FS lookup.
    """
    if not is_valid_uuid(body.project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    if body.provider not in PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"unknown provider: {body.provider!r}"
        )

    try:
        await start_research(
            project_id=body.project_id,
            provider=body.provider,
            model=body.model,
            country_qid=body.country_qid,
            period_start=body.period_start,
            period_end=body.period_end,
            condado_ids=body.condado_ids,
            force_refresh=body.force_refresh,
            session_factory=AsyncSessionLocal,
        )
    except SingleFlightError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return {"run_id": body.project_id, "status": "scheduled"}


# ---------------------------------------------------------------------------
# GET /stream/{run_id}  — drain the SSE queue
# ---------------------------------------------------------------------------
@router.get("/stream/{run_id}")
async def get_stream_endpoint(run_id: str) -> StreamingResponse:
    """Drain the per-project SSE queue until the None sentinel.

    Pitfall 7 / WR-02: late-subscriber 404 is intentional — the producer's
    finally-block evicts _RUN_QUEUES, so reconnect-after-disconnect is not
    supported.
    """
    try:
        queue = get_stream(run_id)
    except KeyError:
        # WR-02 fallback: producer may have finished between POST /start
        # returning and the EventSource opening (fast errors like OOM).
        # Replay the cached terminal envelope as a one-shot stream so the
        # frontend gets the real error instead of a 404 "network failure".
        terminal = get_last_terminal(run_id)
        if terminal is None:
            raise HTTPException(
                status_code=404,
                detail=f"no active research run for {run_id}; POST /start first",
            )

        async def replay() -> AsyncIterator[str]:
            yield terminal

        return StreamingResponse(
            replay(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
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


# ---------------------------------------------------------------------------
# POST /stop/{run_id}  — abort an in-flight run
# ---------------------------------------------------------------------------
@router.post("/stop/{run_id}")
async def post_stop(run_id: str) -> dict:
    """Abort the in-flight research run. Returns {aborted: bool}."""
    aborted = await stop_research(run_id)
    return {"aborted": aborted, "run_id": run_id}


# ---------------------------------------------------------------------------
# GET /providers  — list providers + health (REVIEWS fix #5)
# ---------------------------------------------------------------------------
def _is_configured(provider: Any) -> bool:
    """Best-effort `configured` flag — provider may implement `is_configured()`
    or we fall back to "has any non-NoAuth auth method declared".
    """
    fn = getattr(provider, "is_configured", None)
    if callable(fn):
        try:
            result = fn()
            if hasattr(result, "__await__"):
                return False  # caller bug; treat as not configured
            return bool(result)
        except Exception:  # noqa: BLE001
            return False
    # Fallback: provider always returns configured=True for stub providers.
    return True


@router.get("/providers")
async def get_providers() -> list[dict]:
    """Return provider list with health + Ollama available_models.

    Shape (T-07-07b-01: NO payload / NO key leakage):
        [{provider_id, display_name, healthy, message, configured,
          available_models?}, ...]

    REVIEWS fix #5: Ollama exposes `available_models` via `client.list()`
    so the frontend ProviderSelector can default to whichever installed
    model best matches the ordered preference list.
    """
    out: list[dict] = []
    for pid, provider in PROVIDERS.items():
        # Ollama implements `health()` returning {ok, message, available_models}.
        # Claude implements only `health_check(credentials)` returning HealthStatus.
        # Branch on attribute presence so a future provider with `health()` plugs
        # in without surgery here.
        health_fn = getattr(provider, "health", None)
        if callable(health_fn):
            try:
                h = await health_fn()
            except Exception as exc:  # noqa: BLE001 — surface to UI
                h = {"ok": False, "message": str(exc), "available_models": []}
            healthy = bool(h.get("ok", False))
            message = h.get("message", "")
            available_models = h.get("available_models")
        else:
            try:
                hs = await provider.health_check(None)
            except Exception as exc:  # noqa: BLE001
                healthy = False
                message = str(exc)
                available_models = None
            else:
                healthy = bool(hs.healthy)
                message = hs.message
                available_models = (
                    list(hs.available_models) if hs.available_models is not None else None
                )

        entry = {
            "provider_id": pid,
            "display_name": getattr(provider, "display_name", pid),
            "healthy": healthy,
            "message": message,
            "configured": _is_configured(provider),
        }
        if available_models is not None:
            entry["available_models"] = available_models  # REVIEWS fix #5
        out.append(entry)
    return out


@router.get("/health")
async def get_health() -> dict:
    """Lightweight health endpoint (alias for the SSE-runner consumer)."""
    return {"ok": True}


# ---------------------------------------------------------------------------
# Overlay endpoint (BLOCKER 2 + REVIEWS fix #2)
# ---------------------------------------------------------------------------
@overlay_router.get("/{project_id}/research/overlay")
async def get_overlay(project_id: str) -> dict:
    """Return {exists, covered_condado_ids, meta} for the project's overlay.

    Shape on miss: `{"exists": false, "covered_condado_ids": [], "meta": None}`.
    Shape on hit:  `{"exists": true, "covered_condado_ids": [...],
                     "meta": {provider, model, generated_at, applied_at}}`.

    REVIEWS fix #2: meta carries BOTH generated_at (original LLM-output
    timestamp, possibly older than applied_at on cache-hit paths) AND
    applied_at (when the runner wrote this overlay to the project). Plan 09b
    microcopy renders single-line when they match, two-line when they differ.

    T-07-07b-08 mitigation: trims raw meta sidecar to UI-bound subset — does
    NOT echo prompt_digest / schema_version / country / period to UI
    consumers.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
    pdir = project_dir(project_id)
    overlay_path = pdir / "research_overlay.json"
    if not overlay_path.exists():
        return {"exists": False, "covered_condado_ids": [], "meta": None}
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    covered = list(overlay.keys())

    meta_path = pdir / "research_overlay.meta.json"
    meta: Optional[dict] = None
    if meta_path.exists():
        raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta = {
            "provider": raw_meta.get("provider"),
            "model": raw_meta.get("model"),
            "generated_at": raw_meta.get("generated_at"),  # REVIEWS fix #2
            "applied_at": raw_meta.get("applied_at"),      # REVIEWS fix #2
        }
    return {"exists": True, "covered_condado_ids": covered, "meta": meta}


__all__ = ["router", "overlay_router"]
