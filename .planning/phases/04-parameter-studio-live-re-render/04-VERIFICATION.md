---
phase: 04-parameter-studio-live-re-render
verified: 2026-05-11T12:30:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 1
overrides:
  - must_have: "Move σ from 3.0 → 4.5 reformats territories visibly in <500ms without full re-run"
    reason: "Functional contract verified (pixel diff visible after slider drag — UAT test 4+11, Playwright SC-3 spec). Strict 500ms wall-clock target explicitly moved to Phase 05 optimization via accepted Checkpoint #2 (commit f703865, message: 'relax SC-3 wall-clock budget to 30s pending Phase 05 optimization'). 30s budget applies for Phase 04."
    accepted_by: "veiodruida@gmail.com"
    accepted_at: "2026-05-11T09:45:13Z"
deferred_to_04_1:
  # Phase 04.1 is not yet in ROADMAP.md (only 02.1 is formalized).
  # These items are deferred by documented intent — not regressions.
  # UAT polish gaps (severity noted):
  - truth: "Map canvas keeps current zoom/pan when slider triggers a re-render"
    addressed_in: "Phase 04.1 (backlog — to be opened)"
    severity: major
    root_cause: "CanvasViewer.tsx:206-208 — fitToView() re-runs on every projection reference change"
    evidence: "04-06-HUMAN-UAT.md Gaps section, item 1"
  - truth: "User can preview the previous render alongside the new one to judge slider impact"
    addressed_in: "Phase 04.1 (backlog — to be opened)"
    severity: minor
    evidence: "04-06-HUMAN-UAT.md Gaps section, item 2"
  - truth: "User can verify that a barony's size/extent matches the historical 868 AD dataset"
    addressed_in: "Phase 04.1 (backlog — to be opened)"
    severity: minor
    evidence: "04-06-HUMAN-UAT.md Gaps section, item 3"
  # Code review warnings (from 04-REVIEW.md):
  - truth: "Cancel→POST race puts the run store in error state instead of gracefully retrying (WR-01)"
    addressed_in: "Phase 04.1 (backlog — to be opened)"
    evidence: "04-REVIEW.md WR-01: postRenderCancel→postRender 409 race window"
  - truth: "_RUN_QUEUES and _RUN_TASKS not evicted after run; late stream subscriber hangs (WR-02)"
    addressed_in: "Phase 04.1 (backlog — to be opened)"
    evidence: "04-REVIEW.md WR-02: finally block omits _RUN_QUEUES.pop and _RUN_TASKS.pop"
  - truth: "Dispatch logic duplicated between ParameterSidebar.tsx and useParameterStudioDispatch.ts (WR-03)"
    addressed_in: "Phase 04.1 (backlog — to be opened)"
    evidence: "04-REVIEW.md WR-03: divergence risk if WR-01 fix applied to only one copy"
---

# Phase 04: Parameter Studio (Live Re-render) Verification Report

**Phase Goal:** The same canvas drives the pipeline. Sliders for σ, median passes, fragment threshold, blob-merge threshold; toggles for per-stage outputs; incremental re-render.
**Verified:** 2026-05-11T12:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | Explicit DAG with `version_token` per stage drawn BEFORE first slider | VERIFIED | `dag.py` (`compute_version_token`, `DAG_ORDER`, `STAGE_READS`) committed in `f5dbd9e`/`92e6fbd` (Plan 04-01). Slider components landed in `9d35bcd` (Plan 04-03). Order confirmed via git log. |
| SC-2 | Backend incremental endpoint per stage; in-memory cache of intermediate arrays | VERIFIED | `run_pipeline_incremental` in `__init__.py`, `cache.py` with `_STAGE_CACHE`/`cache_put`/`cache_get`/`cache_clear_project` (RLock-guarded), `render.py` POST/GET/cancel endpoints + `GET /stage/{name}.png`, registered in `main.py`. |
| SC-3 | Move σ from 3.0 → 4.5 reformats territories visibly in <500ms without full re-run | PASSED (override) | Functional contract satisfied: pixel diff verified in UAT tests 4+11 and Playwright `parameter-studio-sc3.spec.ts` (Buffer.compare assertion). 500ms wall-clock relaxed to 30s by accepted Checkpoint #2 (commit `f703865`). Override: Phase 05 optimization target. |
| SC-4 | Cancel restores prior state; Konva `clearCache()` after every geometric mutation | VERIFIED | `priorTokens` / `revertStage` / `revertValues` wired through `useRunStore` → `usePipelineParams`; `CanvasViewer` calls `stage.getLayers().forEach(layer.clearCache(); layer.batchDraw())` gated on `[effectiveCacheVersion, stageView]`. CR-01 (wrong-arity `StageCancelled`) fixed in commit `1aaafd7` with regression tests. UAT test 9 passed: "Cancel reverts slider + canvas". |

**Score:** 4/4 truths verified (1 via accepted override)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/medieval_forge/services/pipeline/dag.py` | `compute_version_token` + `STAGE_READS` + `DAG_ORDER` + `DAG_PARENTS` | VERIFIED | Exports confirmed; 12-entry `DAG_ORDER`; `STAGE_READS["smooth"] == frozenset({"smooth_sigma"})` isolates σ from median token. |
| `backend/medieval_forge/services/pipeline/cache.py` | `_STAGE_CACHE` + `StageEntry` + RLock helpers | VERIFIED | `threading.RLock` present; `cache_put` promotes prior→latest atomically; `cache_clear_project` clears both `_STAGE_CACHE` and `_VORONOI_CACHE`. |
| `backend/medieval_forge/services/pipeline/cleanup.py` | 4 split functions + `StageCancelled` | VERIFIED | `apply_median`, `remove_fragments`, `smooth_per_territory`, `merge_small_blobs` all present with `.copy()` guards; `StageCancelled.__init__` takes one arg. `cleanup_and_smooth` absent from production code. |
| `backend/medieval_forge/services/pipeline/contracts.py` | `RegionConfig.stop_event` field | VERIFIED | `stop_event: Optional[threading.Event] = field(default=None)` at line 131; `import threading` present. |
| `backend/medieval_forge/api/v3/_run_state.py` | `_RUN_QUEUES`, `_RUN_TASKS`, `_RUN_STOP_EVENTS`, `is_run_alive` | VERIFIED | All four dicts present; `is_run_alive` checks `_RUN_TASKS[project_id].done()` and returns `'generate'|'render'|None`. |
| `backend/medieval_forge/api/v3/render.py` | POST/GET/cancel/stage.png routes | VERIFIED | Router registered in `main.py`; `CfgOverrides` pydantic model validates σ ∈ [3.0,4.5], median_passes ∈ [1,12]; `extra="forbid"` on both models. |
| `backend/medieval_forge/services/pipeline/__init__.py` | `run_pipeline_incremental` | VERIFIED | Defined at line 441; `_write_outputs_to_disk` shared between full and incremental paths (D-17); Option A selective writes gated on `affected` stages. |
| `frontend/src/stores/usePipelineParams.ts` | Slider state, debounce, `revertValues` | VERIFIED | `revertValues` restores from `preRenderValues` snapshot; `markRendered` captures snapshot before each dispatch. |
| `frontend/src/stores/useRunStore.ts` | 12-entry `PIPELINE_STAGES`; `priorTokens`; `revertStage` | VERIFIED | `PIPELINE_STAGES` has 12 entries (`median`, `fragment` replace `cleanup`); `priorTokens: Record<string, string>` initialized; `revertStage` spreads into `priorTokens` map. |
| `frontend/src/components/canvas/ParameterSidebar.tsx` | 4 SliderCards + StageViewToggle + sidebar | VERIFIED | Renders `smooth_sigma`, `median_passes`, `fragment_min_px`, `blob_merge_px` with PT-BR labels. Collapse toggle wired. |
| `frontend/src/components/canvas/SliderCard.tsx` | Slider + numeric input + reset icon | VERIFIED | File exists; UAT test 3 (slider cards render) and test 10 (reset icon) passed. |
| `frontend/src/components/canvas/StageViewToggle.tsx` | 5 radios + `stageView` state | VERIFIED | `usePipelineParams` `stageView` wired to `RadioGroup.Root`; UAT tests 2, 5, 6 passed. |
| `frontend/src/components/canvas/CanvasViewer.tsx` | `clearCache()` on `[effectiveCacheVersion, stageView]` | VERIFIED | `stage.getLayers().forEach(layer => { layer.clearCache(); layer.batchDraw() })` in useEffect gated on `[effectiveCacheVersion, stageView]`; `priorTokens.render` folds into `effectiveCacheVersion`. |
| `frontend/src/components/canvas/BaronyLayer.tsx` | Konva `Text` labels at centroids (D-12) | VERIFIED | `fontSize={10}`, `fill="#FFFFFF"`, `shadowBlur={1}`, `shadowColor="black"`, 12-char truncation with `…`; UAT test 8 passed. |
| `frontend/src/pages/ProjectDetail.tsx` | `<ParameterSidebar projectId={id} />` mounted | VERIFIED | Imported and mounted as first child of the horizontal flex container; commit `d2e7534`. |
| `frontend/tests/e2e/parameter-studio-sc3.spec.ts` | SC-3 Playwright spec with pixel diff + timing | VERIFIED | Real assertions: `Buffer.compare(before, after) !== 0`; wall-clock `< 30_000ms`; no `test.skip`. |
| `frontend/tests/e2e/parameter-studio-cancel.spec.ts` | SC-4 Playwright spec with cancel + revert | VERIFIED | Real assertions for slider revert and canvas prior-state restore; `< 500ms` CI budget. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `dag.py::compute_version_token` | `cleanup.py` split functions | `STAGE_READS["median"] = frozenset({"median_passes"})` — σ change does NOT invalidate median token | WIRED | Grep confirmed: `STAGE_READS["smooth"] = frozenset({"smooth_sigma"})` — token isolation correct. |
| `render.py` POST endpoint | `_run_state.py::is_run_alive` | 409 gate before task creation | WIRED | `alive_kind = is_run_alive(project_id)` at line 206; raises 409 if alive. |
| `render.py` cancel endpoint | `contracts.py::stop_event` | `stop_event.set()` → `_check_cancel` → `StageCancelled("write")` | WIRED | CR-01 fixed; single-arg constructor; regression tests `test_stage_cancelled_constructor_takes_exactly_one_arg` + `test_write_outputs_check_cancel_uses_single_arg` in `test_cleanup_split.py`. |
| `__init__.py::run_pipeline` | `cache.py::cache_clear_project` | Called at top of `/generate` path before stages run | WIRED | `cache_clear_project(project_id)` call confirmed in `__init__.py`. |
| `CanvasViewer.tsx` | `useRunStore::priorTokens` | `effectiveCacheVersion = priorTokens.render ?? cacheVersion` | WIRED | Confirmed in CanvasViewer useEffect; prior-token swap triggers cache-bust URL on cancel. |
| `useCanvasArtifacts.ts` | `stageView` differentiator | `queryKey: ['territories-geojson', projectId, cacheVersion, stageView]` | WIRED | Confirmed in Plan 04-04 implementation; stage-view radio switch re-fetches correct raster. |
| `main.py` | `render.py::router` | `app.include_router(v3_render_router, prefix="/api")` | WIRED | Confirmed at `main.py:55`. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `CanvasViewer.tsx` | `effectiveCacheVersion` | `useRunStore.cacheVersion` (bumped by `updated_at` DB write in `render.py:154-158`) | Yes — DB write confirmed; `proj.updated_at = datetime.now(timezone.utc)` triggers TanStack query refetch | FLOWING |
| `ParameterSidebar.tsx` | Slider values | `usePipelineParams.values` (real state with defaults from `PARAM_DEFAULTS`) | Yes — Zustand store with typed defaults; `revertValues` restores from snapshot | FLOWING |
| `BaronyLayer.tsx` | Barony label text | `baronies` array from `useCanvasArtifacts` GeoJSON | Yes — fetched from `/api/v3/projects/{id}/artifacts/baronies.geojson` | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Evidence | Status |
|----------|----------|--------|
| SC-1: DAG structure lands before sliders | Git log: `dag.py` commits `f5dbd9e`/`92e6fbd` predate `9d35bcd` (ParameterSidebar) | PASS |
| SC-2: Incremental endpoint returns 202 + run_id | `render.py:224` returns `{"run_id": run_id, "status": "scheduled", "kind": "render"}` with `status_code=202` | PASS |
| SC-3: Pixel diff visible after slider drag | UAT test 11 + Playwright `Buffer.compare(before, after) !== 0` assertion | PASS |
| SC-4: `clearCache()` fires after geometric mutation | `CanvasViewer.tsx` effect with explicit `stage.getLayers().forEach(layer.clearCache())` | PASS |
| CR-01 fix: `StageCancelled("write")` single arg | `__init__.py:129` confirmed; regression test `test_write_outputs_check_cancel_uses_single_arg` present | PASS |
| Slider bounds validated (ASVS V5) | `CfgOverrides` with `Field(ge=3.0, le=4.5)` for `smooth_sigma`; `extra="forbid"` | PASS |

Full UAT: 12/12 tests passed (see `04-06-HUMAN-UAT.md`). Playwright specs: 2 specs with real assertions (no `test.skip`).

Step 7b: Behavioral spot-checks run against codebase only (servers not started). Runtime verification covered by UAT 12/12.

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SC-1 | 04-01 | Explicit DAG with version_token drawn BEFORE first slider | SATISFIED | `dag.py` + `cache.py` landed in Plan 04-01; slider UI in Plan 04-03 |
| SC-2 | 04-02 | Backend incremental endpoint per stage; in-memory cache | SATISFIED | `run_pipeline_incremental` + `_STAGE_CACHE` + `/render` trio |
| SC-3 | 04-02, 04-06 | σ 3.0→4.5 produces visible pixel diff (timing override applied) | SATISFIED (override) | UAT + Playwright spec; 500ms→30s accepted |
| SC-4 | 04-03, 04-04 | Cancel restores prior state; `clearCache()` after geometric mutation | SATISFIED | `priorTokens` + `revertStage` + `revertValues` + `clearCache` in CanvasViewer |

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `render.py:108` (`sf` unused parameter) | Dead code — `sf` accepted but `AsyncSessionLocal` imported directly | Info (IN-01) | Misleading signature; no functional bug. Deferred to 04.1. |
| `cleanup.py:55` (kernel schedule hardcoded for 8 passes) | Passes 9-12 silently use `sz=5` (same as pass 8) | Info (IN-02) | Undocumented behavior when `median_passes > 8`; slider allows up to 12. Deferred to 04.1. |

No blockers found. CR-01 (`StageCancelled` wrong arity) was the only critical finding and is confirmed fixed in commit `1aaafd7`.

---

### Deferred Items (Phase 04.1)

Items explicitly deferred — they do not affect Phase 04 closure.

| # | Item | Destination | Severity |
|---|------|-------------|----------|
| 1 | Zoom resets on slider re-render — `fitToView()` fires on every projection reference change (UAT gap) | Phase 04.1 | Major |
| 2 | Before/after preview affordance missing — no comparison handle for slider impact (UAT gap) | Phase 04.1 | Minor |
| 3 | Barony historical data discoverability — no in-app panel linking to source data (UAT gap) | Phase 04.1 | Minor |
| 4 | Cancel→POST 409 race puts run store in `error` instead of retrying (WR-01) | Phase 04.1 | Warning |
| 5 | `_RUN_QUEUES`/`_RUN_TASKS` not evicted after run; late stream subscriber hangs (WR-02) | Phase 04.1 | Warning |
| 6 | Dispatch logic duplicated in `ParameterSidebar.tsx` and `useParameterStudioDispatch.ts` (WR-03) | Phase 04.1 | Warning |

Note: Phase 04.1 is not yet formalized in ROADMAP.md (only Phase 02.1 appears). The backlog items should be recorded in `.planning/backlog.md` and a ROADMAP entry created when Phase 04.1 is planned.

---

### Human Verification Required

None. The 12/12 UAT session (2026-05-11, recorded in `04-06-HUMAN-UAT.md`) covered all success criteria requiring human judgment:
- SC-3 functional contract (test 4: sigma drag produces visible re-render; test 11: pixel diff observable)
- SC-4 cancel behavior (test 9: slider reverts, canvas restores prior render)
- UI/UX verification (tests 1-8, 10, 12: layout, labels, radios, collapse, console errors)

The 3 UAT gaps are polish improvements, not failures of Phase 04 success criteria.

---

### Gaps Summary

No gaps. All four Phase 04 success criteria are satisfied:

- **SC-1** is structurally verified: `dag.py` with 12-entry `DAG_ORDER` and `compute_version_token` was committed in Plan 04-01 before any slider component existed.
- **SC-2** is functionally verified: the incremental render endpoint, in-memory stage cache with prior-array preservation, and cross-router 409 gate are all wired and tested.
- **SC-3** is satisfied via accepted override: the functional requirement (visible pixel diff after slider drag) is met and verified; the strict 500ms wall-clock budget was explicitly relaxed to 30s by documented developer decision, with the 500ms target delegated to Phase 05.
- **SC-4** is functionally verified: the cancel revert path (backend stop_event, StageCancelled, stage_cancel SSE, priorTokens swap, revertValues, Konva clearCache) is wired end-to-end; the critical CR-01 bug was fixed before phase closure.

---

_Verified: 2026-05-11T12:30:00Z_
_Verifier: Claude (gsd-verifier)_
