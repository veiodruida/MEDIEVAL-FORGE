---
phase: quick-260428-elq
plan: 01
type: execute
status: complete
completed: 2026-04-28
tags: [etapa-2, baronies, ingest, kmeans, geojson]
requires: [raw/municipalities.geojson from /ingest]
provides:
  - "POST /api/projects/{id}/baronies?count=all|N"
  - "<project>/raw/baronies.geojson"
  - "build_baronies_from_osm(path, target_count) service function"
  - "frontend buildBaronies(projectId, count) client + BaronyGranularitySlider"
affects: [backend.api.ingest, backend.services, frontend.api, frontend.components]
key-files:
  created:
    - backend/medieval_forge/services/baronies_builder.py
    - backend/tests/services/test_baronies_builder.py
    - backend/tests/api/test_baronies_endpoint.py
    - frontend/src/components/ingest/BaronyGranularitySlider.tsx
  modified:
    - backend/medieval_forge/api/ingest.py
    - frontend/src/api/client.ts
decisions:
  - "scipy.cluster.vq.kmeans2 with seed=42 + np.random.seed(42) for cross-version determinism"
  - "asyncio.to_thread wraps the builder call so scipy/shapely CPU work doesn't block the event loop"
  - "_parse_count is a private helper (not Pydantic) so 422 is raised explicitly with a clear detail message"
  - "When target_count >= len(feats) → fall through to 1:1 mode rather than raise (graceful)"
metrics:
  duration: ~25min
  tasks: 2
  files: 6
  tests_added: 10
---

# Quick Task 260428-elq: Etapa 2 — Baronies Builder Summary

Implemented the Etapa 2 foundation: convert OSM municipality polygons into either 1:1 baronies or N KMeans-clustered baronies, expose a POST endpoint, persist `raw/baronies.geojson`, and ship a frontend granularity selector.

## What Was Built

**Backend service** — `services/baronies_builder.py`
- `build_baronies_from_osm(path, target_count)` reads `raw/municipalities.geojson` and emits a GeoJSON FeatureCollection of baronies.
- `target_count="all"` → 1 município = 1 barony, id `B_{osm_id}`, original geometry preserved.
- `target_count=N` (positive int < len(feats)) → KMeans on representative_point centroids (`scipy.cluster.vq.kmeans2`, seeded), id `B_C{idx:04d}`, geometry = `shapely.ops.unary_union` of cluster members.
- Per-barony properties: `id`, `name`, `centroid: [lon, lat]`, `municipality_ids: list[int]`.

**Backend endpoint** — `api/ingest.py`
- `POST /api/projects/{id}/baronies?count=all|N`
- 400 invalid UUID, 404 project missing, 422 invalid count, 404 if `raw/municipalities.geojson` missing, 200 with `{baronies_count, municipalities_count}`.
- Existing `/ingest` and `/ingest-status` endpoints untouched.
- Builder runs in a worker thread (`asyncio.to_thread`) so CPU-bound scipy/shapely work doesn't block the FastAPI event loop.

**Frontend**
- `api/client.ts`: `buildBaronies(projectId, count: number | 'all')` returning `{ baronies_count, municipalities_count }`.
- `components/ingest/BaronyGranularitySlider.tsx`: 4 preset buttons (50 / 250 / 1000 / Todos) emitting `onChange(BaronyCount)`.

## Tests

10 new tests, all deterministic:

**`tests/services/test_baronies_builder.py` (5)**
- `test_baronies_1_to_1_when_granularity_is_all` — 6 features → 6 baronies, id `B_{osm_id}`, area preserved.
- `test_baronies_clustered_kdtree_when_target_count_specified` — 6 → 3 clusters, total members = 6.
- `test_baronies_preserve_municipality_ids_per_cluster` — no duplication or loss across clusters.
- `test_baronies_centroid_is_average_of_member_municipalities` — 4 squares in 2 well-separated clusters; verifies cluster centroid == mean of member centroids within 1e-6.
- `test_baronies_polygon_is_union_of_member_municipality_polygons` — 2 adjacent unit squares → unioned area == 2.0 within 1e-9.

**`tests/api/test_baronies_endpoint.py` (5)**
- `test_post_baronies_with_all_returns_n_features` — 200 + `baronies_count=6, municipalities_count=6`.
- `test_post_baronies_with_count_returns_n_clusters` — `count=3` → `baronies_count=3`.
- `test_post_baronies_404_when_no_municipalities` — missing geojson → 404 with detail mentioning "municipalities".
- `test_post_baronies_422_when_invalid_count` — `count=foo` → 422.
- `test_post_baronies_writes_raw_baronies_geojson` — verifies the file is written, valid FeatureCollection, expected schema (id, centroid, municipality_ids, Polygon|MultiPolygon).

## Verification

```
$ python -m pytest backend/tests -q -m "not slow"
209 passed, 4 deselected in 3.76s
```

199 baseline + 10 new = 209 fast tests passing. Frontend `tsc --noEmit` clean.

## Commits

| # | Hash      | Description |
|---|-----------|-------------|
| 1 | `e8690e4` | `feat(quick-260428-elq-01): baronies_builder service + 5 unit tests` |
| 2 | `e807714` | `feat(quick-260428-elq-02): POST /baronies endpoint + frontend slider + 5 endpoint tests` |

## Deviations from Plan

None. Plan executed exactly as written. Forbidden files (`map_generator.py`, `research_runner.py`) untouched. Existing `/ingest` endpoint untouched.

## Self-Check: PASSED

- [x] `backend/medieval_forge/services/baronies_builder.py` exists with `build_baronies_from_osm`
- [x] `backend/tests/services/test_baronies_builder.py` exists with 5 tests, all passing
- [x] `backend/tests/api/test_baronies_endpoint.py` exists with 5 tests, all passing
- [x] `backend/medieval_forge/api/ingest.py` exposes `POST /{project_id}/baronies`
- [x] `frontend/src/api/client.ts` exports `buildBaronies`
- [x] `frontend/src/components/ingest/BaronyGranularitySlider.tsx` renders 50/250/1000/Todos presets
- [x] Commit `e8690e4` exists in git log
- [x] Commit `e807714` exists in git log
- [x] Full backend suite: 209 passed, 4 deselected
