---
phase: 08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr
plan: 12
subsystem: frontend/canvas-editor-bridge
tags: [gap-closure, GAP-A, SelectionBridge, geoRing, editor-wiring]
dependency-graph:
  requires: []
  provides:
    - BaronyRender.geoRing field (useCanvasArtifacts.ts)
    - SelectionBridge component (frontend/src/components/editor/SelectionBridge.tsx)
    - CanvasViewer mounts SelectionBridge
  affects:
    - useEditorStore.activeTerritoryId (now populated on barony select)
    - useEditorStore.vertices (now populated from BaronyRender.geoRing)
    - VertexEditLayer (now has data to render handles when a barony is selected)
tech-stack:
  added: []
  patterns:
    - null-rendering effect component (mirrors EditorSyncBridge.tsx pattern)
    - zundo pause()/resume() wraps non-undoable setState
    - TDD RED→GREEN per task (test commit then implementation commit)
key-files:
  created:
    - frontend/src/hooks/__tests__/useCanvasArtifacts.geoRing.test.ts
    - frontend/src/components/editor/SelectionBridge.tsx
    - frontend/src/components/editor/__tests__/SelectionBridge.test.tsx
  modified:
    - frontend/src/hooks/useCanvasArtifacts.ts
    - frontend/src/components/canvas/CanvasViewer.tsx
decisions:
  - "Use zundo pause()/resume() around setState({ vertices }) to prevent undo history pollution from selection load"
  - "SelectionBridge placed after HoverTooltip inside canvasPane div (inside effectiveBaronies-in-scope branch)"
  - "RING_B13 open ring fixture corrected: last point must differ from first to be genuinely open"
metrics:
  duration: ~20min
  completed: "2026-05-28T11:49:40Z"
  tasks: 3
  files: 5
---

# Phase 08 Plan 12: SelectionBridge — GAP-A Closure Summary

**One-liner:** Null-rendering SelectionBridge component wires useUIStore.selectedBaronyId → useEditorStore.setActiveTerritoryId + vertices map via stable `${baronyId}#${index}` ids, with zundo pause/resume to prevent undo history pollution.

## What Was Built

### Task 1: BaronyRender.geoRing (useCanvasArtifacts.ts)

Added `geoRing?: [number, number][]` optional field to the `BaronyRender` interface. In the baronies `select()` function, the outer ring is captured once via `firstOuterRing(f.geometry)` and reused for both `geoRingToKonvaPoints(ring, projection)` and the new `geoRing: ring` assignment. No double-fetch, no extra compute. Field is optional — all existing consumers (InspectorSidebar, BaronyLayer, existing tests) typecheck unchanged.

### Task 2: SelectionBridge component

New null-rendering effect component at `frontend/src/components/editor/SelectionBridge.tsx`:

- Subscribes to `useUIStore.selectedBaronyId` and `useUIStore.selectedTerritoryId`
- **Barony selected:** calls `setActiveTerritoryId(baronyId)` + populates `useEditorStore.setState({ vertices })` from the `geoRing` array
- **Condado selected (D-03):** clears `activeTerritoryId(null)` + `vertices: {}`
- **Deselect:** clears both
- **Vertex id scheme:** `${baronyId}#${index}` — stable across re-renders for identical geometry (zundo diff-safe)
- **Closed ring handling:** duplicate last point dropped when `ring[0] === ring[last]`
- **Undo safety:** `temporal.pause()` / `temporal.resume()` wraps all `setState` calls so selection loads never create undo entries

### Task 3: CanvasViewer mounts SelectionBridge

Added `import { SelectionBridge } from '../editor/SelectionBridge'` and `<SelectionBridge baronies={effectiveBaronies} />` inside `canvasPane` div, after `<HoverTooltip>`. The mount is inside the branch where `effectiveBaronies` is in scope (after all early returns).

## Gap Closed

**GAP-A (from 08-VERIFICATION.md):** "Selection→Editor bridge missing. Territory/barony click sets useUIStore.selectedBaronyId but useEditorStore.setActiveTerritoryId is NEVER called."

After this plan:
- Clicking a barony → `setActiveTerritoryId` called + `vertices` populated
- `VertexEditLayer.visibleEntries` (gated on `activeTerritoryId !== null`) can now return non-empty entries
- Handles can render at runtime for the first time

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected open-ring test fixture**
- **Found during:** Task 2 GREEN (vitest run)
- **Issue:** `RING_B13` was defined as `[[-8.0,37.0], [-8.1,37.1], [-8.0,37.2], [-8.0,37.0]]` — last point equals first, making it a closed ring (3 unique vertices). The test comment said "open ring... 4 vertices" and expected length 4.
- **Fix:** Changed last point to `[-7.9, 37.1]` (genuinely different from first) so the ring is actually open and produces 4 vertices.
- **Files modified:** `frontend/src/components/editor/__tests__/SelectionBridge.test.tsx`

**2. [Rule 2 - Missing critical] Added zundo pause/resume for undo safety**
- **Found during:** Advisor review before coding (plan did not mention pause/resume)
- **Issue:** Plan said "use `useEditorStore.setState({ vertices })` directly" but the zundo `equality` function checks `a.vertices === b.vertices` — a new vertices object on selection load would register as a state change and push to `pastStates`, polluting the undo history.
- **Fix:** Added `temporal.pause()` before and `temporal.resume()` after all `setState` calls in SelectionBridge. Verified `pause`/`resume` exist in zundo 2.3 (`isTracking`, `pause`, `resume` present in temporal API).
- **Files modified:** `frontend/src/components/editor/SelectionBridge.tsx`

## Test Coverage

| Test file | Tests | Status |
|-----------|-------|--------|
| `useCanvasArtifacts.geoRing.test.ts` | 5 | GREEN |
| `SelectionBridge.test.tsx` | 16 | GREEN |
| `CanvasViewer.test.tsx` (regression) | 7 | GREEN |
| `InspectorSidebar.test.tsx` (regression) | 17 | GREEN |
| `BaronyLayer.test.tsx` (regression) | via CanvasViewer suite | GREEN |

**Total: 60 tests passing; 0 failures; tsc --noEmit exits 0.**

## Commits

| Hash | Type | Description |
|------|------|-------------|
| f650e90 | test | TDD RED: failing tests for BaronyRender.geoRing field |
| 0f8da0d | feat | TDD GREEN: add BaronyRender.geoRing field |
| 1161edd | test | TDD RED: failing tests for SelectionBridge component |
| 75ee7de | feat | TDD GREEN: implement SelectionBridge |
| 140d6c2 | feat | Mount SelectionBridge in CanvasViewer with effectiveBaronies |

## Known Stubs

None — all paths are wired to real store actions and real geometry data.

## Threat Flags

None — this plan adds no network endpoints, no auth paths, no file access patterns, and no schema changes.

## Self-Check: PASSED

All created files found on disk. All 5 commits verified in git log.

| Item | Status |
|------|--------|
| `useCanvasArtifacts.geoRing.test.ts` | FOUND |
| `SelectionBridge.tsx` | FOUND |
| `SelectionBridge.test.tsx` | FOUND |
| `08-12-SUMMARY.md` | FOUND |
| commit f650e90 (TDD RED geoRing) | FOUND |
| commit 0f8da0d (feat geoRing GREEN) | FOUND |
| commit 1161edd (TDD RED SelectionBridge) | FOUND |
| commit 75ee7de (feat SelectionBridge GREEN) | FOUND |
| commit 140d6c2 (feat CanvasViewer mount) | FOUND |
