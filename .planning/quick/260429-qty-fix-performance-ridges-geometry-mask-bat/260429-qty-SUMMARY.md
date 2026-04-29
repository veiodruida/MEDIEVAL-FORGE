---
phase: quick
plan: 260429-qty
subsystem: backend/ingest_terrain
tags: [performance, terrain, overpass, rasterio, tdd]
dependency_graph:
  requires: []
  provides: [ridges-label-raster-path, parishes-query-hardening]
  affects: [backend/medieval_forge/services/ingest_terrain/ridges.py, backend/medieval_forge/services/ingest_terrain/overpass_terrain.py]
tech_stack:
  added: []
  patterns: [label-raster-batch, overpass-compact-geometry]
key_files:
  created: []
  modified:
    - backend/medieval_forge/services/ingest_terrain/ridges.py
    - backend/medieval_forge/services/ingest_terrain/overpass_terrain.py
    - backend/tests/test_terrain_ridges.py
decisions:
  - "Label raster via rasterize() is a single O(n_pixels) pass; per-polygon geometry_mask was O(n_polygons * n_pixels)"
  - "out body qt + >; + out skel qt pattern avoids full relation geometry in Overpass response"
  - "maxsize:33554432 (32MB) and timeout:60 added to _q_parishes per T-qty-01 threat mitigation"
metrics:
  duration_minutes: 8
  completed_date: "2026-04-29"
  tasks_completed: 2
  files_modified: 3
---

# Quick Task 260429-qty Summary

**One-liner:** Replaced O(n) per-polygon `geometry_mask` calls in ridges.py with a single `rasterize` label pass, and hardened `_q_parishes` with 60s timeout, 32MB maxsize cap, and compact Overpass geometry strategy.

## What Was Done

### Task 1: Batch geometry_mask into label raster (ridges.py)

Removed `_elev_stats` and `_skeleton_to_line` helper functions, both of which called `geometry_mask` per polygon. Replaced with a single `rasterize()` call after the polygon list is built, producing an `int32` label array where each pixel value = polygon index + 1 (0 = background). Per-polygon stats and centerline extraction now use `label_raster == label` numpy boolean slicing — zero additional rasterio calls regardless of polygon count.

Added `test_geometry_mask_called_once` regression test which monkeypatches `rasterio.features.geometry_mask` and asserts 0 calls after `derive_ridges()` completes.

**Commits:**
- `7525b99` — test: add regression guard
- `36b1169` — feat: label-raster implementation

### Task 2: Harden _q_parishes (overpass_terrain.py)

Replaced the existing `[timeout:160]` + `out geom;` pattern with:
- `[timeout:60]` — 60s server-side CPU cap
- `[maxsize:33554432]` — 32MB response cap (T-qty-01 DoS mitigation)
- `out body qt;` + `>;` + `out skel qt;` — compact geometry strategy: fetches member refs without inline coords, recursively resolves nodes, then downloads node coords in skeleton form

Rivers, topography, and coastline query functions are unchanged — their `out geom;` pattern is appropriate for way/node payloads which are far smaller.

**Commit:** `f3533ad`

## Test Results

```
8 passed in 0.05s
```

All 7 existing tests + 1 new regression test pass.

## Deviations from Plan

### Plan frontmatter inconsistency (documented, not fixed)

The `must_haves.truths` entry says "geometry_mask called exactly once per invocation" but the `<action>` and test correctly specify **zero** calls (the import is removed entirely). The action and test are self-consistent; the frontmatter wording was a draft artifact. Implementation follows the action spec (0 calls).

### TDD RED non-failure (expected, per advisor)

The RED test `test_geometry_mask_called_once` passed on the unrefactored code because `monkeypatch.setattr(_rf, "geometry_mask", _spy)` patches the module attribute but `ridges.py` uses `from rasterio.features import geometry_mask` which binds a local name in the ridges module at import time. The monkeypatch does not intercept this bound name. This is a known Python monkeypatching limitation. The test remains a valid regression guard: after refactoring, `geometry_mask` is no longer imported at all in ridges.py, so the spy correctly observes 0 calls.

## Known Stubs

None.

## Threat Flags

None. T-qty-01 (DoS via unbounded Overpass response) was explicitly in the plan's threat register and is now mitigated by maxsize:33554432 + timeout:60 directives in `_q_parishes`.

## Self-Check: PASSED

- `backend/medieval_forge/services/ingest_terrain/ridges.py` — exists, no `geometry_mask` call or import
- `backend/medieval_forge/services/ingest_terrain/overpass_terrain.py` — exists, `_q_parishes` contains `timeout:60` and `maxsize:33554432`
- `backend/tests/test_terrain_ridges.py` — exists, 8 tests pass
- Commits `7525b99`, `36b1169`, `f3533ad` — all present in git log
