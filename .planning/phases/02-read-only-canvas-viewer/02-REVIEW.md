---
phase: 02-read-only-canvas-viewer
reviewed: 2026-04-18T00:00:00Z
depth: standard
files_reviewed: 49
files_reviewed_list:
  - .gitignore
  - backend/medieval_forge/services/baronies_geojson.py
  - backend/medieval_forge/services/generator.py
  - backend/medieval_forge/services/territories_geojson.py
  - backend/tests/test_baronies_geojson.py
  - backend/tests/test_territories_geojson.py
  - frontend/e2e/perf-panzoom.spec.ts
  - frontend/e2e/smoke-tailwind-radix.spec.ts
  - frontend/package.json
  - frontend/playwright.config.ts
  - frontend/src/App.tsx
  - frontend/src/components/canvas/BackgroundLayer.tsx
  - frontend/src/components/canvas/BaronyLayer.tsx
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/DecorationsLayer.tsx
  - frontend/src/components/canvas/FitToViewButton.tsx
  - frontend/src/components/canvas/InspectorSidebar.tsx
  - frontend/src/components/canvas/InteractionLayer.tsx
  - frontend/src/components/canvas/LayerTogglePanel.tsx
  - frontend/src/components/canvas/TerritoryLayer.tsx
  - frontend/src/components/canvas/TerritoryPolygon.tsx
  - frontend/src/components/canvas/__smoke__/CanvasRadixOverlaySmoke.tsx
  - frontend/src/components/canvas/__tests__/BaronyLayer.test.tsx
  - frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx
  - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
  - frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx
  - frontend/src/components/canvas/__tests__/FitToViewButton.test.tsx
  - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
  - frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx
  - frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx
  - frontend/src/components/canvas/__tests__/selection.test.tsx
  - frontend/src/context/ProjectionContext.tsx
  - frontend/src/hooks/useCanvasArtifacts.ts
  - frontend/src/hooks/useKeyboardShortcuts.test.ts
  - frontend/src/hooks/useKeyboardShortcuts.ts
  - frontend/src/hooks/useZoomPan.test.ts
  - frontend/src/hooks/useZoomPan.ts
  - frontend/src/lib/projection.test.ts
  - frontend/src/lib/projection.ts
  - frontend/src/pages/ProjectDetail.tsx
  - frontend/src/stores/uiStore.test.ts
  - frontend/src/stores/uiStore.ts
  - frontend/src/test-setup.ts
  - frontend/src/vite-env.d.ts
  - frontend/vitest.config.ts
  - pyproject.toml
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-18
**Depth:** standard
**Files Reviewed:** 49
**Status:** issues_found

## Summary

The Phase 2 read-only canvas viewer implementation is solid overall: the projection math is well-tested (1000-point round-trip at 1e-9 precision), the Konva layer composition matches the plan's z-order contract, state management is narrow and correctly scoped, and there is extensive unit-test coverage for every component and hook. No critical issues were found — no injection, no hardcoded secrets, no auth bypass, no data-loss paths. Project-id path traversal is guarded at `paths.project_dir`, and all fetch failures have explicit handling.

The issues below are all non-blocking for Phase 2 acceptance but should be addressed before the canvas moves into Phase 3 (edit mode), where concurrency and edge-case geometry will matter more.

Noteworthy risks:

1. A concurrency race in `generator._patch_reload_for_synthetic` (it mutates global `importlib.reload`), which is safe only under the assumption that at most one generation runs at a time.
2. An unreachable-looking fallback branch in `generator._build_region_config`: when `_compute_padded_bbox` returns `{}` (no territory data), the caller's explicit bbox is silently dropped even though the docstring and inline comments promise the opposite.
3. A duplicated definition of `_cleanup_territory_module` in `generator.py` — harmless (second definition wins) but a merge-smell worth removing.
4. `firstOuterRing` in `useCanvasArtifacts` silently discards all but the first polygon of a MultiPolygon; islands and exclaves will render partial until polygonized.
5. A version-floor inconsistency in `pyproject.toml`: `rasterio>=1.4,<2.0` admits 1.5+, which per project CLAUDE.md requires Python 3.12+ but `requires-python` is `>=3.11`.

## Warnings

### WR-01: Duplicated function definition `_cleanup_territory_module`

**File:** `backend/medieval_forge/services/generator.py:81` and `backend/medieval_forge/services/generator.py:116`
**Issue:** `_cleanup_territory_module` is defined twice with identical bodies. The second definition silently shadows the first. This is dead code and a code-smell that often indicates a bad merge or incomplete refactor. Python does not warn about rebinding module-level names, so this will not surface until it diverges.
**Fix:**
```python
# Delete the duplicate at lines 116-117:
#   def _cleanup_territory_module(name: str) -> None:
#       sys.modules.pop(name, None)
# Keep only the original definition at line 81.
```

### WR-02: `_patch_reload_for_synthetic` mutates global `importlib.reload` — race risk under concurrent generations

**File:** `backend/medieval_forge/services/generator.py:98-113`
**Issue:** The context manager patches `importlib.reload` on the global `importlib` module (`_importlib_mod.reload = _safe_reload`), then restores the original on exit. Because `run_generation` dispatches via `asyncio.to_thread`, two generation calls overlapping in the same process would race the patch/restore: the inner thread restores the real `reload` before the outer thread finishes, and any `importlib.reload(...)` call from user code (or a background reload from some other library) in that window would see the wrong value. The patch is also non-atomic — if the thread is cancelled between `_importlib_mod.reload = _safe_reload` and the `try`, restoration never happens.
**Fix:** Either (a) serialize with a module-level `threading.Lock` around the patched window, or (b) patch locally — assign to `map_generator.importlib.reload` so the scope is the vendored module's namespace rather than the global `importlib`:
```python
# Option (b) — narrower scope, no lock required:
_real_reload = map_generator.importlib.reload
map_generator.importlib.reload = _safe_reload
try:
    yield
finally:
    map_generator.importlib.reload = _real_reload
```
Combine with a per-project lock in the API layer if concurrent generations are ever allowed.

### WR-03: `_build_region_config` silently drops caller's bbox when no territory data

**File:** `backend/medieval_forge/services/generator.py:213-220`
**Issue:** When `_compute_padded_bbox` returns `{}` (the branch at line 174, reached when `territory_data` has no centroids), `kwargs.update(padded)` is a no-op. The subsequent loop at line 218 applies every valid RegionConfig field from `config` *except* `lon_min/lon_max/lat_min/lat_max` — they're in `_bbox_keys`. Result: an explicit caller-supplied bbox in the "no territory data" path is silently discarded, contradicting the inline comment at line 172–173 ("No territory data — fall back to caller-supplied values") and the docstring at 194–197 which promises caller values are respected as a minimum envelope. In practice `_run_pipeline_sync` requires a non-empty `territory_data` (ValueError at line 302–305), so this branch may not be reachable today — but the contradiction is a latent bug if `_build_region_config` is ever called from a new entry point.
**Fix:** In the empty-padded case, explicitly apply the caller's bbox keys:
```python
if not padded:
    for k in ("lon_min", "lon_max", "lat_min", "lat_max"):
        v = config.get(k)
        if v is not None and k in valid_fields:
            kwargs[k] = v
```
Place this before the general `for k, v in config.items()` loop, or drop `_bbox_keys` from the skip set when `padded` is empty.

### WR-04: `firstOuterRing` silently drops all but first polygon of a MultiPolygon

**File:** `frontend/src/hooks/useCanvasArtifacts.ts:79-83`
**Issue:** `firstOuterRing` picks `g.coordinates[0]` for `Polygon` and `g.coordinates[0][0]` for `MultiPolygon`. Any real-world territory with islands or exclaves (coastal Galicia, the Azores, Balearics, any state straddling a river delta) will have a MultiPolygon whose non-first polygons are rendered as nothing. The selected territory's gold outline and barony fills will also be partial. Phase 2 covers continental Iberia, so this may be acceptable for the milestone, but it is a correctness gap against real data.
**Fix:** Either render all polygons (return `number[][]` and emit one `Line` per polygon), or add an explicit known-limitation comment noting Phase 2 renders only the primary polygon per condado and tracking work to Phase 3+. A minimal render-all approach:
```typescript
function allOuterRings(
  g: CondadoFeature['geometry'] | BaronyFeature['geometry'],
): [number, number][][] {
  return g.type === 'Polygon' ? [g.coordinates[0]] : g.coordinates.map((p) => p[0])
}
// Then TerritoryRender gains `points: number[][]` and the layers render one Line per ring.
```

### WR-05: `rasterio>=1.4,<2.0` inconsistent with `requires-python = ">=3.11"`

**File:** `pyproject.toml:10,27`
**Issue:** Per project CLAUDE.md (Potential Issue #6), rasterio 1.5+ requires Python 3.12+ and NumPy 2+. The current constraint `rasterio>=1.4,<2.0` resolves to the latest available version, which today is 1.5+. A fresh install on Python 3.11 will either fail at install time or silently install a binary-incompatible build. CI and user machines on 3.11 will diverge from 3.12 machines in surprising ways.
**Fix:**
```toml
# Option A — pin rasterio to 1.4.x to match the 3.11 floor:
"rasterio>=1.4,<1.5",

# Option B — raise Python floor to 3.12 and keep rasterio unpinned:
requires-python = ">=3.12"
# (also bump numpy>=2 since rasterio 1.5 requires it)
```
Option A is less disruptive given the existing dependency list; Option B aligns with the RESEARCH doc's long-term direction.

## Info

### IN-01: `InspectorSidebarWrapper` calls `useCanvasArtifacts` twice per render

**File:** `frontend/src/pages/ProjectDetail.tsx:405,424`
**Issue:** The wrapper calls `useCanvasArtifacts(projectId, null)` to discover metadata, derives a `projection` via `useMemo`, then calls `useCanvasArtifacts(projectId, projection)` again to get the projected territories. TanStack Query dedups the fetches, but each call registers 5 query observers (via `useQueries`), so the component has 10 observer subscriptions where 5 would suffice. There's also a brief "null projection" cycle that computes `points: []` in the `select` transform before being superseded.
**Fix:** Hoist projection derivation up to the level that already has metadata, or split `useCanvasArtifacts` into a `useTerritoryMetadata` hook (no projection needed) + a `useProjectedArtifacts(projection)` hook. Not urgent — Phase 2 data volumes are small.

### IN-02: Variable name reuse `b` in `baronies_geojson.emit_baronies_from_disk`

**File:** `backend/medieval_forge/services/baronies_geojson.py:80-82`
**Issue:** `b` is used as the blue channel integer (`b = int(hexstr[5:7], 16)`) inside the color loop. In the surrounding module (`build_baronies_geojson` at line 40), `b` is the barony dict. They don't collide (different scopes) but readability is low — a future reader scanning for barony iteration may be misled. Also, shadowing a dict name with an integer in a color parser is a classic source of confusion during debugging.
**Fix:** Rename to `blue` (or `bch`) throughout the color-decoding loop for both `baronies_geojson.py:81` and `territories_geojson.py:150`.

### IN-03: `STRtree` adjacency uses `.touches()` which admits single-point corner contact

**File:** `backend/medieval_forge/services/territories_geojson.py:117`
**Issue:** `g.touches(unioned[other_ci])` returns true for polygons sharing even a single vertex (diagonal corner contact). The test at `test_territories_geojson.py:46-48` explicitly acknowledges this: "they may also touch at a corner point (pixel (50,40)) which shapely.touches() counts as adjacency." If the UI intends "shares an edge" semantics (which is the usual adjacency meaning on a territory map), this produces spurious neighbors at the rare pixel intersections of four polygons. For Voronoi-derived maps this is rare; for the demo fixtures it's relatively common.
**Fix:** If spec wants edge-adjacency only, replace with a length check on the shared boundary:
```python
shared = g.boundary.intersection(unioned[other_ci].boundary)
if shared.length > 0:  # rejects 0-length point intersections
    neigh_ids.add(...)
```
Otherwise, document explicitly that single-point contact counts as adjacency.

### IN-04: `InteractionLayer.tsx` — redundant `listening={false}` on Line inside a `listening={false}` Layer

**File:** `frontend/src/components/canvas/InteractionLayer.tsx:27-35`
**Issue:** The Layer already has `listening={false}`; Konva's convention is that a child with default listening still inherits non-interactive behavior when the Layer is non-listening. Setting it on both is redundant (same applies to `BaronyLayer.tsx:19-29`). Not a bug — just stylistic noise.
**Fix:** Drop `listening={false}` from the inner `Line` props; keep it on the Layer only. Conversely, if keeping both for defensive consistency is deliberate, add a one-line comment to that effect to preempt future PR noise.

### IN-05: `CenteredLabel` effect depends only on `props.text`

**File:** `frontend/src/components/canvas/DecorationsLayer.tsx:32-41`
**Issue:** The post-mount offset-calibration effect lists `[props.text]` as its dep array. If `fontSize` or `fontFamily` were ever parameterized (which is likely in Phase 3 when zoom-adaptive typography lands), the measured width would stop re-running. Currently they're hardcoded constants so the effect is correct today.
**Fix:** Either (a) add a comment noting the fontSize/fontFamily are intentionally fixed and must be added to the dep array if parameterized, or (b) proactively include them:
```typescript
useEffect(() => { /* ... */ }, [props.text /* + fontSize, fontFamily when parameterized */])
```

---

## Items Considered and Not Flagged

For reviewer transparency:

- `generator.py:344` — broad `except Exception:` around geojson emission is deliberately documented ("geojson emission failed — canvas will show empty overlays") and does not swallow the primary pipeline failure. Intentional.
- `useZoomPan.ts:100-102` — `(this as unknown as ...).getStage?.()` cast is defensive handling for Konva's `this`-binding contract, not a type escape hatch.
- `hex[1:3]`/`hex[3:5]`/`hex[5:7]` slicing in both `_geojson` builders would crash on malformed color strings; those strings are produced by our own generator so it's inside the trust boundary. Not an issue today; revisit if third-party color maps are ever accepted.
- `App.tsx:14-16` — `/canvas-smoke` dev-only route is correctly gated with `import.meta.env.DEV` so it's stripped from production bundles.
- `CanvasViewer.tsx:141` — `eslint-disable-next-line react-hooks/exhaustive-deps` is correct here; the live-read of `stage.scaleX()` inside the effect is explicitly documented (lines 123–126) as the reason `currentScale` must NOT be in the dep array.

---

_Reviewed: 2026-04-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
