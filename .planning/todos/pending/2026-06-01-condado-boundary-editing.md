---
created: 2026-06-01
source: user request after carve-enclave-hole fix verified
status: pending
relates_to: [08.1 BezierEditLayer, 08.3 pen-tool, canvas_sidecars, condado tier]
---

# Feature: edit a CONDADO's outer boundary as a unit

**User request (2026-06-01):** be able to edit a condado (the tier above barony), not just
baronies. Clarified intent: **edit the condado's OUTER boundary as a unit** — dragging the
condado border should move the border baronies together (the constituent baronies on that
edge follow), not just one barony.

## Current state (investigated 2026-06-01)
- Condados are **render-only aggregates**. There is NO `condados.geojson` sidecar and NO
  editable contour path.
  - Click on a condado → `uiStore.selectIds` (selectedTerritoryIds) → `SelectionBridge` CASE 1
    (`SelectionBridge.tsx:52-58`): clears vertices, loads nothing. Editor stays empty (D-03).
  - Default view shows condados ON / baronies OFF (`uiStore.ts:43-51`); baronies become
    editable only when the Baronies layer is toggled on and a single barony is clicked, which
    loads its ring from `baronies.geojson` (`SelectionBridge.tsx:62-91`).
- Baronies sidecar: `build_baronies_geojson_sidecar` (`canvas_sidecars.py:192-275`) extracts
  one Feature per barony idx from the raster via masked `shapes()`; a `condados.geojson`
  analogue does not exist.

## Scope to design (dedicated plan — significant)
- Backend: a `condados.geojson` sidecar (outer boundary per condado = union of its baronies'
  polygons), regenerated after Apply alongside baronies.
- Frontend: a condado-edit selection path (SelectionBridge load the condado ring; BezierEditLayer
  edit it) — distinct from the render-only condado layer.
- Geometry replay: moving a condado's outer boundary must propagate to the constituent baronies
  on that edge (the border baronies grow/shrink to match the new condado outline) WITHOUT leaving
  ocean holes (reuse the border-shrink gap-fill, commit 396f58e) and WITHOUT violating the
  per-condado / original_idx contracts. This is the hard part — define how the moved condado edge
  redistributes to member baronies.
- Decide interaction: how the user distinguishes "edit condado boundary" vs "edit a barony" (view
  toggle already exists; selection tier needs to be explicit).
- Real-mouse UAT: drag a condado outer edge → member baronies follow → Apply → no hole, condado +
  baronies both consistent.

## Suggested handling
New dedicated plan/phase AFTER phase 08.3 closes (e.g. a new decimal phase). Touches the 08.1
Bézier editor, canvas_sidecars, and manual_edit replay — too large for an ad-hoc add-on.
Relate to [[2026-06-01-shared-border-move-create-vs-extend-prompt]] (both concern multi-barony
boundary semantics).
