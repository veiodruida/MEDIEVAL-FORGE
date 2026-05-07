---
phase: 04-canvas-editing-basic
plan: 07
subsystem: frontend-canvas-editing
tags: [split-tool, undo-redo, keyboard-map, konva, tdd, wave-5, EDIT-04, EDIT-07]
dependency_graph:
  requires:
    - frontend/src/stores/useEditorStore.ts (setActiveTool, setSplitSubMode, pushUndoLabel, popUndoLabel, popRedoLabel, clearRubberBandSelection)
    - frontend/src/stores/useProjectStore.ts (beginTransaction/endTransaction, applyBatchUpdate, removeTerritories, temporal.undo/redo)
    - frontend/src/api/edit.ts (splitTerritory, EditApiError)
    - frontend/src/components/canvas/EditToolbar.tsx (from P05+P06 — extended here)
    - frontend/src/components/canvas/CanvasViewer.tsx (Stage wiring, hook composition)
    - frontend/src/hooks/useRubberBandSelection.ts (P06 — handler composition pattern)
    - frontend/src/hooks/useKeyboardShortcuts.ts (P02 — preserved/extended, not replaced)
  provides:
    - frontend/src/components/canvas/SplitTool.tsx (useSplitTool hook: 3 sub-modes + API + toast)
    - frontend/src/hooks/useUndoShortcut.ts (Ctrl+Z/Y + Cmd+Z/Y + label-stack sync)
    - frontend/src/hooks/useEditKeyboardMap.ts (full Phase-4 keyboard map: E/V/S/Esc)
    - frontend/src/components/canvas/EditToolbar.tsx (updated: Dividir + SegmentedControl + UndoRedoButtons)
    - frontend/src/components/canvas/CanvasViewer.tsx (updated: useSplitTool wiring, useUndoShortcut, useEditKeyboardMap)
  affects:
    - P08 (validation + persistence + settings — all 6 EDIT requirements now have functional wiring)
tech_stack:
  added: []
  patterns:
    - "useSplitTool hook-style (matches useRubberBandSelection pattern): projection passed as param, no useProjection() call inside hook body — avoids ProjectionProvider boundary error when called in CanvasViewer body before JSX return"
    - "dual-return: previewLayer (Konva Layer, inside Stage) + toastEl (Toast.Root, outside Stage DOM) — required because Toast.Root cannot live inside Konva canvas tree"
    - "useSyncExternalStore(useProjectStore.temporal.subscribe, ...) for reactive Undo/Redo button enable/disable — canonical zundo 2.3.0 pattern; useTemporalStore export does NOT exist"
    - "freehand decimation: every 4th point before POST (T-04-07-03 mitigation)"
    - "three parallel keydown hooks on window: useKeyboardShortcuts (Ctrl+0 + Phase-2 Esc), useUndoShortcut (Ctrl+Z/Y), useEditKeyboardMap (E/V/S/Esc); each has its own cleanup"
key_files:
  created:
    - frontend/src/components/canvas/SplitTool.tsx
    - frontend/src/components/canvas/__tests__/SplitTool.test.tsx
    - frontend/src/hooks/useUndoShortcut.ts
    - frontend/src/hooks/useEditKeyboardMap.ts
  modified:
    - frontend/src/components/canvas/EditToolbar.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/hooks/__tests__/useUndoShortcut.test.ts
decisions:
  - "projection passed as parameter to useSplitTool (not useProjection() inside hook) — useProjection() throws outside ProjectionProvider; hook is called in CanvasViewer body before JSX return wraps children in ProjectionProvider"
  - "redo icon: ReloadIcon confirmed present in installed @radix-ui/react-icons; ClockwiseIcon does not exist in the package — try-list resolves to ReloadIcon (not fallback arrow)"
  - "useSyncExternalStore for temporal button reactivity — simpler and leak-free vs polling; useTemporalStore export absent in zundo 2.3.0 as noted in plan output spec"
  - "inline Esc/vertex-edit handler in CanvasViewer (P06) removed as dead code — useEditKeyboardMap handles the same Esc case; removal prevents double-firing"
metrics:
  duration: "~60 minutes"
  completed: "2026-04-24"
  tasks: 3
  files: 7
---

# Phase 04 Plan 07: Split Tool, Undo/Redo, and Keyboard Map Summary

**One-liner:** Split tool hook (snap/polyline/freehand) with Portuguese 422 toast, Undo/Redo toolbar buttons (CounterClockwiseClockIcon/ReloadIcon) reactive via useSyncExternalStore, and full Phase-4 keyboard map (E/V/S/Esc) — closing EDIT-04 and EDIT-07.

## What Was Done

### Task 1 — Split Tool (EDIT-04)

**`frontend/src/components/canvas/SplitTool.tsx`** — hook-style split tool:
- `useSplitTool({ condados, stageRef, projection })` — projection passed as parameter (not via `useProjection()`) to avoid ProjectionProvider boundary errors when called in CanvasViewer body
- **3 sub-modes** from `useEditorStore.splitSubMode`:
  - `snap` — 2 clicks, fires on 2nd click
  - `polyline` — N clicks, dblClick finishes
  - `freehand` — mousedown-drag-mouseup, every 4th point decimated (T-04-07-03)
- **Dual return**: `previewLayer` (Konva Layer for Stage) + `toastEl` (Toast.Root for DOM) — required because Toast.Root is a DOM element, not a canvas element
- **422 error handling** (T-04-07-01, Pitfall 4): catch block parses EditApiError message JSON for `detail` field → shows Portuguese "Linha de corte deve cruzar o território em dois pontos." toast
- **Success path**: `removeTerritories` + `applyBatchUpdate` (2 new polygons) + `pushUndoLabel("Dividir {name}")` + `setActiveTool('select')`
- **Transaction wrapping**: `beginTransaction()/endTransaction()` in try/finally

**`frontend/src/components/canvas/EditToolbar.tsx`** — extended with:
- "Dividir" button (visible in editMode), solid when split active, disabled when no selection
- `SegmentedControl.Root` sub-mode selector (Snap / Polilinha / Livre) — `SegmentedControl` confirmed available in installed `@radix-ui/themes`

**`frontend/src/components/canvas/CanvasViewer.tsx`** — wired:
- `useSplitTool({ condados, stageRef, projection })` called unconditionally
- Stage `draggable` extended: `activeTool !== 'select' && activeTool !== 'split'`
- Composed `onMouseDown/onMouseMove/onMouseUp` handlers: rubber-band deferred when split active
- `onDblClick` → `splitTool.onStageDblClick()` (polyline finish)
- `{splitTool.previewLayer}` inside `<Stage>`, `{splitTool.toastEl}` outside

**Tests**: 4 SplitTool unit tests GREEN (hook export, interface shape, snap 2nd-click, polyline dblClick).

### Task 2 — Undo/Redo (EDIT-07)

**`frontend/src/hooks/useUndoShortcut.ts`**:
- `useEffect` registers `keydown` handler on `window`
- `Ctrl+Z` / `Cmd+Z` → `temporal.undo()` + `popUndoLabel()`
- `Ctrl+Y` / `Cmd+Y` → `temporal.redo()` + `popRedoLabel()`
- `Cmd+Shift+Z` (macOS alternate redo) → `temporal.redo()` + `popRedoLabel()`
- Input guard prevents capture during form input

**`frontend/src/components/canvas/EditToolbar.tsx`** — `UndoRedoButtons` component:
- `CounterClockwiseClockIcon` for Undo (confirmed available)
- `ReloadIcon` for Redo (confirmed available; fallback to `↪` text never reached)
- `useSyncExternalStore(useProjectStore.temporal.subscribe, ...)` for reactive `pastStates.length` and `futureStates.length` — re-renders on every temporal action
- Portuguese tooltips: `"Desfazer: {label}"` / `"Refazer: {label}"` or "Nada a desfazer/refazer" when empty
- Disabled when history exhausted

**Tests**: 5 tests GREEN (3 original RED + 2 new label-sync tests for `popUndoLabel` + `popRedoLabel`).

### Task 3 — Full Phase 4 Keyboard Map

**`frontend/src/hooks/useEditKeyboardMap.ts`**:
- `E` → `toggleEditMode()` + set tool to `select`/`none`
- `V` (editMode + selection) → toggle `vertexEditCondadoId`
- `S` (editMode + selection) → toggle split tool
- `Escape` priority chain: vertex-edit → split → rubber-band → fall through to Phase-2 deselect
- Input guard (INPUT/TEXTAREA/contentEditable) and modifier guard (Ctrl/Cmd/Alt)

**CanvasViewer cleanup**: removed the inline `useEffect` Esc/vertex-edit handler from P06 (dead code — `useEditKeyboardMap` handles the same case; removal prevents double-firing `setVertexEditCondadoId(null)`).

Three parallel `keydown` hooks coexist cleanly:
1. `useKeyboardShortcuts` — Ctrl+0 (fit-to-view) + Phase-2 Esc (deselect)
2. `useUndoShortcut` — Ctrl+Z/Y (undo/redo)
3. `useEditKeyboardMap` — E/V/S/Esc (Phase-4 edit map)

## Redo Icon Resolution

**Installed `@radix-ui/react-icons`**: `ClockwiseIcon` does NOT exist. `ReloadIcon` exists and is used as the redo icon. The try-list resolves to `ReloadIcon` — the text arrow fallback (`↪`) is never reached.

## useSyncExternalStore Pattern Confirmed

`useSyncExternalStore(useProjectStore.temporal.subscribe, () => useProjectStore.temporal.getState().pastStates.length, () => 0)` correctly re-renders the Undo/Redo buttons on every temporal action. `useTemporalStore` is NOT exported by zundo 2.3.0 — this is the canonical reactive-read pattern.

## Phase 4 Status After P07

All 6 EDIT requirements now have end-to-end wiring:
- EDIT-01: Capital drag → Voronoi recalc (P05)
- EDIT-02: Vertex-edit handles (P06)
- EDIT-03: Rubber-band multi-select + merge (P06)
- EDIT-04: Split tool 3 sub-modes (P07) ← NEW
- EDIT-07: Named undo/redo keyboard + toolbar buttons (P07) ← NEW
- EDIT-08: Compound-op batching via beginTransaction/endTransaction (P05, applied throughout)

Remaining for P08: validation badges + export gate + persistence strategy + SettingsPanel (D-06, D-07).

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 0acaf89 | feat | Split tool hook + EditToolbar + CanvasViewer wiring |
| eb19a23 | feat | Undo/Redo keyboard + toolbar buttons |
| aaf5c33 | feat | Full Phase 4 keyboard map (E/V/S/Esc) |
| 0d8b78d | fix | Clear stale cut-line points when split tool deactivated |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] projection passed as parameter instead of useProjection() inside hook**
- **Found during:** Task 1 integration test run
- **Issue:** `useSplitTool` called `useProjection()` which throws `"useProjection must be used inside <ProjectionProvider>"`. The hook is called in `CanvasViewer` component body before the JSX `return` wraps children in `<ProjectionProvider>`. Other hooks like `VertexHandlesLayer` call `useProjection()` safely because they are rendered as children inside `<ProjectionProvider>`.
- **Fix:** Changed `Args` interface to accept `projection: ProjectionConfig | null`; all handlers guard with `if (!projection) return`. Matches the `useRubberBandSelection` precedent.
- **Files modified:** `frontend/src/components/canvas/SplitTool.tsx`, `frontend/src/components/canvas/__tests__/SplitTool.test.tsx`
- **Commit:** 0acaf89

**2. [Rule 1 - Bug] Removed redundant inline Esc/vertex-edit handler from CanvasViewer**
- **Found during:** Task 3 implementation
- **Issue:** `CanvasViewer` had an inline `useEffect` (P06) that called `setVertexEditCondadoId(null)` on Escape. With `useEditKeyboardMap` handling the same case, this would double-fire.
- **Fix:** Removed the inline handler; `useEditKeyboardMap` owns all Phase-4 Esc handling.
- **Files modified:** `frontend/src/components/canvas/CanvasViewer.tsx`
- **Commit:** aaf5c33

**3. [Rule 1 - Bug] Stale cut-line points not cleared on deactivation**
- **Found during:** Post-task review (identified before final commit)
- **Issue:** If a user begins drawing a polyline cut and then presses Esc (or switches tools), the `points` state was never reset. Re-entering split mode would show a ghost line from the previous session.
- **Fix:** Added `useEffect(() => { if (!active) { setPoints([]); isDrawing.current = false } }, [active])` in `useSplitTool`.
- **Files modified:** `frontend/src/components/canvas/SplitTool.tsx`
- **Commit:** 0d8b78d

## Known Stubs

### Rendering gap: split results are not visible until P09

Split tool writes new territory polygons to `useProjectStore` via `applyBatchUpdate` and `removeTerritories`. However, `TerritoryLayer` currently reads from TanStack Query cache (populated from the API response at load time), not directly from the store. Split results will not appear visually on the canvas until P09 wires `TerritoryLayer` to consume the store state as the source of truth. This is the same rendering gap identified for vertex edits in P06.

The split operation itself (API call, undo label push, store update) is fully wired. Only the visual feedback after a successful split is deferred.

Other features in this plan are fully wired:
- `useUndoShortcut` calls real `temporal.undo/redo` + real label-stack operations
- `useEditKeyboardMap` calls real store actions
- `UndoRedoButtons` subscribes to real temporal store state

## Threat Flags

No new trust boundaries beyond the plan's STRIDE register. All 5 mitigations verified:

| Threat | Status |
|--------|--------|
| T-04-07-01 (422 not surfaced) | Mitigated: catch block parses EditApiError → Portuguese toast |
| T-04-07-02 (label stack desync) | Mitigated: every temporal.undo() paired with popUndoLabel(); Tests 4/5 verify |
| T-04-07-03 (runaway freehand cut_line) | Mitigated: every 4th point decimation before POST |
| T-04-07-04 (keyboard swallows app shortcuts) | Mitigated: input/modifier guards in all 3 hooks |
| T-04-07-05 (missing redo icon) | Mitigated: ReloadIcon present; fallback code path exists |

## Self-Check: PASSED
