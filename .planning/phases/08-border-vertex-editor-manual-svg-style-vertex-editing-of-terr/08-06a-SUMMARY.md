---
phase: 08
plan: "06a"
subsystem: vertex-ops
tags: [shapely, topology, fastapi, konva, react, zustand, vertex-editing, barony]
dependency_graph:
  requires: [08-04, 08-05]
  provides: [topology.py, editor-validate-endpoint, VertexCapBadge, VertexEditLayer-ops-wired]
  affects: [08-06b, 08-07, 08-08, 08-09]
tech_stack:
  added: []
  patterns:
    - "validate_edit: shapely is_valid + disjoint check — SELF_INTERSECT + NEIGHBOUR_GAP error codes"
    - "douglas_peucker_simplify: shapely.simplify(preserve_topology=True) tolerance range (0, 0.1]"
    - "POST /editor/validate batch: Pydantic max_length=100 cap (T-08-06a-02), UUID guard (T-08-06a-01)"
    - "VertexEditLayer async handleDragEnd: POST /editor/validate → on valid commit moveVertex (fail-open on error)"
    - "D-03 barony-tier guard: tier prop on VertexEditLayer; non-barony silently no-ops all edit ops"
    - "D-06 add-vertex cap: Layer onClick checks vertexCount >= 1000 before addVertex"
    - "VertexCapBadge: amber at count>=max/2, red at count>=max; null below threshold"
key_files:
  created:
    - backend/medieval_forge/services/pipeline/topology.py
    - backend/medieval_forge/api/v3/editor.py
    - frontend/src/components/editor/VertexCapBadge.tsx
  modified:
    - backend/medieval_forge/main.py
    - backend/tests/unit/test_manual_edit_simplify.py
    - backend/tests/integration/test_editor_validate_endpoint.py
    - frontend/src/components/canvas/VertexEditLayer.tsx
    - frontend/src/components/editor/__tests__/VertexCapBadge.test.tsx
decisions:
  - "fail-open on /editor/validate network error: console.warn + proceed with commit; visual rollback deferred to 08-06b to avoid blocking the user in the happy path"
  - "Polygon ring ordering deferred: onDragEnd posts Object.values(vertices) as coords — no canonical ring order in 08-06a; real ordered representation + edge snapping lands in 08-06b/07"
  - "D-03 tier prop defaults to 'barony' for CanvasViewer backward compat; non-barony tier silently no-ops (no error) per plan"
  - "Stub test replacement: stubs in test_manual_edit_simplify.py and test_editor_validate_endpoint.py replaced entirely (precedent from 08-05 deviation #3); VertexCapBadge.test.tsx stubs replaced with plan-spec tests"
metrics:
  duration_minutes: 30
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 5
---

# Phase 08 Plan 06a: Vertex Ops Part A — topology.py + editor validate endpoint + VertexCapBadge Summary

Wave 5 vertex ops part A complete. Backend topology helpers + POST /editor/validate endpoint + VertexEditLayer ops wired + VertexCapBadge live. 35 tests passing (19 backend + 16 frontend).

## What Was Built

### Task 1 — Backend topology.py + POST /editor/validate endpoint (TDD)

**`backend/medieval_forge/services/pipeline/topology.py`** — NEW topology helpers.

- `validate_edit(target, neighbours)`: Shapely `is_valid` check → SELF_INTERSECT; `disjoint` check per neighbour → NEIGHBOUR_GAP. Returns `(True, None)` for valid. Priority: self-intersect checked before neighbour gap.
- `douglas_peucker_simplify(target, tolerance)`: `shapely.simplify(preserve_topology=True)` — non-negotiable per RESEARCH §Don't Hand-Roll #4. Tolerance range `(0, 0.1]`; raises `ValueError` outside range. UI slider range 0.00001–0.01 stays within backend buffer.

**`backend/medieval_forge/api/v3/editor.py`** — NEW batch validate endpoint.

- `POST /api/v3/projects/{project_id}/editor/validate`
- Pydantic models: `PolygonValidationRequest` (polygon_id, coords, neighbour_ids), `ValidateBatchBody` (`polygons: Field(..., max_length=100)`, `neighbour_lookup`), `ValidateResult` (polygon_id, valid, code).
- UUID guard via `is_valid_uuid(project_id)` → 400 (T-08-06a-01 pattern from render.py).
- `max_length=100` DoS cap (T-08-06a-02).
- Degenerate coord handling: < 3 coords → SELF_INTERSECT without raising (T-08-06a-03).
- Silently skips unknown neighbour_ids from neighbour_lookup (tolerates stale client state after a delete).

**`backend/medieval_forge/main.py`** — extended with `editor_router` import + `app.include_router`.

12 unit tests (validate_edit + douglas_peucker_simplify) + 7 integration tests (endpoint) = **19 backend tests passing**.

### Task 2 — VertexCapBadge + VertexEditLayer wired ops (TDD)

**`frontend/src/components/editor/VertexCapBadge.tsx`** — NEW badge component.

- `count >= max`: red Badge "Limite de N vértices atingido"
- `count >= max/2`: amber Badge "N vértices — simplificar recomendado"
- `count < max/2`: null (no badge)
- Props: `count: number`, `max: number` (D-06 default max=1000 supplied by caller).

**`frontend/src/components/canvas/VertexEditLayer.tsx`** — extended:

- `tier?: TerritoryTier` prop added (D-03): `'barony' | 'condado' | 'duchy' | 'kingdom'`. All edit ops (move, add) silently no-op when tier is not `'barony'`. Default `'barony'` for CanvasViewer backward compat.
- `projectId?: string` prop added for `POST /editor/validate` call.
- `handleDragEnd` made `async`: inverse-projects px → lat/lon → builds coords → `POST /editor/validate` → on valid: `moveVertex`; on invalid: `console.warn + return` (visual rollback deferred to 08-06b).
- `handleLayerClick`: When `activeTool === 'A'` + tier is barony + `vertexCount < 1000` → `addVertex(crypto.randomUUID(), lat, lon)`.
- Layer `onClick={handleLayerClick}` wired.
- `onDragEnd={void handler}` pattern for async handler TypeScript compatibility.

7 VertexCapBadge tests + 9 existing VertexEditLayer tests = **16 frontend tests passing**.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stub test names/shapes didn't match plan spec**
- **Found during:** Task 1, RED phase
- **Issue:** `test_manual_edit_simplify.py` stub had `test_simplify_polygon_reduces_vertex_count_below_cap` but referenced non-existent functions (`simplify_polygon`, `topology_validate`). `test_editor_validate_endpoint.py` used `{"ok": true}` shape instead of `{"valid": true}` from plan. `VertexCapBadge.test.tsx` had `"42 / 100"` format instead of plan-spec copy.
- **Fix:** Replaced all three stub files entirely (precedent: 08-05 Deviation #3).
- **Files modified:** all three test files
- **Commit:** dff63c6, 6c4753b

**2. [Rule 2 - Missing functionality] D-03 barony-tier guard absent in scaffold**
- **Found during:** Task 2, pre-implementation review (advisor recommendation)
- **Issue:** Plan 08-05 scaffold had no `tier` prop on VertexEditLayer. Without it, condado/duchy/kingdom vertices could be edited (violates D-03).
- **Fix:** Added `tier?: TerritoryTier` prop with default `'barony'`; all edit ops gated on `isEditableTier = tier === 'barony'`.
- **Files modified:** `frontend/src/components/canvas/VertexEditLayer.tsx`
- **Commit:** 6c4753b

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `onDragEnd` posts `Object.values(vertices)` as unordered coords | `VertexEditLayer.tsx` | ~197 | No canonical ring-order representation in store yet; real ordering + edge snapping lands in 08-06b/07 |
| Topology invalid → console.warn only (no visual rollback) | `VertexEditLayer.tsx` | ~208 | Handle snap-back + red INVALID_DRAG_STROKE glow deferred to 08-06b per plan |
| Add vertex: no edge-snapping (inserts at raw cursor lat/lon) | `VertexEditLayer.tsx` | ~224 | KDTree edge-hit detection (D-28) deferred to 08-06b |

## Threat Flags

No new threat surfaces beyond the plan's threat model:
- T-08-06a-01 mitigated: endpoint is read-only (validate only, no persist).
- T-08-06a-02 mitigated: `max_length=100` in `ValidateBatchBody`.
- T-08-06a-03 mitigated: Pydantic parse + degenerate coord handling.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `backend/medieval_forge/services/pipeline/topology.py` exists | FOUND |
| `backend/medieval_forge/api/v3/editor.py` exists | FOUND |
| `frontend/src/components/editor/VertexCapBadge.tsx` exists | FOUND |
| `grep -c "preserve_topology=True" topology.py` >= 1 | FOUND (4) |
| `grep -c "editor_router" main.py` >= 1 | FOUND (2) |
| `grep -c "1000" VertexCapBadge.tsx` >= 1 | FOUND (2) |
| commit dff63c6 (backend topology + endpoint) | FOUND |
| commit 6c4753b (VertexCapBadge + VertexEditLayer wired) | FOUND |
| 19 backend pytest passing | PASSED |
| 16 frontend vitest passing | PASSED |
| tsc --noEmit clean | PASSED |
