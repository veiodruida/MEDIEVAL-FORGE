"""POST /api/v3/llm/ollama/launch — start the ollama daemon if it isn't already.

Router prefix is /v3/llm — main.py adds /api at mount time. Full paths:
- POST   /api/v3/llm/ollama/launch
- DELETE /api/v3/llm/ollama/launch  (kills the subprocess WE spawned only)
- GET    /api/v3/llm/ollama/launch  (status + `owned` flag)
- GET    /api/v3/llm/ollama/logs

DELETE only kills the daemon when this backend launched it. A pre-existing
Ollama Desktop daemon is left alone (other apps may depend on it). The GET
response carries an `owned` boolean so the UI can hide the "Parar Ollama"
affordance when we don't own the lifecycle.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, status as http_status

from ...services.llm.ollama_launcher import (
    OllamaBinaryMissing,
    OllamaLaunchTimeout,
    OLLAMA_HOST,
    _is_running,
    get_logs as launcher_get_logs,
    launch as launcher_launch,
    owns_daemon as launcher_owns_daemon,
    shutdown as launcher_shutdown,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v3/llm", tags=["v3-llm-ollama"])


@router.post("/ollama/launch")
async def post_launch() -> dict:
    """Start `ollama serve` (detached subprocess). Idempotent.

    Returns {"ok": True, "was_running": <bool>, "base_url": "<host>"}.
    `was_running=True` when the daemon was already up — no new process spawned.
    """
    try:
        result = await asyncio.to_thread(launcher_launch)
    except OllamaBinaryMissing as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except OllamaLaunchTimeout as exc:
        raise HTTPException(
            status_code=http_status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)
        )
    return {
        "ok": result.ok,
        "was_running": result.was_running,
        "base_url": result.base_url,
    }


@router.get("/ollama/launch")
async def get_launch() -> dict:
    """Status of the ollama daemon.

    `owned` is True iff this backend spawned the running subprocess — only
    then will DELETE actually kill anything.
    """
    running = await asyncio.to_thread(_is_running)
    owned = await asyncio.to_thread(launcher_owns_daemon)
    return {
        "running": running,
        "owned": owned,
        "base_url": OLLAMA_HOST if running else None,
    }


@router.delete("/ollama/launch")
async def delete_launch() -> dict:
    """Kill the `ollama serve` subprocess this backend launched (if any).

    Idempotent — returns ok=True regardless of whether something was killed.
    Pre-existing Ollama Desktop daemons are NEVER touched.
    """
    was_running = await asyncio.to_thread(launcher_shutdown)
    return {"ok": True, "was_running": was_running}


@router.get("/ollama/logs")
async def get_ollama_logs(tail: int = 200) -> dict:
    """Return the last `tail` lines of `ollama serve` stdout/stderr.

    Only populated when this backend launched the daemon (PIPE attached).
    If Ollama was already running before launch, returns an empty list.
    """
    tail = max(1, min(tail, 1000))
    return {"lines": launcher_get_logs(tail)}


__all__ = ["router"]
