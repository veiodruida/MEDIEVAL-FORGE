---
phase: quick
plan: 260429-qty
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/ingest_terrain/ridges.py
  - backend/medieval_forge/services/ingest_terrain/overpass_terrain.py
  - backend/tests/test_terrain_ridges.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "ridges.py calls geometry_mask exactly once per derive_ridges() invocation (label raster path), not once per polygon"
    - "_q_parishes returns a query with timeout:60 and maxsize:33554432 guards"
    - "all existing ridge tests still pass after the refactor"
  artifacts:
    - path: "backend/medieval_forge/services/ingest_terrain/ridges.py"
      provides: "label-raster batch path replacing per-polygon geometry_mask calls"
    - path: "backend/medieval_forge/services/ingest_terrain/overpass_terrain.py"
      provides: "_q_parishes with 60s timeout, 32MB maxsize, compact out body qt + skel qt"
    - path: "backend/tests/test_terrain_ridges.py"
      provides: "regression test asserting geometry_mask call count == 1 per invocation"
  key_links:
    - from: "backend/medieval_forge/services/ingest_terrain/ridges.py"
      to: "rasterio.features.rasterize"
      via: "label_raster = rasterize([(poly, i+1) for i, poly in enumerate(polys)], ...)"
      pattern: "rasterize"
    - from: "backend/medieval_forge/services/ingest_terrain/overpass_terrain.py"
      to: "_q_parishes"
      via: "timeout:60 and maxsize:33554432 directives in query string"
      pattern: "maxsize:33554432"
---

<objective>
Fix two performance bottlenecks introduced in Phase 02.1 terrain ingestion:

1. ridges.py calls `geometry_mask` once per polygon in both `_elev_stats` and `_skeleton_to_line`.
   For Spain-scale DEMs with hundreds of polygons, this is O(n_polygons * n_pixels) — extremely slow.
   Fix: replace with a single `rasterio.features.rasterize` label pass, then slice per label with numpy masks.

2. overpass_terrain.py `_q_parishes` downloads full relation geometry via `out geom;`.
   For a large bbox (Spain) this can return tens of MB and run for minutes.
   Fix: switch to `out body qt; >; out skel qt;` compact geometry strategy, cap server-side
   timeout at 60s, and add `[maxsize:33554432]` (32MB) to abort runaway responses.

Purpose: Make terrain ingestion viable for real country-scale DEMs without multi-minute hangs.
Output: Two modified service files + one new regression test in test_terrain_ridges.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/PROJECT.md
backend/medieval_forge/services/ingest_terrain/ridges.py
backend/medieval_forge/services/ingest_terrain/overpass_terrain.py
backend/tests/test_terrain_ridges.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Batch geometry_mask into a single label raster in ridges.py</name>
  <files>
    backend/medieval_forge/services/ingest_terrain/ridges.py
    backend/tests/test_terrain_ridges.py
  </files>
  <behavior>
    - geometry_mask is called exactly 1 time total per derive_ridges() call (not N times per polygon)
    - _elev_stats and _skeleton_to_line are removed or replaced by label-based helpers
    - elev stats (min/max/mean) for each polygon are identical to the old per-polygon results
    - centerline pixels for each polygon are identical to the old per-polygon skeleton mask results
    - all 7 existing tests in test_terrain_ridges.py continue to pass without modification
    - new test: test_geometry_mask_called_once asserts mock call count == 1
  </behavior>
  <action>
Add `from rasterio.features import rasterize` to imports in ridges.py (it is already imported
from rasterio.features but only `shapes` and `geometry_mask` — add `rasterize`).

After the polygon list `polys` is built (step 7), produce the label raster in one shot:

```python
height, width = z.shape
# Label raster: pixel value = polygon index+1 (0 = background)
label_raster = np.zeros((height, width), dtype=np.int32)
if polys:
    shapes_with_labels = [(poly.__geo_interface__, i + 1) for i, poly in enumerate(polys)]
    label_raster = rasterize(
        shapes_with_labels,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.int32,
    )
```

Remove the `_elev_stats` and `_skeleton_to_line` functions entirely. Replace per-polygon calls
in the build-features loop with label-based numpy slicing:

```python
for i, poly in enumerate(polys):
    label = i + 1
    pix_mask = label_raster == label          # boolean mask for this polygon

    # Elevation stats
    sample = z[pix_mask & (z != nodata)]
    if sample.size == 0:
        elev_min, elev_max, elev_mean = 0.0, 0.0, 0.0
    else:
        elev_min, elev_max, elev_mean = float(sample.min()), float(sample.max()), float(sample.mean())

    # Centerline from skeleton pixels inside this polygon's label mask
    ys, xs = np.where(skeleton & pix_mask)
    if len(xs) < 2:
        cx, cy = poly.centroid.x, poly.centroid.y
        centerline = LineString([(cx, cy), (cx + 1e-6, cy + 1e-6)])
    else:
        coords = [transform * (int(c), int(r)) for r, c in zip(ys, xs)]
        centerline = LineString(coords)
    ...
```

Also remove `geometry_mask` from the rasterio.features import line (it is no longer used).

Write the test in test_terrain_ridges.py:

```python
def test_geometry_mask_called_once(monkeypatch):
    """geometry_mask must not be called during derive_ridges (label-raster path)."""
    import rasterio.features as _rf
    calls = []
    original = _rf.geometry_mask
    def _spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(_rf, "geometry_mask", _spy)
    derive_ridges(SYNTHETIC_DEM, sensitivity="med")
    assert calls == [], f"geometry_mask was called {len(calls)} time(s); expected 0"
```

Note: the spy checks for 0 calls because the new code path uses `rasterize` + numpy masks
and no longer imports or calls `geometry_mask` at all.
  </action>
  <verify>
    <automated>cd C:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE && python -m pytest backend/tests/test_terrain_ridges.py -v 2>&1 | tail -20</automated>
  </verify>
  <done>
    All 8 tests pass (7 existing + 1 new geometry_mask call-count test).
    `geometry_mask` import removed from ridges.py.
    `rasterize` import added and used for the label raster.
  </done>
</task>

<task type="auto">
  <name>Task 2: Harden _q_parishes with timeout, maxsize, compact geometry</name>
  <files>
    backend/medieval_forge/services/ingest_terrain/overpass_terrain.py
  </files>
  <action>
Replace `_q_parishes` in overpass_terrain.py. The new query must:

1. Use `[out:json][timeout:60][maxsize:33554432]` as the global header (60s server-side
   timeout; 32MB response cap — consistent with safe Overpass practice).
2. Use `out body qt;` + `>;` + `out skel qt;` instead of `out geom;`.
   `out body qt;` fetches the relation metadata + member refs (no coords).
   `>;` recursively resolves all referenced nodes/ways.
   `out skel qt;` downloads the node coordinates in skeleton (compact) form.
   This is the standard Overpass compact-geometry pattern for relations.

```python
def _q_parishes(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> str:
    return (
        "[out:json][timeout:60][maxsize:33554432];\n"
        "(\n"
        f'  relation["boundary"="administrative"]["admin_level"="8"]'
        f'({lat_min},{lon_min},{lat_max},{lon_max});\n'
        ");\nout body qt;\n>;\nout skel qt;\n"
    )
```

Verify `_relation_to_geojson_feature` (imported from ingest_osm) is compatible: it already
processes `members` arrays with way/node refs, so the compact geometry response (which returns
nodes separately in the same payload) is handled by the existing Overpass client's element
processing. No change to `_relation_to_geojson_feature` is required.

Leave all other query functions (`_q_rivers`, `_q_topography`, `_q_coastline`) unchanged.
Their `out geom;` pattern is appropriate for ways/nodes which are far smaller payloads.
  </action>
  <verify>
    <automated>cd C:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE && python -c "
from medieval_forge.services.ingest_terrain.overpass_terrain import _q_parishes
q = _q_parishes(-9.5, 36.0, -6.0, 42.3)
assert 'timeout:60' in q, 'missing timeout:60'
assert 'maxsize:33554432' in q, 'missing maxsize:33554432'
assert 'out body qt' in q, 'missing out body qt'
assert 'out skel qt' in q, 'missing out skel qt'
assert 'out geom' not in q, 'out geom should be removed'
print('OK:', repr(q[:120]))
"</automated>
  </verify>
  <done>
    _q_parishes produces a query string containing:
    - [timeout:60] and [maxsize:33554432] in the header
    - `out body qt;` and `out skel qt;` replacing `out geom;`
    No other query functions are modified.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Overpass API response | External service response size and timing — capped by new maxsize/timeout directives |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qty-01 | Denial of Service | _q_parishes | mitigate | maxsize:33554432 caps response at 32MB; timeout:60 caps server CPU at 60s — both directives abort the query before an oversized response reaches the client |
| T-qty-02 | Denial of Service | derive_ridges label raster | accept | rasterize still allocates an int32 array of DEM dimensions; unchanged from old code's implicit mask allocations; acceptable for local tool |
</threat_model>

<verification>
Run full terrain test suite:

```bash
cd C:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE
python -m pytest backend/tests/test_terrain_ridges.py -v
```

Expected: 8 tests pass (7 existing + 1 new `test_geometry_mask_called_once`).

Spot-check query strings:

```bash
python -c "
from medieval_forge.services.ingest_terrain.overpass_terrain import _q_parishes, _q_rivers
print('=== parishes ===')
print(_q_parishes(-9.5, 36.0, -6.0, 42.3))
print('=== rivers (unchanged) ===')
print(_q_rivers(-9.5, 36.0, -6.0, 42.3))
"
```

Confirm parishes query has `timeout:60`, `maxsize:33554432`, `out body qt`, `out skel qt`.
Confirm rivers query still has `timeout:160` and `out geom` (unchanged).
</verification>

<success_criteria>
- derive_ridges() no longer calls geometry_mask at all (rasterize label path used instead)
- _q_parishes query string contains [timeout:60][maxsize:33554432] and uses compact out body qt / out skel qt pattern
- All 8 tests in test_terrain_ridges.py pass
- No other test files are broken
</success_criteria>

<output>
After completion, create `.planning/quick/260429-qty-fix-performance-ridges-geometry-mask-bat/260429-qty-SUMMARY.md`
</output>
