---
phase: 08
plan: "08"
subsystem: landmask-editor
tags: [landmask, dag-invalidation, per-country-kd-tree, pitfall-3, warning-4, warning-5, tdd]
dependency_graph:
  requires: [08-05, 08-06a, 08-06b, 08-07]
  provides: [LandmaskEditorHeader, landmask-mode-VertexEditLayer, landmask_replace-endpoint, DAG-04-cascade]
  affects: [08-09, 08-11]
tech_stack:
  added: []
  patterns:
    - "landmask_override field on RegionConfig: None=default parity, set=override path in build_land_mask"
    - "STAGE_READS['landmask'] includes 'landmask_override' → version_token invalidates on edit (DAG-04)"
    - "VertexEditLayer editableLayer prop: 'baronies'|'landmask'; cyan #06b6d4 handles in landmask mode"
    - "PT/ES border (40 pts) as Konva.Line listening=false — Pitfall 3 invariant enforced"
    - "All landmask handle ops funnel through setVerticesAndLog chokepoint (WARNING-6)"
    - "build_per_country_trees helper in voronoi.py for CLAUDE.md Rule #3 assertion tests"
key_files:
  created:
    - frontend/src/components/editor/LandmaskEditorHeader.tsx
    - frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx
    - backend/tests/integration/test_landmask_edit.py
    - backend/tests/integration/test_landmask_cascade.py
  modified:
    - frontend/src/components/canvas/VertexEditLayer.tsx
    - frontend/src/components/canvas/LayerTogglePanel.tsx
    - frontend/src/stores/useEditorStore.ts
    - backend/medieval_forge/api/v3/editor.py
    - backend/medieval_forge/api/v3/render.py
    - backend/medieval_forge/services/pipeline/contracts.py
    - backend/medieval_forge/services/pipeline/dag.py
    - backend/medieval_forge/services/pipeline/landmask.py
    - backend/medieval_forge/services/pipeline/voronoi.py
decisions:
  - "landmask_override on RegionConfig (not a new cfg class) preserves single-mutable-input invariant (D-V3-05)"
  - "build_land_mask fast-path returns early when override set — pt_data/es_municipalities ignored (T-08-08-01)"
  - "DoS cap (T-08-08-02) enforced imperatively in editor.py dispatch (Pydantic untyped dict cannot validate nested list length)"
  - "build_per_country_trees helper added to voronoi.py — exposes Rule #3 invariant for test assertions without changing setup_baronies signature"
  - "Rule 1 bug fix: build_land_mask default path now guards n==0 to avoid np.argmax ValueError on all-ocean input"
  - "Cascade wiring: _render_producer queries latest landmask_replace EditEvent and sets cfg.landmask_override before pipeline run; without this DAG-04 tokens changed but build_land_mask re-ran from municipality data"
metrics:
  duration_minutes: 80
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 9
---

# Phase 08 Plan 08: Landmask Editor — Manual/Auto Toggle + DAG-04 Cascade Summary

Editable landmask polygon layer with 2-mode toggle (Manual/Auto-immediate), cyan vertex handles, PT/ES border read-only enforcement (Pitfall 3), and full DAG-04 cascade invalidation via `landmask_override` on `RegionConfig`.

## What Was Built

### Task 1 — Frontend LandmaskEditorHeader + VertexEditLayer landmask mode (TDD)

**`frontend/src/components/editor/LandmaskEditorHeader.tsx`** — NEW (62 lines):
- Manual/Auto-immediate RadioGroup toggle (D-05)
- Orange Badge `"Modo auto: ~10s por edição"` visible in auto mode
- `"Aplicar landmask"` Button `variant="outline"` visible in manual mode only (UI-SPEC Discretion #5)
- `onApply` callback for parent to POST `/editor/apply op_type='landmask_replace'`

**`frontend/src/components/canvas/VertexEditLayer.tsx`** — EXTENDED:
- New `editableLayer: 'baronies' | 'landmask'` prop
- `landmaskCoords` prop: renders cyan `#06b6d4` Circle handles when `editableLayer='landmask'`
- `borderCoords` prop: PT/ES border (40 pts) rendered as `Konva.Line listening={false}` (Pitfall 3 — no pointer events)
- DEV assertion: `console.assert(borderCoords.length === 40, ...)` using `import.meta.env.DEV`
- Landmask dragend in auto-immediate mode fires `onLandmaskCoordsChange` (D-05)
- All ops route through `setVerticesAndLog` with `op: 'landmask_vertex_move'` (WARNING-6 chokepoint)
- Local coord state buffers manual-mode drags until Apply

**`frontend/src/components/canvas/LayerTogglePanel.tsx`** — EXTENDED:
- New optional props: `projectId`, `branchId`, `onApplyLandmask`
- `Separator` + `LandmaskEditorHeader` section below the 5 layer checkboxes

**`frontend/src/stores/useEditorStore.ts`** — EXTENDED:
- `EditOp.op` union extended with `'landmask_vertex_move' | 'landmask_vertex_add' | 'landmask_vertex_delete'`

**Tests (5 + 3 = 8 frontend tests):**
- `LandmaskEditorHeader.test.tsx`: 5 tests — initial state Manual, auto shows orange badge, manual shows outline button, auto hides button, clicking Apply calls onApply
- `VertexEditLayer.test.tsx`: 3 new landmask tests — cyan handles in landmask mode, border line has listening=false, auto-immediate mode wiring

**Frontend: 25 tests green (5 LandmaskEditorHeader + 20 VertexEditLayer). `tsc --noEmit` clean.**

### Task 2 — Backend landmask_replace op + DAG cascade (TDD)

**`backend/medieval_forge/services/pipeline/contracts.py`** — EXTENDED:
- `RegionConfig.landmask_override: Optional[List[Tuple[float, float]]] = None`
- None = default (D-17 parity carry-forward); set = editor replace path
- T-08-08-01: does not touch `border_polygon`

**`backend/medieval_forge/services/pipeline/dag.py`** — EXTENDED:
- `STAGE_READS["landmask"]` now includes `"landmask_override"` (WARNING-4 fix / DAG-04)
- Version token for landmask changes when override is set → triggers full cascade

**`backend/medieval_forge/services/pipeline/landmask.py`** — EXTENDED:
- `build_land_mask` fast-path: when `cfg.landmask_override is not None`, rasterize directly from override polygon (skip PT/ES municipality loop)
- Island removal with `n==0` guard preserved in fast-path
- Rule 1 bug fix: default path now also guards `n==0` to avoid `np.argmax` ValueError on all-ocean input

**`backend/medieval_forge/services/pipeline/voronoi.py`** — EXTENDED:
- New `build_per_country_trees(condados: list[dict]) -> dict[str, cKDTree]` helper
- Exposes CLAUDE.md Rule #3 invariant assertion API: `len(result) == number of distinct countries`

**`backend/medieval_forge/api/v3/editor.py`** — EXTENDED:
- `ApplyOpBody.op_type` regex extended: `^(split|merge|translate|landmask_replace)$`
- `landmask_replace` dispatch: validates `new_landmask_coords` presence + 50000 cap (T-08-08-02)
- Returns standard BLOCKER-1 response (no geometry keys)

**Tests (18 integration tests):**
- `test_landmask_edit.py` (10 tests): endpoint response shape, count bump, edit_events row, coords in payload, DoS cap rejection, contracts field, STAGE_READS inclusion, token invalidation, token stability, per-country KD-tree count
- `test_landmask_cascade.py` (8 tests): token cascade chain, border cfg isolation, DAG parents, stage reads, default parity, distinct overrides differ, build_land_mask override path, build_land_mask none path

**Backend: 31 integration tests green (18 new + 13 pre-existing). Parity tests green.**

### Cascade Wiring Fix (post-Task-2 deviation, commit 6d7cfee)

**`backend/medieval_forge/api/v3/render.py`** — EXTENDED:
- `_render_producer` now queries the latest `landmask_replace` EditEvent for `branch_id` before calling `run_pipeline_incremental`
- If found: `cfg.landmask_override = [tuple(pt) for pt in coords]` — ensures `build_land_mask` uses the editor-supplied polygon
- Without this: DAG-04 tokens changed correctly (version_token includes `landmask_override`) but the cfg field was always `None` (built from `load_region` which has no edit_event knowledge), so `build_land_mask` re-ran from original municipality data ignoring the edit

**`backend/medieval_forge/api/v3/editor.py`** — EXTENDED (landmask_replace dispatch):
- Added `cache_clear_branch(project_id, body.branch_id)` after persist — belt-and-suspenders alongside DAG token change

**`backend/tests/integration/test_landmask_cascade.py`** — EXTENDED:
- Added `TestRenderProducerCascadeWiring` class (1 test): simulates the exact DB read `_render_producer` uses and asserts `cfg.landmask_override` equals persisted coords — regression guard

**Backend: 97 integration tests green after wiring fix (19 landmask + 78 pre-existing).**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] np.argmax ValueError on all-ocean input in build_land_mask default path**
- **Found during:** Task 2, test_build_land_mask_none_override_uses_input_data
- **Issue:** `build_land_mask` with empty pt_data + no municipalities → `land` array all-False → `nd_label` returns `n=0` → `sizes[1:]` is empty → `np.argmax([])` raises `ValueError: attempt to get argmax of an empty sequence`
- **Fix:** Guard `if n > 0: if len(sizes) > 1:` around the island-removal block in both fast-path and default path
- **Files modified:** `backend/medieval_forge/services/pipeline/landmask.py`
- **Commit:** 5fede89

**2. [Rule 2 - Missing Critical Security] DoS cap on new_landmask_coords cannot use Pydantic field constraint on untyped dict**
- **Found during:** Task 2, T-08-08-02 implementation
- **Issue:** `ApplyOpBody.payload` is typed as `dict` (untyped), so Pydantic cannot validate `max_length` on `payload.new_landmask_coords`. A 50001-item list would pass Pydantic validation silently.
- **Fix:** Added imperative len() check in the `landmask_replace` dispatch branch; returns HTTP 422 when exceeded
- **Files modified:** `backend/medieval_forge/api/v3/editor.py`
- **Commit:** 5fede89

**3. [Rule 2 - Missing Critical Functionality] voronoi.py did not expose per-country tree builder for test assertions**
- **Found during:** Task 2, test_per_country_kd_tree_invariant_preserved
- **Issue:** `setup_baronies` builds two KD-trees internally but returns them as positional tuple values, not queryable by country key. Test needed `build_per_country_trees(condados) -> dict[country, KDTree]`.
- **Fix:** Added `build_per_country_trees` helper that groups condados by `country` key and builds one tree per country. Does not change `setup_baronies` signature (D-01 verbatim port preserved).
- **Files modified:** `backend/medieval_forge/services/pipeline/voronoi.py`
- **Commit:** 5fede89

## Known Stubs

None — all planned functionality is wired. The `onApplyLandmask` callback in `LayerTogglePanel` defaults to a no-op when not provided by parent; full wiring into `CanvasViewer` is deferred to plan 08-11 (CanvasViewer integration).

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: client-supplied-polygon-coords | `editor.py` /editor/apply landmask_replace | Client supplies new_landmask_coords; used for persist only. T-08-08-01 mitigated: border_polygon NOT in payload, never overwritten. T-08-08-02 mitigated: 50000 cap enforced imperatively. Coords are not trusted for raster render directly — they flow through cfg.landmask_override into build_land_mask on next /render call. |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `LandmaskEditorHeader.tsx` created | FOUND |
| `LandmaskEditorHeader.test.tsx` filled (5 tests) | FOUND |
| `VertexEditLayer.tsx` landmask mode | FOUND |
| `LayerTogglePanel.tsx` Separator + LandmaskEditorHeader | FOUND |
| `useEditorStore.ts` EditOp extended | FOUND |
| `contracts.py` landmask_override field | FOUND |
| `dag.py` STAGE_READS['landmask'] includes landmask_override | FOUND |
| `landmask.py` fast-path when override set | FOUND |
| `voronoi.py` build_per_country_trees | FOUND |
| `editor.py` op_type regex includes landmask_replace | FOUND |
| `test_landmask_edit.py` 10 tests | FOUND |
| `test_landmask_cascade.py` 8 tests | FOUND |
| variant="outline" in LandmaskEditorHeader | FOUND (count=1) |
| color="orange" in LandmaskEditorHeader | FOUND (count=1) |
| 5 LandmaskEditorHeader tests green | PASSED |
| 20 VertexEditLayer tests green | PASSED |
| 18 backend integration tests green | PASSED |
| Parity tests green | PASSED |
| tsc --noEmit clean | PASSED |
| commit b57f4fa (Task 1) | FOUND |
| commit 5fede89 (Task 2) | FOUND |
| render.py _render_producer reads latest landmask_replace event | FOUND (6d7cfee) |
| editor.py landmask_replace calls cache_clear_branch | FOUND (6d7cfee) |
| TestRenderProducerCascadeWiring (1 test) | FOUND (6d7cfee) |
| 97 integration tests green after cascade wiring fix | PASSED |
| commit 6d7cfee (cascade wiring fix) | FOUND |
