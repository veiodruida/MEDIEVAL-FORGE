---
phase: quick-260426-qlo
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/voronoi.py
  - backend/medieval_forge/api/edit.py
  - backend/tests/services/test_voronoi.py
autonomous: true
requirements:
  - QLO-01
must_haves:
  truths:
    - "After move_capital, no returned polygon contains coordinates outside the project's land area (clipped to land mask when available, to bbox otherwise)."
    - "Previously-unbounded Voronoi cells (edge seeds) now produce a valid clipped polygon instead of being silently dropped."
    - "When neither land mask nor bbox is provided (e.g. unit-test direct calls), recalc_neighbors keeps the existing unbounded-cell-skip behavior — backwards-compatible for the existing test suite."
  artifacts:
    - path: "backend/medieval_forge/services/voronoi.py"
      provides: "recalc_neighbors with optional land_mask + bbox clip; _load_land_mask_for_project helper."
      contains: "def recalc_neighbors"
    - path: "backend/medieval_forge/api/edit.py"
      provides: "move_capital wires land mask + bbox from project's generated/ directory into recalc_neighbors."
      contains: "_load_land_mask_for_project"
    - path: "backend/tests/services/test_voronoi.py"
      provides: "Regression test: coastal-capital recalc returns polygon contained in land mask."
      contains: "def test_recalc_neighbors_clips_to_land_mask"
  key_links:
    - from: "backend/medieval_forge/api/edit.py::move_capital"
      to: "backend/medieval_forge/services/voronoi.py::recalc_neighbors"
      via: "land_mask + bbox kwargs derived from generated/lookup_condado.png + territory_metadata.json bounds"
      pattern: "recalc_neighbors\\([^)]*land_mask"
---

<objective>
Fix orphan bug #3 from `.planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md` (line 177): `recalc_neighbors` does not clip Voronoi cells to the land mask after a capital move, so cells can extend into the ocean and previously-unbounded cells get silently dropped.

Purpose: After a capital drag, the resulting polygons must stay inside the project's land area (matches generation-time behavior).
Output: `recalc_neighbors` accepts optional `land_mask` (Shapely geometry in lon/lat) and `bbox` parameters; `move_capital` derives both from the project's existing artifacts (`generated/lookup_condado.png` + `generated/territory_metadata.json`) and passes them in. Regression test guards the behavior.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@backend/medieval_forge/services/voronoi.py
@backend/medieval_forge/api/edit.py
@backend/medieval_forge/services/territories_geojson.py
@backend/medieval_forge/lib/map_generator.py
@backend/tests/services/test_voronoi.py

<interfaces>
<!-- Existing contracts the executor must preserve. -->

From backend/medieval_forge/services/voronoi.py:
```python
def recalc_neighbors(
    condado_id: str,
    new_lon: float,
    new_lat: float,
    territory_data: dict,
) -> dict[str, Any]:
    # returns {"updated_territories": {id: geojson_polygon}, "affected_ids": [str, ...]}
```
The signature is extended with two NEW optional kwargs (default None — preserves current
test-suite behavior):
  - `land_mask: shapely.geometry.base.BaseGeometry | None = None`  # in lon/lat
  - `bbox: tuple[float, float, float, float] | None = None`        # (lon_min, lat_min, lon_max, lat_max)

From backend/medieval_forge/api/edit.py::move_capital — already calls
`voro_svc.recalc_neighbors(condado_id, body.lon, body.lat, territory_data)`.
Add land_mask + bbox kwargs sourced from a project loader.

From backend/medieval_forge/services/territories_geojson.py — `_pixel_polygon_to_lonlat`
already implements the px → lon/lat inversion using `_ProjCfg`. Reuse the same math
for the land-mask polygonization (do NOT reinvent the projection).

From backend/medieval_forge/lib/map_generator.py::export_metadata — `territory_metadata.json`
contains `bounds: {lon_min, lon_max, lat_min, lat_max}` and `map_size: [W*upscale, H*upscale]`.
The lookup raster (`lookup_condado.png`) is at `map_w × map_h` (NOT upscaled).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend recalc_neighbors with optional land_mask + bbox clipping</name>
  <files>backend/medieval_forge/services/voronoi.py, backend/tests/services/test_voronoi.py</files>
  <behavior>
    - Test A (`test_recalc_neighbors_no_clip_backwards_compat`): calling recalc_neighbors WITHOUT land_mask/bbox on the existing TRIANGLE_SEEDS / Iberia fixtures returns the same shape it does today (no regressions in the existing test suite).
    - Test B (`test_recalc_neighbors_clips_to_bbox`): construct 4 seeds inside a small bbox (e.g. (0,0)-(10,10)), pass `bbox=(0,0,10,10)`. Every returned polygon's exterior coords lie within [0,10] × [0,10]. Cells that would be unbounded WITHOUT a bbox are now bounded and present in `updated_territories`.
    - Test C (`test_recalc_neighbors_clips_to_land_mask`): land_mask = Shapely Polygon shaped like the left half of the bbox (a coastline at x=5). Move a seed near x=4.5. The returned polygon for that seed has every coord with x <= 5 + 1e-6 (entirely within the land mask). `shapely.contains(land_mask.buffer(1e-6), returned_poly)` is True.
    - Test D (`test_recalc_neighbors_drops_cells_fully_outside_land_mask`): if a Voronoi cell ends up entirely outside the land mask after clipping (empty intersection), the cell is omitted from `updated_territories` and its id is omitted from `affected_ids` (no zero-area / empty geometries returned).
  </behavior>
  <action>
    Modify `recalc_neighbors` in `backend/medieval_forge/services/voronoi.py`:

    1. Extend signature:
       ```python
       def recalc_neighbors(
           condado_id, new_lon, new_lat, territory_data,
           *,
           land_mask=None,   # shapely BaseGeometry in lon/lat, or None
           bbox=None,        # (lon_min, lat_min, lon_max, lat_max), or None
       ) -> dict[str, Any]:
       ```

    2. Build a single `clip_geom` (Shapely Polygon/MultiPolygon) once, before the cell loop:
       - If `land_mask is not None` → `clip_geom = land_mask`.
       - Elif `bbox is not None` → `clip_geom = shapely.geometry.box(lon_min, lat_min, lon_max, lat_max)`.
       - Else → `clip_geom = None` (legacy behavior — preserves existing test pass).

    3. For unbounded cells (the existing `if not region or -1 in region: continue` branch):
       - If `clip_geom is not None`: reconstruct the unbounded cell using a far-bbox extension — the simplest robust approach is to compute a bounding box much larger than `clip_geom.bounds` (e.g. 10× the diagonal), then build the unbounded ridge by extending the finite ridges along the Voronoi `furthest_site=False` ridge_vertices/ridge_points pair direction. Reuse the standard scipy idiom (see scipy docs `voronoi_plot_2d` source) — reference implementation: for each `-1` vertex, compute the ridge midpoint and a perpendicular direction, extend by `radius`. Then clip with `clip_geom`.
       - If `clip_geom is None`: keep existing `continue` (skip).

    4. For bounded cells: build the polygon as today, then if `clip_geom is not None`, replace `poly` with `poly.intersection(clip_geom)`.

    5. After clipping, defensively normalize:
       - If the result is `GeometryCollection` or `MultiPolygon`, keep the largest `Polygon` by area (consistent with single-cell semantics).
       - If the result is empty (`is_empty`), skip the cell entirely (do NOT add to `updated_territories`, do NOT add to `affected_ids`).
       - Re-run `is_valid` / `buffer(0)` repair and `orient(sign=1.0)` on the final polygon.

    6. Update the docstring to document `land_mask` / `bbox` and to note that clipping is now applied when either is supplied.

    Also, IN THE SAME FILE, add a small public helper that the API layer will use:

    ```python
    def load_land_mask_and_bbox(generated_dir: pathlib.Path) -> tuple[BaseGeometry | None, tuple[float, float, float, float] | None]:
        """Return (land_mask_geom, bbox_tuple) derived from a project's generated/ dir.

        Land mask is built from lookup_condado.png by rasterio.features.shapes(mask=pc>=0)
        + unary_union, then projected pixel→lon/lat using the same inversion as
        territories_geojson._pixel_polygon_to_lonlat (DRY: import the helper).
        bbox comes from territory_metadata.json `bounds`.
        Returns (None, None) gracefully if files are missing.
        """
    ```
    Implementation:
    - Read `territory_metadata.json` → `bounds` → bbox tuple.
    - Open `lookup_condado.png` with PIL → numpy. Reuse the same color-table → index logic
      already implemented in `services/territories_geojson.emit_territories_from_disk`,
      OR (simpler since we only need a binary mask): the land mask = any pixel that is
      NOT pure black `(0,0,0)`. Confirm by inspection of map_generator output —
      `generate_lookup_map` only writes background as black. Use the simple binary mask:
      `mask = (img.sum(axis=-1) > 0)`.
    - `rasterio.features.shapes(mask.astype(np.uint8), mask=mask)` → unary_union of polygons.
    - Project pixel coords to lon/lat by reusing `_pixel_polygon_to_lonlat` from
      `services.territories_geojson` (build a `_ProjCfg` from the metadata bounds +
      raster size; `upscale=1`, `lon_scale = cos(mid_lat)` matching map_generator).
    - Return `(land_mask_geom, bbox)`. On any FileNotFoundError / KeyError / ValueError
      log a warning and return `(None, bbox_or_None)` so the caller still gets bbox if
      possible.

    IMPORTANT: do NOT invent a new projection. Reuse `_pixel_polygon_to_lonlat`. If that
    helper is module-private (leading underscore), promote it to public (rename to
    `pixel_polygon_to_lonlat`) and update the in-file callers (territories_geojson uses
    it once, both call-sites are local).

    THEN add the four tests described in <behavior> to `backend/tests/services/test_voronoi.py`.
    Use simple shapely geometries built inline (no fixture files required for tests B/C/D).
    Test A is satisfied by the existing tests continuing to pass — re-run the full
    `test_voronoi.py` module to confirm.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; python -m pytest tests/services/test_voronoi.py -x -q</automated>
  </verify>
  <done>
    All four new tests pass; all pre-existing tests in test_voronoi.py still pass; recalc_neighbors signature documents land_mask + bbox; load_land_mask_and_bbox helper is exported from services/voronoi.py.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire land mask + bbox into move_capital endpoint</name>
  <files>backend/medieval_forge/api/edit.py, backend/tests/api/test_edit_api.py</files>
  <behavior>
    - Test (`test_move_capital_clips_returned_polygons_to_bbox`): given a fixture project on disk with a known `territory_metadata.json` containing `bounds`, after POST to `/projects/{id}/territories/{cid}/recalc` with new lon/lat near the bbox edge, every returned polygon's exterior coordinates lie within the bounds (lon ∈ [lon_min, lon_max], lat ∈ [lat_min, lat_max]). Use existing test fixtures if they already provide `territory_metadata.json`; otherwise create a minimal one in a tmp project dir.
    - The existing `test_edit_api.py` tests (move_capital persistence, 404 on missing condado, etc.) MUST continue to pass — the change is additive.
  </behavior>
  <action>
    In `backend/medieval_forge/api/edit.py::move_capital`:

    1. After computing `territory_data` (line ~80) and BEFORE `voro_svc.recalc_neighbors(...)`, call:
       ```python
       from ..services.paths import project_dir
       try:
           generated_dir = project_dir(project_id) / "generated"
           land_mask, bbox = voro_svc.load_land_mask_and_bbox(generated_dir)
       except ValueError:
           # Non-UUID project_id (test path) — no clipping
           land_mask, bbox = None, None
       ```

    2. Pass them through:
       ```python
       result = voro_svc.recalc_neighbors(
           condado_id, body.lon, body.lat, territory_data,
           land_mask=land_mask,
           bbox=bbox,
       )
       ```

    3. Add a one-line log at INFO level when neither was found, e.g.
       `logger.info("move_capital: no land_mask/bbox for project=%s — recalc unclipped", project_id)`,
       so observability matches the new code path.

    Add the regression test in `backend/tests/api/test_edit_api.py`. Pattern after the
    existing move_capital test — use the same project-dir fixture / tmp_path setup and
    assert: for every polygon in `response.json()["updated_territories"].values()`, walk
    coordinates and assert each lon/lat is within bounds. This confirms the wiring works
    end-to-end (load helper → service → response).

    Do NOT change the response schema. Do NOT change persistence logic. Do NOT change
    the API contract. Only the geometry values change.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; python -m pytest tests/api/test_edit_api.py tests/services/test_voronoi.py -x -q</automated>
  </verify>
  <done>
    New endpoint test passes; all existing edit_api tests still pass; manual UAT verifiable: drag a coastal capital → returned polygon does not extend into the ocean. Frontend rebuild not required for this fix (geometry comes back via existing PATCH/recalc response).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Frontend → /territories/{cid}/recalc | New lon/lat from the canvas drag |
| Disk → load_land_mask_and_bbox | Reads lookup_condado.png + territory_metadata.json from project dir |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qlo-01 | Tampering | territory_metadata.json `bounds` field | accept | File is project-local, written by trusted generator. If `bounds` is missing/malformed, helper returns `(None, None)` → recalc falls back to legacy unclipped path (no crash, observable via log). |
| T-qlo-02 | DoS | load_land_mask_and_bbox polygonization | mitigate | rasterio.features.shapes runs once per move_capital call; on the ~1920×1080 lookup raster it is O(pixels) but bounded. If perf issue surfaces, add per-project in-memory LRU cache keyed by file mtime (out of scope for this fix). |
| T-qlo-03 | Information disclosure | project_dir traversal | mitigate | Reuses existing `paths.project_dir()` which validates UUID — already enforced T-PATH constraint. No new path inputs. |
</threat_model>

<verification>
- `cd backend && python -m pytest tests/services/test_voronoi.py tests/api/test_edit_api.py -x -q` passes (all old + 5 new tests).
- Spot-check via running app: drag the capital of a coastal condado (e.g. one of the Galician ones near the Atlantic) right up to the coastline → reload territories.geojson → polygon is contained within prior land outline. (Optional manual UAT — automated tests are the source of truth.)
</verification>

<success_criteria>
- `recalc_neighbors` accepts `land_mask` + `bbox` and clips when supplied; behavior unchanged when neither is supplied.
- Previously-unbounded Voronoi cells now produce a valid clipped polygon when `land_mask` or `bbox` is supplied.
- `move_capital` endpoint loads both from the project's `generated/` artifacts and passes them through.
- Regression test asserts no returned polygon coord exceeds the bbox after a coastal-capital recalc.
- Existing test suite (test_voronoi.py + test_edit_api.py) still passes — no contract or persistence changes.
</success_criteria>

<output>
Quick task — append to `.planning/STATE.md` Quick Tasks Completed table after merge:

| 260426-qlo | Fix orphan bug: recalc_neighbors clips Voronoi cells to land mask (or bbox fallback) after capital move | 2026-04-26 | {commit} | [260426-qlo-fix-orphan-bug-recalc-neighbors-does-not](./quick/260426-qlo-fix-orphan-bug-recalc-neighbors-does-not/) |
</output>
