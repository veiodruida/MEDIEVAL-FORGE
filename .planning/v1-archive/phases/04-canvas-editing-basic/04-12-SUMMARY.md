---
phase: 04-canvas-editing-basic
plan: 12
status: complete
completed: 2026-04-25
depends_on: 04-11
---

# 04-12 Summary — Shift-click multi-select (UAT T3 secondary gap)

## What was implemented

Added shift-click multi-select affordance to territory click handling in `TerritoryLayer.tsx` + `TerritoryPolygon.tsx`. Closes the secondary gap of UAT T3: rubber-band drag was the only multi-select path shipped before, but SC3 promised shift-click too.

## Changes

### TerritoryPolygon.tsx
- Widened `onClick` signature from `(id: string) => void` to `(id: string, shift: boolean) => void`
- Reads `e.evt.shiftKey === true` from the Konva click event and forwards it to the caller

### TerritoryLayer.tsx
- Imported `useEditorStore`
- Replaced the single-arg `handleClick` with a branching version:
  - `shift && editMode` → toggles condado id in `rubberBandSelectionIds` (adds if absent, removes if present)
  - plain click → clears any existing multi-select, then calls `ui.select(id)`
- `useCallback(..., [])` with empty dep array — all store reads via `getState()` inside the body keep the callback reference === across shift-click mutations

## Test approach used

**Hybrid**: rendered `TerritoryLayer` with a minimal `react-konva` mock that captures the `onClick` prop of each `Line` render into a `capturedHandlers` array (via `vi.hoisted`). Tests invoke handlers directly with `{ evt: { shiftKey: true/false } }`. No Konva canvas context required.

For Test 6 (reference stability): verified that after a shift-click (which mutates `rubberBandSelectionIds` → triggers TerritoryLayer re-render), `capturedHandlers.items.length` stays at the baseline count (3 territories) rather than doubling to 6. This confirms `React.memo` on `TerritoryPolygon` skips the re-render because `handleClick` reference is stable → `areEqual` returns true.

## Test results — 6/6 pass

| Test | Status |
|------|--------|
| T1: plain click sets single selection; rubberBandSelectionIds unchanged | ✓ |
| T2: shift-click in edit mode adds id to rubberBandSelectionIds | ✓ |
| T3: shift-click accumulates; toggle removes | ✓ |
| T4: shift-click outside edit mode falls through to plain select | ✓ |
| T5: plain click clears existing multi-select before single-select | ✓ |
| T6: handleClick reference stable across shift-click mutations | ✓ |

Full suite: 157/160 pass (3 pre-existing failures in research module, unrelated). `TerritoryLayer.test.tsx` (3 existing tests) still passes — no regression.

## UAT T3 status (combined with 04-11)

- `useProjectStore` is now hydrated on mount (04-11) → `projectId` non-null → `SelectionFloatingToolbar` guard passes
- Rubber-band drag still works unchanged
- Shift-click now toggles ids into `rubberBandSelectionIds` → `SelectionFloatingToolbar` shows Fundir when length ≥ 2
- T3 should now pass end-to-end pending manual UAT confirmation

## Known UX limitation

Shift-click selected territories do not receive a distinct visual highlight — only the Fundir button appearing signals an active multi-select. `isSelected` in `TerritoryPolygon` still reflects only `useUIStore.selectedTerritoryId` (single). If the user reports that the multi-selected polygons should be visually highlighted, handle in a future polish plan.

## Stage click / Escape behavior

Stage background click (`handleStageClick`) clears `selectedTerritoryId` but does NOT clear `rubberBandSelectionIds`. This is intentional and consistent with rubber-band behavior (rubber-band hook owns the lifecycle). Left as-is per plan scope.
