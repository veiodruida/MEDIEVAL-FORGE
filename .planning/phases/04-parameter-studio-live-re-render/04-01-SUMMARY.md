---
phase: "04"
plan: "01"
subsystem: pipeline-cache-dag
tags: [wave-1, refactor, dag, cache, cleanup-split, tdd, parity]
dependency_graph:
  requires:
    - backend/medieval_forge/services/pipeline/cleanup.py (Phase 01 monolith)
    - frontend/src/stores/useRunStore.ts (Phase 03 11-stage list)
  provides:
    - backend/medieval_forge/services/pipeline/cleanup.py (4 split functions + StageCancelled)
    - backend/medieval_forge/services/pipeline/cache.py (_STAGE_CACHE + StageEntry + helpers)
    - backend/medieval_forge/services/pipeline/dag.py (compute_version_token + STAGE_READS + DAG_ORDER)
    - backend/medieval_forge/services/pipeline/contracts.py (stop_event field)
    - frontend/src/stores/useRunStore.ts (12-entry PIPELINE_STAGES)
  affects:
    - backend/medieval_forge/services/pipeline/__init__.py (rewired to 4-stage sequential calls)
tech_stack:
  added: []
  patterns:
    - "4-stage split: apply_median / remove_fragments / smooth_per_territory / merge_small_blobs"
    - "StageCancelled exception for cooperative cancel (cfg.stop_event threading.Event)"
    - "sha256[:16] version_token from sorted(reads) + sorted(upstream_tokens)"
    - "threading.RLock for _STAGE_CACHE concurrent access"
    - "StageEntry latest+prior pair per stage per project"
key_files:
  created:
    - backend/medieval_forge/services/pipeline/cache.py
    - backend/medieval_forge/services/pipeline/dag.py
    - backend/tests/unit/_cleanup_monolith_snapshot.py
  modified:
    - backend/medieval_forge/services/pipeline/cleanup.py
    - backend/medieval_forge/services/pipeline/contracts.py
    - backend/medieval_forge/services/pipeline/__init__.py
    - backend/tests/unit/test_cleanup_split.py
    - backend/tests/unit/test_dag_tokens.py
    - backend/tests/unit/test_stage_cache.py
    - frontend/src/stores/useRunStore.ts
    - frontend/src/stores/__tests__/useRunStore.test.ts
    - frontend/src/components/workspace/__tests__/RunLogPanel.test.tsx
    - frontend/src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx
decisions:
  - "Monolith cleanup_and_smooth removed entirely (not kept alongside split functions) — plan requirement"
  - "stop_event uses threading.Event directly (not a string forward-ref) since import threading is added at module scope"
  - "_cleanup_monolith_snapshot.py created before rewriting cleanup.py so parity assertion has the gold-standard reference"
  - "Task 3 rewire done during Task 1 to unblock test collection (import error from __init__.py importing cleanup_and_smooth)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-10"
  tasks_completed: 3
  files_created: 3
  files_modified: 10
---

# Phase 04 Plan 01: DAG + Cache Infrastructure Summary

**One-liner:** Pipeline cache topology (4-function cleanup split, sha256 version_token, RLock-guarded _STAGE_CACHE, 12-stage DAG_ORDER) delivered as a pure refactor with byte-equal parity at default cfg.

## What Was Built

### Task 1: Split cleanup.py into 4 cacheable functions + StageCancelled

`cleanup_and_smooth` monolith replaced with 4 separately callable functions:

| Function | Lines | Input guard | Purpose |
|----------|-------|-------------|---------|
| `apply_median` | ~20 | `raw.copy()` | 8 median filter passes (kernels 11/11/9/9/7/7/5/5) |
| `remove_fragments` | ~18 | `med.copy()` | Drop barony fragments < cfg.fragment_min_px |
| `smooth_per_territory` | ~15 | allocates fresh result | Per-territory Gaussian smoothing, winner-takes-all |
| `merge_small_blobs` | ~14 | `sm.copy()` | Merge final baronies < cfg.blob_merge_px |

`StageCancelled(stage_name)` exception defined; `_check_cancel(cfg, stage)` called at function entry AND inside the 8-pass median loop (D-14 cancel < 2 s).

`RegionConfig` gained `stop_event: Optional[threading.Event] = field(default=None)` — default None preserves Phase 01 parity exactly.

`services/pipeline/__init__.py` rewired: the 3-rapid-emit block replaced with 4 real sequential start/done pairs emitting `median`, `fragment`, `smooth`, `merge`.

6 unit tests pass (test_cleanup_split.py): no-mutate guards for apply_median, remove_fragments, merge_small_blobs; smooth_per_territory returns a new array; per-stage parity vs monolith inline verification; D-17 chain parity assertion.

### Task 2: cache.py + dag.py

**cache.py public API:**
- `StageEntry(token, array, prior_token, prior_array)` — dataclass
- `_STAGE_CACHE: dict[str, dict[str, StageEntry]]` — module-level dict
- `cache_get(project_id, stage_name) -> Optional[StageEntry]`
- `cache_put(project_id, stage_name, token, array)` — promotes current to prior atomically under RLock
- `cache_clear_project(project_id)` — drops all stage entries for a project

**dag.py public API:**
- `compute_version_token(stage_name, reads, cfg, upstream_tokens) -> str` — 16-char sha256 hex
- `STAGE_READS: dict[str, frozenset[str]]` — 12 entries, single source of truth
- `DAG_ORDER: tuple[str, ...]` — 12 entries: landmask, border, voronoi, median, fragment, smooth, merge, hierarchy, render, lookup, metadata, export
- `DAG_PARENTS: dict[str, tuple[str, ...]]` — upstream edge map

STAGE_READS reference table:

| Stage | Reads |
|-------|-------|
| median | `{median_passes}` |
| fragment | `{fragment_min_px}` |
| smooth | `{smooth_sigma}` |
| merge | `{blob_merge_px}` |
| hierarchy | `{}` (upstream array only) |
| export | `{output_dir}` |

8 unit tests pass (4 dag_tokens + 4 stage_cache): token stability, sigma isolation, median invalidation, upstream cascade, put/get lifecycle, prior promotion, clear isolation, concurrent thread-safety.

### Task 3: Frontend PIPELINE_STAGES + D-17 parity gate

`useRunStore.ts` PIPELINE_STAGES expanded from 11 to 12: `'cleanup'` removed, `'median'` and `'fragment'` added between `'voronoi'` and `'smooth'`.

Updated tests:
- `useRunStore.test.ts`: test name and length assertion updated
- `RunLogPanel.test.tsx`: stage count 11→12, pending count 8→9
- `ProjectDetail.workspace.test.tsx`: 4 assertions updated (11→12)

**D-17 parity gate:** `pytest tests/parity/test_iberia_868.py -x -q` — 11 passed, byte-equal lookup PNGs confirmed at default cfg.

**vitest:** 156 passed, 34 skipped, 0 failed.

## Parity Verification

```
pytest tests/parity/test_iberia_868.py -x -q
...........                                                         [100%]
11 passed in 40.36s
```

Byte-equal confirmation: the 4 split functions called in sequence produce identical output to the Phase 01 monolith `cleanup_and_smooth` at default `iberia_config()`. The split is a pure refactor — no semantic change at default cfg (D-17).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Rewired __init__.py import during Task 1 to unblock test collection**
- **Found during:** Task 1 GREEN phase
- **Issue:** Running `pytest tests/unit/test_cleanup_split.py` after writing the split functions failed with `ImportError: cannot import name 'cleanup_and_smooth'` because `__init__.py` still imported the removed monolith. The conftest imports the full app, which imports `__init__.py`.
- **Fix:** Replaced `from .cleanup import cleanup_and_smooth` with the 4-name import AND replaced the call site in one batch (Task 3 Step 1 done during Task 1 to unblock the suite).
- **Files modified:** `backend/medieval_forge/services/pipeline/__init__.py`
- **Commit:** 92e6fbd (included in Task 1 commit)

**2. [Rule 1 - Bug] Frontend tests hardcoded stage counts**
- **Found during:** Task 3 vitest run
- **Issue:** 5 tests in `RunLogPanel.test.tsx` and `ProjectDetail.workspace.test.tsx` hardcoded `11` for stage counts, breaking when PIPELINE_STAGES expanded to 12. Not noted in plan's `<action>` section.
- **Fix:** Updated 6 hardcoded assertions to 12 (or 9 for the pending count that was 12 - 2 done - 1 active).
- **Files modified:** `RunLogPanel.test.tsx`, `ProjectDetail.workspace.test.tsx`
- **Commit:** 22b3ec2

**3. [Rule 2 - Missing Critical Functionality] Created _cleanup_monolith_snapshot.py before rewriting cleanup.py**
- **Found during:** Advisor pre-flight call
- **Issue:** Plan's step 3 instructs creating the snapshot file for parity tests, but the plan's ordering would have the executor rewrite cleanup.py first and then create the snapshot from memory. Creating it first avoids reconstruction from git history.
- **Fix:** Created `_cleanup_monolith_snapshot.py` as the first action of Task 1 before modifying cleanup.py.
- **Files modified:** `backend/tests/unit/_cleanup_monolith_snapshot.py`
- **Commit:** 92e6fbd

## Commits

| Hash | Message | Files |
|------|---------|-------|
| 92e6fbd | feat(04-01): split cleanup.py into 4 cacheable functions + StageCancelled | cleanup.py, contracts.py, __init__.py, test_cleanup_split.py, _cleanup_monolith_snapshot.py |
| f5dbd9e | feat(04-01): add cache.py + dag.py with version_token + STAGE_READS + DAG_ORDER | cache.py, dag.py, test_dag_tokens.py, test_stage_cache.py |
| 22b3ec2 | feat(04-01): expand PIPELINE_STAGES to 12 entries + D-17 parity verified | useRunStore.ts + 3 test files |

## Known Stubs

None. All 14 unit tests written in this plan are fully implemented with real assertions.

## Threat Flags

None. Plan 04-01 refactors internal pipeline modules only — no new HTTP endpoints, no new auth surfaces, no user-input parsing, no new data flows across trust boundaries. The `_STAGE_CACHE` RLock (T-04-01-01) and `StageCancelled` propagation contract (T-04-01-02) are mitigated as documented in the plan's threat register.

## Self-Check: PASSED
