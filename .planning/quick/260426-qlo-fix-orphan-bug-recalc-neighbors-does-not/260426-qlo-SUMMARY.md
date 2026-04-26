---
phase: quick-260426-qlo
plan: 01
subsystem: backend/geometry
tags: [bug-fix, voronoi, clipping, edit-api, geometry]
tech_stack:
  added: []
  patterns: ["sentinel-seeds bounding for Voronoi edge cells", "shapely.intersection clip with largest-polygon normalization"]
requires: ["backend/medieval_forge/services/voronoi.py::recalc_neighbors", "backend/medieval_forge/services/territories_geojson.pixel_polygon_to_lonlat"]
provides: ["recalc_neighbors land_mask + bbox clipping", "voronoi.load_land_mask_and_bbox(generated_dir) helper"]
affects: ["move_capital endpoint output geometry"]
key_files:
  created: []
  modified:
    - backend/medieval_forge/services/voronoi.py
    - backend/medieval_forge/services/territories_geojson.py
    - backend/medieval_forge/services/baronies_geojson.py
    - backend/medieval_forge/api/edit.py
    - backend/tests/services/test_voronoi.py
    - backend/tests/api/test_edit_api.py
decisions:
  - "Sentinel-seeds approach (4 far corners) chosen over scipy ridge-extension idiom — far simpler, equivalent end result after clipping; sentinels invisible in output because their polygons never contain real-seed indices"
  - "land_mask wins over bbox when both supplied (bbox becomes implicit in the mask)"
  - "affected_ids semantics differ by mode: with clip → only survivors; without clip → all affected_indices (preserves legacy backwards-compat for unit tests + early callers)"
  - "load_land_mask_and_bbox never raises — graceful (None, None) on missing/malformed files so move_capital still runs unclipped"
metrics:
  duration_minutes: 18
  completed: 2026-04-26
  tasks: 2
  tests_added: 5
  tests_passing: "39/39 in-scope (services/test_voronoi + api/test_edit_api + test_territories_geojson + test_baronies_geojson)"
---

# Quick Task 260426-qlo: Clip recalc_neighbors to Land Mask Summary

Fix orphan bug #3 from `.planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md` — Voronoi cells from `recalc_neighbors` could extend into the ocean after a capital move, and previously-unbounded edge cells were silently dropped. Now `recalc_neighbors` accepts optional `land_mask` (Shapely geometry, lon/lat) and `bbox` kwargs, and `move_capital` derives both from the project's `generated/` artifacts via the new `load_land_mask_and_bbox` helper.

## What Changed

### `services/voronoi.py`
- Extended `recalc_neighbors(...)` with keyword-only `land_mask: BaseGeometry | None = None` and `bbox: tuple[float, float, float, float] | None = None`.
- When clipping is requested, **4 sentinel seeds** are added far outside the clip extent so every real seed gets a bounded Voronoi cell — replaces the scipy ridge-extension idiom with simpler, equivalent code.
- Each cell is intersected with `clip_geom` (`land_mask` if set else bbox); result is normalized via new `_select_largest_polygon` (handles Polygon / MultiPolygon / GeometryCollection from `shapely.intersection`).
- Cells whose intersection is empty are dropped from **both** `updated_territories` AND `affected_ids` (per Test D contract).
- When neither kwarg is supplied, legacy behavior preserved (unbounded cells skipped, `affected_ids` reflects full affected set).
- New public `load_land_mask_and_bbox(generated_dir: Path)` builds:
  - `bbox` from `territory_metadata.json::bounds`
  - `land_mask` from `lookup_condado.png` via `rasterio.features.shapes(mask = pixel_sum > 0)` → `unary_union` → projected to lon/lat using the **same** inversion math as `territories_geojson.pixel_polygon_to_lonlat` (DRY).
  - Never raises — returns `(None, None)` on missing/malformed inputs so callers degrade gracefully.

### `services/territories_geojson.py` + `services/baronies_geojson.py`
- Promoted `_pixel_polygon_to_lonlat` → `pixel_polygon_to_lonlat` (public). Both in-repo callers updated.

### `api/edit.py`
- `move_capital` now calls `load_land_mask_and_bbox(project_dir(project_id) / "generated")` and passes both into `recalc_neighbors`.
- `ValueError` (non-UUID test path) → fall back to no clipping.
- `INFO` log when neither artifact available, so observability matches the new code path.

### Tests added (5)
1. `test_recalc_neighbors_no_clip_backwards_compat` — legacy 4-arg call returns the same shape (unbounded skip + `affected_ids` = all affected indices).
2. `test_recalc_neighbors_clips_to_bbox` — bbox rescues edge cells; every coord lies within bbox.
3. `test_recalc_neighbors_clips_to_land_mask` — moved cell entirely contained in mask; verified via `shapely.contains(mask.buffer(1e-6), poly)`.
4. `test_recalc_neighbors_drops_cells_fully_outside_land_mask` — c1/c2 cells in ocean half dropped from both `updated_territories` and `affected_ids`; no zero-area geometries leak.
5. `test_move_capital_clips_returned_polygons_to_bbox` — end-to-end API test asserting every returned polygon coord is within the project's bbox loaded from `territory_metadata.json` (no `lookup_condado.png` written → exercises the bbox-only graceful-degrade path).

## Verification

```text
backend $ python -m pytest tests/services/test_voronoi.py tests/api/test_edit_api.py tests/test_territories_geojson.py tests/test_baronies_geojson.py -q
......................................                                  [100%]
39 passed in 0.21s
```

All 4 must_haves.truths satisfied:
- Returned polygons stay inside land area (clipped to mask if available, else bbox). ✓
- Previously-unbounded cells produce valid clipped polygons. ✓
- Without land_mask/bbox kwargs, recalc_neighbors keeps the existing unbounded-cell-skip behavior. ✓
- Land mask + bbox derived from project's `generated/` artifacts, end-to-end wired through move_capital. ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Renamed `_pixel_polygon_to_lonlat` in `baronies_geojson.py`**
- **Found during:** Full backend test suite run after Task 1 (collection error).
- **Issue:** `baronies_geojson.py` still imported the old private name `_pixel_polygon_to_lonlat`, breaking module collection.
- **Fix:** `replace_all` rename in `baronies_geojson.py` to use the new public name.
- **Files modified:** `backend/medieval_forge/services/baronies_geojson.py`
- **Commit:** 6e252ba (folded into Task 2 GREEN commit)

**2. [Discretionary - Test fixture refinement] Test D seed configuration**
- **Found during:** Task 1 GREEN run.
- **Issue:** Initial Test D seed config (c1/c2 at x=8 with mask x<=5) produced cells whose Voronoi region touched the boundary, so `intersection` returned a thin sliver instead of dropping the cell.
- **Fix:** Moved c1/c2 to x=9 and tightened mask to x<=4 — Voronoi midpoint between c0 (x=2.5) and c1 (x=9) is at x=5.75, well outside the mask, so c1/c2 cells are now strictly outside post-clip.
- **Files modified:** `backend/tests/services/test_voronoi.py`
- **Commit:** d962b0f (folded into Task 1 GREEN commit)

## Pre-existing Out-of-Scope Failures

Full backend test run shows 15 unrelated failures in LLM/auth/research/SSE subsystems (`test_llm_retry`, `test_providers_endpoint`, `test_research_sse`, `test_generate`, `test_ingest`, `test_auth_session`, `test_condado_assignment`, `test_llm_registry`, `test_llm_schemas`, `test_oauth_flow`). None touch voronoi/edit/territories. Out of scope for this fix per `<scope_boundary>` rule.

## Self-Check: PASSED

- `backend/medieval_forge/services/voronoi.py` — FOUND (recalc_neighbors signature now `*, land_mask=None, bbox=None`; load_land_mask_and_bbox helper present)
- `backend/medieval_forge/services/territories_geojson.py` — FOUND (`pixel_polygon_to_lonlat` public)
- `backend/medieval_forge/services/baronies_geojson.py` — FOUND (import updated)
- `backend/medieval_forge/api/edit.py` — FOUND (move_capital passes land_mask + bbox)
- `backend/tests/services/test_voronoi.py` — FOUND (4 new tests)
- `backend/tests/api/test_edit_api.py` — FOUND (1 new test + metadata fixture)
- Commit 90a7326 (RED voronoi tests) — FOUND
- Commit d962b0f (GREEN Task 1) — FOUND
- Commit 948059b (RED API test) — FOUND
- Commit 6e252ba (GREEN Task 2 + baronies rename) — FOUND
