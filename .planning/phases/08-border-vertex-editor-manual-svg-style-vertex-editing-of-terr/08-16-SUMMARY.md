---
phase: 08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr
plan: 16
subsystem: frontend/landmask-editor-wiring
tags: [gap-closure, LANDMASK-01, LANDMASK-02, editableLayer, landmask-ring, path-b]
dependency-graph:
  requires: [08-14, 08-15]
  provides:
    - EditableLayer type in useEditorStore (store as single source of truth)
    - editableLayer state + setEditableLayer setter (zundo-excluded)
    - GET /editor/landmask_ring backend endpoint (Path B — NE union or branch event)
    - useLandmaskRing TanStack hook
    - LandmaskEditorHeader Switch toggle (data-testid=landmask-edit-toggle)
    - CanvasViewer plumbs editableLayer/landmaskCoords/onLandmaskCoordsChange to VertexEditLayer
    - CanvasViewer plumbs onApplyLandmask to LayerTogglePanel (real callback, not stub)
    - Manual Apply + auto-immediate both POST new_landmask_coords to backend
  affects:
    - LANDMASK-01 (landmask editable; PT/ES border read-only) — now FULL FIDELITY
    - LANDMASK-02 (manual + auto-immediate modes) — now FULL FIDELITY
tech-stack:
  added: []
  patterns:
    - "EditableLayer type in store (single source) + re-export in VertexEditLayer for backward compat"
    - "latestLandmaskRef seeded from query ring; updated every dragend so Apply never sends []"
    - "Path B: GET /editor/landmask_ring — branch edit-event coords priority, NE unary_union fallback"
    - "VertexEditLayer always calls onLandmaskCoordsChange (parent owns POST vs buffer decision)"
key-files:
  created:
    - frontend/src/hooks/useLandmaskRing.ts
    - frontend/src/stores/__tests__/useEditorStore.editableLayer.test.ts
    - backend/tests/integration/test_landmask_ring_endpoint.py
  modified:
    - frontend/src/stores/useEditorStore.ts
    - frontend/src/components/canvas/VertexEditLayer.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/components/editor/LandmaskEditorHeader.tsx
    - frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx
    - frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx
    - backend/medieval_forge/api/v3/editor.py
decisions:
  - "Path B chosen for landmask ring source: coastline.geojson is MultiLineString of OSM ways (not a closed polygon ring) and is NOT in ARTIFACT_FILES allowlist (would 404). New GET /editor/landmask_ring uses unary_union of PT+ES Natural Earth polygons as default, overridden by branch landmask_replace EditEvent if present."
  - "Surgical fix to VertexEditLayer.handleLandmaskDragEnd: removed auto-immediate guard; always calls onLandmaskCoordsChange. Parent (CanvasViewer) owns POST-vs-buffer decision based on landmaskMode. Prevents manual-mode Apply from sending empty coords."
  - "latestLandmaskRef seeded from useLandmaskRing query on load so Apply with zero drags sends current landmask ring (not [])."
  - "EditableLayer type moved from VertexEditLayer to useEditorStore (store as single source); VertexEditLayer re-exports it for backward compat (no consumers to update)."
metrics:
  duration: ~25min
  completed: "2026-05-28T12:29:13Z"
  tasks: 3
  files: 10
---

# Phase 08 Plan 16: LANDMASK-01/02 Full Fidelity — editableLayer Toggle + Coord Plumbing

**One-liner:** editableLayer store toggle (baronies↔landmask, zundo-excluded) + GET /editor/landmask_ring endpoint (Path B: Natural Earth union + branch override) + full CanvasViewer plumbing so landmask handles render cyan and Apply/auto-immediate POST new_landmask_coords to backend.

## What Was Built

### Task 1: editableLayer store toggle + landmask ring source (TDD)

**`frontend/src/stores/useEditorStore.ts`** — EXTENDED:
- New `export type EditableLayer = 'baronies' | 'landmask'` (store as single source of truth)
- `editableLayer: EditableLayer` state field (default `'baronies'`) — NOT in zundo partialize
- `setEditableLayer(l: EditableLayer)` action — sets field via `set()` only, no undo history

**`frontend/src/components/canvas/VertexEditLayer.tsx`** — REFACTORED:
- Removed own `export type EditableLayer` declaration
- Imports `EditableLayer` from store instead
- Re-exports `EditableLayer` from store for backward compat (consumers unchanged)

**`backend/medieval_forge/api/v3/editor.py`** — EXTENDED:
- New `GET /{project_id}/editor/landmask_ring?branch_id=...` endpoint
- Priority: branch `landmask_replace` EditEvent coords → Natural Earth PT+ES `unary_union` exterior → 404
- Returns `{ ring: [[lon,lat], ...], source: 'branch_edit_event'|'natural_earth' }`
- READ-ONLY (no DB writes, no cache side effects)

**`frontend/src/hooks/useLandmaskRing.ts`** — NEW:
- TanStack `useQuery` hook fetching the landmask ring from the backend
- Mirrors `useCanvasArtifacts` pattern; returns `Array<[number,number]> | undefined`
- `staleTime: 0` so `queryClient.invalidateQueries(['landmask-ring'])` picks up Apply immediately

**Tests (TDD RED → GREEN):**
- `useEditorStore.editableLayer.test.ts`: 6 tests — default 'baronies', toggle to 'landmask', round-trip, no pastStates growth, no editLog growth, type importable from store
- `test_landmask_ring_endpoint.py`: 5 tests — 400 on bad UUID, NE fallback, branch event priority, no-event fallback, ring shape validation

### Task 2: Visible editableLayer toggle in LandmaskEditorHeader

**`frontend/src/components/editor/LandmaskEditorHeader.tsx`** — EXTENDED:
- New Radix `Switch` with `data-testid="landmask-edit-toggle"` at top of Landmask section
- Reads `editableLayer` + `setEditableLayer` from `useEditorStore`
- Checked when `editableLayer === 'landmask'`; calls `setEditableLayer('landmask'/'baronies')` on change
- Existing manual/auto RadioGroup + Apply button unchanged (they control landmaskMode)

**`frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx`** — EXTENDED:
- Updated mock: added `Switch`, `Text`, `mockSetEditableLayer`, `mockEditableLayer`
- 4 new tests: toggle renders unchecked when baronies, checked when landmask, ON calls setEditableLayer('landmask'), OFF calls setEditableLayer('baronies')
- Total: 9 tests (5 original + 4 new)

**`frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx`** — UPDATED:
- Fixed pre-existing `Separator` missing from Radix mock (would 404 at test time)
- Added `Switch`, `Heading`, `Box`, `Badge`, `Button`, `RadioGroup` to mock (needed by LandmaskEditorHeader)
- Updated checkbox count assertion: 5 layers + 1 landmask-toggle = 6 total

### Task 3: CanvasViewer coord plumbing + apply callback

**`frontend/src/components/canvas/CanvasViewer.tsx`** — EXTENDED:
- Imports `useLandmaskRing` hook
- Reads `editableLayer` and `landmaskMode` from `useEditorStore`
- `landmaskRing = useLandmaskRing(projectId, activeBranchId)` — query ring as handle seed
- `latestLandmaskRef` seeded from query ring; updated on every `handleLandmaskCoordsChange` call
- `handleLandmaskCoordsChange`: always buffers; POSTs immediately when `landmaskMode === 'auto-immediate'`
- `handleApplyLandmask`: async POSTs `latestLandmaskRef.current` (manual Apply path)
- `<VertexEditLayer>` mount: added `editableLayer`, `landmaskCoords={landmaskRing}`, `onLandmaskCoordsChange`
- `<LayerTogglePanel>` mount: added `onApplyLandmask={handleApplyLandmask}` (replaces 08-14 no-op)

**`frontend/src/components/canvas/VertexEditLayer.tsx`** — SURGICAL FIX:
- `handleLandmaskDragEnd`: removed `if (landmaskMode === 'auto-immediate')` guard
- Now always calls `onLandmaskCoordsChange?.(newCoords)` — parent owns POST vs buffer decision
- Removed `landmaskMode` store selector (no longer read in this component)
- Prevents manual-mode Apply from sending `new_landmask_coords: []` (empty payload wipe)

## Gap Closed

**LANDMASK-01 + LANDMASK-02 — Full Fidelity:**

Before this plan:
- `LayerTogglePanel` received `projectId`/`branchId` from CanvasViewer (Plan 14) but no `onApplyLandmask` → Apply was a no-op
- No `editableLayer` store state existed → no UI toggle to flip baronies↔landmask
- `VertexEditLayer` received no `landmaskCoords` → `localLandmaskCoords` was always `[]` → handles never rendered
- Manual Apply would POST `new_landmask_coords: []` even if it worked (wipe)

After this plan:
- Radix Switch in LandmaskEditorHeader flips `editableLayer` baronies↔landmask via store
- `useLandmaskRing` fetches the actual ring (branch override > NE union)
- `landmaskRing` flows into `VertexEditLayer.landmaskCoords` → cyan handles render when `editableLayer==='landmask'`
- Every dragend updates `latestLandmaskRef` (always); auto-immediate POSTs immediately
- Apply button POSTs `latestLandmaskRef.current` (seeded from ring, updated by drags) — never empty

## Landmask Ring Source Decision

**Path B selected** (as anticipated by the plan's scope flag):

`coastline.geojson` is NOT viable because:
1. It is a `MultiLineString` of OSM coastline ways merged by `line_merge()` — not a closed polygon ring
2. It is NOT in `ARTIFACT_FILES` allowlist in `artifacts.py` (would 404 at the frontend fetch)
3. Converting disjoint ways to a ring would require non-trivial topology repair

**Path B implementation**: `GET /api/v3/projects/{id}/editor/landmask_ring`
- Priority 1: latest `landmask_replace` EditEvent for `branch_id` → returns those coords
- Priority 2: `shapely.ops.unary_union([get_country_polygon('PT'), get_country_polygon('ES')])` → exterior ring
- Priority 3: 404 (frontend returns `undefined`; VertexEditLayer renders no handles)

This is additive (no DAG/parity change) and READ-ONLY as permitted by the plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] VertexEditLayer auto-immediate guard caused empty Apply payload in manual mode**
- **Found during:** Task 3 implementation (flagged by advisor)
- **Issue:** `handleLandmaskDragEnd` only called `onLandmaskCoordsChange` when `landmaskMode === 'auto-immediate'`. In manual mode, `latestLandmaskRef.current` stayed at `[]` (initial seed before any drag), so clicking Apply would POST `new_landmask_coords: []` — wiping the landmask.
- **Fix:** Remove the `if (landmaskMode === 'auto-immediate')` guard from `VertexEditLayer`. Always call `onLandmaskCoordsChange`. Move the POST-vs-buffer decision to `CanvasViewer.handleLandmaskCoordsChange`. Seed `latestLandmaskRef.current = landmaskRing` on query resolve.
- **Files modified:** `VertexEditLayer.tsx`, `CanvasViewer.tsx`
- **Commit:** 22004cd

**2. [Rule 1 - Bug] LayerTogglePanel.test.tsx mock missing Separator (pre-existing)**
- **Found during:** Task 2 test run
- **Issue:** `LayerTogglePanel` already imported `Separator` from Plan 08-08, but the test mock didn't export it → vitest "No Separator export defined" error on all 6 tests.
- **Fix:** Added `Separator`, `Switch`, `Heading`, `Box`, `Badge`, `Button`, `RadioGroup` to the mock. Updated checkbox count expectation (5→6) to account for the new landmask-edit-toggle.
- **Files modified:** `LayerTogglePanel.test.tsx`
- **Commit:** e6c6172

## Test Coverage

| Test file | Tests | Status |
|-----------|-------|--------|
| `useEditorStore.editableLayer.test.ts` | 6 | GREEN |
| `useEditorStore.test.ts` (pre-existing) | 11 | GREEN |
| `LandmaskEditorHeader.test.tsx` | 9 (5+4 new) | GREEN |
| `LayerTogglePanel.test.tsx` | 6 | GREEN |
| `VertexEditLayer.test.tsx` | 20 | GREEN |
| `VertexEditLayerPolygonOps.test.tsx` | 14 | GREEN |
| `CanvasViewer.test.tsx` | 7 | GREEN |
| `CanvasViewer.panOnSelect.test.tsx` | 9 | GREEN |
| `CanvasViewer.fitToView.test.tsx` | 3 | GREEN |
| `CanvasViewer.clearCache.test.tsx` | 3 | GREEN |
| `test_landmask_ring_endpoint.py` | 5 | GREEN |

**Total: 100 frontend tests + 5 backend integration tests passing; tsc --noEmit exits 0.**

## Commits

| Hash | Type | Description |
|------|------|-------------|
| d7d38f4 | feat | Task 1: editableLayer store toggle + landmask ring endpoint |
| e6c6172 | feat | Task 2: editableLayer toggle in LandmaskEditorHeader |
| 22004cd | feat | Task 3: plumb landmask coords + apply callback in CanvasViewer |

## Known Stubs

None — all wired props flow to real store state, real API data, and real backend endpoint.
The `landmask-edit-toggle` Switch is visible and functional; the Apply callback POSTs real coords.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: read-only-endpoint | `editor.py` GET /editor/landmask_ring | New READ-ONLY endpoint returns landmask ring. No auth required (same posture as all v3 project endpoints). T-08-16-01: returns only ring coords, no sensitive data. Branch edit-event lookup scoped by branch_id param — no cross-branch leakage (branch_id is validated against EditEvent.branch_id). |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `useEditorStore.ts` has `editableLayer` field + `setEditableLayer` | VERIFIED |
| `editableLayer` NOT in partialize (grep) | VERIFIED |
| `useEditorStore.editableLayer.test.ts` exists (6 tests) | FOUND |
| `useLandmaskRing.ts` exists | FOUND |
| `test_landmask_ring_endpoint.py` exists (5 tests) | FOUND |
| `editor.py` has `get_landmask_ring` endpoint | VERIFIED |
| `LandmaskEditorHeader.tsx` has `data-testid="landmask-edit-toggle"` | VERIFIED |
| `CanvasViewer.tsx` has `editableLayer` (read + prop, ≥2 hits) | VERIFIED (4 hits) |
| `CanvasViewer.tsx` has `new_landmask_coords` (≥1 hit) | VERIFIED (2 hits) |
| `CanvasViewer.tsx` VertexEditLayer has `landmaskCoords` prop | VERIFIED |
| `CanvasViewer.tsx` VertexEditLayer has `onLandmaskCoordsChange` prop | VERIFIED |
| `CanvasViewer.tsx` LayerTogglePanel has `onApplyLandmask` prop | VERIFIED |
| commit d7d38f4 (Task 1) | FOUND |
| commit e6c6172 (Task 2) | FOUND |
| commit 22004cd (Task 3) | FOUND |
| `tsc --noEmit` exits 0 | PASSED |
| 100 frontend tests passing | PASSED |
| 5 backend integration tests passing | PASSED |
