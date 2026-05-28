---
phase: 08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr
plan: 14
subsystem: frontend/editor-wiring
tags: [gap-closure, GAP-B, BranchInitializer, branch-init-defect, prop-wiring]
dependency-graph:
  requires: [08-12]
  provides:
    - BranchInitializer component (frontend/src/components/editor/BranchInitializer.tsx)
    - ProjectDetail mounts BranchInitializer
    - CanvasViewer wires projectId/branchId/tier to VertexEditLayer
    - CanvasViewer wires projectId/branchId to LayerTogglePanel
  affects:
    - useEditorStore.activeBranchId (now non-null on workspace load)
    - VertexEditLayer split/merge/translate (no longer early-return with null branchId)
    - LayerTogglePanel LandmaskEditorHeader (now reachable via projectId/branchId)
tech-stack:
  added: []
  patterns:
    - null-returning effect component (mirrors EditorSyncBridge.tsx pattern)
    - persisted-match-else-main branch selection strategy
    - TDD RED→GREEN for BranchInitializer
key-files:
  created:
    - frontend/src/components/editor/BranchInitializer.tsx
    - frontend/src/components/editor/__tests__/BranchInitializer.test.tsx
  modified:
    - frontend/src/pages/ProjectDetail.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
decisions:
  - "BranchInitializer is read-only against localStorage — it never writes; persistence on explicit switch remains in BranchPicker"
  - "onApplyLandmask intentionally NOT set in CanvasViewer — a no-op stub would falsely imply LANDMASK-02 delivery; Plan 08-16 supplies the real callback"
  - "editableLayer left at default 'baronies' in VertexEditLayer — no store state today flips baronies<->landmask; landmask edit surface is Plan 08-16"
metrics:
  duration: ~5min
  completed: "2026-05-28T12:02:44Z"
  tasks: 3
  files: 4
---

# Phase 08 Plan 14: BranchInitializer + Prop Wiring — GAP-B Closure Summary

**One-liner:** BranchInitializer auto-selects main/persisted branch on load (activeBranchId non-null), and CanvasViewer now passes projectId/branchId/tier='barony' to VertexEditLayer plus projectId/branchId to LayerTogglePanel so split/merge/translate no longer early-return.

## What Was Built

### Task 1: BranchInitializer component (TDD RED → GREEN)

New null-returning effect component at `frontend/src/components/editor/BranchInitializer.tsx`:

- Props: `{ projectId: string | undefined }`
- Reads `useBranches(projectId)` and `useEditorStore.activeBranchId`
- Effect with deps `[branches, activeBranchId]`:
  - Idempotent: `if (activeBranchId) return` first — never clobbers a user's explicit pick
  - Waits for branches data: `if (!branches || branches.length === 0) return`
  - Tries `loadPersistedActiveBranchId()` → matches against branches list
  - Falls back to `branches.find((b) => b.is_main) ?? branches[0]`
  - Calls `useEditorStore.getState().setActiveBranchId(chosen.id)`
- Read-only against localStorage — never calls `localStorage.setItem`
- Returns null. Mirrors EditorSyncBridge.tsx null-return pattern.

Test coverage: 7 tests covering all 5 behavior cases (default→main, persisted-match, persisted-stale→main, already-set→noop, empty-branches→noop + undefined branches + undefined projectId).

### Task 2: ProjectDetail mounts BranchInitializer

- Added `import { BranchInitializer } from '../components/editor/BranchInitializer'`
- Added `<BranchInitializer projectId={id} />` immediately after `<WorkspaceToolbar .../>` in the return tree
- Returns null — no DOM impact; active branch is set before user reaches any edit tool

### Task 3: CanvasViewer prop wiring

In `frontend/src/components/canvas/CanvasViewer.tsx`:

1. Added `const activeBranchId = useEditorStore((s) => s.activeBranchId)` near existing `activeTerritoryId` read (line 167)
2. VertexEditLayer mount (line ~700) upgraded with full props:
   ```tsx
   <VertexEditLayer
     stageRef={stageRef}
     viewport={vertexViewport}
     tier="barony"
     projectId={projectId}
     branchId={activeBranchId ?? undefined}
   />
   ```
3. LayerTogglePanel mount upgraded with projectId + branchId:
   ```tsx
   <LayerTogglePanel
     projectId={projectId}
     branchId={activeBranchId ?? undefined}
   />
   ```
   `onApplyLandmask` intentionally NOT set — Plan 08-16 supplies the real coord-carrying callback.

## Gap Closed

**GAP-B (from 08-VERIFICATION.md) — polygon-op path:**

- Before: `<VertexEditLayer stageRef viewport />` with NO projectId/branchId/tier → split (579), merge (614), translate (691) early-return silently.
- After: props wired + activeBranchId auto-set on load → early-return guard passes → ops reach the `/editor/apply` POST.

**GAP-B (branch-init defect) — latent defect also closed:**

- Before: `activeBranchId` started null and was only set when user opened BranchPicker. Wiring `branchId={activeBranchId}` alone would still pass null on first load.
- After: BranchInitializer auto-selects main/persisted branch on mount → activeBranchId non-null when branches exist.

**Scope note (LANDMASK-01/02 explicitly deferred):**

Passing projectId/branchId to LayerTogglePanel makes the landmask header *reachable*. It does NOT make landmask polygons *editable* — that requires a new `editableLayer` store toggle and coord plumbing, which is Plan 08-16.

## Deviations from Plan

None — plan executed exactly as written.

## Test Coverage

| Test file | Tests | Status |
|-----------|-------|--------|
| `BranchInitializer.test.tsx` | 7 | GREEN |
| `ProjectDetail.workspace.test.tsx` | 16 | GREEN |
| `ProjectDetail.errorBoundary.test.tsx` | 1 | GREEN |
| `CanvasViewer.test.tsx` | 7 | GREEN |
| `CanvasViewer.panOnSelect.test.tsx` | 9 | GREEN |
| `CanvasViewer.fitToView.test.tsx` | 3 | GREEN |
| `CanvasViewer.clearCache.test.tsx` | 3 | GREEN |

**Total: 58 tests passing; 0 failures; tsc --noEmit exits 0.**

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 6e9cc94 | test | TDD RED: failing tests for BranchInitializer |
| f56eed7 | feat | TDD GREEN: BranchInitializer — auto-select active branch on load |
| d662930 | feat | Mount BranchInitializer in ProjectDetail |
| a631633 | feat | Wire VertexEditLayer/LayerTogglePanel props in CanvasViewer |

## Known Stubs

None — all wired props flow to real store state (activeBranchId from useEditorStore) and real API data (projectId from CanvasViewer props).

## Threat Flags

None — this plan adds no network endpoints, no auth paths, no file access patterns, and no schema changes. All changes are frontend prop wiring and a null-returning effect component.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `BranchInitializer.tsx` | FOUND |
| `BranchInitializer.test.tsx` | FOUND |
| `ProjectDetail.tsx` contains `BranchInitializer` import + mount | VERIFIED |
| `CanvasViewer.tsx` contains `activeBranchId` (read + 2 usages) | VERIFIED |
| `CanvasViewer.tsx` VertexEditLayer has `tier="barony"` + `branchId` | VERIFIED |
| `CanvasViewer.tsx` LayerTogglePanel has `branchId` | VERIFIED |
| commit 6e9cc94 (TDD RED) | FOUND |
| commit f56eed7 (feat BranchInitializer) | FOUND |
| commit d662930 (feat ProjectDetail mount) | FOUND |
| commit a631633 (feat CanvasViewer wiring) | FOUND |
| `tsc --noEmit` exits 0 | PASSED |
| 58 tests passing | PASSED |
