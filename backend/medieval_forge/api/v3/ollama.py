"""POST /api/v3/llm/ollama/launch — start the ollama daemon if it isn't already.

Router prefix is /v3/llm — main.py adds /api at mount time. Full path:
- POST   /api/v3/llm/ollama/launch
- GET    /api/v3/llm/ollama/launch  (status)

No DELETE: the Ollama daemon is a shared system service (LMStudio + other
local-LLM apps may depend on it), not owned by Medieval Forge. Users stop it
via the Ollama Desktop tray icon.
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
    launch as launcher_launch,
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
    """Canonical 'is the ollama daemon up?' status (mirrors llamacpp shape)."""
    running = await asyncio.to_thread(_is_running)
    return {"running": running, "base_url": OLLAMA_HOST if running else None}


__all__ = ["router"]
