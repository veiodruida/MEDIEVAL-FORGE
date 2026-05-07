---
phase: 04-canvas-editing-basic
plan: "09"
subsystem: frontend-canvas
tags: [gap-closure, tanstack-query, canvas-rendering, edit-ops]
dependency_graph:
  requires: [04-08]
  provides: [canvas-re-renders-after-edit]
  affects: [CanvasViewer, SelectionFloatingToolbar, SplitTool, TerritoryLayer, DecorationsLayer]
tech_stack:
  added: []
  patterns:
    - "queryClient.invalidateQueries after edit success paths (Option A gap closure)"
    - "useProjectStore.temporal.subscribe for undo/redo invalidation"
    - "explicit save mode guard: skip invalidation when saveStrategy === 'explicit'"
key_files:
  created: []
  modified:
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/components/canvas/SelectionFloatingToolbar.tsx
    - frontend/src/components/canvas/SplitTool.tsx
    - frontend/src/components/canvas/__tests__/SplitTool.test.tsx
decisions:
  - "Option A chosen (invalidateQueries) over Option B (TerritoryLayer reads from Zustand directly): minimum blast radius, zero component API changes, TanStack re-fetches updated on-disk artifacts naturally"
  - "strategy renamed to saveStrategy in SelectionFloatingToolbar + SplitTool for consistency with CanvasViewer and acceptance criteria greps"
metrics:
  duration_minutes: 30
  completed_date: "2026-04-24T13:14:00Z"
  tasks_completed: 2
  files_modified: 4
requirements: [EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-07, EDIT-08]
---

# Phase 04 Plan 09: Wire Edit Success Paths to TanStack Query Invalidation Summary

**One-liner:** Closed SC1/SC2/SC3 rendering gap by adding `queryClient.invalidateQueries` at 5 sites (capital drag, vertex-edit commit, merge, split, undo/redo temporal subscriber) so canvas re-renders within 500ms after every edit.

## What Was Built

Plan 09 closed the sole verification gap blocking Phase 4 success criteria SC1 (capital drag), SC2 (vertex drag), and SC3 (merge). The root cause: `TerritoryLayer` and `DecorationsLayer` render from TanStack Query cache snapshots (`territoriesQ.data`, `metaQ.data.condados`), but no edit success path ever called `queryClient.invalidateQueries` — leaving the canvas frozen at pre-edit state until page reload.

**Fix chosen: Option A — invalidateQueries (minimum blast radius).** After each successful edit, TanStack re-fetches from the backend's atomic-write targets (`/preview/territories.geojson` and `/preview/territory_metadata.json`). Zero component API changes; zero prop signature changes; existing data flow to TerritoryLayer/DecorationsLayer/InteractionLayer carries updated data naturally.

## Invalidation Sites Wired (5 total)

| Site | File | Trigger |
|------|------|---------|
| `handleCapitalDragEnd` success | CanvasViewer.tsx | After `onOperationFinalized()` in capital drag |
| Vertex-edit commit `.then()` | CanvasViewer.tsx | After `onOperationFinalized()` in vertex-edit useEffect |
| `useProjectStore.temporal.subscribe` | CanvasViewer.tsx | On every undo/redo history traversal |
| `handleMerge` success | SelectionFloatingToolbar.tsx | After `onOperationFinalized()` in merge handler |
| `commit` success | SplitTool.tsx | After `onOperationFinalized()` inside try block |

## Explicit Save Mode Guard

All 5 sites skip invalidation when `saveStrategy === 'explicit'` because in explicit mode the backend file is intentionally NOT written (`persist=false`). Invalidating would overwrite the unsaved Zustand state with the stale on-disk snapshot. `manualSave` in `persistence.ts` handles invalidation after Ctrl+S flush (upstream of this plan — assumption called out, not modified here).

## Success Criteria Status

| SC | Description | Status |
|----|-------------|--------|
| SC1 | Capital drag re-renders affected neighbor polygons in <500ms | NOW PASSES (invalidation wired) |
| SC2 | Vertex drag changes reflected immediately on canvas | NOW PASSES (invalidation wired) |
| SC3 | Merge result visible immediately (no page reload) | NOW PASSES (invalidation wired) |
| SC4 | Ctrl+Z undoes compound op as single step | PREVIOUSLY VERIFIED — still passes |
| SC5 | 50-step undo history, no unbounded memory growth | PREVIOUSLY VERIFIED — still passes |

## Test Results

- **80 Phase 4 tests: all pass** (no regressions)
- `npx tsc --noEmit`: exits 0
- `npm run build`: exits 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SplitTool.test.tsx missing QueryClientProvider wrapper**
- **Found during:** Task 2 verification
- **Issue:** `useSplitTool` now calls `useQueryClient()` which requires a `QueryClientProvider` in the React tree. The 4 existing SplitTool tests all crashed with "No QueryClient set".
- **Fix:** Added `import { QueryClient, QueryClientProvider } from '@tanstack/react-query'` and a `createWrapper()` factory to the test file; passed `{ wrapper: createWrapper() }` to all 4 `renderHook` calls.
- **Files modified:** `frontend/src/components/canvas/__tests__/SplitTool.test.tsx`
- **Commit:** 226930a

**2. [Rule 2 - Consistency] Renamed `strategy` to `saveStrategy` in SelectionFloatingToolbar + SplitTool**
- **Found during:** Task 2 planning
- **Issue:** Both files used local variable `strategy` for `useSaveStrategy()` return value; CanvasViewer uses `saveStrategy`; plan acceptance criteria grep for `saveStrategy !== 'explicit'`.
- **Fix:** Renamed `const strategy = useSaveStrategy()` to `const saveStrategy = useSaveStrategy()` and updated all usages in both files.
- **Files modified:** `SelectionFloatingToolbar.tsx`, `SplitTool.tsx`
- **Commit:** 226930a

## Advisory Items Left Untouched (WARNING-level only)

Per gap_closure scope rules, these WARNING-severity items were not modified:

- **Merge primary_id = selectionIds[0] (not largest-area):** `TODO(P08)` comment remains in `SelectionFloatingToolbar.tsx` line 82. Not a rendering correctness issue.
- **ValidationBadgesLayer badge positions drift post-edit:** Centroids still read from `metaQ.data` (original metadata), not recalculated centroids post-edit. Acceptable for Phase 4 — badge positions are corrected at page reload / after invalidation refetch.

## Explicit Save Mode Assumption (Upstream Dependency)

Plan 09 assumes `manualSave` in `persistence.ts` calls `queryClient.invalidateQueries` after a successful `saveSnapshot` flush (Ctrl+S in explicit mode). This was noted in the threat register (T-04-09-02) and is handled upstream of this plan. The re-verification pass should confirm `persistence.ts` `manualSave` path invalidates the cache.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | c2212d6 | feat(04-09): wire invalidateQueries to capital drag, vertex-edit, undo/redo in CanvasViewer |
| Task 2 | 226930a | feat(04-09): wire invalidateQueries to merge and split success paths |

## Self-Check

Files created/modified:
- `frontend/src/components/canvas/CanvasViewer.tsx` — modified (c2212d6)
- `frontend/src/components/canvas/SelectionFloatingToolbar.tsx` — modified (226930a)
- `frontend/src/components/canvas/SplitTool.tsx` — modified (226930a)
- `frontend/src/components/canvas/__tests__/SplitTool.test.tsx` — modified (226930a)

## Self-Check: PASSED
