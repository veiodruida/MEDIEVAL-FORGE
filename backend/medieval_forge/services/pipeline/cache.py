"""Phase 04 D-03 + Phase 08 D-23: in-memory _STAGE_CACHE keyed by (project_id, branch_id, stage).

D-03: Two versions per stage (latest + prior). No disk persistence. Process death clears
everything (single-user local tool). Cleared on full POST /generate via cache_clear_project;
preserved across POST /render calls.

D-23: Cache key extended from (project_id, stage) to (project_id, branch_id, stage).
Default branch_id="main" preserves backward-compat for pre-Phase-8 projects.
Branch switch = cache HIT if that branch was previously generated (cache is NOT cleared
on branch switch — only on fresh generate or explicit cache_clear_branch call).

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
    """Latest + prior pair for a single stage of a single project+branch."""
    token: str
    array: np.ndarray
    prior_token: Optional[str] = None
    prior_array: Optional[np.ndarray] = None


# Outer key = project_id (UUID string).
# Middle key = branch_id (string, default "main").
# Inner key = stage_name from DAG_ORDER.
_STAGE_CACHE: dict[str, dict[str, dict[str, StageEntry]]] = {}
_CACHE_LOCK = threading.RLock()

# Side-table for non-array voronoi intermediates (Voronoi object, index arrays,
# points, clipped polygons) that cannot be stored in StageEntry.array.
# Shape: project_id -> branch_id -> voronoi dict.
# Cleared together with _STAGE_CACHE on cache_clear_project so a fresh
# POST /generate always cold-starts voronoi (D-03).
_VORONOI_CACHE: dict[str, dict[str, dict]] = {}


def cache_get(project_id: str, branch_id: str, stage_name: str) -> Optional[StageEntry]:
    """Return the StageEntry for (project, branch, stage) or None if absent."""
    with _CACHE_LOCK:
        return _STAGE_CACHE.get(project_id, {}).get(branch_id, {}).get(stage_name)


def cache_put(project_id: str, branch_id: str, stage_name: str, token: str,
              array: np.ndarray) -> None:
    """Promote current to prior, store new (token, array) as current.

    Atomicity invariant: call ONLY when the stage completes WITHOUT raising
    StageCancelled. On cancel, the entry MUST stay unchanged so the prior_array
    remains the canonical revert target (D-13).
    """
    with _CACHE_LOCK:
        if project_id not in _STAGE_CACHE:
            _STAGE_CACHE[project_id] = {}
        if branch_id not in _STAGE_CACHE[project_id]:
            _STAGE_CACHE[project_id][branch_id] = {}
        existing = _STAGE_CACHE[project_id][branch_id].get(stage_name)
        prior_token = existing.token if existing is not None else None
        prior_array = existing.array if existing is not None else None
        _STAGE_CACHE[project_id][branch_id][stage_name] = StageEntry(
            token=token,
            array=array,
            prior_token=prior_token,
            prior_array=prior_array,
        )


def cache_clear_project(project_id: str) -> None:
    """Drop ALL stage entries for a project (all branches). Called on fresh POST /generate (D-03).

    Also clears _VORONOI_CACHE so the voronoi side-table stays consistent with
    the main cache — a fresh generate always cold-starts voronoi.
    """
    with _CACHE_LOCK:
        _STAGE_CACHE.pop(project_id, None)
        _VORONOI_CACHE.pop(project_id, None)


def cache_clear_branch(project_id: str, branch_id: str) -> None:
    """Drop stage entries for a single branch of a project.

    Used when switching away from a branch to evict stale entries (BRANCH-02).
    Does NOT clear other branches or the voronoi side-table for other branches.
    """
    with _CACHE_LOCK:
        if project_id in _STAGE_CACHE:
            _STAGE_CACHE[project_id].pop(branch_id, None)
        if project_id in _VORONOI_CACHE:
            _VORONOI_CACHE[project_id].pop(branch_id, None)


__all__ = [
    "StageEntry",
    "_STAGE_CACHE",
    "_VORONOI_CACHE",
    "_CACHE_LOCK",
    "cache_get",
    "cache_put",
    "cache_clear_project",
    "cache_clear_branch",
]
