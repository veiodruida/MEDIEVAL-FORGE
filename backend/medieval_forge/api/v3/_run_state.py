"""Shared run-state dicts for v3 SSE endpoints (generate + render).

Module-level singletons. Both api/v3/generate.py and api/v3/render.py import
from here so the cross-router 409 single-flight gate (Plan 04-02 Task 2) can
inspect both task slots atomically.

Layout:
  _RUN_QUEUES[project_id]      -> asyncio.Queue[str | None]   (SSE producer)
  _RUN_TASKS[project_id]       -> asyncio.Task                 (the producer task)
  _RUN_STOP_EVENTS[project_id] -> threading.Event              (D-14 cancel signal)
  _RUN_KIND[project_id]        -> 'generate' | 'render'        (for diagnostics + 409 detail)

Single-flight invariant: at most ONE alive task per project across BOTH dicts.
is_run_alive() is the canonical check.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Optional


_RUN_QUEUES: dict[str, asyncio.Queue[Optional[str]]] = {}
_RUN_TASKS: dict[str, asyncio.Task] = {}
_RUN_STOP_EVENTS: dict[str, threading.Event] = {}
_RUN_KIND: dict[str, str] = {}


def is_run_alive(project_id: str) -> Optional[str]:
    """Return 'generate' | 'render' if a task for that project is still alive,
    else None. Cross-router single-flight gate (D-04)."""
    task = _RUN_TASKS.get(project_id)
    if task is not None and not task.done():
        return _RUN_KIND.get(project_id, "unknown")
    return None


__all__ = [
    "_RUN_QUEUES",
    "_RUN_TASKS",
    "_RUN_STOP_EVENTS",
    "_RUN_KIND",
    "is_run_alive",
]
