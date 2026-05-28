---
phase: 08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr
plan: 13
subsystem: frontend/editor-ui
tags: [gap-closure, ux, tool-palette, radix, zustand]
dependency_graph:
  requires: [useEditorStore (activeTool/selectTool), useKeyboardShortcuts (shared state)]
  provides: [EditToolPalette component, visible edit-mode affordance in WorkspaceToolbar]
  affects: [WorkspaceToolbar layout, GAP-C closure, UX-01 requirement]
tech_stack:
  added: []
  patterns: [Radix IconButton + Tooltip, Zustand selector, TDD RED→GREEN]
key_files:
  created:
    - frontend/src/components/editor/EditToolPalette.tsx
    - frontend/src/components/editor/__tests__/EditToolPalette.test.tsx
  modified:
    - frontend/src/components/workspace/WorkspaceToolbar.tsx
decisions:
  - "ScissorsIcon used instead of Scissors1Icon (not exported in installed @radix-ui/react-icons version)"
  - "MixIcon used directly (available in installed version, no fallback needed)"
  - "EditToolPalette placed after BranchPicker and before Undo/Redo block in right-cluster Flex, per UI-SPEC action spec"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-28"
  tasks_completed: 2
  files_changed: 3
---

# Phase 08 Plan 13: EditToolPalette (GAP-C Closure) Summary

**One-liner:** Radix IconButton palette with V/A/D/S/M/Esc tools bound to useEditorStore.activeTool/selectTool, mounted in WorkspaceToolbar, making the edit mode discoverable with active-tool highlighting.

## What Was Built

### Task 1: EditToolPalette component (TDD)

Created `frontend/src/components/editor/EditToolPalette.tsx` (120 lines):

- Renders 6 `IconButton size="2"` buttons in `Flex gap="1"`: V (CursorArrowIcon), A (PlusIcon), D (TrashIcon), S (ScissorsIcon), M (MixIcon), Esc (Cross2Icon).
- Reads `activeTool` from `useEditorStore` — pure reflection, no local state.
- Active tool renders `variant="solid" color="blue"`; inactive renders `variant="soft" color="gray"`.
- `aria-pressed={isActive}` on each button for accessibility and test targeting.
- Each button wrapped in Radix `Tooltip` with PT-BR label and 300ms delay.
- `data-testid="edit-tool-{v|a|d|s|m|esc}"` on each button for UAT targeting.
- Container has `data-testid="edit-tool-palette"`.
- Esc button calls `selectTool(null)`; tool buttons call `selectTool(key)`.

TDD flow:
- RED commit `1c23442`: 8 tests targeting non-existent file → import error.
- GREEN commit `9835abe`: component created → 8/8 tests pass.

### Task 2: Mount in WorkspaceToolbar

Modified `frontend/src/components/workspace/WorkspaceToolbar.tsx`:
- Added `import { EditToolPalette } from '../editor/EditToolPalette'` (line 12).
- Mounted `<EditToolPalette />` after `<BranchPicker projectId={project?.id} />` and before the Undo/Redo Tooltip block (line 162), inside the right-cluster `<Flex align="center" gap="2">`.
- All 9 existing WorkspaceToolbar tests continue to pass.

## Verification

```
npx tsc --noEmit          → exit 0 (no TypeScript errors)
npx vitest run EditToolPalette   → 8/8 tests pass
npx vitest run WorkspaceToolbar  → 9/9 tests pass
grep -n "EditToolPalette" WorkspaceToolbar.tsx  → line 12 (import) + line 162 (JSX mount)
grep -n "BranchPicker\|EditToolPalette" WorkspaceToolbar.tsx → BranchPicker at 158, EditToolPalette at 162 (correct order)
```

## Key Design Properties

- **Single state source**: keyboard shortcuts (`useKeyboardShortcuts V/A/D/S/M`) and palette buttons both call `useEditorStore.selectTool`. No duplication, no sync needed.
- **Zero local state**: the palette is a pure read from `useEditorStore.activeTool`. Any external update (keyboard, store reset, branch switch) is reflected automatically.
- **Esc is never "active"**: `activeTool` type is `EditTool = 'V'|'A'|'D'|'S'|'M'|null` — `'ESC'` never matches, so `isActive` is structurally `false` for the cancel button.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Icon Substitution (noted, not a deviation)

**ScissorsIcon used instead of Scissors1Icon** — the plan explicitly states "use `ScissorsIcon`/`MixerHorizontalIcon` if exact icon unavailable and note the substitution in a comment". `Scissors1Icon` is not exported in the installed `@radix-ui/react-icons` version. `ScissorsIcon` is used with an inline comment. `MixIcon` IS available and used directly (no substitution needed for M tool).

## Known Stubs

None — the palette is fully functional: buttons render, onClick calls selectTool, activeTool drives visual state.

## Threat Flags

None — frontend-only UI component, no new network endpoints, no auth paths, no schema changes.

## Commits

| Hash | Message |
|------|---------|
| `1c23442` | test(08-13): add failing test for EditToolPalette |
| `9835abe` | feat(08-13): implement EditToolPalette bound to useEditorStore |
| `7658353` | feat(08-13): mount EditToolPalette in WorkspaceToolbar |

## Self-Check: PASSED

- `frontend/src/components/editor/EditToolPalette.tsx` — FOUND
- `frontend/src/components/editor/__tests__/EditToolPalette.test.tsx` — FOUND
- `frontend/src/components/workspace/WorkspaceToolbar.tsx` (modified) — FOUND
- Commit `1c23442` — FOUND
- Commit `9835abe` — FOUND
- Commit `7658353` — FOUND
