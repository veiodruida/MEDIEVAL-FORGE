---
phase: 04-canvas-editing-basic
plan: 06
subsystem: frontend-canvas-editing
tags: [rubber-band-select, merge, vertex-edit, konva, undo-batching, wave-4, EDIT-02, EDIT-03]
dependency_graph:
  requires:
    - frontend/src/stores/useEditorStore.ts (rubberBandSelectionIds, activeTool, vertexEditCondadoId from P03)
    - frontend/src/stores/useProjectStore.ts (beginTransaction/endTransaction, applyBatchUpdate, setTerritory, removeTerritories from P03)
    - frontend/src/api/edit.ts (mergeTerritories, reshapeGeometry from P05)
    - frontend/src/components/canvas/CanvasViewer.tsx (Stage wiring from P05)
    - frontend/src/components/canvas/EditToolbar.tsx (minimal toolbar from P05)
    - frontend/src/context/ProjectionContext.tsx (useProjection hook)
    - frontend/src/lib/projection.ts (geoToCanvas, canvasToGeo)
    - backend (GET /vertex-handles endpoint from P02 — assumed available)
  provides:
    - frontend/src/hooks/useRubberBandSelection.ts (rubber-band logic, centroid containment, Stage mouse handlers)
    - frontend/src/hooks/__tests__/useRubberBandSelection.test.ts (5 unit tests)
    - frontend/src/components/canvas/SelectionFloatingToolbar.tsx (Fundir button, merge wiring, Toast)
    - frontend/src/components/canvas/VertexHandlesLayer.tsx (12 DP handles, drag-to-reshape, Konva Layer)
    - frontend/src/api/edit.ts (VertexHandle types + fetchVertexHandles — appended)
    - frontend/src/components/canvas/EditToolbar.tsx (Editar Vértices button added)
    - frontend/src/components/canvas/CanvasViewer.tsx (rubber-band Stage wiring, vertex-edit commit effect, activeTool gating)
  affects:
    - P07 (V keyboard shortcut, E shortcut, full keyboard map deferred here)
    - P08 (largest-area primary_id for merge deferred here)
    - P09 (TerritoryLayer live-deform wiring deferred — see Known Stubs)
tech_stack:
  added: []
  patterns:
    - rubber-band selection via transparent Konva Rect + centroid containment on mouseUp
    - Stage.draggable gated on activeTool !== 'select' (Pitfall 2 resolution)
    - vertex-edit as one undo step via beginTransaction on entry / endTransaction after reshapeGeometry on Esc-exit
    - fetchVertexHandles once-per-session with source_index anchors for full-detail ring writes (D-02)
    - SelectionFloatingToolbar positioned via stage.getAbsoluteTransform().point() + container().getBoundingClientRect()
key_files:
  created:
    - frontend/src/hooks/useRubberBandSelection.ts
    - frontend/src/hooks/__tests__/useRubberBandSelection.test.ts
    - frontend/src/components/canvas/SelectionFloatingToolbar.tsx
    - frontend/src/components/canvas/VertexHandlesLayer.tsx
  modified:
    - frontend/src/api/edit.ts
    - frontend/src/components/canvas/EditToolbar.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
decisions:
  - "Stage.draggable gated on activeTool !== 'select' — editMode ON defaults to activeTool='select' via useEffect; Pitfall 2 confirmed live"
  - "Handles fetched once per vertex-edit session using source_index anchors — subsequent drags update local handle state without re-fetching; full ring detail preserved between handles (D-02)"
  - "T-04-06-04 cleanup: useEffect returns endTransaction() if component unmounts mid-session to prevent orphaned transactions"
  - "Merge primary_id = selectionIds[0] — largest-area calculation deferred to P08; documented as TODO(P08)"
  - "Non-adjacent merge proceeds with amber Toast (D-03 honoured)"
  - "clearCache() not needed for TerritoryLayer re-draw — geometry reference change on setTerritory triggers React re-render of TerritoryPolygon new points prop (A2: ASSUMED, not empirically confirmed)"
metrics:
  duration_minutes: ~120
  completed_date: "2026-04-24"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 7
---

# Phase 04 Plan 06: Rubber-Band Select, Merge Toolbar, and Vertex Handles Summary

**One-liner:** Rubber-band multi-select with floating Fundir toolbar (EDIT-03) + vertex-edit handles with Douglas-Peucker decimation from /vertex-handles (EDIT-02); Pitfall 2 Stage draggable gated on activeTool; one undo step per operation via beginTransaction/endTransaction.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Rubber-band selection hook + Stage wiring | `138e622` |
| 2 | SelectionFloatingToolbar + merge wiring + fetchVertexHandles | `2b881b5` |
| 3 | VertexHandlesLayer + vertex-edit commit effect + Editar Vértices button | `d908879` |

## What Was Built

### Task 1 — Rubber-Band Selection Hook + Stage Wiring

`useRubberBandSelection` hook encapsulates all rubber-band logic:
- `isActive = editMode && activeTool === 'select'` — drives all gating
- `onMouseDown`: fires only when `e.target === e.target.getStage()` (empty canvas area), records start position
- `onMouseMove`: computes rect dimensions, updates `selectionRect` state
- `onMouseUp`: filters `condados` by centroid containment (canvas-space point-in-rect), calls `setRubberBandSelectionIds`

`CanvasViewer.tsx` wiring:
- `Stage` receives `draggable={activeTool !== 'select'}` — resolves Pitfall 2 (pan vs rubber-band conflict)
- `useEffect` on `editMode`: ON → `setActiveTool('select')`, OFF → `setActiveTool('none')`
- Rubber-band `Layer` with dashed `Rect` (`fill="rgba(110,86,207,0.1)"`, `stroke="rgba(110,86,207,0.7)"`, `dash={[4,2]}`)

5 unit tests pass: editMode-off no-op, mouseDown init, mouseMove update, mouseUp centroid selection (León+Castela in, Toledo out), isActive gate. Fixed mock identity bug during development (see Deviations).

### Task 2 — SelectionFloatingToolbar + Merge Wiring + fetchVertexHandles

`SelectionFloatingToolbar`:
- Renders when `rubberBandSelectionIds.length >= 2`
- Position computed via `stage.getAbsoluteTransform().point({x,y})` + `container().getBoundingClientRect()` — accounts for zoom/pan
- Fundir button: `beginTransaction` → `mergeTerritories` → `applyBatchUpdate` + `removeTerritories` → `endTransaction` → `pushUndoLabel` → `clearSelection`
- Non-adjacent warning: `response.warning === 'non_adjacent_multipolygon'` → amber Radix Toast
- `endTransaction` called on both success and failure paths (not `finally`) to avoid double-call

`api/edit.ts` additions: `VertexHandle` interface, `VertexHandlesResponse` interface, `fetchVertexHandles` function (GET `/vertex-handles?target=12`).

### Task 3 — VertexHandlesLayer + Vertex-Edit Commit + Editar Vértices Button

`VertexHandlesLayer`:
- Uses `useProjection()` (following DecorationsLayer precedent — safe inside Konva Stage)
- Fetches handles once per session (`handlesLoadedFor` guard prevents re-fetch on re-render)
- `handleDragEnd(sourceIndex)`: converts canvas position back to geo via `canvasToGeo`, writes to `exterior[source_index]` (preserving full ring detail between handles), keeps polygon closed (syncs first/last coord if boundary vertex), calls `setTerritory` + updates local handle state
- UI-SPEC colors: `fill="#ffffff"`, `stroke="#6E56CF"`, `strokeWidth=1.5`, `radius=6`

`CanvasViewer.tsx` vertex-edit commit effect:
- `prevVertexEditIdRef` tracks transition null→id (enter) and id→null (exit)
- Enter: `beginTransaction()`
- Exit: `reshapeGeometry(projectId, id, { geometry: poly })` → `endTransaction()` → `pushUndoLabel("Editar vértices — {name}")`
- Cleanup: `return () => { if (prevVertexEditIdRef.current) endTransaction() }` (T-04-06-04)
- Esc keydown handler: `setVertexEditCondadoId(null)` when vertex-edit active

`EditToolbar.tsx`: Editar Vértices button visible when `editMode`, active (solid) when `vertexEditId` set, disabled when no selection and not in vertex-edit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock stage identity check**
- **Found during:** Task 1 unit test writing
- **Issue:** `useRubberBandSelection.onMouseDown` guards with `e.target === e.target.getStage()` to detect empty-area clicks. Initial mock used `{ ...mockStage, getStage: () => mockStage }` as event target — the spread creates a new object, so `e.target !== e.target.getStage()` was always true, causing early return on every event.
- **Fix:** `makeMockStage` factory sets `getStage: () => stage` as a closure on the same object reference. Events pass `mockStage` directly as `e.target`. All 5 tests went from 3 failing → 5 passing.
- **Files modified:** `frontend/src/hooks/__tests__/useRubberBandSelection.test.ts`
- **Commit:** `138e622`

**2. [Rule 1 - Bug] Corrected store action name**
- **Found during:** Task 1 implementation
- **Issue:** Plan interfaces documented `setRubberBandSelection(ids)` but actual store action is `setRubberBandSelectionIds`.
- **Fix:** Used `setRubberBandSelectionIds` throughout hook and toolbar.
- **Files modified:** `frontend/src/hooks/useRubberBandSelection.ts`, `frontend/src/components/canvas/SelectionFloatingToolbar.tsx`
- **Commit:** `138e622`

**3. [Rule 1 - Bug] Corrected projection type name**
- **Found during:** Task 1 implementation
- **Issue:** Plan referenced `import type { Projection }` but actual export from projection context is `ProjectionConfig`.
- **Fix:** Used `ProjectionConfig` type throughout.
- **Files modified:** `frontend/src/hooks/useRubberBandSelection.ts`
- **Commit:** `138e622`

### Intentional Deferrals (not deviations)

- **Largest-area primary_id for merge:** `primary_id = selectionIds[0]` — true largest-area computation requires iterating polygon coordinate arrays; deferred to P08. Documented as `// TODO(P08)` in `SelectionFloatingToolbar.tsx`.
- **V keyboard shortcut:** Deferred to P07 alongside full keyboard map. Comment in `EditToolbar.tsx` and `CanvasViewer.tsx`.
- **Split/Undo/Redo toolbar buttons:** Deferred to P07. Placeholder comment in `EditToolbar.tsx`.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `setTerritory` writes to `useProjectStore.territories` but `TerritoryLayer` renders from TanStack Query snapshot (`territoriesQ.data`) — polygon does NOT deform live during vertex-edit drag | `frontend/src/components/canvas/TerritoryLayer.tsx` | ~1-50 (no `useProjectStore` import) | Pre-existing architectural gap (same limitation affects capital drag from P05). The plan's verification §4 ("polygon deforms live") cannot be confirmed visually. Future plan must subscribe `TerritoryLayer` to the store OR invalidate TanStack Query cache on `setTerritory`. |

## Assumptions

| ID | Assumption | Basis |
|----|-----------|-------|
| A1 | Backend GET `/vertex-handles?target=12` exists and returns `{ handles: [{lon, lat, source_index}] }` | Backend decimate_polygon implemented in P02; endpoint wired in P04 |
| A2 | `clearCache()` not needed — `setTerritory` replaces geometry reference, triggering React re-render of TerritoryPolygon via new `points` prop | DecorationsLayer Pitfall-8 precedent; not empirically confirmed in vertex-edit context |

## Open Items for P07

- V keyboard shortcut for Editar Vértices toggle
- E keyboard shortcut for Edit Mode toggle
- Full keyboard map (Escape handling is wired but not systematised)
- Undo/Redo toolbar buttons (Split button also deferred)
- Error toast when `reshapeGeometry` PATCH fails

## Self-Check: PASSED

All 7 implementation files exist on disk. All 3 task commits (138e622, 2b881b5, d908879) verified in git log.
