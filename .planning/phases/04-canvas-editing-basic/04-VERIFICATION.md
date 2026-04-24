---
phase: 04-canvas-editing-basic
verified: 2026-04-24T14:00:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/5
  gaps_closed:
    - "SC1 — capital drag re-renders polygons: queryClient.invalidateQueries wired at handleCapitalDragEnd success path (CanvasViewer.tsx line 173)"
    - "SC2 — vertex drag reflected on canvas: queryClient.invalidateQueries wired at vertex-edit commit success path (CanvasViewer.tsx line 173)"
    - "SC3 — merge result visible immediately: queryClient.invalidateQueries wired at handleMerge success path (SelectionFloatingToolbar.tsx line 127)"
    - "SC3 split result visible: queryClient.invalidateQueries wired at split commit success path (SplitTool.tsx line 112)"
    - "Undo/redo invalidation: temporal.subscribe wired in CanvasViewer.tsx (line 462) calls invalidateQueries on every history traversal"
  gaps_remaining:
    - "manualSave() in persistence.ts does not call queryClient.invalidateQueries after successful saveSnapshot flush — canvas stays frozen in explicit save mode after Ctrl+S"
  regressions: []
gaps:
  - truth: "Ctrl+S in explicit save mode flushes to disk AND updates the canvas immediately (no reload required)"
    status: failed
    reason: "manualSave() in frontend/src/services/persistence.ts (lines 91-106) calls saveSnapshot() and markSaved() but contains no queryClient.invalidateQueries call. After a successful Ctrl+S flush in explicit mode, the on-disk territories.geojson is updated and SaveStatusIndicator shows 'Salvo', but the TanStack Query cache is never invalidated. The canvas remains frozen at the pre-edit visual state until the user manually reloads the page."
    artifacts:
      - path: "frontend/src/services/persistence.ts"
        issue: "Lines 91-106: manualSave() calls saveSnapshot() + markSaved() with no queryClient.invalidateQueries call anywhere in the function or file"
    missing:
      - "After await saveSnapshot() succeeds (line 99), call queryClient.invalidateQueries({ queryKey: ['canvasArtifacts', projectId] }) before markSaved(). Requires obtaining queryClient via getQueryClient() or passing it as a parameter — persistence.ts currently has no React context access."
      - "One clean approach: export an invalidateCanvasCache callback from CanvasViewer and register it in manualSave, mirroring the pattern used for the 5 inline invalidation sites. Alternatively, wire invalidation inside the Ctrl+S handler in useUndoShortcut.ts which already imports manualSave."
human_verification:
  - test: "Capital drag re-renders in under 500ms (auto/per_op mode)"
    expected: "Dragging a capital marker causes the affected neighbor Voronoi polygons to visually update on the Konva canvas within 500ms — no page reload required"
    why_human: "Cannot measure render latency or confirm visual polygon update via grep. Requires running the app with a loaded project, dragging a capital in auto or per_op save mode, and observing whether polygons redrawn correctly and quickly."
  - test: "Vertex drag immediately reflected on canvas (auto/per_op mode)"
    expected: "Dragging a border vertex reshapes the polygon outline on canvas without reload"
    why_human: "Visual confirmation required; grep confirms the invalidation call exists but not that the re-fetched geometry matches the visual expectation."
  - test: "Merge result immediately visible (auto/per_op mode)"
    expected: "After clicking Fundir on 2+ selected territories, a single merged polygon replaces the selected set on canvas without reload"
    why_human: "Visual confirmation of correct polygon union display required."
  - test: "Ctrl+Z undoes capital drag as single compound step (visual)"
    expected: "Pressing Ctrl+Z after a capital drag restores both the capital marker position and all affected neighbor polygon shapes in one step — no partial revert"
    why_human: "Compound undo correctness is unit-tested, but the visual completeness of the canvas rollback (both DecorationsLayer capital marker and TerritoryLayer polygons) requires human observation."
---

# Phase 04: Canvas Editing — Basic Re-Verification Report

**Phase Goal:** User can drag a capital marker to reshape Voronoi territories in under 500ms, merge adjacent territories into one, and undo/redo all operations with a 50-step history that groups compound side effects as single steps.
**Verified:** 2026-04-24T14:00:00Z
**Status:** gaps_found
**Re-verification:** Yes — after Plan 09 gap closure

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can drag a capital marker and watch affected neighbor polygons recalculate and re-render in under 500ms, persisted | VERIFIED (auto/per_op) | queryClient.invalidateQueries wired at handleCapitalDragEnd success path — CanvasViewer.tsx invalidateCanvasArtifacts helper lines 171-175 called after onOperationFinalized(). Explicit-mode guard at line 172 (saveStrategy !== 'explicit'). Temporal subscriber at line 462 handles undo/redo invalidation. |
| 2 | User can drag individual border vertices; change reflected immediately on canvas and saved | VERIFIED (auto/per_op) | Same invalidateCanvasArtifacts helper called in vertex-edit commit .then() path (CanvasViewer.tsx). Store mutation + invalidation chain wired. |
| 3 | User can select 2+ adjacent territories and merge them; result is one polygon with preserved exterior topology | VERIFIED (auto/per_op) | SelectionFloatingToolbar.tsx lines 127-128: invalidateQueries after handleMerge success. SplitTool.tsx lines 112-113: invalidateQueries after split commit. All 4 operations (capital drag, vertex edit, merge, split) now invalidate cache on success. |
| 4 | User can press Ctrl+Z after capital drag and entire compound op undone as single step | VERIFIED | useUndoShortcut wires Ctrl+Z to temporal.undo(). beginTransaction/endTransaction with try/finally frames compound ops. Test 3 in CapitalDrag.test.tsx asserts pastStates.length===1. Temporal subscribe invalidation at CanvasViewer.tsx line 462 also refreshes canvas on undo/redo. |
| 5 | Undo/redo supports 50 steps; browser memory does not grow unboundedly with 800+ territories | VERIFIED | limit:50 confirmed in useProjectStore. diff function (not boolean) stores key-level deltas only. partialize excludes projectId+loading. Test enforces 51-entry cap. |

**Score:** 4/5 truths fully verified (SC1/SC2/SC3 verified in auto and per_op save modes; gap remains for explicit save mode only)

### Deferred Items

No items deferred to later phases. The explicit-mode manualSave gap is within Phase 4 scope — it affects the D-07 persistence strategy feature introduced in Plan 08.

### Required Artifacts — Regression Check

| Artifact | Status | Evidence |
|----------|--------|----------|
| `backend/medieval_forge/services/voronoi.py` | VERIFIED | No regressions — unchanged since initial verification |
| `backend/medieval_forge/api/edit.py` | VERIFIED | No regressions — unchanged since initial verification |
| `frontend/src/stores/useProjectStore.ts` | VERIFIED | No regressions — temporal/diff/limit/beginTransaction confirmed unchanged |
| `frontend/src/components/canvas/CanvasViewer.tsx` | VERIFIED (with gap) | invalidateCanvasArtifacts helper wired at 2 sites (capital drag, vertex-edit commit). temporal.subscribe at line 462. Explicit-mode guard present. |
| `frontend/src/components/canvas/SelectionFloatingToolbar.tsx` | VERIFIED | invalidateQueries at lines 127-128 after merge success. saveStrategy renamed from strategy for consistency. |
| `frontend/src/components/canvas/SplitTool.tsx` | VERIFIED | invalidateQueries at lines 112-113 after split commit. QueryClientProvider wrapper added to test file. |
| `frontend/src/services/persistence.ts` | GAP | manualSave() (lines 91-106) contains no invalidateQueries call after saveSnapshot() success |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| handleCapitalDragEnd success | queryClient.invalidateQueries | invalidateCanvasArtifacts helper | WIRED | CanvasViewer.tsx lines 171-175; guard: saveStrategy !== 'explicit' at line 172 |
| vertex-edit commit .then() | queryClient.invalidateQueries | invalidateCanvasArtifacts helper | WIRED | CanvasViewer.tsx same helper; confirmed by grep |
| useProjectStore.temporal.subscribe | queryClient.invalidateQueries | subscribe callback | WIRED | CanvasViewer.tsx lines 462-465; explicit guard at line 463 |
| handleMerge success | queryClient.invalidateQueries | inline call | WIRED | SelectionFloatingToolbar.tsx lines 127-128 |
| split commit success | queryClient.invalidateQueries | inline call | WIRED | SplitTool.tsx lines 112-113 |
| manualSave() saveSnapshot success | queryClient.invalidateQueries | — | MISSING | persistence.ts lines 91-106; no invalidation after successful Ctrl+S flush |
| useUndoShortcut Ctrl+S | manualSave() | import from services/persistence | WIRED | useUndoShortcut.ts line 4 import, lines 38-40 handler |
| TerritoryLayer render | TanStack Query refetch | invalidateQueries triggers staleTime bypass | WIRED (auto/per_op) | Only broken in explicit mode where manualSave does not invalidate |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Status |
|----------|---------------|--------|--------|
| TerritoryLayer | territories prop | territoriesQ.data — invalidated by Plan 09 on every successful edit (auto/per_op) | FLOWING (auto/per_op); HOLLOW after Ctrl+S in explicit mode |
| DecorationsLayer | condados.lon/lat | metaQ.data.condados — same invalidation path | FLOWING (auto/per_op); HOLLOW after Ctrl+S in explicit mode |
| useProjectStore.territories | territories Record | setTerritory / applyBatchUpdate — store updated, cache invalidated on success | FLOWING |
| manualSave explicit flush | — | saveSnapshot writes disk; TanStack cache NOT invalidated | DISCONNECTED |

### Behavioral Spot-Checks

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| invalidateQueries at capital drag | grep invalidateQueries CanvasViewer.tsx | Lines 173-174 confirmed | PASS |
| invalidateQueries at merge | grep invalidateQueries SelectionFloatingToolbar.tsx | Lines 127-128 confirmed | PASS |
| invalidateQueries at split | grep invalidateQueries SplitTool.tsx | Lines 112-113 confirmed | PASS |
| temporal.subscribe wired | grep temporal.subscribe CanvasViewer.tsx | Line 462 confirmed | PASS |
| explicit-mode guard present | grep "saveStrategy.*explicit" CanvasViewer.tsx | Lines 172 and 463 confirmed | PASS |
| manualSave invalidates cache | grep invalidateQueries persistence.ts | No match | FAIL |
| SplitTool tests pass with QueryClientProvider wrapper | SplitTool.test.tsx createWrapper() | Added in commit 226930a | PASS |
| saveStrategy rename consistent | grep "const saveStrategy" SelectionFloatingToolbar.tsx SplitTool.tsx | Confirmed | PASS |

### Requirements Coverage

| Requirement | Plans | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| EDIT-01 | P05, P09 | Capital drag + Voronoi recalc <500ms | VERIFIED (auto/per_op) | Backend at 2.7ms. Canvas re-renders via invalidateQueries in auto/per_op. Explicit mode gap. |
| EDIT-02 | P06, P09 | Border vertex drag to reshape polygon | VERIFIED (auto/per_op) | vertex-edit commit path wired to invalidateQueries |
| EDIT-03 | P06, P09 | Territory merge | VERIFIED (auto/per_op) | handleMerge wired to invalidateQueries |
| EDIT-04 | P07, P09 | Territory split by cut line | VERIFIED (auto/per_op) | split commit wired to invalidateQueries |
| EDIT-07 | P07 | Ctrl+Z/Y undo/redo 50-step | VERIFIED | useUndoShortcut, limit:50, temporal subscriber invalidation |
| EDIT-08 | P05+ | Compound ops as single undo step | VERIFIED | beginTransaction/endTransaction, pastStates.length===1 test |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/services/persistence.ts` | 91-106 | manualSave() calls saveSnapshot() + markSaved() but no invalidateQueries | BLOCKER | In explicit save mode, Ctrl+S saves to disk and shows 'Salvo' but canvas stays frozen at pre-edit state |
| `frontend/src/components/canvas/SelectionFloatingToolbar.tsx` | 82 | `// TODO(P08)` — largest-area primary_id | WARNING | Merge uses selectionIds[0] as primary, not largest polygon (cosmetic, not a correctness blocker) |
| `frontend/src/components/canvas/ValidationBadgesLayer.tsx` | (centroid source) | Badge centroids from metaQ metadata, not recalculated post-edit | WARNING | Badge positions drift after vertex edits; corrected at next invalidation refetch |

### Human Verification Required

#### 1. Capital drag re-renders in under 500ms (auto/per_op mode)

**Test:** Load a project. Ensure save mode is "auto" or "per_op". Drag a capital marker to a new position.
**Expected:** Affected neighbor Voronoi polygons visually update on the Konva canvas within 500ms, without reloading the page.
**Why human:** Cannot measure render latency or confirm visual polygon redraw via grep. Requires running the app.

#### 2. Vertex drag reflected immediately on canvas (auto/per_op mode)

**Test:** Enter vertex-edit mode on a territory. Drag a border vertex to a new position, then commit.
**Expected:** The polygon outline reshapes immediately on canvas; the updated geometry is visible without page reload.
**Why human:** Visual confirmation required; grep confirms the invalidation exists but not the end-to-end visual result.

#### 3. Merge result visible immediately (auto/per_op mode)

**Test:** Rubber-band select 2+ adjacent territories. Click Fundir.
**Expected:** The selected polygons are replaced by a single merged polygon on canvas without page reload.
**Why human:** Visual correctness of the merged polygon boundary requires human observation.

#### 4. Ctrl+Z undoes capital drag as single compound step (visual)

**Test:** Drag a capital, observe polygon update. Press Ctrl+Z.
**Expected:** Both the capital marker position and all affected neighbor polygons revert to pre-drag state in a single undo step. No partial revert (e.g., capital moves back but polygons stay at recalculated state).
**Why human:** Compound undo correctness is unit-tested but visual canvas completeness of the rollback (both DecorationsLayer and TerritoryLayer) requires human observation.

### Gaps Summary

Plan 09 successfully closed the primary gap from the initial verification: the five invalidation sites (capital drag, vertex-edit commit, merge, split, and undo/redo temporal subscriber) are all wired. SC1, SC2, and SC3 are now verified for the auto and per_op save modes.

One targeted gap remains: **explicit save mode (Ctrl+S) does not invalidate the TanStack Query cache.** After a successful `manualSave()` call, `saveSnapshot()` writes the updated geometry to `territories.geojson` and `markSaved()` flips the indicator to "Salvo", but no `queryClient.invalidateQueries` is called. The canvas stays frozen at the pre-edit visual state. Users who prefer the explicit "save when I say so" workflow will see a confusing state: save confirmation shown, but map appears unchanged until they reload.

The fix is contained to a single function. The main challenge is that `persistence.ts` is a Zustand-based service module with no React context, so `useQueryClient()` cannot be called directly. The cleanest patterns are: (a) register an invalidation callback via a module-level setter, (b) invalidate inside the Ctrl+S handler in `useUndoShortcut.ts` which already imports `manualSave` and runs in React context, or (c) pass `queryClient` as a parameter to `manualSave()`.

**SQLite persistence deviation (advisory, carried forward):** ROADMAP SC1 states "persisted to SQLite." The implementation persists edits via atomic file write (`territories.geojson`, `os.replace`). User-visible durability is met. No downstream phase depends on querying a territories SQLite table. Informational only.

---

_Verified: 2026-04-24T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
