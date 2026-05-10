"""Phase 04 D-03: in-memory _STAGE_CACHE with latest+prior per stage per project.

Two versions per stage. No disk persistence. Process death clears everything (single-user
local tool — no LRU policy in Phase 04). Cleared on full POST /generate via
cache_clear_project; preserved across POST /render calls (D-03).

Thread-safety: one threading.RLock guards _STAGE_CACHE because the asyncio event loop
reads it (for the 409 gate / affected-stages diff) while the worker thread writes
after each split function completes. RLock (not Lock) because the DAG walker may
re-enter under the same thread.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class StageEntry:
    """Latest + prior pair for a single stage of a single project."""
    token: str
    array: np.ndarray
    prior_token: Optional[str] = None
    prior_array: Optional[np.ndarray] = None


# Outer key = project_id (UUID string). Inner key = stage_name from DAG_ORDER.
_STAGE_CACHE: dict[str, dict[str, StageEntry]] = {}
_CACHE_LOCK = threading.RLock()


def cache_get(project_id: str, stage_name: str) -> Optional[StageEntry]:
    """Return the StageEntry for (project, stage) or None if absent."""
    with _CACHE_LOCK:
        return _STAGE_CACHE.get(project_id, {}).get(stage_name)


def cache_put(project_id: str, stage_name: str, token: str,
              array: np.ndarray) -> None:
    """Promote current to prior, store new (token, array) as current.

    Atomicity invariant: call ONLY when the stage completes WITHOUT raising
    StageCancelled. On cancel, the entry MUST stay unchanged so the prior_array
    remains the canonical revert target (D-13).
    """
    with _CACHE_LOCK:
        if project_id not in _STAGE_CACHE:
            _STAGE_CACHE[project_id] = {}
        existing = _STAGE_CACHE[project_id].get(stage_name)
        prior_token = existing.token if existing is not None else None
        prior_array = existing.array if existing is not None else None
        _STAGE_CACHE[project_id][stage_name] = StageEntry(
            token=token,
            array=array,
            prior_token=prior_token,
            prior_array=prior_array,
        )


def cache_clear_project(project_id: str) -> None:
    """Drop all stage entries for a project. Called on fresh POST /generate (D-03)."""
    with _CACHE_LOCK:
        _STAGE_CACHE.pop(project_id, None)


__all__ = [
    "StageEntry",
    "_STAGE_CACHE",
    "cache_get",
    "cache_put",
    "cache_clear_project",
]
