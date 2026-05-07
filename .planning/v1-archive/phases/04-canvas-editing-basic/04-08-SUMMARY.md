---
phase: 04-canvas-editing-basic
plan: 08
subsystem: frontend-canvas-editing
tags: [validation, persistence, save-strategy, export-gate, badges, tdd, wave-6, D-06, D-07, EDIT-01, EDIT-02, EDIT-03, EDIT-04]
dependency_graph:
  requires:
    - frontend/src/types/editing.ts (ValidationIssue, SaveStrategy, SaveStatus, ProjectGeometryState)
    - frontend/src/stores/useProjectStore.ts (territories, capitals, projectId)
    - frontend/src/stores/useEditorStore.ts (pushUndoLabel, clearRubberBandSelection)
    - frontend/src/api/edit.ts (moveCapital, reshapeGeometry, mergeTerritories, splitTerritory — all extended)
    - frontend/src/components/canvas/CanvasViewer.tsx (capital drag end + vertex-edit commit)
    - frontend/src/components/canvas/SelectionFloatingToolbar.tsx (handleMerge)
    - frontend/src/components/canvas/SplitTool.tsx (commit function)
    - frontend/src/pages/ProjectDetail.tsx (export button location, header)
    - frontend/src/context/ProjectionContext.tsx (useProjection — used in ValidationBadgesLayer)
  provides:
    - frontend/src/services/validation.ts (validateTerritories, pointInPolygon)
    - frontend/src/stores/useValidationStore.ts (setIssuesForIds, clearAll)
    - frontend/src/components/canvas/ValidationBadgesLayer.tsx (8px circles at centroids)
    - frontend/src/services/persistence.ts (usePersistenceStore, onOperationFinalized, manualSave, initPersistence, useSaveStatus, useSaveStrategy, setStrategy)
    - frontend/src/components/canvas/SaveStatusIndicator.tsx (header badge)
    - frontend/src/components/canvas/SettingsPanel.tsx (Radix Dialog + RadioGroup)
    - frontend/src/hooks/useBeforeUnloadGuard.ts (beforeunload guard)
  affects:
    - Phase 5 (EDIT-05 terrain brush, EDIT-06 reference overlay — same EditToolbar/CanvasViewer patterns)
    - Phase 6 (full VALIDATE-01..07 panel extends useValidationStore pattern established here)
    - Phase 6 (export ZIP regeneration — now gated properly by errorCount)
tech_stack:
  added: []
  patterns:
    - "validateTerritories: pure function, client-side only, checks empty_polygon / polygon_invalid / capital_outside via ray-casting; non_adjacent_merge surfaced at merge time"
    - "useValidationStore: plain Zustand (no temporal) — derived state, not history. setIssuesForIds merges new results for affected ids, keeps issues for unaffected"
    - "Stable Zustand selector pattern: pull raw array with useStore(s => s.arr), filter with useMemo — avoids inline filter returning new array every render (React useSyncExternalStore infinite loop)"
    - "persistence.ts: module-level debounceTimer + clearTimeout on each onOperationFinalized call (T-04-08-03 single timer pattern)"
    - "EditOptions { persist: boolean } optional second arg on all 4 edit helpers; ?persist=false query string appended when false"
    - "manualSave: dynamic import('../api/edit') to avoid circular dependency at module scope"
    - "initPersistence(): called once at main.tsx module scope before React tree mounts"
key_files:
  created:
    - frontend/src/services/validation.ts
    - frontend/src/services/__tests__/validation.test.ts
    - frontend/src/stores/useValidationStore.ts
    - frontend/src/components/canvas/ValidationBadgesLayer.tsx
    - frontend/src/services/persistence.ts
    - frontend/src/services/__tests__/persistence.test.ts
    - frontend/src/components/canvas/SaveStatusIndicator.tsx
    - frontend/src/components/canvas/SettingsPanel.tsx
    - frontend/src/hooks/useBeforeUnloadGuard.ts
  modified:
    - frontend/src/api/edit.ts (EditOptions + saveSnapshot)
    - frontend/src/hooks/useUndoShortcut.ts (Ctrl+S → manualSave)
    - frontend/src/components/canvas/CanvasViewer.tsx (revalidation + persist flag + onOperationFinalized)
    - frontend/src/components/canvas/InspectorSidebar.tsx (Problemas de Validação block)
    - frontend/src/components/canvas/SelectionFloatingToolbar.tsx (persist flag + onOperationFinalized)
    - frontend/src/components/canvas/SplitTool.tsx (persist flag + onOperationFinalized)
    - frontend/src/pages/ProjectDetail.tsx (export gate + SaveStatusIndicator + SettingsPanel + useBeforeUnloadGuard)
    - frontend/src/main.tsx (initPersistence)
decisions:
  - "Stable selector for useValidationStore in InspectorSidebar: pull raw issues array then filter with useMemo — inline filter selector creates new array every render, triggering React useSyncExternalStore infinite loop (same gotcha as zundo temporal in P07)"
  - "manualSave uses dynamic import('../api/edit') to load saveSnapshot — avoids circular dep between persistence.ts → api/edit.ts → (indirectly) stores"
  - "ValidationBadgesLayer uses useProjection() — safe here because it renders as a Konva Layer inside Stage which is inside ProjectionProvider in CanvasViewer (unlike SplitTool hook called before JSX return)"
  - "initPersistence called at module scope in main.tsx before React renders — guarantees strategy loaded from localStorage before any component reads useSaveStrategy()"
  - "onOperationFinalized placed after pushUndoLabel() in success path only — never in catch blocks (T-04-08-04 contract: explicit-mode crash loses edits by design)"
metrics:
  duration: "~90 minutes"
  completed: "2026-04-24"
  tasks: 2
  files: 17
---

# Phase 04 Plan 08: Validation + Persistence (D-06, D-07) Summary

**One-liner:** Per-operation validation with red/amber canvas badges + export gate (D-06), and 3-strategy configurable persistence engine (auto/per_op/explicit) with SaveStatusIndicator, SettingsPanel, Ctrl+S flush, and beforeunload guard (D-07) — closing Phase 4.

## What Was Done

### Task 1 — Validation Service + Badges + Inspector + Export Gate (D-06)

**`frontend/src/services/validation.ts`** — pure validation function:
- `validateTerritories(affectedIds, state)` checks only the listed territory IDs against the current store snapshot
- Rules: `empty_polygon` (exterior ring empty), `polygon_invalid` (<4 vertices OR duplicate consecutive points), `capital_outside` (ray-casting `pointInPolygon` test)
- MultiPolygon handled: capital-in-any-ring check; each ring checked for empty
- Intentionally not a full map scan — Phase 6 adds VALIDATE-01..07 full panel

**`frontend/src/stores/useValidationStore.ts`** — plain Zustand store (no temporal):
- `setIssuesForIds(affectedIds, newIssues)` replaces issues for affected condados, keeps the rest — correct merge semantics
- `clearAll()` for test teardown and future reset-on-project-load

**`frontend/src/components/canvas/ValidationBadgesLayer.tsx`** — Konva Layer:
- 8px `Circle` at each condado centroid with +12px Y offset (above capital icon)
- `#e5484d` (Radix red-9) for error, `#f76b15` (Radix orange-9) for warning
- `listening={false}` — no interaction capture
- `useProjection()` safe here (inside ProjectionProvider, unlike SplitTool hook)

**CanvasViewer wiring**:
- Capital drag end: `setIssuesForIds(response.affected_ids, validateTerritories(...))` after `pushUndoLabel`
- Vertex-edit commit: validation in `.then()` after successful `reshapeGeometry` PATCH

**InspectorSidebar**:
- `useValidationStore(s => s.issues)` + `useMemo` filter (avoids useSyncExternalStore loop)
- "Problemas de Validação" block rendered below Group 4 when selectedId has issues
- Color-coded `Badge` (red/orange) + `Text` message per issue

**ProjectDetail export gate**:
- `Tooltip` wraps `Button`; content switches between "Corrija os erros de validação primeiro" and "Exportar pacote Unity"
- `disabled={exportZip.isPending || errorCount > 0}` (frontend gate; Phase 6 adds backend enforcement per T-04-08-01)

**Tests**: 7 validation unit tests GREEN (empty polygon, <4 vertices, duplicate points, capital outside, valid polygon, skip unknown id, only validate affectedIds).

### Task 2 — Persistence Strategy Engine (D-07)

**`frontend/src/services/persistence.ts`** — strategy engine:
- `usePersistenceStore`: Zustand store with strategy (from localStorage), status, markEdit/markSaved/markUnsaved
- `onOperationFinalized()`: dispatches by strategy — auto (markEdit + 1500ms debounce timer), per_op (markSaved), explicit (markUnsaved). Single global timer cleared on each call (T-04-08-03)
- `manualSave()`: explicit-only, dynamic-imports `saveSnapshot`, calls `POST /api/projects/{id}/geometry/save`, sets saved on 200
- `initPersistence()`: loads strategy from localStorage at bootstrap, resets status to 'saved'
- T-04-08-05: `loadStrategy()` validates value is one of `{auto, per_op, explicit}`; falls back to 'auto'

**`frontend/src/api/edit.ts`** extensions:
- `EditOptions { persist: boolean }` optional second arg on `moveCapital`, `mergeTerritories`, `splitTerritory`, `reshapeGeometry`
- `?persist=false` query string appended when `opts.persist === false`
- `saveSnapshot(projectId, { territories, capitals })` → `POST /api/projects/{id}/geometry/save`

**`frontend/src/components/canvas/SaveStatusIndicator.tsx`**:
- Radix `Badge`: green "Salvo ✓" / gray "Salvando…" / amber "Alterações não salvas"

**`frontend/src/components/canvas/SettingsPanel.tsx`**:
- Radix `Dialog.Root` (NOT Sheet — UI-SPEC constraint)
- `RadioGroup.Root` with 3 options: "Automático (1.5s após edição)" / "Por operação" / "Manual (Ctrl+S)"
- `setStrategy(v)` called on radio change — persists to localStorage immediately

**`frontend/src/hooks/useBeforeUnloadGuard.ts`**:
- Registers `beforeunload` handler when `strategy === 'explicit' && status === 'unsaved'`
- `e.preventDefault()` + `e.returnValue = ''` triggers browser confirmation dialog

**Call site wiring**:
- `useUndoShortcut.ts`: `Ctrl+S / Cmd+S` → `void manualSave()`
- `CanvasViewer.tsx`: capital drag + vertex-edit commit → `const persist = saveStrategy !== 'explicit'` → pass `{ persist }` to `moveCapital` / `reshapeGeometry`; `onOperationFinalized()` on success path
- `SelectionFloatingToolbar.tsx`: merge → persist flag + `onOperationFinalized()` after `pushUndoLabel`
- `SplitTool.tsx`: split commit → persist flag + `onOperationFinalized()` after `pushUndoLabel`
- `ProjectDetail.tsx`: `<SaveStatusIndicator />` + `<SettingsPanel />` in header Flex; `useBeforeUnloadGuard()` at component top
- `main.tsx`: `initPersistence()` at module scope before React tree

**Tests**: 8 persistence unit tests GREEN (auto debounce, per_op immediate, explicit unsaved, debounce reset on rapid calls, manualSave calls saveSnapshot + sets saved, manualSave no-op for non-explicit, initPersistence sets saved).

## Decision Coverage Table (D-01..D-09)

| Decision | Plan(s) | Coverage |
|----------|---------|----------|
| D-01: Capital drag UX (preview on release) | P05 | Full |
| D-02: Border vertex affordance (explicit edit + decimated) | P06 | Full |
| D-03: Merge via rubber-band + floating toolbar | P06 | Full |
| D-04: Split tool 3 sub-modes | P07 | Full |
| D-05: Named undo/redo transactions | P07 | Full |
| D-06: Real-time validation + inline badges + export gate | **P08** | Full |
| D-07: Configurable persistence strategy | **P08** | Full |
| D-08: Voronoi recalc scope (affected neighbors only) | P05 | Full |
| D-09: Edit mode gating (read-only vs editable) | P05 | Full |

## Requirement Coverage Table

| Requirement | Plan(s) | Coverage |
|-------------|---------|----------|
| EDIT-01: Capital drag → Voronoi recalc | P05 | Full |
| EDIT-02: Vertex-edit handles | P06 | Full |
| EDIT-03: Rubber-band multi-select + merge | P06 | Full |
| EDIT-04: Split tool 3 sub-modes | P07 | Full |
| EDIT-07: Named undo/redo keyboard + toolbar | P07 | Full |
| EDIT-08: Compound-op batching (beginTransaction/endTransaction) | P05, applied throughout | Full |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 263a792 | feat | Validation service + badges layer + inspector detail + export gate (D-06) |
| d3e58c4 | feat | Persistence strategy engine + SaveStatusIndicator + SettingsPanel + beforeunload guard (D-07) |
| 22b2713 | fix | Wire D-06 validation to merge and split finalize paths (SelectionFloatingToolbar + SplitTool) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Inline Zustand selector returning new array caused React infinite loop**
- **Found during:** Task 1 InspectorSidebar integration tests (9 tests failed with "Maximum update depth exceeded")
- **Issue:** `useValidationStore(s => selectedId ? s.issues.filter(...) : [])` creates a new array on every render call. React's `useSyncExternalStore` (used by Zustand internally) detects the getSnapshot result as unstable and enters a forced-rerender loop.
- **Fix:** Split into `const allIssues = useValidationStore(s => s.issues)` (stable reference) + `useMemo(() => allIssues.filter(...), [allIssues, selectedId])`. Added `import { useMemo }` to InspectorSidebar.
- **Files modified:** `frontend/src/components/canvas/InspectorSidebar.tsx`
- **Commit:** 263a792

**2. [Rule 1 - Bug] `response` variable out of scope after try block**
- **Found during:** TypeScript check after Task 1 — `TS2552: Cannot find name 'response'`
- **Issue:** In `handleCapitalDragEnd`, `const response = await moveCapital(...)` was declared inside the `try` block, making it inaccessible to the revalidation code after the `finally` block.
- **Fix:** Changed to `let affectedIds: string[] = []` declared before `try`, populated inside try block: `affectedIds = response.affected_ids`.
- **Files modified:** `frontend/src/components/canvas/CanvasViewer.tsx`
- **Commit:** 263a792

**3. [Rule 2 - Missing] Validation not wired to merge and split finalize paths**
- **Found during:** Post-task review — plan behavior spec states "After each finalize (capital drag end, merge success, split success, vertex-edit commit), call validateTerritories"
- **Issue:** `SelectionFloatingToolbar.handleMerge` and `SplitTool.commit` had persist flag + `onOperationFinalized()` wired but no `validateTerritories` / `setIssuesForIds` call. The `non_adjacent_multipolygon` warning was shown as a Toast only, not stored in `useValidationStore` (so InspectorSidebar and export gate would not see it).
- **Fix:** Added `validateTerritories` + `setIssuesForIds` calls after merge/split success in both files. For merge: also pushes `non_adjacent_merge` `ValidationIssue` to store alongside existing Toast. For split: validates both new territory halves. Added `setIssuesForIds` to `useCallback` dep array in `useSplitTool`.
- **Files modified:** `frontend/src/components/canvas/SelectionFloatingToolbar.tsx`, `frontend/src/components/canvas/SplitTool.tsx`
- **Commit:** 22b2713

**4. [Rule 2 - Missing] Unused type imports in validation.ts caused tsc error**
- **Found during:** TypeScript check — `TS6196: 'GeoJSONPolygon' is declared but never used`
- **Issue:** Plan sample code imported `GeoJSONPolygon` and `GeoJSONMultiPolygon` as named type imports but the implementation uses duck-typing via `.type === 'Polygon'` checks; these types were unused.
- **Fix:** Removed the two unused type imports.
- **Files modified:** `frontend/src/services/validation.ts`
- **Commit:** 263a792

## Known Stubs

### Rendering gap: validation badges not visible until P09

`ValidationBadgesLayer` reads condado centroids from `TerritoryMetadataCondado.lon/lat` (the original centroid from `territory_metadata.json`). After edits (vertex drag, split, merge), the centroid positions in the metadata JSON do not update in real-time — only the polygon geometry in `useProjectStore.territories` changes. So the badge position may drift slightly from the actual condado center until the page is refreshed (metadata re-loaded).

This is the same P06 rendering-gap pattern: the source of truth for rendered positions is split between TanStack Query (metadata) and Zustand (edited geometry). P09 wires `TerritoryLayer` to consume store state; at that point centroid recomputation can be added.

Other stubs are fully wired: validation rules run on real geometry, export gate uses real error count, all 3 save strategies affect real API calls.

## Phase 4 Complete: All 6 EDIT Requirements End-to-End

| Requirement | Status |
|-------------|--------|
| EDIT-01: Capital drag → Voronoi recalc (<500ms) | Wired P05 |
| EDIT-02: Vertex-edit handles (D-P decimation) | Wired P06 |
| EDIT-03: Rubber-band multi-select + merge | Wired P06 |
| EDIT-04: Split tool 3 sub-modes | Wired P07 |
| EDIT-07: Named undo/redo (keyboard + toolbar) | Wired P07 |
| EDIT-08: Compound-op batching | Applied throughout P05-P08 |

## Recommendations for Phase 5 / Phase 6

- **Phase 5 (EDIT-05 terrain brush)**: Follow same hook-style pattern as `useSplitTool` — called in CanvasViewer body before JSX return, projection passed as parameter. Mount layer inside Stage.
- **Phase 6 (full validation panel)**: Extend `useValidationStore` — it's already structured to hold all issue types. The `validateTerritories` pure function can be replaced with a server-side call to the VALIDATE-01..07 endpoint while keeping the same store interface.
- **Phase 6 (export gate enforcement)**: Current gate is frontend-only (T-04-08-01). Phase 6 must add backend-side VALIDATE-07 check before allowing ZIP generation.
- **Phase 6 (revalidation on undo/redo)**: T-04-08-02: undo/redo does not trigger revalidation. After a temporal.undo(), the canvas may show stale validation badges. Phase 6 should hook into the zundo `onTemporalStateChange` callback to revalidate the full territory set.
- **P09 (centroid position accuracy)**: Once TerritoryLayer subscribes to Zustand store geometry, compute centroids from actual polygon coordinates so validation badge positions stay accurate after vertex edits.

## Threat Flags

No new trust boundaries beyond the plan's STRIDE register. All 5 mitigations verified:

| Threat | Status |
|--------|--------|
| T-04-08-01 (export bypass) | Mitigated: `disabled={errorCount > 0}` + Tooltip. Frontend-only gate documented. |
| T-04-08-02 (stale validation on undo/redo) | Accepted: deferred to Phase 6 per plan. |
| T-04-08-03 (debounce timer leak) | Mitigated: `clearTimeout(debounceTimer)` before each new schedule; single global timer. |
| T-04-08-04 (lost edits in explicit mode crash) | Accepted: beforeunload guard warns on close; single-session only by design. |
| T-04-08-05 (localStorage tampering) | Mitigated: `loadStrategy()` validates value is one of `{auto, per_op, explicit}`; falls back to 'auto'. |

## Self-Check: PASSED
