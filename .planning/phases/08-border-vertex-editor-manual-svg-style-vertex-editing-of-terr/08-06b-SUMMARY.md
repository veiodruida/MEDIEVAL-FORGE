---
phase: 08
plan: "06b"
subsystem: vertex-ops
tags: [snap, shared-vertex, topology, konva, react, zustand, barony, topo-block]
dependency_graph:
  requires: [08-06a]
  provides: [snap.ts, sharedVertex.ts, VertexEditLayer-snap-coupling-topo-visuals, backend-coupling-tests]
  affects: [08-07, 08-08, 08-09, 08-11]
tech_stack:
  added: []
  patterns:
    - "snapToNeighbour: SNAP_SCREEN_PX(5) / stageScale = world-unit tolerance (Pitfall 7 fix)"
    - "buildSharedVertexIndex: O(N^2) naive scan, tolerance 1e-6; getCoupledVertices → coupled drag"
    - "D-30: single setVerticesAndLog call for N coupled vertices (one undoable op)"
    - "D-26 TOPO-01 visual: invalidDragId state → #ef4444 fill+stroke for 600ms then revert"
    - "D-27 warn flags: computeWarnFlags (duplicate vertex ≤1e-6, sliver bbox-area <0.001°)"
    - "D-28 Alt-disable: window keydown/keyup listener sets altHeld; passed to snapToNeighbour"
key_files:
  created:
    - frontend/src/lib/snap.ts
    - frontend/src/lib/sharedVertex.ts
  modified:
    - frontend/src/lib/__tests__/snap.test.ts
    - frontend/src/lib/__tests__/sharedVertex.test.ts
    - frontend/src/components/canvas/VertexEditLayer.tsx
    - frontend/src/components/canvas/__tests__/VertexEditLayer.test.tsx
    - backend/tests/unit/test_topology_validate.py
    - backend/tests/unit/test_shared_vertex_coupling.py
decisions:
  - "Snap threshold uses stageRef.current.scaleX() (Konva zoom), not ProjectionContext — ProjectionContext maps geo↔canvas at fixed scale; zoom factor is on Konva Stage (Pitfall 7)"
  - "D-27 browser-side sliver check uses bbox-area proxy (<0.001°²), not Shapely area — Shapely runs backend-side on /editor/validate commit; frontend flag is advisory only"
  - "DEGENERATE blocking code in test_topology_validate stub dropped — D-27 explicitly non-blocking; replaced with test confirming sliver passes validate_edit cleanly"
  - "Shared-vertex index rebuilt on activeTerritoryId change and on each mouseup commit — cheap because N per editable region is small (O(N^2) acceptable, Karpathy §Pitfall 8)"
  - "BARONY_A_BROKEN fixture corrected: shrink right edge to x=0.8 (not expand to x=1.2) to produce real gap vs BARONY_B(left=1.0)"
metrics:
  duration_minutes: 35
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 6
---

# Phase 08 Plan 06b: Snap + Shared-Vertex Coupling + Topology-Block Visuals Summary

Scale-aware snap (Pitfall 7 fix), shared-vertex coupled drag (D-30), topology-block red visual (D-26), and D-27 warn-badge flags — all wired into VertexEditLayer with 44 tests green.

## What Was Built

### Task 1 — snap.ts + sharedVertex.ts + tests (TDD)

**`frontend/src/lib/snap.ts`** — NEW scale-aware snap utility (TOPO-03, D-28).

- `snapToNeighbour(cursorWorld, candidates, stageScale, altHeld)`: Pitfall 7 fix — converts SNAP_SCREEN_PX (5) to world-unit tolerance via `5 / stageScale`. At zoom=1: 5 world units; at zoom=10: 0.5 world units. Hold Alt → returns null (D-28).
- Naive O(N) scan over candidates — N is small after viewport culling; no premature optimization (Karpathy §Pitfall 8).

**`frontend/src/lib/sharedVertex.ts`** — NEW shared-vertex index utility (TOPO-04, D-30).

- `buildSharedVertexIndex(vertices, tolerance=1e-6)`: O(N²) naive scan; only coupled vertices (≥1 partner) appear as keys. Refresh on edit-mode entry + mouseup.
- `getCoupledVertices(index, vertexId)`: returns coupled group or `[vertexId]` singleton for isolated vertex.
- D-30 default-and-only: no escape hatch.

**16 tests green** (8 snap + 8 sharedVertex) — explicit numeric fixtures per user memory.

### Task 2 — VertexEditLayer extensions + backend coupling tests (TDD)

**`frontend/src/components/canvas/VertexEditLayer.tsx`** — extended:

- **Alt-key state** (D-28): `window keydown/keyup` listener → `altHeld` state → passed to `snapToNeighbour` each drag frame.
- **Snap per drag frame** (TOPO-03): `handleDragMove` RAF callback calls `snapToNeighbour(cursorWorld, candidates, stageRef.current.scaleX(), altHeld)`; if hit → `setSnapTargetPx({x, y})`.
- **Snap target indicator** (D-28): `<Circle data-testid="snap-target-indicator" stroke="#eab308" strokeWidth={2} radius={8} listening={false}/>` rendered when `snapTargetPx !== null`.
- **Snap-to on drag end** (D-28): `handleDragEnd` re-runs snap check; if snap hit, snaps final position to candidate coords before validation.
- **Shared-vertex coupling** (TOPO-04, D-30): `sharedIndexRef` rebuilt on `activeTerritoryId` change; `handleDragEnd` calls `getCoupledVertices` → if group.length > 1, calls `setVerticesAndLog(nextVertices, {op:'move', vertexIds:coupledIds})` — single undoable op per D-30.
- **Topology-block visual** (TOPO-01, D-26): on invalid `/editor/validate` response → `setInvalidDragId(id)` → handle fill turns `#ef4444`; after 600ms revert. Vertex snaps back (mouseup aborts commit).
- **D-27 warn flags**: `computeWarnFlags(vertices)` — duplicate vertex (Euclidean ≤1e-6) + sliver polygon (bbox area <0.001°); fires `onWarnFlagsChange` prop on every vertex change. Inspector reads this for amber badges.

**`backend/tests/unit/test_topology_validate.py`** — Wave-0 stub replaced entirely:

- `test_self_intersecting_figure8_polygon_returns_SELF_INTERSECT_code`: bowtie Polygon
- `test_valid_square_with_no_neighbours_returns_True_None`: unit square
- `test_disjoint_neighbour_after_edit_returns_NEIGHBOUR_GAP_code`: SQUARE + DISJOINT_SQUARE(5,5)
- `test_touching_neighbour_after_edit_returns_True_None`: SQUARE + SQUARE_NEIGHBOUR(shared edge at x=1)
- `test_self_intersect_checked_before_neighbour_gap`: priority ordering
- `test_degenerate_near_zero_area_polygon_is_still_valid_in_validate_edit`: D-27 non-blocking confirmation (1e-5 wide sliver)

**`backend/tests/unit/test_shared_vertex_coupling.py`** — Wave-0 stub replaced entirely:

- `test_coupled_vertex_move_barony_A_is_valid_post_edit`: shared edge moved x=1→x=1.2 in both baronies
- `test_coupled_vertex_move_barony_B_is_valid_post_edit`: symmetric check
- `test_coupled_polygons_share_zero_distance_after_move`: Shapely distance() == 0.0
- `test_non_coupled_move_leaves_gap_and_returns_NEIGHBOUR_GAP`: A shrinks to x=0.8, B stays at x=1.0
- `test_non_shared_vertex_move_does_not_affect_non_touching_neighbour`: outer vertex move preserves touch

**44 tests green** (33 frontend + 11 backend).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stub APIs don't match plan spec (snap.test.ts + sharedVertex.test.ts)**
- **Found during:** Task 1, RED phase
- **Issue:** `snap.test.ts` stub used `snapToVertex`; plan spec uses `snapToNeighbour`. `sharedVertex.test.ts` used `findSharedVertices`/`propagateVertexMove`; plan spec uses `buildSharedVertexIndex`/`getCoupledVertices`.
- **Fix:** Both stubs replaced entirely with plan-spec API tests per 08-06a Deviation #3 precedent.
- **Files modified:** `snap.test.ts`, `sharedVertex.test.ts`
- **Commit:** c189d31

**2. [Rule 1 - Bug] `DEGENERATE` blocking code contradicts D-27**
- **Found during:** Task 2, backend RED phase
- **Issue:** `test_topology_validate.py` stub had `test_duplicate_vertex_coordinates_returns_DEGENERATE_code` as a blocking error. D-27 explicitly states duplicate vertex is a **non-blocking warning** (amber badge). `validate_edit` only handles SELF_INTERSECT + NEIGHBOUR_GAP.
- **Fix:** Removed DEGENERATE test; replaced with `test_degenerate_near_zero_area_polygon_is_still_valid_in_validate_edit` which confirms D-27 non-blocking semantics.
- **Files modified:** `test_topology_validate.py`
- **Commit:** 9e3cef3

**3. [Rule 1 - Bug] `BARONY_A_BROKEN` fixture caused false overlap, not gap**
- **Found during:** Task 2, backend GREEN phase (1 test failed on first run)
- **Issue:** `BARONY_A_BROKEN = Polygon([(0,0),(1.2,0),(1.2,1),(0,1)])` expands A beyond x=1 → A and B(starting at x=1) overlapped, making them non-disjoint → `validate_edit` returned valid (no gap).
- **Fix:** Changed fixture to `Polygon([(0,0),(0.8,0),(0.8,1),(0,1)])` — shrinks A's right edge to x=0.8, creating real gap between A(right=0.8) and B(left=1.0).
- **Files modified:** `test_shared_vertex_coupling.py`
- **Commit:** 9e3cef3

**4. [Rule 1 - Bug] `require('../VertexEditLayer')` CJS call in ESM test context**
- **Found during:** Task 2, frontend GREEN phase (2 tests failed)
- **Issue:** Two new tests used `require('../VertexEditLayer')` in a Vitest ESM environment → "Cannot find module" error.
- **Fix:** Added `SNAP_TARGET_STROKE` and `INVALID_DRAG_STROKE` to the existing static import line; replaced `require()` calls with the imported constants.
- **Files modified:** `VertexEditLayer.test.tsx`
- **Commit:** 9e3cef3

## Known Stubs

None — all stubs from 08-06a that were deferred to 08-06b are now resolved:

| Previously-deferred stub | Resolution in 08-06b |
|---|---|
| Topology invalid → console.warn only (no visual rollback) | TOPO-01 red fill #ef4444 + 600ms revert + snap-back |
| Add tool: no edge-snapping | Snap now wired in onDragEnd (TOPO-03) |
| onDragEnd posts unordered coords | Coupled move uses position from snapResult or raw drag (D-28 applied) |

Remaining stub: canonical ring ordering (vertex sequence as polygon ring) — deferred to 08-07 when ordered vertex representation lands. Coords are posted as `Object.entries(vertices)` which preserves insertion order but not ring closure order.

## Threat Flags

No new threat surfaces beyond the plan's threat model:
- T-08-06b-01 mitigated: validate endpoint is advisory only; `/editor/apply` (08-11) re-validates on server side.
- T-08-06b-02 accepted: O(N²) sharedVertex is acceptable for small N; replace with KDTree only if measured slow.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `frontend/src/lib/snap.ts` exists | FOUND |
| `frontend/src/lib/sharedVertex.ts` exists | FOUND |
| `grep -c "stageScale" snap.ts` ≥ 2 | FOUND (6) |
| `grep -c "1e-6\|tolerance" sharedVertex.ts` ≥ 2 | FOUND (5) |
| `grep -c "snapToNeighbour\|sharedVertex" VertexEditLayer.tsx` ≥ 2 | FOUND (7) |
| `grep -c "#eab308" VertexEditLayer.tsx` ≥ 1 | FOUND (3) |
| `grep -c "#ef4444" VertexEditLayer.tsx` ≥ 1 | FOUND (2) |
| 16 frontend lib tests green (snap + sharedVertex) | PASSED |
| 17 frontend component tests green (VertexEditLayer) | PASSED |
| 11 backend unit tests green (topology_validate + shared_vertex_coupling) | PASSED |
| tsc --noEmit clean | PASSED |
| commit c189d31 (Task 1) | FOUND |
| commit 9e3cef3 (Task 2) | FOUND |
