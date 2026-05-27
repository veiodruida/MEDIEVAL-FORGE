---
phase: 08
plan: "04"
subsystem: frontend-state
tags: [zustand, zundo, tanstack-query, editor-store, undo-redo, branches, snapshots]
dependency_graph:
  requires: [08-03a, 08-03b]
  provides: [useEditorStore, branches-api-hooks, snapshots-api-hooks, EditorSyncBridge]
  affects: [08-05, 08-06a, 08-06b, 08-07, 08-08, 08-09]
tech_stack:
  added: []
  patterns:
    - "zundo temporal middleware with partialize + equality + limit=100"
    - "referential equality on partialize slice prevents non-undoable setState from polluting history"
    - "_suppressSubscribe guard prevents temporal.subscribe → setState → subscribe recursion"
    - "TanStack Query ['v3','branches',projectId] + ['v3','branches',pid,bid,'snapshots'] key shapes"
    - "null-render EditorSyncBridge wires EditEventSink to useAppendEditEvent"
key_files:
  created:
    - frontend/src/stores/useEditorStore.ts
    - frontend/src/stores/__tests__/useEditorStore.test.ts
    - frontend/src/api/branches.ts
    - frontend/src/api/snapshots.ts
    - frontend/src/components/editor/EditorSyncBridge.tsx
  modified: []
decisions:
  - "equality: (a,b) => a.vertices===b.vertices && a.editLog===b.editLog required to prevent non-undoable setStates from polluting pastStates — without equality, zundo's partialize produces new objects on every call, Object.is always false, everything goes into history"
  - "_suppressSubscribe flag in temporal.subscribe prevents setState → _handleSet → subscribe recursion; guard is set/cleared synchronously so no async race"
  - "EditorSyncBridge response adapter: maps auto_snapshot!=null && !error → snapshot_persisted:true for store editsSinceSnapshot reset"
metrics:
  duration_minutes: 35
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 0
---

# Phase 08 Plan 04: Frontend State Foundation Summary

Wave 3 frontend foundation complete. `useEditorStore` (Zustand + zundo temporal), TanStack Query branch/snapshot hooks, and `EditorSyncBridge` are live and tested.

## What Was Built

### Task 1 — useEditorStore with zundo temporal (TDD)

`frontend/src/stores/useEditorStore.ts` — NEW store (D-V3-04, built from scratch, not v1 restored).

Key design points:
- `temporal` middleware wraps the store with `partialize: (s) => ({vertices, editLog})` and `limit: 100`
- `equality: (a,b) => a.vertices===b.vertices && a.editLog===b.editLog` ensures only real vertex/log mutations enter history — non-undoable actions (`selectTool`, `setActiveBranchId`) produce referentially equal partialize slices and are skipped
- `setVerticesAndLog` is the WARNING-6 chokepoint: all 3 undoable ops (`moveVertex`, `addVertex`, `deleteVertices`) delegate here; the registered `EditEventSink` fires on every commit
- D-37 auto-snapshot: when `editsSinceSnapshot % 25 === 0`, the 25th POST includes `snapshot_payload_if_due`; `sink` returns `{snapshot_persisted: true}` → store resets counter to 0
- `switchBranch(branchId, payload)`: setState + temporal.clear() + localStorage write
- Gemini review UX: `undoLabels`/`redoLabels` stacks maintained in lockstep with zundo via `temporal.subscribe` + `_suppressSubscribe` guard (see Deviations)

11 vitest tests covering: initial state, moveVertex undoable, selectTool exclusion, 100-cap, switchBranch, undo/redo round-trip, marquee delete (1 op for N vertices), WARNING-6 sink call count, D-37 25th-call snapshot, editsSinceSnapshot reset, undoLabels/redoLabels UX lifecycle.

### Task 2 — TanStack Query hooks + EditorSyncBridge

`frontend/src/api/branches.ts`:
- `useBranches(projectId)` — GET; lazy-creates main branch (D-10)
- `useCreateBranch(projectId)` — POST 201; throws 400/409
- `useRenameBranch(projectId)` — PATCH; allows main rename (D-15)
- `useDeleteBranch(projectId)` — DELETE 204; throws 409 BRANCH_PROTECTED

`frontend/src/api/snapshots.ts`:
- `useBranchSnapshots(pid, bid)` — GET list reverse-chronological
- `useCreateSnapshot(pid, bid)` — POST 201; throws 413 on oversized blob
- `useRestoreSnapshot(pid, bid)` — POST restore; returns full payload for switchBranch
- `useAppendEditEvent(pid, bid)` — POST edit-events; accepts `snapshot_payload_if_due`; WARNING-6 chokepoint

`frontend/src/components/editor/EditorSyncBridge.tsx`:
- null-render component; registers `mutateAsync` adapter as `EditEventSink` on mount
- Adapter maps `{op_type, payload, snapshot_payload_if_due}` → backend shape
- Maps `{auto_snapshot: {snapshot_id, seq}}` → `{snapshot_persisted: true}` for store counter reset
- Deregisters on unmount; re-registers when `branchId` changes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] zundo equality option required to prevent non-undoable setState from polluting pastStates**
- **Found during:** Task 1, RED → GREEN phase
- **Issue:** Without `equality`, zundo's `partialize()` produces a new object on every `setState` call. `Object.is(newObj, oldObj)` always returns `false` → every `setState` (including `selectTool`, `setActiveBranchId`) pushed to pastStates. Test T3 (`selectTool does NOT push to pastStates`) failed with `expected 1 to be 2`.
- **Fix:** Added `equality: (a, b) => a.vertices === b.vertices && a.editLog === b.editLog` to the temporal options. Referential equality on the two partialized fields means only `setVerticesAndLog` (which creates new `vertices`/`editLog` arrays) produces a history entry.
- **Files modified:** `frontend/src/stores/useEditorStore.ts`
- **Commit:** 1acdd1f

**2. [Rule 1 - Bug] temporal.subscribe → setState recursion (stack overflow)**
- **Found during:** Task 1, first test run
- **Issue:** `useEditorStore.setState()` inside `temporal.subscribe` triggered zundo's wrapped `store.setState` which called `temporalHandleSet` → subscriber fired again → infinite recursion (Maximum call stack size exceeded).
- **Fix:** Added `_suppressSubscribe` boolean guard that is set `true` before calling `setState` inside the subscriber and reset `false` immediately after. Since the subscriber fires synchronously on temporal state change, the guard prevents re-entrant execution without any async complexity.
- **Files modified:** `frontend/src/stores/useEditorStore.ts`
- **Commit:** 1acdd1f

## Known Stubs

None. All hooks return real data from 08-03a/b endpoints. Initial store state (`vertices: {}`, `editLog: []`) is correct empty state, not a placeholder.

## Threat Flags

No new network surfaces beyond those documented in the plan's threat model. The hooks consume endpoints already secured in 08-03a/b (UUID guard, Pydantic validation). localStorage key `medieval-forge:active_branch_id` has accepted-risk disposition per T-08-04-01 (worst case: stale branch_id, backend recovers with 200 + main).

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `frontend/src/stores/useEditorStore.ts` exists | FOUND |
| `frontend/src/stores/__tests__/useEditorStore.test.ts` exists | FOUND |
| `frontend/src/api/branches.ts` exists | FOUND |
| `frontend/src/api/snapshots.ts` exists | FOUND |
| `frontend/src/components/editor/EditorSyncBridge.tsx` exists | FOUND |
| commit 1acdd1f (useEditorStore + tests) | FOUND |
| commit 76c0d9c (hooks + EditorSyncBridge) | FOUND |
| vitest 11/11 passing | PASSED |
| tsc --noEmit clean | PASSED |
