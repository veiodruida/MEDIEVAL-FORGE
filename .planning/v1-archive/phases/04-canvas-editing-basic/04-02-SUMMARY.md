---
phase: 04-canvas-editing-basic
plan: 02
subsystem: backend-geometry-service
tags: [voronoi, shapely, scipy, geometry, tdd, wave-1]
dependency_graph:
  requires:
    - backend/tests/services/test_voronoi.py (RED scaffolds from P01)
  provides:
    - backend/medieval_forge/services/voronoi.py (6 exported geometry functions)
  affects:
    - P04 (api/edit.py must call these functions for all 4 edit operations)
tech_stack:
  added: []
  patterns:
    - "GeoJSON-dict I/O at function boundaries — callers never handle Shapely objects"
    - "Pitfall 4 pre-validation: polygon.exterior.intersection(cut_line_geom) before ops.split"
    - "Adjacency rebuild-from-scratch after every merge (Pitfall 3)"
    - "Douglas-Peucker binary search for decimate_polygon with is_valid guard (Shapely #2165)"
key_files:
  created:
    - backend/medieval_forge/services/voronoi.py
  modified:
    - backend/tests/services/test_voronoi.py
decisions:
  - "GeoJSON-dict I/O: all 6 functions accept and return JSON-serializable dicts, converting to/from Shapely only internally — makes FastAPI serialization trivial and keeps geometry deps isolated"
  - "recalc_neighbors signature follows the test contract: (condado_id, new_lon, new_lat, territory_data) not the plan's illustrative snippet (seeds, moved_idx, land_mask_polygon)"
  - "orient from shapely.ops not shapely top-level — shapely 2.1.2 exposes orient only via shapely.ops"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-24"
  tasks: 2
  files: 2
---

# Phase 04 Plan 02: Backend Geometry Service Summary

**One-liner:** Pure-Python geometry service (`voronoi.py`) with 6 exported functions — Voronoi adjacency, neighbor-only recalc, merge (unary_union), split (ops.split + Pitfall 4 guard), and decimate (Douglas-Peucker); all 9 Wave-0 tests GREEN.

## What Was Done

Built `backend/medieval_forge/services/voronoi.py` — the central geometry module that every Phase 4 edit API endpoint (Plan 04) will call. All scipy and Shapely dependencies are isolated here; the API layer never imports scipy or Shapely directly.

### Functions Exported

| Function | Purpose | Key Pattern |
|----------|---------|-------------|
| `build_adjacency(points)` | scipy ridge_points → index→neighbors dict | Rebuild from scratch after every merge (Pitfall 3) |
| `find_affected_neighbors(moved_idx, adj)` | {moved} ∪ ridge-neighbors | Used to scope recalc to N+1 seeds only |
| `recalc_neighbors(condado_id, new_lon, new_lat, territory_data)` | Full Voronoi recompute, returns only affected polygons as GeoJSON | 2.7ms on 93-seed Iberia fixture; 500ms budget not approached |
| `merge_territories(geometries, primary_id, condado_ids)` | unary_union with non-adjacent warning | is_valid + buffer(0) repair; orient CCW |
| `split_territory(geometry, cut_line, original_id)` | ops.split with Pitfall 4 pre-validation | pre-val: ≥2 exterior crossings; post-val: ≥2 output polys |
| `decimate_polygon(geometry, target_vertices)` | Douglas-Peucker binary search to ~12 handles | is_valid guard per Shapely issue #2165; returns last valid result |

### Test Results

All 9 Wave-0 voronoi tests turned GREEN:

| Test | Status |
|------|--------|
| `test_build_adjacency_returns_symmetric_neighbor_map` | PASS |
| `test_adjacency_rebuilt_after_merge` | PASS |
| `test_find_affected_neighbors_returns_moved_plus_ridge_neighbors` | PASS |
| `test_recalc_neighbors_returns_updated_geometries_within_500ms` | PASS |
| `test_merge_unary_union_produces_valid_polygon_from_2_adjacent` | PASS |
| `test_merge_non_adjacent_returns_multipolygon_flagged_warning` | PASS |
| `test_split_valid_line_returns_two_polygons` | PASS |
| `test_split_non_bisecting_line_raises_valueerror` | PASS |
| `test_decimate_polygon_returns_at_most_15_vertices` | PASS |

### Performance Measurement

`recalc_neighbors` on Iberia fixture (93 seeds, condado `oviedo`, moved 0.1° east):
- **Elapsed: 2.7ms** — far under the 500ms budget (EDIT-01)
- Affected condados: `['oviedo', 'pravia', 'gijon', 'liebana', 'leon', 'astorga']` (6 of 93)
- Updated territories returned: 5 (1 unbounded cell skipped as expected)

### Decimate Tolerance

The default `tolerance_range=(0.0, 1.0)` with binary search works well for the 50-gon test fixture (geographic-degree scale). For canvas-pixel coordinate systems, callers should pass a narrower range (e.g., `(0.0, 50.0)`). No tuning was required to pass the test.

### Pitfall 4 Validation

`split_territory` raises `ValueError` on:
- 0-crossing input (line entirely outside polygon): "only 0 boundary crossing(s)"
- 1-crossing input (line touching one edge only): "only 1 boundary crossing(s)"
- Post-split: if `ops.split` somehow returns <2 polygons despite crossings

Both pre-validation and post-validation paths are present in the implementation.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 0aad774 | feat | Voronoi adjacency + neighbor-only recalc (Task 1) |
| 1d8f680 | feat | merge_territories + split_territory + decimate_polygon (Task 2) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test fixture access — condados are lists, not dicts**
- **Found during:** Task 1 (first test run)
- **Issue:** `test_recalc_neighbors_returns_updated_geometries_within_500ms` accessed `condados[0]["id"]`, `condados[0]["lon"]`, `condados[0]["lat"]` but `territory_iberia.json` stores condados as lists `[id, name, lon, lat, duchy_id, baronies]`. The Wave 0 RED phase never ran the test against real data (ModuleNotFoundError was the RED signal), so the dict-access bug was latent.
- **Fix:** Changed to index access: `first_condado[0]`, `first_condado[2]`, `first_condado[3]`
- **Files modified:** `backend/tests/services/test_voronoi.py`
- **Commit:** 0aad774

**2. [Rule 1 - Bug] orient import — shapely.ops not shapely top-level**
- **Found during:** Task 1 (import error on first run)
- **Issue:** Plan code snippet specified `from shapely import is_valid, orient, simplify` but Shapely 2.1.2 does not export `orient` at the top-level package. It is in `shapely.ops`.
- **Fix:** Changed import to `from shapely.ops import orient, split, unary_union`
- **Files modified:** `backend/medieval_forge/services/voronoi.py`
- **Commit:** 0aad774

**3. [Discretion] recalc_neighbors API adapted to test contract**
- **Plan snippet:** `recalc_neighbors(seeds, moved_idx, land_mask_polygon)` returning `dict[int, Polygon]`
- **Test contract:** `recalc_neighbors(condado_id, new_lon, new_lat, territory_data)` returning `{"updated_territories": {...}, "affected_ids": [...]}`
- **Decision:** Implemented the test contract. The plan's code snippet was illustrative — the committed Wave 0 tests define the binding API. Internally, the implementation still extracts seeds and moved_idx from territory_data for the scipy call.

## Known Stubs

None. All 6 functions are fully implemented; no placeholder returns or hardcoded data.

## Threat Flags

None. This module introduces no new network endpoints, auth paths, or file access patterns. The threat mitigations from the plan's STRIDE register are all implemented:

| Threat | Status |
|--------|--------|
| T-04-02-01 (DoS — recalc at scale) | Mitigated: perf test passes at 2.7ms; warning logged if >500ms |
| T-04-02-02 (DoS — large polygon merge) | Pre-condition documented; enforcement deferred to api/edit.py (Plan 04) |
| T-04-02-03 (I — split silent failure) | Mitigated: pre + post validation; raises ValueError |
| T-04-02-04 (I — invalid merge geometry) | Mitigated: is_valid + buffer(0) repair; raises ValueError if unrecoverable |
| T-04-02-05 (T — invalid decimate result) | Mitigated: is_valid guard per iteration; falls back to last valid |

## Self-Check: PASSED

Files verified:
- backend/medieval_forge/services/voronoi.py: FOUND (326 lines)
- backend/tests/services/test_voronoi.py: FOUND (modified)

Commits verified:
- 0aad774: FOUND
- 1d8f680: FOUND

Test run: 9 passed in 0.02s
