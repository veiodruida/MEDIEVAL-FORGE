"""POST/DELETE/GET /api/v3/llm/llamacpp/launch — subprocess launch endpoint (D-08, D-08b).

Router prefix is /v3/llm — main.py adds /api at mount time. Full paths:
- POST   /api/v3/llm/llamacpp/launch
- DELETE /api/v3/llm/llamacpp/launch
- GET    /api/v3/llm/llamacpp/launch  (review-fix #4 — canonical status surface)

Body validation via pydantic; exception mapping centralized below. Idempotency,
auto-port, path-traversal guard, and subprocess lifecycle live in
services/llm/llamacpp_launcher.py (plan 07.1-02).

Threat model:
- T-07.1-07-01 unauthenticated POST/DELETE on localhost-bound dev API: accept
  (local-only dev server, no auth surface introduced this phase; consistent with
  Phase 03 D-13 backend purge of v1 auth.py).
- T-07.1-07-02 model body field arbitrary string: validated downstream by
  launcher's path-traversal guard (T-07.1-05-02). Defense-in-depth here:
  pydantic strips whitespace, enforces non-empty.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, status as http_status
from pydantic import BaseModel, Field

from ...services.llm.llamacpp_launcher import (
    LlamacppBinaryMissing,
    LlamacppInvalidModelFilename,
    LlamacppLaunchConflict,
    LlamacppModelNotFound,
    launch as launcher_launch,
    shutdown as launcher_shutdown,  # review-fix #4: single sync entry point
    status as launcher_status,
)

logger = logging.getLogger(__name__)

# CRITICAL: prefix is /v3/llm; main.py adds /api at mount time.
router = APIRouter(prefix="/v3/llm", tags=["v3-llm-llamacpp"])


class LaunchBody(BaseModel):
    """POST body — selected gguf filename relative to models dir."""

    model: str = Field(..., min_length=1, description="gguf filename (basename only)")


@router.post("/llamacpp/launch")
async def post_launch(body: LaunchBody) -> dict:
    """Spawn llama-server for the selected model. Idempotent by model path (D-08).

    Returns LaunchResult JSON: {ok, base_url, pid, model, started_at}.
    """
    try:
        result = launcher_launch(body.model)
    except LlamacppInvalidModelFilename as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except LlamacppModelNotFound as exc:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(exc))
    except LlamacppBinaryMissing as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except LlamacppLaunchConflict as exc:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(exc))
    return {
        "ok": result.ok,
        "base_url": result.base_url,
        "pid": result.pid,
        "model": result.model,
        "started_at": result.started_at,
    }


@router.delete("/llamacpp/launch")
async def delete_launch() -> dict:
    """Stop the running llama-server (D-08b). Discretion #7: idempotent 200.

    Returns {"ok": True, "was_running": <bool>}. No 404 when nothing alive —
    matches "click Parar then click Parar again is harmless" UX.

    review-fix #4: calls the single sync `launcher_shutdown` via
    `asyncio.to_thread` (no more `shutdown_sync` wrapper).
    """
    was_running = await asyncio.to_thread(launcher_shutdown)
    return {"ok": True, "was_running": was_running}


@router.get("/llamacpp/launch")
async def get_launch() -> dict:
    """Canonical "is a llama-server up?" status (review-fix #4 — Codex HIGH).

    Single source of truth consumed by the frontend `useLlamacppStatus` hook
    (plan 07.1-06). AuthSetupSheet (plan 07.1-08) derives `isRunning` from
    `status.data?.running === true` — replacing the broken mutation-cache-
    derived running state.

    Returns:
      {
        "running": bool,
        "pid": int | None,
        "model": str | None,
        "base_url": str | None,
        "started_at": str (ISO8601) | None,
      }
    """
    s = launcher_status()
    if s is None:
        return {
            "running": False,
            "pid": None,
            "model": None,
            "base_url": None,
            "started_at": None,
        }
    return {
        "running": True,
        "pid": s["pid"],
        "model": s["model"],
        "base_url": s["base_url"],
        "started_at": s["started_at"],
    }


__all__ = ["router"]
