---
phase: 05-canvas-editing-advanced
plan: 01
subsystem: stores + backend-api
tags: [terrain-paint, overlay, zustand, fastapi, geojson, tdd]
dependency_graph:
  requires: [04-canvas-editing-basic]
  provides: [TerrainType contracts, terrain_types store slice, overlay uiStore, brush editorStore, paintTerrain API client, paint-terrain backend endpoint]
  affects: [useProjectStore temporal diff, territories.geojson feature properties, edit.py router]
tech_stack:
  added: []
  patterns: [zundo pause/resume _handleSet pattern for compound-op batching, GeoJSON feature properties as terrain storage, Shapely Point.contains land mask guard, URL.revokeObjectURL blob lifecycle]
key_files:
  created:
    - backend/tests/api/test_paint_terrain.py
    - frontend/src/stores/__tests__/uiStore.test.ts
  modified:
    - frontend/src/types/editing.ts
    - frontend/src/stores/useProjectStore.ts
    - frontend/src/stores/uiStore.ts
    - frontend/src/stores/useEditorStore.ts
    - frontend/src/api/edit.ts
    - backend/medieval_forge/schemas.py
    - backend/medieval_forge/api/edit.py
    - backend/medieval_forge/services/territories_geojson.py
decisions:
  - "terrain_types optional in ProjectGeometryState interface (backward compat with existing callers using the type without terrain)"
  - "activeTerrain/brushRadius added to EditorStore only (not EditorState) — transient UI state, not canonical editor state shape"
  - "hydrate() pauses temporal, sets state, resumes + clears to prevent initial load polluting undo history"
  - "uiStore.test.ts URL.revokeObjectURL stubbed at top-level (jsdom does not define it)"
  - "test_setTerrainType_records_diff_entry asserts prePauseSnapshot stored (zundo _handleSet stores snapshot verbatim, not diff delta)"
metrics:
  duration: ~35min
  completed: 2026-04-27
  tasks: 3
  files: 8
---

# Phase 05 Plan 01: Foundation Contracts + Backend Paint-Terrain Endpoint Summary

Interface-first plan establishing the complete type contracts, store extensions, and backend endpoint required by Plans 5.2 (terrain UI) and 5.3 (overlay UI) — with TDD Wave 0 RED→GREEN cycle completed.

## What Was Built

**TerrainType contracts (editing.ts):** `TerrainType` union, `TERRAIN_TYPES` tuple, `PaintTerrainRequest/Response`, `ToolMode` extended with `'paint'`, `ProjectGeometryState.terrain_types` (optional for backward compat), `TERRAIN_HEX/EMOJI/LABELS_PT` palette constants, `TERRAIN_UNPAINTED_HEX`.

**useProjectStore terrain_types slice:** `terrain_types: Record<string, TerrainType>` added to `GeometrySlice` (partialize + diff). Three new actions: `setTerrainType`, `clearTerrainType`, `restoreTerrainTypes`. `diff()` extended with a third comparison block for `terrain_types`. `patchTemporalPauseResume` `hasChanged` check extended to include terrain_types reference. `hydrate()` now accepts optional fourth `terrain_types` argument and pauses/clears temporal so initial load does not pollute undo history.

**uiStore overlay + terrain layer:** `'terrain'` added to `LayerName` (default off). `overlayImageUrl: string | null` and `overlayOpacity: number` (0.5 default). `setOverlayImageUrl` with `URL.revokeObjectURL` discipline (revokes prior blob on replace or null). `setOverlayOpacity` with 0–1 clamping.

**useEditorStore brush state:** `activeTerrain: TerrainType | null` (null default), `brushRadius: number` (30 default, range 10–80). `setActiveTerrain` and `setBrushRadius` actions.

**paintTerrain API client (edit.ts):** `export const paintTerrain(projectId, req): Promise<PaintTerrainResponse>` — always write-through (no `?persist=` flag).

**Backend schemas.py:** `TerrainType = Literal[...]` and `PaintTerrainRequest/PaintTerrainResponse` Pydantic models.

**Backend edit.py:** `POST /projects/{project_id}/edit/paint-terrain` — filters `territory_ids` to `known_ids` (T-5-01 security), rejects invalid `terrain_type` via Pydantic Literal (T-5-02), checks `land_mask.contains(Point(lon, lat))` per centroid, persists via `save_territories + touch_project`.

**territories_geojson.py:** `load_territories` returns `terrain_type: Optional[str]`; `save_territories` writes `terrain_type` property only when present (compact format).

## Test Results

- `backend/tests/api/test_paint_terrain.py`: 5/5 GREEN
- `backend/tests/api/test_edit_api.py`: 13/13 GREEN (no regression)
- `frontend/src/stores/__tests__/useProjectStore.test.ts`: 10/10 GREEN
- `frontend/src/stores/__tests__/uiStore.test.ts`: 5/5 GREEN
- `frontend/src/stores/__tests__/useEditorStore.test.ts`: 4/4 GREEN (existing, no regression)
- `npx tsc --noEmit`: 0 errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `ProjectGeometryState.terrain_types` made optional**
- **Found during:** Task 1 TypeScript compile check
- **Issue:** Adding `terrain_types` as required field to `ProjectGeometryState` broke all existing callers (CanvasViewer, SelectionFloatingToolbar, SplitTool, validation.test.ts) that construct `ProjectGeometryState`-typed objects without the new field
- **Fix:** Made `terrain_types?: Record<string, TerrainType>` optional — store initializes to `{}`, type remains compatible
- **Files modified:** `frontend/src/types/editing.ts`
- **Commit:** 1ac091e

**2. [Rule 1 - Bug] `hydrate()` must pause/clear temporal to avoid polluting undo history**
- **Found during:** Task 2 implementation + advisor pre-work note
- **Issue:** Plain `set({...})` in hydrate with the new `terrain_types` diff block would record an undo entry for the initial project load (plan notes "paused per existing pattern" but existing hydrate was NOT paused)
- **Fix:** Added `pause()` → `set(...)` → `resume()` → `clear()` in hydrate body
- **Files modified:** `frontend/src/stores/useProjectStore.ts`
- **Commit:** 7810709

**3. [Rule 1 - Bug] `test_setTerrainType_records_diff_entry` expectation corrected**
- **Found during:** Task 2 test run (1 failing)
- **Issue:** Test expected `lastEntry.terrain_types` to contain `{c1: undefined}` (the diff delta), but zundo `_handleSet(prePauseSnapshot, ...)` stores the snapshot verbatim — `terrain_types: {}` (empty, pre-change). The diff function is called on `undo()`, not on recording.
- **Fix:** Corrected assertion to `expect(lastEntry.terrain_types).toEqual({})` — verifies a history entry WAS recorded and contains the terrain_types slice (the pre-change snapshot)
- **Files modified:** `frontend/src/stores/__tests__/useProjectStore.test.ts`
- **Commit:** 7810709

**4. [Rule 2 - Missing] `URL.revokeObjectURL` stub for jsdom test environment**
- **Found during:** Task 2 uiStore test run (2 failing with "revokeObjectURL does not exist")
- **Issue:** jsdom does not define `URL.revokeObjectURL`, so `vi.spyOn(URL, 'revokeObjectURL')` throws before the test body runs
- **Fix:** Added `if (typeof URL.revokeObjectURL === 'undefined') { URL.revokeObjectURL = () => undefined }` at top of uiStore.test.ts
- **Files modified:** `frontend/src/stores/__tests__/uiStore.test.ts`
- **Commit:** 7810709

## Known Stubs

None — no UI components wired in this plan. All contracts are backend/store/type layer only.

## Threat Flags

None — all threat model mitigations from the plan's `<threat_model>` were implemented (T-5-01 known_ids filter, T-5-02 Pydantic Literal). No new unplanned surface introduced.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| All 10 key files exist on disk | PASSED |
| Commits 1ac091e, 7810709, aff1f6b exist in git log | PASSED |
| `TerrainType` appears 6x in editing.ts | PASSED |
| `terrain_type` appears 4x in territories_geojson.py (load + save) | PASSED |
| `paint_terrain`/`paint-terrain` appears 2x in edit.py | PASSED |
| 18 backend tests green (5 new + 13 regression) | PASSED |
| 19 frontend store tests green | PASSED |
| `npx tsc --noEmit` exits 0 | PASSED |
