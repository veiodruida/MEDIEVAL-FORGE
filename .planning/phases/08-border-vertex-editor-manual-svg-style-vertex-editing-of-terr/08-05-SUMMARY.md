---
phase: 08
plan: "05"
subsystem: frontend-canvas
tags: [konva, vertex-editor, viewport-culling, raf-throttle, keyboard-shortcuts, ua-detection]
dependency_graph:
  requires: [08-04]
  provides: [VertexEditLayer, CoordTooltip, DesktopRequiredBanner, useKeyboardShortcuts-phase08]
  affects: [08-06a, 08-06b, 08-07, 08-08, 08-09]
tech_stack:
  added: []
  patterns:
    - "Konva 6th layer (z=5) mounts always; renders only when activeTerritoryId !== null"
    - "RAF throttle: cancelAnimationFrame + requestAnimationFrame on every dragmove tick (T-08-05-01)"
    - "Local preview ref (useRef<Record<string,{x,y}>>) for in-flight drag; single store commit on dragEnd"
    - "Viewport culling in world coords (lat/lon bbox + 10% margin) via useMemo"
    - "CoordTooltip: position:fixed DOM div, not Radix Tooltip (no DOM anchor on Konva canvas)"
    - "isDesktopRequired: navigator.maxTouchPoints > 0 && !matchMedia('(pointer: fine)').matches"
    - "useKeyboardShortcuts extended: V/A/D/S/M/Esc/Del + Ctrl+Z/Ctrl+Shift+Z gated on activeElement guard"
    - "clearCache per-layer on activeTerritoryId change via useEffect cleanup (Pitfall 10)"
key_files:
  created:
    - frontend/src/components/canvas/VertexEditLayer.tsx
    - frontend/src/components/canvas/CoordTooltip.tsx
    - frontend/src/components/DesktopRequiredBanner.tsx
  modified:
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/hooks/useKeyboardShortcuts.ts
    - frontend/src/components/canvas/__tests__/VertexEditLayer.test.tsx
    - frontend/src/components/__tests__/DesktopRequiredBanner.test.tsx
    - frontend/src/hooks/__tests__/useKeyboardShortcuts.phase08.test.ts
decisions:
  - "stageRef kept in VertexEditLayer Props for 08-06a snap/zoom integration — unused in 05 (prefixed _stageRef to satisfy TS6133)"
  - "vertexViewport computed in CanvasViewer from projection + stageRef.scaleX()/position(); passed as prop to VertexEditLayer so culling works correctly under zoom/pan"
  - "setCoordTooltip declared in CanvasViewer now; wired by 08-06a when dragmove emits lat/lon; void-suppressed to avoid TS6133"
  - "Esc shortcut: when activeTool !== null dismisses tool (selectTool(null)); when activeTool === null falls through to UIStore.select(null) — Phase 03 behavior preserved"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 5
---

# Phase 08 Plan 05: Canvas Scaffold — VertexEditLayer + CoordTooltip + Shortcuts Summary

Wave 4 canvas scaffold complete. Six-layer Konva stack is live; `VertexEditLayer` renders viewport-culled vertex handles with RAF-throttled drag preview; `CoordTooltip` provides the DOM-overlay coordinate display; `DesktopRequiredBanner` gates touch-primary UAs; `useKeyboardShortcuts` extended with all Phase 08 tool + undo/redo shortcuts.

## What Was Built

### Task 1 — VertexEditLayer + CoordTooltip + CanvasViewer wiring

**`frontend/src/components/canvas/VertexEditLayer.tsx`** — NEW 6th Konva layer.

Key design:
- `useMemo`-based viewport culling: filters `useEditorStore.vertices` to those inside viewport bbox + 10% margin (`expandBBox(viewport, 0.1)`) in world lat/lon coords. Culling avoids the `geoToCanvas` projection for off-screen vertices entirely.
- RAF throttle: `cancelAnimationFrame(rafRef.current)` + `requestAnimationFrame(...)` on every `onDragMove` guarantees exactly one pending frame (T-08-05-01 DoS guard). Writes to `previewRef` (local `useRef`) — NOT `useEditorStore.setState`.
- `onDragEnd`: `canvasToGeo(x, y, projection)` inverse-projects px → lat/lon → single `useEditorStore.getState().moveVertex(id, lat, lon)` call (enters zundo history once per drag).
- UI-SPEC color constants as hex literals: `VERTEX_FILL_UNSELECTED=#4a9eff`, `VERTEX_FILL_SELECTED=#f0c040`, `VERTEX_FILL_HOVER=#ffffff`, `SNAP_TARGET_STROKE=#eab308`, `INVALID_DRAG_STROKE=#ef4444`.
- Pitfall 10: `useEffect` cleanup clears layer cache via `layerRef.current.clearCache()` on `activeTerritoryId` change.
- `listening=false` when `activeTerritoryId === null` (skip hit-testing on read-only layers).

**`frontend/src/components/canvas/CoordTooltip.tsx`** — NEW DOM overlay.
- `position: 'fixed'`, `pointerEvents: 'none'`, `zIndex: 60` (above HoverTooltip at z=50).
- `ui-monospace, monospace` font, `lat.toFixed(6)` + `lon.toFixed(6)`.
- Returns `null` when `visible=false`.

**`frontend/src/components/canvas/CanvasViewer.tsx`** — extended:
- Imports and mounts `VertexEditLayer` as 6th layer (after `InteractionLayer`).
- Imports and renders `CoordTooltip` as DOM sibling (state owned in CanvasViewer; wired by 08-06a).
- `vertexViewport` useMemo: computes lat/lon bbox from `projection + stageRef.scaleX()/position() + viewportW/H` for culling.
- `useEditorStore(s => s.activeTerritoryId)` drives Pitfall 10 clearCache useEffect.

**9 vitest tests green** covering: null-activeTerritoryId (no handles), viewport culling (outside-far excluded), RAF throttle (moveVertex not called during render), onDragEnd wiring, #4a9eff unselected fill, #f0c040 selected fill, CoordTooltip position:fixed/zIndex:60/monospace/6-decimals, CoordTooltip hidden when visible=false, module export sanity.

### Task 2 — DesktopRequiredBanner + useKeyboardShortcuts extension

**`frontend/src/components/DesktopRequiredBanner.tsx`** — NEW UA-gated banner.
- `isDesktopRequired()`: `navigator.maxTouchPoints > 0 && !window.matchMedia('(pointer: fine)').matches` (UI-SPEC §Notes #8 verbatim).
- Renders `<Callout.Root color="amber" role="alert">` when touch-primary; `null` on desktop/hybrid.

**`frontend/src/hooks/useKeyboardShortcuts.ts`** — extended (Phase 03 behavior preserved):
- Added imports: `useEditorStore`, `EditTool`.
- Editable-element guard: `INPUT | TEXTAREA | SELECT | contentEditable` blocks all Phase 08 shortcuts (UX-01).
- `Ctrl+Z` → `useEditorStore.temporal.getState().undo()`.
- `Ctrl+Shift+Z` → `useEditorStore.temporal.getState().redo()`.
- `V/A/D/S/M` → `useEditorStore.getState().selectTool(TOOL)`.
- `Escape` with `activeTool !== null` → `selectTool(null)`; with `activeTool === null` → `UIStore.select(null)` (Phase 03 fallback).
- `Delete/Backspace` with `selectedVertexIds.length > 0` → `deleteVertices(selectedVertexIds)`.

**7 + 10 = 17 vitest tests green** across DesktopRequiredBanner + useKeyboardShortcuts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] stageRef unused in VertexEditLayer — TS6133**
- **Found during:** Task 1, tsc check
- **Issue:** `stageRef` prop declared for future 08-06a snap/zoom integration but unused in 08-05 → TS6133 error.
- **Fix:** Renamed destructured param to `_stageRef` (underscore prefix signals intentional non-use). Prop interface kept intact for 08-06a callers.
- **Files modified:** `frontend/src/components/canvas/VertexEditLayer.tsx`
- **Commit:** 41d085e

**2. [Rule 1 - Bug] setCoordTooltip unused in CanvasViewer — TS6133**
- **Found during:** Task 1, tsc check
- **Issue:** `setCoordTooltip` declared for 08-06a wiring but no caller in 08-05 → TS6133.
- **Fix:** Added `void setCoordTooltip` suppression with comment explaining 08-06a will wire the drag callback.
- **Files modified:** `frontend/src/components/canvas/CanvasViewer.tsx`
- **Commit:** 41d085e

**3. [Rule 1 - Bug] Wave-0 stubs had wrong ownership markers**
- **Found during:** Task 1/2 test authoring
- **Issue:** `VertexEditLayer.test.tsx` stub declared "implemented in plan 08-07"; `useKeyboardShortcuts.phase08.test.ts` declared "implemented in plan 08-09" — both owned by 08-05 per plan frontmatter.
- **Fix:** Replaced stubs entirely with plan-specified tests (9 + 10 tests). Future plans (08-07/09) will overwrite their respective sections.
- **Files modified:** both test files
- **Commit:** 41d085e, e39f987

**4. [Rule 1 - Bug] Esc test needed async activeTool override**
- **Found during:** Task 2, test RED→GREEN
- **Issue:** Mock `getState` returned `activeTool: null` → Esc hit UIStore branch, not `selectTool(null)`. Test expected `selectTool(null)`.
- **Fix:** Made the Esc test `async` and used dynamic import to override `useEditorStore.getState` with `activeTool: 'V'` for that test case.
- **Files modified:** `useKeyboardShortcuts.phase08.test.ts`
- **Commit:** e39f987

## Known Stubs

- `CoordTooltip` state (`coordTooltip` in CanvasViewer) is declared but always `visible: false` — wired by 08-06a when `onDragMove` emits cursor lat/lon. No visual content blocked by this: the tooltip simply doesn't appear until 08-06a.
- `_stageRef` prop in `VertexEditLayer` will be used by 08-06a for snap tolerance computation (`5 / stage.scaleX()`).

## Threat Flags

No new network surfaces. The only new input path is keyboard events (already gated by `activeElement` guard) and Konva drag events (RAF-throttled; no store mutation until `dragEnd`). T-08-05-01 (runaway RAF loop) is mitigated: `cancelAnimationFrame` called before each `requestAnimationFrame` in `handleDragMove`.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `frontend/src/components/canvas/VertexEditLayer.tsx` exists | FOUND |
| `frontend/src/components/canvas/CoordTooltip.tsx` exists | FOUND |
| `frontend/src/components/DesktopRequiredBanner.tsx` exists | FOUND |
| `frontend/src/components/canvas/CanvasViewer.tsx` contains VertexEditLayer | FOUND |
| `frontend/src/hooks/useKeyboardShortcuts.ts` contains V/A/D/S/M shortcuts | FOUND |
| commit 41d085e (VertexEditLayer + CoordTooltip + CanvasViewer) | FOUND |
| commit e39f987 (DesktopRequiredBanner + useKeyboardShortcuts) | FOUND |
| 26 vitest tests passing (9 + 7 + 10) | PASSED |
| tsc --noEmit clean | PASSED |
| grep requestAnimationFrame VertexEditLayer.tsx returns 2 | PASSED |
| grep "zIndex: 60" CoordTooltip.tsx returns 1 | PASSED |
| grep VertexEditLayer CanvasViewer.tsx returns 6 | PASSED |
| grep maxTouchPoints DesktopRequiredBanner.tsx returns 5 | PASSED |
| grep color="amber" DesktopRequiredBanner.tsx returns 1 | PASSED |
