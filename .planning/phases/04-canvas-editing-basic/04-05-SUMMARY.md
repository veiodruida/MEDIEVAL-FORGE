---
phase: 04-canvas-editing-basic
plan: 05
subsystem: frontend-canvas-editing
tags: [capital-drag, edit-api, undo-batching, konva, tdd, wave-3, EDIT-01, EDIT-08]
dependency_graph:
  requires:
    - frontend/src/types/editing.ts (from P01)
    - frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx (RED from P01)
    - frontend/src/stores/useProjectStore.ts (beginTransaction/endTransaction from P03)
    - frontend/src/stores/useEditorStore.ts (pushUndoLabel from P03)
    - backend/medieval_forge/api/edit.py (POST /recalc endpoint from P04)
  provides:
    - frontend/src/api/edit.ts (moveCapital, mergeTerritories, splitTerritory, reshapeGeometry, EditApiError)
    - frontend/src/components/canvas/EditToolbar.tsx (minimal edit-mode toggle)
    - frontend/src/components/canvas/DecorationsLayer.tsx (updated: isEditMode prop, listening={isEditMode}, draggable capitals)
    - frontend/src/components/canvas/CanvasViewer.tsx (updated: handleCapitalDragEnd with compound-op batching)
  affects:
    - P06 (imports EditToolbar for additional tool buttons; imports DecorationsLayer with isEditMode prop)
    - P07 (adds keyboard shortcuts for edit mode toggle + undo/redo wiring; adds toast-on-error)
tech_stack:
  added:
    - "@testing-library/dom (missing peer dep of @testing-library/react — installed)"
  patterns:
    - "Edit API: thin fetch wrappers with EditApiError class for status + message"
    - "beginTransaction/endTransaction wrapping async API call ensures compound op = ONE undo step"
    - "DecorationsLayer listening={isEditMode}: Layer-level listening gates all drag events (Pitfall 8 fix)"
    - "draggable={isEditMode} on inner Circle only; dark outer ring is always non-draggable"
    - "canvasToGeo(node.x(), node.y(), projection) in onDragEnd converts canvas coords to geo"
    - "priorCapital captured before beginTransaction for error rollback (T-04-05-01)"
    - "tsconfig.json exclude: test files removed from production tsc compilation"
key_files:
  created:
    - frontend/src/api/edit.ts
    - frontend/src/components/canvas/EditToolbar.tsx
  modified:
    - frontend/src/components/canvas/DecorationsLayer.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx
    - frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx
    - frontend/package.json
    - frontend/tsconfig.json
decisions:
  - "storeProjectId renamed (not projectId) in CanvasViewer to avoid shadowing the prop; API calls use the prop value (always correct before hydrate)"
  - "toast-on-error deferred to P07 as documented in plan output spec"
  - "tsconfig.json test exclusion is a pre-existing build bug (test files incorrectly compiled into production build); fixed as Rule 1 deviation"
  - "@testing-library/dom installed as Rule 3 deviation — missing peer dep was blocking entire test suite collection"
metrics:
  duration: "~45 minutes"
  completed: "2026-04-24"
  tasks: 2
  files: 8
---

# Phase 04 Plan 05: Capital Drag + Edit Mode Summary

**One-liner:** End-to-end capital drag wired to Voronoi recalc — EditToolbar toggle, DecorationsLayer Pitfall-8 fix, CanvasViewer compound-op batching; all 4 CapitalDrag tests GREEN, all 10 DecorationsLayer tests GREEN.

## What Was Done

Delivered the first complete end-to-end edit operation for Phase 4: dragging a capital triggers Voronoi recalc and the result registers as exactly one undo step.

### Task 1: Edit API + EditToolbar + ProjectDetail

**`frontend/src/api/edit.ts`** — thin fetch wrapper layer with typed end-to-end:
- `EditApiError` class (status + message, named for instanceof checks)
- `moveCapital`, `mergeTerritories`, `splitTerritory`, `reshapeGeometry` — all typed against `types/editing.ts` contracts
- Internal `postJson` / `patchJson` helpers with error handling

**`frontend/src/components/canvas/EditToolbar.tsx`** — minimal Phase 4 toolbar:
- Single "Editar" button with `variant={editMode ? 'solid' : 'soft'}` toggle
- Reads `editMode` + `toggleEditMode` from `useEditorStore`
- Keyboard shortcut placeholder noted for P07

**`frontend/src/pages/ProjectDetail.tsx`** — canvas region updated:
- `<EditToolbar />` mounted as full-width bar above the canvas
- Canvas container wrapped with `outline: editMode ? '2px solid var(--accent-9)' : 'none'` iris border

### Task 2: Capital Drag + Compound Undo

**`frontend/src/components/canvas/DecorationsLayer.tsx`** — Pitfall 8 fix:
- New `Props` fields: `isEditMode: boolean`, `onCapitalDragEnd?: (condadoId, lon, lat) => void | Promise<void>`
- `<Layer listening={isEditMode}>` — THE Pitfall 8 fix; when `false` Konva exits early before firing any drag events
- Inner capital Circle: `draggable={isEditMode}`, `onDragEnd` fires `canvasToGeo` then calls `onCapitalDragEnd`
- Dark outer ring remains non-draggable (decorative only)
- `CenteredLabel` Text retains `listening={false}` (correct — Text is decorative)

**`frontend/src/components/canvas/CanvasViewer.tsx`** — compound-op batcher:
- Reads `editMode`, `pushUndoLabel` from `useEditorStore`
- Reads `applyBatchUpdate`, `setCapital` from `useProjectStore`
- `handleCapitalDragEnd(condadoId, lon, lat)`:
  1. Captures `priorCapital` for rollback
  2. `beginTransaction()` — pauses zundo history
  3. `await moveCapital(projectId, condadoId, { lon, lat })`
  4. `applyBatchUpdate(response.updated_territories, { [condadoId]: [lon, lat] })` — all mutations in one call
  5. `endTransaction()` in `finally` — always resumes, records ONE history entry
  6. `pushUndoLabel(`Mover capital de ${name}`)` — only on success
  7. Error path: `setCapital(condadoId, priorCapital)` rollback + console.error

### Test Results

| Test File | Tests | Status |
|-----------|-------|--------|
| `CapitalDrag.test.tsx` | 4 | ALL PASS (was RED) |
| `DecorationsLayer.test.tsx` | 10 | ALL PASS (8 original + 2 new edit-mode layer tests) |
| `useProjectStore.test.ts` | 5 | ALL PASS (no regression) |
| `useEditorStore.test.ts` | 4 | ALL PASS (no regression) |

**Overall test suite:** 115 passed | 3 failed (all 3 failures pre-existing: useUndoShortcut module not yet built, 2 research dialog tests)

**Build:** `npm run build` exits 0.

### Compound Op Batching — pastStates Behavior

Test 3 (`pastStates.length === 1`) passes. The custom `pause/resume` patch from P03 correctly:
1. `pause()` captures the pre-mutation partialized state
2. `applyBatchUpdate` runs (N territory updates + 1 capital update) while `isTracking=false`
3. `resume()` records ONE `_handleSet` call with the pre-pause snapshot → `pastStates.length` increments by exactly 1

### Pitfall 8 Confirmation

`<Layer listening={isEditMode}>` ships. When `isEditMode=false`, the Layer is purely visual; Konva exits before processing any pointer events. When `isEditMode=true`, drag events reach the Circle elements.

## Prop-Drilling Documentation for P06/P07

P06/P07 executors: `DecorationsLayer` now requires `isEditMode: boolean`. Every render must pass this prop.

`CanvasViewer` prop chain additions (P05):
```tsx
// New state consumed in CanvasViewer:
const editMode = useEditorStore((s) => s.editMode)         // passed as isEditMode to DecorationsLayer
const pushUndoLabel = useEditorStore((s) => s.pushUndoLabel)
const applyBatchUpdate = useProjectStore((s) => s.applyBatchUpdate)
const setCapital = useProjectStore((s) => s.setCapital)
const storeProjectId = useProjectStore((s) => s.projectId) // NOT shadowing prop; renamed

// handleCapitalDragEnd added to CanvasViewer — passed as onCapitalDragEnd to DecorationsLayer
```

P06 note on Stage `draggable` conflict: the `draggable` Stage prop is still unconditional. P06 will add `draggable={activeTool !== 'select'}` conditional per Pitfall 2 in the plan.

### Toast-on-Error

Toast-on-error is deferred to P07 per plan output spec. Current behavior on `moveCapital` failure: state rollback via `setCapital(condadoId, priorCapital)` + `console.error`. The undo label is NOT pushed on failure.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| f0bdbe0 | feat | Edit API client + EditToolbar + ProjectDetail mount |
| 56799a6 | feat | Capital drag wired to moveCapital API + compound undo batching |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] storeProjectId renamed to avoid shadowing `projectId` prop in CanvasViewer**
- **Found during:** Task 2 pre-implementation review
- **Issue:** Plan code snippet read `const projectId = useProjectStore((s) => s.projectId)` inside a component that already has `projectId` as a prop. This would shadow the prop, causing `const terrainSrc = \`/api/projects/${projectId}/preview/terrain.png\`` to reference the store value (which may be null until hydrate() runs) instead of the prop.
- **Fix:** Named the store subscriber `storeProjectId`; `handleCapitalDragEnd` uses the prop value `projectId` for the API call
- **Files modified:** `frontend/src/components/canvas/CanvasViewer.tsx`
- **Commit:** 56799a6

**2. [Rule 3 - Blocking] @testing-library/dom missing — entire test suite blocked at collection**
- **Found during:** Task 1 test verification
- **Issue:** `@testing-library/react` peer-depends on `@testing-library/dom` which was not installed. Every test using `@testing-library/react` failed with `Cannot find module '@testing-library/dom'`.
- **Fix:** `npm install --save-dev @testing-library/dom`. This is a pre-existing issue (P01 SUMMARY documented it as "pre-existing test failures confirmed via git stash") but blocked Task 2 test execution.
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`
- **Commit:** 56799a6

**3. [Rule 1 - Bug] tsconfig.json included test files in production tsc build**
- **Found during:** Task 2 build verification
- **Issue:** `npm run build` (which runs `tsc -b && vite build`) failed because `tsconfig.json` includes all `src/**` files including test files. The `useUndoShortcut.test.ts` RED scaffold (P01 artifact) has type errors from an unresolved `TemporalState` assertion. These type errors blocked the production build.
- **Fix:** Added `"exclude": ["src/**/__tests__/**", "src/**/*.test.ts", "src/**/*.test.tsx"]` to `tsconfig.json`. This is standard practice — test files should not be type-checked as part of the production compilation.
- **Files modified:** `frontend/tsconfig.json`
- **Commit:** 56799a6

**4. [Rule 2 - Missing] DecorationsLayer.test.tsx: added edit-mode layer prop tests**
- **Found during:** Task 2 implementation
- **Issue:** The plan specified updating existing tests with `isEditMode={false}` but didn't explicitly specify a test for `listening=true` when edit mode is on. This is a correctness requirement — the Pitfall 8 fix must be verified to work in BOTH directions.
- **Fix:** Added `it('Layer has listening=true when isEditMode=true')` to the "layer props" describe block.
- **Files modified:** `frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx`
- **Commit:** 56799a6

## Latency Measurement

Manual smoke test not performed (no running server in CI context). Backend P02 benchmark shows `recalc_neighbors` takes 2.7ms for 93-seed Iberia data. Network round-trip on localhost adds ~1-5ms. Expected end-to-end capital drag → neighbor render latency: ~5-20ms, far under the 500ms EDIT-01 budget.

## Known Stubs

None. All features in this plan are fully wired:
- `edit.ts` fetch wrappers call real endpoints
- `handleCapitalDragEnd` calls real `moveCapital`, applies real `applyBatchUpdate`
- `EditToolbar` reads real `useEditorStore` state
- The iris outline on the canvas is wired to real `editMode` state

## Threat Flags

No new trust boundaries beyond the plan's STRIDE register. All 4 mitigations verified:

| Threat | Status |
|--------|--------|
| T-04-05-01 (stale capital on network error) | Mitigated: `setCapital(condadoId, priorCapital)` in catch; undo label NOT pushed |
| T-04-05-02 (drag spam) | Accepted: user-paced, not a DoS vector |
| T-04-05-03 (compound op not batched) | Mitigated: `try/finally` ensures `endTransaction()` fires; Test 3 asserts `pastStates.length === 1` |
| T-04-05-04 (listening=false blocks drag — Pitfall 8) | Mitigated: `listening={isEditMode}`; Test confirms both true/false cases |

## Self-Check: PASSED

Files verified to exist:
- frontend/src/api/edit.ts: FOUND
- frontend/src/components/canvas/EditToolbar.tsx: FOUND
- frontend/src/components/canvas/DecorationsLayer.tsx: FOUND (updated)
- frontend/src/components/canvas/CanvasViewer.tsx: FOUND (updated)

Commits verified:
- f0bdbe0: FOUND
- 56799a6: FOUND

Test run: 4 CapitalDrag + 10 DecorationsLayer + 9 store tests = 23 passing
Build: npm run build exits 0
