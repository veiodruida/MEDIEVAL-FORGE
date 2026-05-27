---
phase: 08
plan: 02
subsystem: pipeline-cache
tags: [cache, branch, d-23, wave-2]
dependency_graph:
  requires: [08-01]
  provides: [branch-scoped-cache]
  affects: [08-03a, 08-03b, 08-04, 08-10]
tech_stack:
  added: []
  patterns:
    - "_STAGE_CACHE nested 3-level: [project_id][branch_id][stage] -> StageEntry"
    - "_VORONOI_CACHE nested 3-level: [project_id][branch_id] -> dict"
    - "cache_clear_branch for per-branch eviction (branch lifecycle)"
    - "branch_id threaded from HTTP body -> cfg.branch_id -> cache layer"
key_files:
  created:
    - backend/tests/integration/test_render_with_branch.py
  modified:
    - backend/medieval_forge/services/pipeline/cache.py
    - backend/medieval_forge/services/pipeline/contracts.py
    - backend/medieval_forge/services/pipeline/__init__.py
    - backend/medieval_forge/api/v3/render.py
    - backend/tests/unit/test_stage_cache_branch.py
    - backend/tests/integration/test_render_endpoint.py
    - backend/tests/integration/test_render_cancel.py
  deleted:
    - backend/tests/unit/test_stage_cache.py
decisions:
  - "branch_id defaults to 'main' everywhere — preserves byte-equal Iberia parity for all pre-Phase-8 projects"
  - "generate.py left untouched — always uses branch_id='main' via RegionConfig default, no body param needed"
  - "test_iberia_868_render_default.py left untouched — cfg.branch_id defaults to 'main', no explicit change required"
  - "test_stage_cache.py deleted (atomic swap) — test_stage_cache_branch.py is the single source of truth"
  - "_RUN_QUEUES/_RUN_TASKS keys kept as project_id string (not extended to tuple) — concurrent renders on different branches not needed in Wave 2; deferred per plan scope"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-27"
  tasks: 2
  files: 8
---

# Phase 08 Plan 02: Branch-Scoped Cache Key Extension Summary

Branch-aware cache layer: `_STAGE_CACHE` key extended from `(project_id, stage)` to `(project_id, branch_id, stage)` per D-23, atomically updating all 9 callsites across cache.py, the pipeline orchestrator, and the render endpoint.

## What Was Built

### Task 1: cache.py signature extension + contracts.py

- `_STAGE_CACHE` shape: `dict[project_id][branch_id][stage_name] -> StageEntry`
- `_VORONOI_CACHE` shape: `dict[project_id][branch_id] -> dict`
- `cache_get(project_id, branch_id, stage_name)` — 3-arg
- `cache_put(project_id, branch_id, stage_name, token, array)` — 3-arg
- `cache_clear_project(project_id)` — drops ALL branches for project (DAG-05)
- `cache_clear_branch(project_id, branch_id)` — NEW: evicts single branch (BRANCH-02)
- `RegionConfig.branch_id: str = "main"` added — default preserves Iberia parity
- `test_stage_cache.py` deleted; `test_stage_cache_branch.py` promoted with 6 tests (BRANCH-01/02, DAG-04/05)

### Task 2: Orchestrator + render endpoint + test updates (atomic)

- `pipeline/__init__.py`: all `cache_get`/`cache_put` calls in `run_pipeline` and `run_pipeline_incremental` gain `cfg.branch_id` (9 callsites updated)
- `_VORONOI_CACHE` reads/writes in `__init__.py` nested under `[project_id][cfg.branch_id]`
- `api/v3/render.py`: `RenderRequest.branch_id` field with `Field(default="main", pattern=r"^[a-zA-Z0-9_-]{1,255}$")` (T-08-02-01 mitigated)
- `_render_producer` receives `branch_id` param, sets `cfg.branch_id` via `dataclasses.replace`
- `cache_get` in StageCancelled handler uses `branch_id` (not hardcoded "main")
- `get_stage_raster` uses `"main"` (stage viz always reads main branch)
- `test_render_endpoint.py` Test 4: cache calls updated to 3-arg form
- `test_render_cancel.py` Test 4: cache calls updated to 3-arg form
- `test_render_with_branch.py`: 3 tests implementing BRANCH-04, BRANCH-05, DAG-01+02

## Deviations from Plan

### Intentional Scope Reductions

**1. generate.py — no changes made**
- Plan listed `generate.py` as a file to modify
- `_generate_producer` always cold-starts with `cfg = replace(load_region(...))` and calls `run_pipeline(cfg)` which uses `cfg.branch_id` defaulting to `"main"` — no explicit wiring needed
- `generate.py` POST body was intentionally not given a `branch_id` param: generate always creates on "main" (confirmed by plan's own note: "New projects always use 'main'")
- No change needed; no callsites to fix

**2. test_iberia_868_render_default.py — no changes made**
- Plan listed this file as needing `branch_id="main"` explicit update
- Both `cfg_gen = replace(load_region(...))` and `cfg_render = replace(load_region(...))` inherit `RegionConfig.branch_id = "main"` from the dataclass default
- Cache operations in `run_pipeline` and `run_pipeline_incremental` use `cfg.branch_id` which is already `"main"`
- Parity test passes without modification — confirmed by 24/24 integration tests passing

**3. _RUN_QUEUES/_RUN_TASKS keys kept as project_id string (not extended to tuple)**
- Plan Step 2 mentioned extending to `(project_id, branch_id)` tuple for per-branch single-flight
- Decision: deferred — concurrent renders on different branches is a Wave 4+ concern; the 409 gate per project_id is correct for current scope
- Documented as known limitation; plan 08-10 can revisit when branch-parallel rendering is needed

## Test Results

```
24/24 PASSED — unit/test_stage_cache_branch.py + integration/test_render_endpoint.py +
               integration/test_render_cancel.py + integration/test_render_with_branch.py
```

3 pre-existing failures in full suite (NOT caused by this plan):
- `test_llm_registry_*` — expects 3 providers, project has 6 (Phase 07.2 regression, out of scope)
- `test_run_pipeline_emits_22_events_in_canonical_order` — expects 24 events, got 26 (manual_edit stage added in 08-01, out of scope)

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1 | `615a3bf` | feat(08-02): extend cache key to (project_id, branch_id, stage) per D-23 |
| Task 2 | `4d07e17` | feat(08-02): update all 9 callsites to branch-scoped cache (D-23 atomic blast radius) |

## Known Stubs

None — all branch cache functionality is fully wired. `test_render_with_branch.py` uses stubs for pipeline execution speed but tests the real cache layer directly.

## Self-Check: PASSED
