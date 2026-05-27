---
phase: 08
plan: "09"
subsystem: frontend-branching-ux
tags: [radix-dialog, branch-picker, undo-tooltip, snapshot-timeline, slider-conflict, pitfall-9, tanstack-query]
dependency_graph:
  requires: [08-03a, 08-03b, 08-04]
  provides: [BranchPicker, NewBranchDialog, RenameBranchDialog, DeleteBranchDialog, CopyBranchToMainDialog, SliderConflictDialog, SnapshotTimeline]
  affects: [WorkspaceToolbar, ParameterSidebar]
tech_stack:
  added: []
  patterns:
    - "Radix DropdownMenu for branch picker (not Select — action items need onSelect+preventDefault for dialog triggers)"
    - "Pitfall 9 gate: await useCreateSnapshot 201 BEFORE setConflictOpen(true) in ParameterSidebar"
    - "OP_LABEL_PT map in WorkspaceToolbar reads undoLabels.at(-1) for dynamic Undo/Redo tooltip"
    - "Mock BranchPicker + EditorSyncBridge in WorkspaceToolbar tests to avoid QueryClientProvider requirement"
key_files:
  created:
    - frontend/src/components/editor/BranchPicker.tsx
    - frontend/src/components/editor/NewBranchDialog.tsx
    - frontend/src/components/editor/RenameBranchDialog.tsx
    - frontend/src/components/editor/DeleteBranchDialog.tsx
    - frontend/src/components/editor/CopyBranchToMainDialog.tsx
    - frontend/src/components/editor/SliderConflictDialog.tsx
    - frontend/src/components/editor/SnapshotTimeline.tsx
  modified:
    - frontend/src/components/workspace/WorkspaceToolbar.tsx
    - frontend/src/components/canvas/ParameterSidebar.tsx
    - frontend/src/components/editor/__tests__/BranchPicker.test.tsx
    - frontend/src/components/editor/__tests__/SliderConflictDialog.test.tsx
    - frontend/src/components/workspace/__tests__/WorkspaceToolbar.test.tsx
    - frontend/src/components/workspace/__tests__/WorkspaceToolbar.cancel.test.tsx
    - frontend/src/components/canvas/__tests__/ParameterSidebar.test.tsx
decisions:
  - "Used Radix DropdownMenu instead of Select for BranchPicker: action items below Separator need onSelect+preventDefault to trigger dialogs — Radix Select resists this pattern for non-value items"
  - "CopyBranchToMainDialog uses client-side path (no backend endpoint in files_modified): restore latest source snapshot payload → createSnapshot on main → switchBranch"
  - "OP_LABEL_PT placed in WorkspaceToolbar.tsx (single-use, per plan default) — not extracted to editor/labels.ts"
  - "WorkspaceToolbar/ParameterSidebar pre-existing tests mock BranchPicker+EditorSyncBridge+snapshots to avoid QueryClientProvider requirement (Rule 1 fix)"
metrics:
  duration_minutes: 45
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 7
---

# Phase 08 Plan 09: Wave 7 Branching UX Summary

Wave 7 branching UX complete. 7 new components + WorkspaceToolbar extension + ParameterSidebar D-19 intercept. 14 new tests pass (7 BranchPicker + 7 SliderConflictDialog); 57 total affected tests pass; tsc clean.

## What Was Built

### Task 1 — BranchPicker + 4 branch dialogs + WorkspaceToolbar wiring

**`BranchPicker.tsx`** (311 lines) — Radix `DropdownMenu` (see Deviations) driven by `useBranches` + `useEditorStore.activeBranchId`. Trigger shows current branch name. Items: branches sorted by `updated_at` desc with `(N edits)` format per UI-SPEC Discretion. Below Separator: Nova ramificação..., Renomear..., Copiar para main (hidden on main), Excluir (disabled on main per D-15). Branch selection calls `switchBranch()` which rehydrates store + clears zundo history.

**`NewBranchDialog.tsx`** — Radix Dialog with TextField + Criar/Cancelar. Calls `useCreateBranch.mutateAsync`; on success closes and auto-switches to new branch.

**`RenameBranchDialog.tsx`** — Dialog + TextField defaulted to current name; PATCH via `useRenameBranch`.

**`DeleteBranchDialog.tsx`** — Red confirm copy per UI-SPEC. DELETE via `useDeleteBranch`; on success switches to main.

**`CopyBranchToMainDialog.tsx`** — Red confirm. Client-side flow: `useRestoreSnapshot` of latest source snapshot → `useCreateSnapshot` on main with `trigger='manual'` → `switchBranch('main', payload)`.

**`WorkspaceToolbar.tsx` extension:**
- `OP_LABEL_PT` map exported: 11 entries covering all `EditOp.op` types
- `undoLabels`/`redoLabels` from `useEditorStore` drive dynamic Undo/Redo button tooltips: `Desfazer Mover Vértice`, `Desfazer Dividir`, etc. Plain `Desfazer`/`Refazer` when stacks empty
- BranchPicker mounted left of "Gerar Mapa" per UI-SPEC §Toolbar Layout
- `<EditorSyncBridge />` mounted once for WARNING-6 chokepoint registration
- `grep -c "undoLabels"` → 6; `grep -cE "OP_LABEL_PT|Mover Vértice"` → 5

### Task 2 — SliderConflictDialog + SnapshotTimeline + ParameterSidebar D-19

**`SliderConflictDialog.tsx`** — Radix Dialog. Props: `{open, branchName, snapshotSeq, onConfirm, onCancel}`. Green callout shows snapshot #N saved. Red "Confirmar e regenerar" + outline "Cancelar — manter edições". The Pitfall 9 ordering contract is documented: callers must `await useCreateSnapshot` (get 201) before setting `open=true`.

**`SnapshotTimeline.tsx`** — Card listing snapshots reverse-chronological from `useBranchSnapshots`. Each item shows `#seq`, trigger badge (auto/manual/pre_slider_change), date, size. Restore button calls `useRestoreSnapshot.mutateAsync(snapshotId)` → `switchBranch(branchId, payload)`. Renders in InspectorSidebar editor panel (caller mounts it).

**`ParameterSidebar.tsx` extension (D-19 + Pitfall 9):**
- `wrappedRender` intercepts every slider commit: if `editLog.length > 0`, POSTs `pre_slider_change` snapshot FIRST via `useCreateSnapshot.mutateAsync`
- Only on success (mutateAsync resolves → 201 equivalent): sets `conflictSnapshotSeq` + opens `SliderConflictDialog`
- On catch (5xx): reverts slider via `pendingRevertRef.current?.()` — no dialog
- Confirm handler: calls `pendingRenderRef.current()` (debouncedRender)
- Cancel handler: calls `pendingRevertRef.current()` (slider revert)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Radix Select replaced with DropdownMenu for BranchPicker**
- **Found during:** Task 1, BranchPicker implementation
- **Issue:** Plan specifies "Radix Select" but Select does not support mixing value-selection items with action items that trigger dialogs. `Select.Item.onSelect` fires a value change that also attempts to update the Select's controlled value — action items like "Nova ramificação..." have no valid value to return, causing the component to reset or error.
- **Fix:** Used `Radix DropdownMenu` which supports `onSelect={(e) => { e.preventDefault(); openDialog(); }}` pattern cleanly. Behavior is identical to user: dropdown shows branches + separator + action items.
- **Files modified:** `frontend/src/components/editor/BranchPicker.tsx`
- **Commit:** df3aaef

**2. [Rule 1 - Bug] Pre-existing WorkspaceToolbar + ParameterSidebar tests broke after adding TanStack Query hooks**
- **Found during:** Task 2, post-commit verification
- **Issue:** Adding `BranchPicker` (uses `useBranches`) to WorkspaceToolbar and `useCreateSnapshot` to ParameterSidebar caused pre-existing unit tests to fail with "No QueryClient set" because the test wrappers had no `QueryClientProvider`.
- **Fix:** Mocked `BranchPicker`, `EditorSyncBridge`, and snapshots API in the relevant test files. This is the minimal non-invasive fix — test scope stays on the original subjects (toolbar layout, parameter dispatch) without needing full TanStack context.
- **Files modified:** `WorkspaceToolbar.test.tsx`, `WorkspaceToolbar.cancel.test.tsx`, `ParameterSidebar.test.tsx`
- **Commit:** c2d0ca6

**3. [Rule 3 - Planner ambiguity] CopyBranchToMainDialog uses client-side path**
- **Found during:** Task 1 implementation
- **Issue:** Plan says "planner picks; recommend backend endpoint added inline" but no backend file is in `files_modified`. Backend endpoint would require a new plan task.
- **Fix:** Client-side path: `useRestoreSnapshot(latestSnap.id)` → `useCreateSnapshot(main, trigger='manual', payload)` → `switchBranch('main', payload)`. Semantically equivalent to a server-side replace. Documented in decisions.
- **Files modified:** `frontend/src/components/editor/CopyBranchToMainDialog.tsx`
- **Commit:** df3aaef

## Known Stubs

None. All components wire to real API hooks from 08-03a/b. Initial store state (`vertices: {}`, `editLog: []`) is correct empty state for new branches.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: client_xss | BranchPicker.tsx | Branch names rendered in DropdownMenu.Item — React auto-escapes text content; no dangerouslySetInnerHTML used (T-08-09-01 accepted disposition) |

T-08-09-02 (copy-to-main race): mitigated by snapshot create before switch — if snapshot fails, copy is aborted.
T-08-09-03 (Pitfall 9 modal order): mitigated by `await createSnapshot.mutateAsync` gate in ParameterSidebar.wrappedRender.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `frontend/src/components/editor/BranchPicker.tsx` (311 lines ≥ 60) | FOUND |
| `frontend/src/components/editor/NewBranchDialog.tsx` | FOUND |
| `frontend/src/components/editor/RenameBranchDialog.tsx` | FOUND |
| `frontend/src/components/editor/DeleteBranchDialog.tsx` | FOUND |
| `frontend/src/components/editor/CopyBranchToMainDialog.tsx` | FOUND |
| `frontend/src/components/editor/SliderConflictDialog.tsx` | FOUND |
| `frontend/src/components/editor/SnapshotTimeline.tsx` | FOUND |
| `WorkspaceToolbar.tsx` undoLabels references (≥1) | 6 found |
| `WorkspaceToolbar.tsx` OP_LABEL_PT / Mover Vértice (≥1) | 5 found |
| `SliderConflictDialog.tsx` snapshotSeq references (≥1) | 6 found |
| commit df3aaef (Task 1) | FOUND |
| commit c2d0ca6 (Task 2) | FOUND |
| vitest BranchPicker.test.tsx 7/7 | PASSED |
| vitest SliderConflictDialog.test.tsx 7/7 | PASSED |
| vitest 57/57 total (editor + stores) | PASSED |
| tsc --noEmit clean | PASSED |
