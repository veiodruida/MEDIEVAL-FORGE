---
phase: "04"
plan: "02"
subsystem: api-pipeline
tags: [wave-2, sse, incremental-render, dag, cache, cancel, parity, tdd]
dependency_graph:
  requires:
    - backend/medieval_forge/api/v3/_run_state.py (shared run-state dicts from this plan Task 1)
    - backend/medieval_forge/services/pipeline/cache.py (StageEntry + cache_get/cache_put from 04-01)
    - backend/medieval_forge/services/pipeline/dag.py (compute_version_token + DAG_ORDER from 04-01)
    - backend/medieval_forge/services/pipeline/cleanup.py (4 split functions + StageCancelled from 04-01)
  provides:
    - backend/medieval_forge/api/v3/_run_state.py
    - backend/medieval_forge/api/v3/render.py
    - backend/medieval_forge/services/pipeline/__init__.py (run_pipeline_incremental + _write_outputs_to_disk)
    - backend/medieval_forge/main.py (v3_render_router registered)
    - backend/tests/integration/test_render_endpoint.py (8 wired tests)
    - backend/tests/integration/test_render_cancel.py (4 wired tests)
    - backend/tests/parity/test_iberia_868_render_default.py (D-17 parity test)
  affects:
    - 04-03 (frontend slider hooks: POST /render + GET /render/stream consumer)
    - 04-04 (useCanvasArtifacts: GET /stage/{name}.png consumer)
    - 04-06 (e2e: parameter-studio-sc3 + cancel specs)
tech_stack:
  added: []
  patterns:
    - "Cross-router 409 via shared _run_state.py is_run_alive() — both /generate and /render checked"
    - "Completed-stages closure list in _render_producer (advisor item 2 fix)"
    - "_VORONOI_CACHE side-table for non-array voronoi intermediates (advisor item 1 fix)"
    - "_write_outputs_to_disk extracted as shared helper called by both run paths (D-17 by construction)"
    - "Pydantic Field(ge=, le=) + model_config extra=forbid on both CfgOverrides and RenderRequest (ASVS V5)"
    - "stage_name allowlist frozenset in /stage/{name}.png endpoint (T-04-02-06 no FS traversal)"
key_files:
  created:
    - backend/medieval_forge/api/v3/_run_state.py
    - backend/medieval_forge/api/v3/render.py
  modified:
    - backend/medieval_forge/api/v3/generate.py
    - backend/medieval_forge/services/pipeline/__init__.py
    - backend/medieval_forge/main.py
    - backend/tests/integration/test_render_endpoint.py
    - backend/tests/integration/test_render_cancel.py
    - backend/tests/parity/test_iberia_868_render_default.py
    - backend/tests/unit/test_v3_generate.py
    - backend/tests/unit/test_pipeline_module.py
    - backend/tests/unit/test_run_pipeline_on_stage.py
key-decisions:
  - "Completed-stages tracked via closure list in _render_producer (not return value from run_pipeline_incremental) — return value unavailable in except block on StageCancelled (advisor item 2)"
  - "_VORONOI_CACHE side-table stores non-array voronoi intermediates (bars, bpx, bc, bd, bk, nb, nc, land_2x) separately from _STAGE_CACHE which holds only numpy arrays (advisor item 1)"
  - "_write_outputs_to_disk extracted verbatim from run_pipeline body — no cleanup during extraction to preserve D-17 byte-equal guarantee"
  - "_RUN_KIND[project_id] set BEFORE task creation in both generate.py and render.py (advisor item 8 race guard)"
  - "extra=forbid on both CfgOverrides AND RenderRequest (not just the outer model) — covers both test_render_clamps and test_render_rejects_unknown_cfg_field"
  - "run_pipeline gains optional project_id=None param for cache population; None skips all cache machinery (Phase 01 CLI parity preserved)"
requirements-completed: ["SC-2", "SC-3", "SC-4"]
duration: "~35 minutes"
completed: "2026-05-10"
---

# Phase 04 Plan 02: Backend Incremental Render Summary

**Cross-router 409-gated SSE render trio (POST /render + stream + cancel) with DAG-walking run_pipeline_incremental, cooperative stop_event cancel, and D-17 byte-equal parity proven by full pipeline comparison test.**

## Performance

- **Duration:** ~35 minutes
- **Started:** 2026-05-10T17:00:00Z
- **Completed:** 2026-05-10T17:35:00Z
- **Tasks:** 2
- **Files created:** 2
- **Files modified:** 9

## Accomplishments

- Shared `_run_state.py` module with `is_run_alive()` enables cross-router 409 gate covering both `/generate` and `/render` — single-flight invariant proven by `test_render_409_when_generate_alive`
- `run_pipeline_incremental` walks 12-stage DAG, recomputes only dirty stages (token mismatch), writes all 10 output files via shared `_write_outputs_to_disk` helper
- D-17 incremental==full parity proven: cold-cache `run_pipeline_incremental` at default cfg produces byte-equal SHA-256 hashes for all 10 Unity contract files
- Cancel path (D-13/D-14): `stop_event.set()` propagates to `apply_median` between passes via `_check_cancel`; `stage_cancel` SSE events carry `prior_token`; cache NOT updated on cancel (atomicity invariant)
- 13 new tests wired (8 endpoint + 4 cancel + 1 D-17 parity); 115 total backend tests green

## 4 New Render Endpoints

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/v3/projects/{id}/render` | `{cfg_overrides: {smooth_sigma: 3.5}, stage_view: "..."}` | 202 `{run_id, status, kind}` or 409 |
| GET | `/api/v3/projects/{id}/render/stream` | — | SSE `stage_start/stage_done/stage_cancel/done` |
| POST | `/api/v3/projects/{id}/render/cancel` | — | 200 `{status: cancel_requested}` or 404 |
| GET | `/api/v3/projects/{id}/stage/{name}.png` | — | 200 PNG or 400 (bad name) or 404 (cache miss) |

## _run_state.py Shared Dicts + is_run_alive Contract

```python
_RUN_QUEUES: dict[str, asyncio.Queue[Optional[str]]]   # SSE producer per project
_RUN_TASKS: dict[str, asyncio.Task]                     # asyncio task per project
_RUN_STOP_EVENTS: dict[str, threading.Event]            # D-14 cancel signal per project
_RUN_KIND: dict[str, str]                               # 'generate' | 'render' per project

def is_run_alive(project_id: str) -> Optional[str]:
    """Return 'generate' | 'render' if alive, else None. D-04 cross-router gate."""
```

`_RUN_KIND` is set BEFORE task creation to eliminate the race window where `is_run_alive` could return `"unknown"`.

## run_pipeline_incremental DAG-Walk Logic

For each stage in `DAG_ORDER` (12 stages):

1. Compute `new_token = compute_version_token(stage, STAGE_READS[stage], cfg, upstream_tokens)`
2. If `cache_get(project_id, stage)` is None or `cached.token != new_token` → recompute, `cache_put` (only on success)
3. Otherwise → read `cache_get(project_id, stage).array` (skip recompute)

Cache typing strategy:
- `_STAGE_CACHE` (StageEntry.array) holds numpy arrays for all 12 stages' primary output
- `_VORONOI_CACHE` side-table holds non-array voronoi intermediates: `bars`, `bpx`, `bc`, `bd`, `bk`, `nb`, `nc`, `land_2x`
- On warm cache with only smooth_sigma changed: `median`, `fragment` stages skip; only `smooth`, `merge`, `hierarchy`, `render`, `lookup`, `metadata`, `export` recompute

## Test Counts

| File | Tests | Covers |
|------|-------|--------|
| `test_render_endpoint.py` | 8 | D-04 409 gate, D-05 bounds, D-18 fresh cfg, stage_view no-recompute |
| `test_render_cancel.py` | 4 | D-13 cache atomicity, D-14 < 2s cancel, stage_cancel events |
| `test_iberia_868_render_default.py` | 1 | D-17 incremental==full at default cfg (byte-equal SHA-256) |

Total new: **13 tests** (all passing).

## D-17 Incremental==Full Proof

```
pytest tests/parity/test_iberia_868_render_default.py -x -q
.                                                     [100%]
1 passed in 65.23s
```

All 10 Unity contract files (lookup PNGs, visual PNGs, JSON sidecars, mountain/river data) produce identical SHA-256 hashes from `run_pipeline` vs `run_pipeline_incremental` at default `iberia_config()` on cold cache.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Completed-stages closure list in _render_producer**
- **Found during:** Task 2 pre-implementation advisor review
- **Issue:** Plan skeleton read `affected` from `run_pipeline_incremental` return value inside the `except StageCancelled` block — but `asyncio.to_thread()` raises before returning when StageCancelled is raised, so `affected` would always be `[]` on cancel.
- **Fix:** Added `completed_stages: list[str]` closure list updated by the `on_stage` bridge on `"done"` events; used this in `except StageCancelled` instead of the return value.
- **Files modified:** `backend/medieval_forge/api/v3/render.py`
- **Committed in:** 43de932

**2. [Rule 2 - Missing Critical] _VORONOI_CACHE side-table for non-array intermediates**
- **Found during:** Task 2 pre-implementation advisor review
- **Issue:** `setup_baronies()` returns a 9-tuple with mixed types; `StageEntry.array: np.ndarray` cannot hold these. Plan skeleton silently glossed over this.
- **Fix:** Created `_VORONOI_CACHE: dict[str, dict]` module-level side-table in `__init__.py` storing `bars`, `bpx`, `bc`, `bd`, `bk`, `nb`, `nc`, `land_2x`, `pt_data`, `es_municipalities` per project. Cache key lookup remains numpy-array-only.
- **Files modified:** `backend/medieval_forge/services/pipeline/__init__.py`
- **Committed in:** 43de932

**3. [Rule 1 - Bug] test_pipeline_module.py signature check too strict**
- **Found during:** Task 2 GREEN phase, full suite run
- **Issue:** `test_run_pipeline_signature` asserted `params == ["cfg"]` exactly. Adding `project_id: Optional[str] = None` (backwards-compatible) broke this overly strict check.
- **Fix:** Updated assertion to check `"cfg" in params` and verify `project_id` defaults to None.
- **Files modified:** `backend/tests/unit/test_pipeline_module.py`
- **Committed in:** 43de932

**4. [Rule 1 - Bug] test_run_pipeline_on_stage.py uses stale 11-stage CANONICAL_STAGES**
- **Found during:** Task 2 GREEN phase, full suite run
- **Issue:** `CANONICAL_STAGES` still contained `"cleanup"` (old 11-stage model) — Plan 04-01 replaced it with `"median"` + `"fragment"` but this test wasn't updated (only `useRunStore.ts` was updated in Plan 04-01). The test had been silently broken since 04-01 landed.
- **Fix:** Updated `CANONICAL_STAGES` to 12-stage tuple with `"median"` + `"fragment"` replacing `"cleanup"`; updated docstring from 22 to 24 events.
- **Files modified:** `backend/tests/unit/test_run_pipeline_on_stage.py`
- **Committed in:** 43de932

**5. [Rule 2 - Missing Critical] extra=forbid on CfgOverrides (not just RenderRequest)**
- **Found during:** Task 2 design review — test_render_rejects_unknown_cfg_field exercises a nested unknown field
- **Issue:** Plan specified `model_config = {"extra": "forbid"}` on `RenderRequest` only. But `test_render_rejects_unknown_cfg_field` sends `{"cfg_overrides": {"unknown_field": 42}}` — unknown nested field. `CfgOverrides` also needed `extra=forbid`.
- **Fix:** Added `model_config = {"extra": "forbid"}` to `CfgOverrides` as well as `RenderRequest`.
- **Files modified:** `backend/medieval_forge/api/v3/render.py`
- **Committed in:** 43de932

---

**Total deviations:** 5 auto-fixed (2 Rule 2 missing critical, 2 Rule 1 bugs, 1 Rule 2 missing critical)
**Impact on plan:** All fixes essential for correctness. No scope creep. D-17 and D-13 would have been broken without items 1 and 2.

## Commits

| Hash | Message | Files |
|------|---------|-------|
| 250fc8b | refactor(04-02): extract _RUN_QUEUES/_RUN_TASKS to shared _run_state.py | _run_state.py, generate.py, test_v3_generate.py |
| 43de932 | feat(04-02): create render.py + run_pipeline_incremental + 12 integration tests | render.py, __init__.py, main.py, 5 test files |

## Known Stubs

None. All 13 tests written in this plan are fully implemented with real assertions. The parity test runs both pipeline paths end-to-end.

## Threat Flags

None beyond what the plan's threat register already covers. All T-04-02-01 through T-04-02-06 mitigations are implemented and verified by the integration test suite.

## Self-Check: PASSED

All files verified present; both commits verified in git log; 115 backend tests pass (103 unit+integration + 12 parity including D-17).
