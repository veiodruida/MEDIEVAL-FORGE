---
phase: 02-read-only-canvas-viewer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/generator.py
  - backend/medieval_forge/services/territories_geojson.py
  - backend/medieval_forge/services/baronies_geojson.py
  - backend/medieval_forge/api/generate.py
  - backend/tests/test_territories_geojson.py
  - backend/tests/test_baronies_geojson.py
  - frontend/package.json
  - frontend/vitest.config.ts
  - frontend/playwright.config.ts
  - frontend/e2e/smoke-tailwind-radix.spec.ts
  - frontend/e2e/__baselines__/canvas-radix-overlay.png
  - frontend/src/test-setup.ts
  - frontend/src/lib/projection.ts
  - frontend/src/lib/projection.test.ts
  - frontend/src/stores/uiStore.ts
  - frontend/src/stores/uiStore.test.ts
  - frontend/src/context/ProjectionContext.tsx
  - frontend/src/hooks/useCanvasArtifacts.ts
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/BackgroundLayer.tsx
  - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
  - frontend/src/components/canvas/__smoke__/CanvasRadixOverlaySmoke.tsx
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
nyquist_compliant: true
requirements: [CANVAS-01]
requirements_addressed: [CANVAS-01]

must_haves:
  truths:
    - "Backend emits territories.geojson with per-condado polygon + neighbors after generation"
    - "Backend emits baronies.geojson with per-barony polygon + fill color (D-02 data dependency)"
    - "FastAPI serves both territories.geojson and baronies.geojson via /api/projects/{id}/preview/{filename} (whitelisted)"
    - "Frontend projection module converts lon/lat <-> canvas pixels with < 1e-9 round-trip error"
    - "Konva Stage mounts inside /projects/:id and renders terrain PNG on Background layer"
    - "Tailwind v4 + Radix overlay stays opaque over a Konva Stage (Playwright toHaveScreenshot regression + RGB pixel sample)"
    - "Vitest + Playwright test infrastructure is installed and wired into npm scripts"
  artifacts:
    - path: "backend/medieval_forge/services/territories_geojson.py"
      provides: "build_territories_geojson(project_id) reads lookup_condado.png + territory_metadata.json + lookup_condado_colors.json and writes territories.geojson with {id, name, geometry, properties.neighbors}"
      min_lines: 40
    - path: "backend/medieval_forge/services/baronies_geojson.py"
      provides: "build_baronies_geojson(project_id) reads lookup_barony.png + territory_metadata.json + lookup_barony_colors.json and writes baronies.geojson with {id, name, condado_id, geometry, properties.fill}"
      min_lines: 40
    - path: "backend/tests/test_territories_geojson.py"
      provides: "pytest asserts territories.geojson features have id + polygon + neighbors list"
    - path: "backend/tests/test_baronies_geojson.py"
      provides: "pytest asserts baronies.geojson features have id + polygon + fill color"
    - path: "frontend/src/lib/projection.ts"
      provides: "ProjectionConfig type, buildProjectionConfig, geoToCanvas, canvasToGeo, geoRingToKonvaPoints"
      exports: ["ProjectionConfig", "buildProjectionConfig", "geoToCanvas", "canvasToGeo", "geoRingToKonvaPoints", "computeFitToView"]
    - path: "frontend/src/stores/uiStore.ts"
      provides: "Zustand useUIStore with selectedTerritoryId, layerVisibility, select, toggleLayer"
      exports: ["useUIStore", "type LayerName"]
    - path: "frontend/src/context/ProjectionContext.tsx"
      provides: "React context for ProjectionConfig"
      exports: ["ProjectionProvider", "useProjection"]
    - path: "frontend/src/hooks/useCanvasArtifacts.ts"
      provides: "TanStack Query hooks for territories.geojson + baronies.geojson + color lookups + territory_metadata"
      exports: ["useCanvasArtifacts"]
    - path: "frontend/src/components/canvas/CanvasViewer.tsx"
      provides: "Top-level canvas component: Stage + BackgroundLayer only (Territories/Baronies/Decorations/Interaction added in 2.2/2.3)"
    - path: "frontend/e2e/smoke-tailwind-radix.spec.ts"
      provides: "Playwright visual smoke: Radix Card over magenta Konva Stage, toHaveScreenshot baseline + center-pixel pngjs RGB sample NOT magenta"
  key_links:
    - from: "backend/medieval_forge/services/generator.py"
      to: "territories_geojson.build_territories_geojson + baronies_geojson.build_baronies_geojson"
      via: "call after map_generator.generate_maps in _run_pipeline_sync — after lookup PNGs + territory_metadata.json exist on disk"
      pattern: "build_territories_geojson\\(|build_baronies_geojson\\("
    - from: "backend/medieval_forge/services/generator.py"
      to: "GENERATED_FILE_WHITELIST"
      via: "append 'territories.geojson' + 'baronies.geojson' so /preview route can serve them"
      pattern: "territories\\.geojson|baronies\\.geojson"
    - from: "frontend/src/pages/ProjectDetail.tsx"
      to: "CanvasViewer"
      via: "render inside project detail when status in {generated, exported}"
      pattern: "<CanvasViewer"
    - from: "frontend/src/hooks/useCanvasArtifacts.ts"
      to: "/api/projects/{id}/preview/territories.geojson and /preview/baronies.geojson"
      via: "fetch with staleTime: Infinity"
      pattern: "preview/territories\\.geojson|preview/baronies\\.geojson"
    - from: "frontend/src/lib/projection.ts"
      to: "inicio/map_generator.py geo_to_pixel"
      via: "identical affine formula so Konva polygons align with terrain.png pixel-for-pixel"
      pattern: "lonScale"
---

<objective>
Stand up Phase 2's foundation: (1) emit the missing `territories.geojson` + neighbor adjacency AND `baronies.geojson` on the backend so the canvas has polygon geometry to render for BOTH condados and baronies (D-01, D-02), (2) prove the Tailwind v4 + Radix + Konva integration is healthy with a Wave-0 Playwright visual-regression smoke before investing in real canvas components, (3) install Vitest + Playwright test infrastructure, (4) port the exact `map_generator.py` projection math to TypeScript, (5) create the Zustand UI slice + TanStack Query artifact loader + ProjectionContext, and (6) mount a read-only Konva Stage with just the Background (terrain PNG) layer inside `/projects/:id`.

Purpose: Without `territories.geojson` + the `neighbors` field the canvas cannot render polygons (CANVAS-01) or show neighbor chips (D-06 group 4). Without `baronies.geojson` the D-02 decision ("baronies render when toggle ON") cannot be honored — BaronyLayer would render empty. Without the Pitfall-2 smoke test we risk silent transparency regressions. Without the projection module, Konva overlays drift from `terrain.png`. All four unblock plans 2.2 and 2.3.

Output: A project that, when opened at `/projects/:id` in a `generated` state, displays a pan-less/zoom-less Konva Stage showing the terrain PNG. Plan 2.2 consumes territories.geojson + baronies.geojson and renders them. No interactions yet — those land in 2.3. All downstream plans consume the contracts defined here.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md
@.planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md
@.planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md
@.planning/phases/02-read-only-canvas-viewer/02-VALIDATION.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
@CLAUDE.md

<interfaces>
<!-- Contracts executors MUST use verbatim. No exploration needed. -->

From `inicio/map_generator.py` (lines 152–171) — the projection math (MUST be mirrored exactly in TypeScript):
```python
def geo_to_pixel(lon, lat, cfg, w=None, h=None):
    w = w or cfg.map_w
    h = h or cfg.map_h
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    px = int((lon - cfg.lon_min) * cfg.lon_scale / span * w)
    py = int((1.0 - (lat - cfg.lat_min) / (cfg.lat_max - cfg.lat_min)) * h)
    return (px, py)

def pixel_to_geo(px, py, cfg, w=None, h=None):
    w = w or cfg.map_w
    h = h or cfg.map_h
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    lon = px / w * span / cfg.lon_scale + cfg.lon_min
    lat = cfg.lat_max - py / h * (cfg.lat_max - cfg.lat_min)
    return (lon, lat)
```
TS port MUST use sub-pixel floats (drop the `int(...)` cast — it is a Python rasterization artifact, not part of the projection contract; see RESEARCH §Pattern 1 Important note).

**Vendored black-box constraint (from `backend/medieval_forge/services/generator.py` module docstring):**
> D-04: map_generator is treated as a vendored black box. We do NOT modify it.

This means Task 1 **must NOT** edit `inicio/map_generator.py` signatures. `generate_maps()` has return type `None`; it writes files to disk. Our territories.geojson + baronies.geojson builders therefore operate **after** `_run_pipeline_sync` completes, reading back from already-emitted artifacts on disk:
- `generated/lookup_condado.png` — per-pixel condado index via color→id mapping in `lookup_condado_colors.json`
- `generated/lookup_barony.png` + `lookup_barony_colors.json` — same for baronies
- `generated/territory_metadata.json` — hierarchy + per-condado id/name/lon/lat/duchy/kingdom/baronies[]

From `backend/medieval_forge/services/generator.py`:
```python
GENERATED_FILE_WHITELIST: frozenset[str]  # include 'terrain.png', 'territories.png', ...
_GENERATOR_OUTPUTS: tuple[str, ...]       # raw filenames from map_generator
_PREVIEW_ALIASES: dict[str, str]          # {"terrain.png": "terrain_lookup.png", ...}
def _run_pipeline_sync(project_id, generated_dir, config) -> dict[str, str]   # synchronous worker
async def run_generation(project_id, config) -> dict                           # thread wrapper
```

From `backend/medieval_forge/api/generate.py`:
```python
@router.get("/{project_id}/preview/{filename}")
async def get_preview(project_id: str, filename: str) -> FileResponse
# Validates UUID, checks filename against GENERATED_FILE_WHITELIST, returns FileResponse from <project>/generated/<filename>.
```
No new FastAPI route is needed — both new files piggyback on `/preview/{filename}` once added to the whitelist.

From `frontend/src/main.tsx`:
```tsx
<Theme appearance="light" accentColor="iris" radius="medium">
  <QueryClientProvider client={queryClient}>
    <BrowserRouter><App /></BrowserRouter>
  </QueryClientProvider>
</Theme>
```

From `frontend/src/index.css`:
```css
@import "@radix-ui/themes/styles.css";   /* MUST come before Tailwind — Pitfall 2 */
@import "tailwindcss";
```

From `frontend/src/api/client.ts` — existing TanStack Query patterns:
```ts
useQuery({ queryKey: ['<name>', projectId], queryFn: () => jsonFetch<T>(`/api/...`), enabled: Boolean(projectId), staleTime: Infinity })
```

From `frontend/package.json` — currently installed deps (confirmed):
```json
"dependencies": {
  "react": "^19.2.0", "react-dom": "^19.2.0", "react-router-dom": "^7.14.0",
  "@tanstack/react-query": "^5.99.0", "zustand": "^5.0.12", "zundo": "^2.3.0",
  "@radix-ui/themes": "^3.3.0"
}
```
Add: `"konva": "^10"`, `"react-konva": "^19"`. Dev-deps: `"pngjs"` for pixel-buffer RGB sampling in the Playwright smoke.

ProjectionConfig (exact type for all downstream plans):
```ts
export interface ProjectionConfig {
  lonMin: number; lonMax: number;
  latMin: number; latMax: number;
  mapW: number;   mapH: number;   // pixel dimensions of terrain.png (map_size from metadata)
  lonScale: number;               // cos((latMin+latMax)/2 * pi/180)
}
```

UIStore slice shape (exact — plans 2.2/2.3 extend, not reshape):
```ts
export type LayerName = 'terrain' | 'territories' | 'borders' | 'capitals' | 'labels'
interface UIState {
  selectedTerritoryId: string | null
  layerVisibility: Record<LayerName, boolean>
  select: (id: string | null) => void
  toggleLayer: (name: LayerName) => void
}
// Initial state (D-09): terrain=true, territories=true, borders=true, capitals=true, labels=false
```

territories.geojson feature shape (NEW contract — frozen by this plan, consumed by 2.2/2.3):
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "C_CORUNA",
      "geometry": { "type": "Polygon", "coordinates": [[[lon, lat], ...]] },
      "properties": {
        "id": "C_CORUNA",
        "name": "Coruña",
        "neighbors": ["C_LUGO", "C_BETANZOS"]
      }
    }
  ]
}
```
Polygon `coordinates` are in WGS84 `(lon, lat)` order per GeoJSON RFC 7946. `neighbors` is the list of condado IDs whose polygons share an edge (computed via `shapely.STRtree` + `.touches()` in Python). For Phase 2 condados, `neighbors` is ALWAYS a present `string[]` (possibly empty, never missing).

baronies.geojson feature shape (NEW contract — D-02):
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "B_BETANZOS",
      "geometry": { "type": "Polygon", "coordinates": [[[lon, lat], ...]] },
      "properties": {
        "id": "B_BETANZOS",
        "name": "B_BETANZOS",
        "condado_id": "C_CORUNA",
        "fill": "#abcdef"
      }
    }
  ]
}
```
`fill` is resolved from `lookup_barony_colors.json` at emission time so the frontend can render without the extra lookup (keeps BaronyLayer simple).
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Backend — emit territories.geojson + baronies.geojson (CANVAS-01 + D-02 data deps)</name>
  <files>
    backend/medieval_forge/services/territories_geojson.py (NEW),
    backend/medieval_forge/services/baronies_geojson.py (NEW),
    backend/medieval_forge/services/generator.py (MODIFY — append to whitelist + invoke both emitters after _materialise_aliases),
    backend/tests/test_territories_geojson.py (NEW),
    backend/tests/test_baronies_geojson.py (NEW)
  </files>
  <read_first>
    - backend/medieval_forge/services/generator.py (ALL — note module docstring "D-04: map_generator is treated as a vendored black box. We do NOT modify it." — enforced path is read-back from emitted artifacts)
    - backend/medieval_forge/services/paths.py (project_dir, is_valid_uuid, ensure_project_dirs)
    - backend/medieval_forge/api/generate.py (confirm /preview/{filename} uses GENERATED_FILE_WHITELIST — no route changes needed)
    - inicio/map_generator.py lines 798–935 (generate_maps returns None; writes lookup_condado.png + lookup_barony.png + lookup_*_colors.json + territory_metadata.json to disk — these are our INPUTS)
    - inicio/map_generator.py lines 650–730 (generate_lookup_map + export_metadata — output shapes)
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Open Questions 1 & 2 (the chosen path: rasterio.features.shapes + shapely.STRtree)
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Security Domain (V4/V5 — whitelist reuse pattern)
    - backend/pyproject.toml (confirm rasterio + shapely are installed — Phase 1 pinned rasterio>=1.4,<1.5)
  </read_first>
  <behavior>
    - Test 1 (condados): `build_territories_geojson(project_id, pc, condados, cfg_like)` writes `territories.geojson` under `project_dir(project_id) / "generated"` with a top-level `FeatureCollection` whose `features[*].id` matches the condado id, `features[*].geometry.type ∈ {"Polygon","MultiPolygon"}`, and `features[*].properties.neighbors` is a `list[str]`.
    - Test 2 (adjacency): For a synthetic 4-quadrant `pc` raster (A top-left, B top-right, C bottom-left; no D), `neighbors` for A = sorted {B, C}, B = {A}, C = {A}. No self-loops.
    - Test 3 (baronies): `build_baronies_geojson(project_id, pb, baronies_index, condados, cfg_like, barony_colors)` writes `baronies.geojson` where each feature has `id`, `properties.condado_id`, `properties.fill` (hex from lookup), and Polygon/MultiPolygon geometry.
    - Test 4 (whitelist): `GENERATED_FILE_WHITELIST` contains both `territories.geojson` AND `baronies.geojson`.
    - Test 5 (path traversal): Calling either builder with a non-UUID raises `ValueError` via `project_dir()`.
    - Test 6 (read-back integration smoke): A helper `emit_canvas_geojson_from_disk(generated_dir, project_id)` reads `lookup_condado.png`, `lookup_condado_colors.json`, `territory_metadata.json`, `lookup_barony.png`, `lookup_barony_colors.json`, reconstructs `pc`/`pb`/`condados`/`baronies`, and invokes both builders. Tested with a synthetic fixture directory.
  </behavior>
  <action>
    Create `backend/medieval_forge/services/territories_geojson.py`:

    ```python
    """CANVAS-01 data dependency: emit territories.geojson with per-condado
    polygon + neighbors adjacency.

    VENDORED BLACK BOX CONSTRAINT: inicio/map_generator.py is not modified.
    This module runs AFTER generate_maps() has written its files to disk and
    reconstructs the condado raster from lookup_condado.png + lookup_condado_colors.json.

    T-PATH: project_id is validated via paths.project_dir() (ValueError on bad UUID).
    V5 input validation: filename 'territories.geojson' is appended to
    GENERATED_FILE_WHITELIST in generator.py; the existing /preview/{filename}
    route handles the actual serving — no new route is introduced.
    """
    from __future__ import annotations

    import json
    from pathlib import Path
    from typing import Any

    import numpy as np
    import rasterio.features
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    from .paths import project_dir


    class _ProjCfg:
        """Minimal cfg-like shim holding the fields we need for lon/lat inversion.
        Populated from territory_metadata.json + lookup_condado.png shape.
        """
        __slots__ = ("lon_min", "lon_max", "lat_min", "lat_max", "map_w", "map_h", "upscale", "lon_scale")

        def __init__(self, lon_min, lon_max, lat_min, lat_max, map_w, map_h, upscale, lon_scale):
            self.lon_min = lon_min; self.lon_max = lon_max
            self.lat_min = lat_min; self.lat_max = lat_max
            self.map_w = map_w;     self.map_h = map_h
            self.upscale = upscale
            self.lon_scale = lon_scale


    def _pixel_polygon_to_lonlat(geom: dict, cfg: _ProjCfg) -> dict:
        """Apply the inverse of map_generator.geo_to_pixel to every vertex.
        The lookup PNG is at map_w*upscale × map_h*upscale — use that as W/H.
        """
        W = cfg.map_w * cfg.upscale
        H = cfg.map_h * cfg.upscale
        span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale

        def px_to_lonlat(px: float, py: float) -> tuple[float, float]:
            lon = px / W * span / cfg.lon_scale + cfg.lon_min
            lat = cfg.lat_max - py / H * (cfg.lat_max - cfg.lat_min)
            return (lon, lat)

        def ring(coords):
            return [list(px_to_lonlat(x, y)) for x, y in coords]

        if geom["type"] == "Polygon":
            return {"type": "Polygon", "coordinates": [ring(r) for r in geom["coordinates"]]}
        if geom["type"] == "MultiPolygon":
            return {"type": "MultiPolygon",
                    "coordinates": [[ring(r) for r in poly] for poly in geom["coordinates"]]}
        raise ValueError(f"unsupported geometry type: {geom['type']}")


    def build_territories_geojson(
        project_id: str,
        pc: np.ndarray,
        condados: list[list[Any]],
        cfg: _ProjCfg,
    ) -> Path:
        """Write territories.geojson with per-condado polygon + neighbors."""
        out_dir = project_dir(project_id) / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)

        pc32 = pc.astype(np.int32)
        shapes_per_idx: dict[int, list] = {}
        for geom, idx in rasterio.features.shapes(pc32, mask=(pc32 >= 0)):
            i = int(idx)
            shapes_per_idx.setdefault(i, []).append(shape(geom))

        features: list[dict] = []
        unioned: dict[int, Any] = {}
        for ci, c in enumerate(condados):
            geoms = shapes_per_idx.get(ci, [])
            if not geoms:
                continue
            u = unary_union(geoms)
            unioned[ci] = u
            lonlat_geojson = _pixel_polygon_to_lonlat(mapping(u), cfg)
            features.append({
                "type": "Feature",
                "id": c[0],
                "geometry": lonlat_geojson,
                "properties": {"id": c[0], "name": c[1], "neighbors": []},
            })

        idx_to_id = {ci: condados[ci][0] for ci in unioned}
        id_to_ci = {v: k for k, v in idx_to_id.items()}
        tree_geoms = list(unioned.values())
        tree = STRtree(tree_geoms)
        ci_by_geom_idx = list(unioned.keys())

        for feat in features:
            ci = id_to_ci[feat["id"]]
            g = unioned[ci]
            neigh_ids: set[str] = set()
            for qi in tree.query(g):
                other_ci = ci_by_geom_idx[qi]
                if other_ci == ci:
                    continue
                if g.touches(unioned[other_ci]):
                    neigh_ids.add(idx_to_id[other_ci])
            feat["properties"]["neighbors"] = sorted(neigh_ids)

        out_path = out_dir / "territories.geojson"
        out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        return out_path


    def reconstruct_pc_from_lookup(lookup_png_path: Path, colors_json_path: Path) -> np.ndarray:
        """Read lookup_condado.png (RGB) + lookup_condado_colors.json (id → "#rrggbb")
        and produce an int32 raster where each pixel is the condado index (-1 = none).
        """
        from PIL import Image
        img = np.array(Image.open(lookup_png_path).convert("RGB"))  # (H, W, 3) uint8
        H, W, _ = img.shape
        colors = json.loads(Path(colors_json_path).read_text())
        # colors maps condado-id string → "#rrggbb". We need index → (r,g,b).
        # The index is the order in territory_metadata's condados list (same order the
        # generator uses for ci). Order preservation is the caller's responsibility —
        # pass condados list aligned with colors.
        pc = np.full((H, W), -1, dtype=np.int32)
        # Build a (r,g,b) → index map using the condado id order known to the caller.
        return img, pc  # caller completes the lookup after aligning id order


    def emit_territories_from_disk(
        project_id: str,
        generated_dir: Path,
        cfg: _ProjCfg,
    ) -> Path:
        """Read-back orchestrator. Resolves pc + condados from disk, calls builder."""
        import json as _json
        from PIL import Image
        meta = _json.loads((generated_dir / "territory_metadata.json").read_text())
        condados_meta = meta["condados"]  # list of dicts per export_metadata
        # Rehydrate the tuple/list shape build_territories_geojson expects: [id, name, lon, lat, duchy, baronies]
        condados = [
            [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
            for c in condados_meta
        ]
        id_to_ci = {c[0]: i for i, c in enumerate(condados)}
        colors = _json.loads((generated_dir / "lookup_condado_colors.json").read_text())  # id → "#rrggbb"
        img = np.array(Image.open(generated_dir / "lookup_condado.png").convert("RGB"))
        H, W, _ = img.shape
        pc = np.full((H, W), -1, dtype=np.int32)
        for cid, hexstr in colors.items():
            r = int(hexstr[1:3], 16); g = int(hexstr[3:5], 16); b = int(hexstr[5:7], 16)
            mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == b)
            ci = id_to_ci.get(cid)
            if ci is not None:
                pc[mask] = ci
        return build_territories_geojson(project_id, pc, condados, cfg)
    ```

    Create `backend/medieval_forge/services/baronies_geojson.py` — same structure, but emits baronies with `condado_id` and `fill` properties:

    ```python
    """D-02 data dependency: emit baronies.geojson.

    Read-back approach (same vendored-black-box constraint as territories_geojson).
    Inputs from disk: lookup_barony.png, lookup_barony_colors.json, territory_metadata.json.
    """
    from __future__ import annotations

    import json
    from pathlib import Path
    from typing import Any

    import numpy as np
    import rasterio.features
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    from .paths import project_dir
    from .territories_geojson import _ProjCfg, _pixel_polygon_to_lonlat


    def build_baronies_geojson(
        project_id: str,
        pb: np.ndarray,
        baronies: list[dict],   # [{ "name": "B_X", "condado_idx": int, "duchy": ..., "pixel_count": int }]
        condados: list[list[Any]],
        cfg: _ProjCfg,
        barony_colors: dict[str, str],   # name -> "#rrggbb"
    ) -> Path:
        out_dir = project_dir(project_id) / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)

        pb32 = pb.astype(np.int32)
        shapes_per_idx: dict[int, list] = {}
        for geom, idx in rasterio.features.shapes(pb32, mask=(pb32 >= 0)):
            i = int(idx)
            shapes_per_idx.setdefault(i, []).append(shape(geom))

        features: list[dict] = []
        for bi, b in enumerate(baronies):
            geoms = shapes_per_idx.get(bi, [])
            if not geoms:
                continue
            u = unary_union(geoms)
            lonlat = _pixel_polygon_to_lonlat(mapping(u), cfg)
            condado_id = condados[b["condado_idx"]][0] if 0 <= b["condado_idx"] < len(condados) else ""
            features.append({
                "type": "Feature",
                "id": b["name"],
                "geometry": lonlat,
                "properties": {
                    "id": b["name"],
                    "name": b["name"],
                    "condado_id": condado_id,
                    "fill": barony_colors.get(b["name"], "#888888"),
                },
            })

        out_path = out_dir / "baronies.geojson"
        out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        return out_path


    def emit_baronies_from_disk(project_id: str, generated_dir: Path, cfg: _ProjCfg) -> Path:
        from PIL import Image
        meta = json.loads((generated_dir / "territory_metadata.json").read_text())
        baronies = meta.get("baronies", [])
        condados = [
            [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
            for c in meta["condados"]
        ]
        barony_colors = json.loads((generated_dir / "lookup_barony_colors.json").read_text())
        name_to_bi = {b["name"]: i for i, b in enumerate(baronies)}
        img = np.array(Image.open(generated_dir / "lookup_barony.png").convert("RGB"))
        H, W, _ = img.shape
        pb = np.full((H, W), -1, dtype=np.int32)
        for bname, hexstr in barony_colors.items():
            r = int(hexstr[1:3], 16); g = int(hexstr[3:5], 16); b = int(hexstr[5:7], 16)
            mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == b)
            bi = name_to_bi.get(bname)
            if bi is not None:
                pb[mask] = bi
        return build_baronies_geojson(project_id, pb, baronies, condados, cfg, barony_colors)
    ```

    Modify `backend/medieval_forge/services/generator.py`:

    1. Append both new filenames to the whitelist:
    ```python
    GENERATED_FILE_WHITELIST: frozenset[str] = frozenset(
        list(_GENERATOR_OUTPUTS)
        + list(_PREVIEW_ALIASES.keys())
        + list(_AUXILIARY_OUTPUTS)
        + ["territories.geojson", "baronies.geojson"]
    )
    ```

    2. Inside `_run_pipeline_sync`, AFTER `_materialise_aliases(generated_dir)` and BEFORE building the manifest, add:
    ```python
    # CANVAS-01 + D-02: build GeoJSON artifacts by reading back the generator's
    # lookup PNGs + territory_metadata.json from disk. Keeps inicio/map_generator.py
    # as an untouched black box (D-04 in this module's docstring).
    from .territories_geojson import emit_territories_from_disk, _ProjCfg
    from .baronies_geojson import emit_baronies_from_disk
    cfg_shim = _ProjCfg(
        lon_min=region_cfg.lon_min, lon_max=region_cfg.lon_max,
        lat_min=region_cfg.lat_min, lat_max=region_cfg.lat_max,
        map_w=region_cfg.map_w,     map_h=region_cfg.map_h,
        upscale=region_cfg.upscale, lon_scale=region_cfg.lon_scale,
    )
    try:
        emit_territories_from_disk(project_id, generated_dir, cfg_shim)
        emit_baronies_from_disk(project_id, generated_dir, cfg_shim)
    except Exception:
        logger.exception("geojson emission failed for %s — canvas will show empty overlays", project_id)
        # Do not fail the pipeline; PNG outputs still usable.
    ```

    Create `backend/tests/test_territories_geojson.py`:

    ```python
    import json
    import uuid
    import numpy as np
    import pytest
    from medieval_forge.services.territories_geojson import build_territories_geojson, _ProjCfg

    def _cfg(mw=100, mh=80):
        return _ProjCfg(lon_min=-10.0, lon_max=0.0, lat_min=36.0, lat_max=44.0,
                        map_w=mw, map_h=mh, upscale=1, lon_scale=0.78)

    def test_emits_geojson_with_id_polygon_neighbors(tmp_path, monkeypatch):
        pid = str(uuid.uuid4())
        from medieval_forge.services import paths as _paths
        monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")

        W, H = 100, 80
        pc = np.full((H, W), -1, dtype=np.int32)
        pc[:40, :50] = 0; pc[:40, 50:] = 1; pc[40:, :50] = 2

        condados = [
            ["C_A", "AlphaLand", -7.5, 42.0, "D1", []],
            ["C_B", "BetaLand",  -2.5, 42.0, "D1", []],
            ["C_C", "GammaLand", -7.5, 38.0, "D1", []],
        ]
        out = build_territories_geojson(pid, pc, condados, _cfg())
        data = json.loads(out.read_text())
        assert data["type"] == "FeatureCollection"
        ids = {f["id"] for f in data["features"]}
        assert ids == {"C_A", "C_B", "C_C"}
        for f in data["features"]:
            assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
            assert isinstance(f["properties"]["neighbors"], list)
        by_id = {f["id"]: f for f in data["features"]}
        assert set(by_id["C_A"]["properties"]["neighbors"]) == {"C_B", "C_C"}
        assert by_id["C_B"]["properties"]["neighbors"] == ["C_A"]
        assert by_id["C_C"]["properties"]["neighbors"] == ["C_A"]

    def test_invalid_uuid_rejected():
        with pytest.raises(ValueError):
            build_territories_geojson("not-a-uuid", np.zeros((1,1), dtype=np.int32), [], _cfg())

    def test_whitelist_contains_territories_and_baronies_geojson():
        from medieval_forge.services.generator import GENERATED_FILE_WHITELIST
        assert "territories.geojson" in GENERATED_FILE_WHITELIST
        assert "baronies.geojson" in GENERATED_FILE_WHITELIST
    ```

    Create `backend/tests/test_baronies_geojson.py`:

    ```python
    import json, uuid
    import numpy as np
    import pytest
    from medieval_forge.services.baronies_geojson import build_baronies_geojson
    from medieval_forge.services.territories_geojson import _ProjCfg

    def _cfg():
        return _ProjCfg(-10.0, 0.0, 36.0, 44.0, 100, 80, 1, 0.78)

    def test_emits_baronies_with_condado_id_and_fill(tmp_path, monkeypatch):
        pid = str(uuid.uuid4())
        from medieval_forge.services import paths as _paths
        monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
        W, H = 100, 80
        pb = np.full((H, W), -1, dtype=np.int32)
        pb[:40, :50] = 0; pb[:40, 50:] = 1
        baronies = [
            {"name": "B_A1", "condado_idx": 0, "duchy": "D1", "pixel_count": 2000},
            {"name": "B_B1", "condado_idx": 1, "duchy": "D1", "pixel_count": 2000},
        ]
        condados = [["C_A", "Alpha", -7.5, 42.0, "D1", ["B_A1"]],
                    ["C_B", "Beta",  -2.5, 42.0, "D1", ["B_B1"]]]
        colors = {"B_A1": "#ff0000", "B_B1": "#00ff00"}
        out = build_baronies_geojson(pid, pb, baronies, condados, _cfg(), colors)
        data = json.loads(out.read_text())
        by_id = {f["id"]: f for f in data["features"]}
        assert by_id["B_A1"]["properties"]["condado_id"] == "C_A"
        assert by_id["B_A1"]["properties"]["fill"] == "#ff0000"
        assert by_id["B_B1"]["properties"]["condado_id"] == "C_B"
    ```

    Run: `cd backend && pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py -q`.
  </action>
  <verify>
    <automated>cd backend && pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `backend/medieval_forge/services/territories_geojson.py` exists and exports `build_territories_geojson` + `emit_territories_from_disk`
    - `backend/medieval_forge/services/baronies_geojson.py` exists and exports `build_baronies_geojson` + `emit_baronies_from_disk`
    - `grep -n "territories.geojson\\|baronies.geojson" backend/medieval_forge/services/generator.py` returns at least 2 matches inside `GENERATED_FILE_WHITELIST` construction
    - `grep -n "emit_territories_from_disk\\|emit_baronies_from_disk" backend/medieval_forge/services/generator.py` returns calls inside `_run_pipeline_sync` after `_materialise_aliases`
    - `grep -n "def generate_maps" inicio/map_generator.py` signature is UNCHANGED (vendored black box respected — D-04)
    - `cd backend && pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py -q` exits 0 with 5+ passing tests
  </acceptance_criteria>
  <done>Backend emits BOTH `territories.geojson` (per-condado polygons + neighbors) AND `baronies.geojson` (per-barony polygons + condado_id + fill) after every `run_generation`; both are whitelisted; map_generator.py is unchanged; unit tests pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wave 0 test infrastructure + Tailwind/Radix visual-regression smoke (Pitfall 2 guard)</name>
  <files>
    frontend/package.json (MODIFY — add konva, react-konva, vitest, @testing-library/react, @testing-library/jest-dom, jsdom, @playwright/test, pngjs; add scripts),
    frontend/vitest.config.ts (NEW),
    frontend/playwright.config.ts (NEW),
    frontend/src/test-setup.ts (NEW),
    frontend/e2e/smoke-tailwind-radix.spec.ts (NEW),
    frontend/e2e/__baselines__/canvas-radix-overlay.png (NEW — committed baseline screenshot),
    frontend/src/components/canvas/__smoke__/CanvasRadixOverlaySmoke.tsx (NEW),
    frontend/src/App.tsx (MODIFY — add /canvas-smoke route behind DEV-only guard)
  </files>
  <read_first>
    - frontend/package.json (current deps — verify konva/react-konva/vitest absent)
    - frontend/vite.config.ts (existing Vite config — vitest.config.ts extends this)
    - frontend/src/main.tsx (Theme wrapper; QueryClient)
    - frontend/src/index.css (Radix-before-Tailwind import order; MUST NOT change)
    - frontend/src/App.tsx (current routes)
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pitfall 2 + §Example 7 (smoke test code)
    - .planning/phases/02-read-only-canvas-viewer/02-VALIDATION.md §Wave 0 Requirements + Manual-Only Verifications
  </read_first>
  <behavior>
    - Test 1: `npm run test -- --run` exits 0 with Vitest installed and configured (jsdom env, testing-library extensions loaded via test-setup).
    - Test 2 (PRIMARY gate — visual regression): `npm run test:e2e -- smoke-tailwind-radix.spec.ts` runs a Playwright test that navigates to the smoke route and calls `await expect(page).toHaveScreenshot('canvas-radix-overlay.png', { maxDiffPixelRatio: 0.02 })` against the committed baseline. Regression of Pitfall 2 (Radix card turns transparent → magenta shows through) fails this gate.
    - Test 3 (SECONDARY gate — pixel-buffer RGB sample): After the visual regression passes, take `page.screenshot({ clip: cardBBox })` → decode with `pngjs` → assert the center-pixel RGB is NOT `(255, 0, 255)` (magenta tolerance ± 8).
    - Test 4 (TERTIARY diagnostic — getComputedStyle): On failure of the above, also assert the Radix Card's `backgroundColor` via `getComputedStyle` is not `rgba(..., 0)`. Kept for debugging only; failure of this alone is not the blocker — the visual/pixel gates are.
    - Test 5: Negative-control documentation — comment block inside the spec describing how to swap `index.css` import order to prove the visual regression catches it.
    - Test 6: `npm install` completes WITHOUT `--legacy-peer-deps`.
  </behavior>
  <action>
    Run the install from `frontend/`:
    ```bash
    cd frontend
    npm install --save konva@^10 react-konva@^19
    npm install --save-dev vitest@^3 @testing-library/react@^16 @testing-library/jest-dom@^6 jsdom @playwright/test@^1 @vitest/coverage-v8 pngjs@^7 @types/pngjs@^6
    npx playwright install chromium
    ```

    Update `frontend/package.json` scripts:
    ```json
    "scripts": {
      "dev": "vite",
      "build": "tsc -b && vite build",
      "preview": "vite preview",
      "test": "vitest",
      "test:e2e": "playwright test",
      "test:e2e:update": "playwright test --update-snapshots"
    }
    ```

    Create `frontend/vitest.config.ts`:
    ```ts
    import { defineConfig } from 'vitest/config'
    import react from '@vitejs/plugin-react'

    export default defineConfig({
      plugins: [react()],
      test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: ['./src/test-setup.ts'],
        include: ['src/**/*.{test,spec}.{ts,tsx}'],
      },
    })
    ```

    Create `frontend/src/test-setup.ts`:
    ```ts
    import '@testing-library/jest-dom/vitest'
    ```

    Create `frontend/playwright.config.ts`:
    ```ts
    import { defineConfig, devices } from '@playwright/test'

    export default defineConfig({
      testDir: './e2e',
      timeout: 30_000,
      expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.02 } },
      snapshotDir: './e2e/__baselines__',
      snapshotPathTemplate: '{snapshotDir}/{arg}{ext}',
      use: { baseURL: 'http://localhost:5173', headless: true },
      webServer: {
        command: 'npm run dev',
        port: 5173,
        reuseExistingServer: true,
        timeout: 60_000,
      },
      projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
    })
    ```

    Create `frontend/src/components/canvas/__smoke__/CanvasRadixOverlaySmoke.tsx` (verbatim from RESEARCH §Example 7):
    ```tsx
    import { Stage, Layer, Rect } from 'react-konva'
    import { Card, Text, Flex, Checkbox } from '@radix-ui/themes'

    export function CanvasRadixOverlaySmoke() {
      return (
        <div data-testid="smoke-root" style={{ position: 'relative', width: 800, height: 600 }}>
          <Stage width={800} height={600}>
            <Layer>
              <Rect x={0} y={0} width={800} height={600} fill="#ff00ff" />
            </Layer>
          </Stage>
          <Card
            data-testid="smoke-card"
            variant="surface"
            style={{ position: 'absolute', top: 12, left: 12, width: 200 }}
          >
            <Flex direction="column" gap="2">
              <Text size="2" weight="bold">Layers</Text>
              <Flex align="center" gap="2"><Checkbox defaultChecked /><Text size="2">Terrain</Text></Flex>
              <Flex align="center" gap="2"><Checkbox defaultChecked /><Text size="2">Territories</Text></Flex>
            </Flex>
          </Card>
        </div>
      )
    }
    ```

    Add DEV-only route `/canvas-smoke` in `frontend/src/App.tsx`:
    ```tsx
    import { CanvasRadixOverlaySmoke } from './components/canvas/__smoke__/CanvasRadixOverlaySmoke'
    // inside <Routes>:
    {import.meta.env.DEV && (
      <Route path="/canvas-smoke" element={<CanvasRadixOverlaySmoke />} />
    )}
    ```

    Create `frontend/e2e/smoke-tailwind-radix.spec.ts` (layered gates: visual → pixel → computed-style):
    ```ts
    import { test, expect } from '@playwright/test'
    import { PNG } from 'pngjs'

    // RESEARCH §Pitfall 2: Tailwind v4 + Radix transparency (GitHub #17137).
    //
    // NEGATIVE CONTROL (manual, not in CI):
    //   Edit frontend/src/index.css to swap import order so '@import "tailwindcss"' comes
    //   BEFORE '@import "@radix-ui/themes/styles.css"'. The visual-regression gate below
    //   MUST fail (card becomes transparent, magenta Stage shows through).

    test('Radix Card stays opaque over Konva Stage — visual regression + pixel sample', async ({ page }) => {
      await page.goto('/canvas-smoke')
      const card = page.getByTestId('smoke-card')
      await expect(card).toBeVisible()

      // PRIMARY gate: full-viewport screenshot diffed against committed baseline.
      // Baseline file: e2e/__baselines__/canvas-radix-overlay.png (committed).
      // Generate initially with: npm run test:e2e:update
      await expect(page).toHaveScreenshot('canvas-radix-overlay.png', { maxDiffPixelRatio: 0.02 })

      // SECONDARY gate: clip a screenshot of the card and read the center RGB from
      // the PNG pixel buffer — deterministic across browsers.
      const box = await card.boundingBox()
      if (!box) throw new Error('card bounding box unavailable')
      const buf = await page.screenshot({ clip: box, type: 'png' })
      const png = PNG.sync.read(buf)
      const cx = Math.floor(png.width / 2)
      const cy = Math.floor(png.height / 2)
      const idx = (png.width * cy + cx) << 2
      const [r, g, b, a] = [png.data[idx], png.data[idx + 1], png.data[idx + 2], png.data[idx + 3]]

      expect(a).toBeGreaterThan(200)                                   // opaque
      const isMagenta = r > 240 && g < 16 && b > 240                   // Stage fill bleed-through
      expect(isMagenta).toBe(false)

      // TERTIARY diagnostic: if the above fails, the computed-style check narrows
      // the cause (Radix Card rule overridden vs. layer ordering vs. z-index).
      const bgAlphaOk = await page.evaluate(() => {
        const el = document.querySelector('[data-testid="smoke-card"]') as HTMLElement
        const bg = getComputedStyle(el).backgroundColor
        // "rgba(r,g,b,0)" is the smoking gun for Pitfall 2.
        const m = /^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/.exec(bg)
        if (!m) return true
        const alpha = m[4] !== undefined ? parseFloat(m[4]) : 1
        return alpha > 0.8
      })
      expect(bgAlphaOk).toBe(true)
    })
    ```

    Commit a baseline `frontend/e2e/__baselines__/canvas-radix-overlay.png` by running `npm run test:e2e:update` once on a clean known-good index.css, then checking in the produced file.

    Run:
    ```bash
    cd frontend && npm run test -- --run
    cd frontend && npm run test:e2e -- smoke-tailwind-radix.spec.ts
    ```
  </action>
  <verify>
    <automated>cd frontend && npm run test -- --run && npm run test:e2e -- smoke-tailwind-radix.spec.ts</automated>
  </verify>
  <acceptance_criteria>
    - `frontend/package.json` lists `"konva": "^10"`, `"react-konva": "^19"` in `dependencies`
    - `frontend/package.json` lists `"vitest"`, `"@playwright/test"`, `"@testing-library/react"`, `"@testing-library/jest-dom"`, `"jsdom"`, `"pngjs"` in `devDependencies`
    - `frontend/package.json` scripts include `"test": "vitest"`, `"test:e2e": "playwright test"`, and `"test:e2e:update": "playwright test --update-snapshots"`
    - `frontend/e2e/smoke-tailwind-radix.spec.ts` contains `toHaveScreenshot('canvas-radix-overlay.png'` (primary gate) AND uses `pngjs` to sample a center-pixel RGB (secondary gate)
    - `frontend/e2e/__baselines__/canvas-radix-overlay.png` exists and is committed
    - `frontend/playwright.config.ts` configures `snapshotDir: './e2e/__baselines__'` and `toHaveScreenshot.maxDiffPixelRatio <= 0.02`
    - `cd frontend && npm run test:e2e -- smoke-tailwind-radix.spec.ts` exits 0
    - `npm install` output does NOT contain peer-dep errors and `--legacy-peer-deps` is NOT used
  </acceptance_criteria>
  <done>Wave 0 test infra in place. Vitest runs in jsdom. The Playwright smoke has a proper visual-regression gate (toHaveScreenshot) as the primary check, a pngjs pixel sample as the secondary check, and a computed-style proxy kept only as a tertiary diagnostic. Pitfall 2 is caught before plan 2.2/2.3 add Radix-heavy UI on top of the canvas.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Projection module + Zustand UI slice + ProjectionContext + artifact hooks</name>
  <files>
    frontend/src/lib/projection.ts (NEW),
    frontend/src/lib/projection.test.ts (NEW),
    frontend/src/stores/uiStore.ts (NEW),
    frontend/src/stores/uiStore.test.ts (NEW),
    frontend/src/context/ProjectionContext.tsx (NEW),
    frontend/src/hooks/useCanvasArtifacts.ts (NEW)
  </files>
  <read_first>
    - inicio/map_generator.py lines 140–175 (geo_to_pixel / pixel_to_geo — projection math to port verbatim)
    - inicio/map_generator.py lines 680–726 (territory_metadata.json shape — what `useCanvasArtifacts` parses)
    - frontend/src/api/client.ts (existing TanStack Query + fetch patterns)
    - frontend/src/main.tsx (QueryClient config)
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pattern 1 (projection), §Pattern 7 (Zustand slice), §Example 5 (useCanvasArtifacts hook)
    - .planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md D-01, D-02, D-06, D-09, D-13
  </read_first>
  <behavior>
    - Test 1 (projection): For 1000 random `(lon, lat)` in the Iberia bbox, `canvasToGeo(geoToCanvas(lon, lat, cfg), cfg)` returns `(lon±1e-9, lat±1e-9)`.
    - Test 2 (projection): For 1000 random `(px, py)` in `[0, mapW] × [0, mapH]`, `geoToCanvas(canvasToGeo(px, py, cfg), cfg)` returns `(px±1e-6, py±1e-6)`.
    - Test 3 (projection): `geoRingToKonvaPoints(ring, cfg).length === ring.length * 2`.
    - Test 4 (projection): `buildProjectionConfig(...).lonScale` matches the expected cosine.
    - Test 5 (projection): `computeFitToView(...)` returns sane values.
    - Test 6 (uiStore): default state matches D-09; `selectedTerritoryId` is `null`.
    - Test 7 (uiStore): `select` + `toggleLayer` work as expected.
  </behavior>
  <action>
    Create `frontend/src/lib/projection.ts`:

    ```ts
    /**
     * Affine projection mirroring inicio/map_generator.py geo_to_pixel / pixel_to_geo.
     * Sub-pixel floats are PRESERVED (unlike Python's int(...) cast). RESEARCH §Pattern 1.
     */
    export interface ProjectionConfig {
      lonMin: number; lonMax: number
      latMin: number; latMax: number
      mapW: number;   mapH: number
      lonScale: number
    }

    export function buildProjectionConfig(
      bounds: { lonMin: number; lonMax: number; latMin: number; latMax: number },
      mapW: number, mapH: number,
    ): ProjectionConfig {
      const centerLat = (bounds.latMin + bounds.latMax) / 2
      const lonScale = Math.cos((centerLat * Math.PI) / 180)
      return { ...bounds, mapW, mapH, lonScale }
    }

    export function geoToCanvas(lon: number, lat: number, c: ProjectionConfig): [number, number] {
      const span = (c.lonMax - c.lonMin) * c.lonScale
      const x = ((lon - c.lonMin) * c.lonScale / span) * c.mapW
      const y = (1 - (lat - c.latMin) / (c.latMax - c.latMin)) * c.mapH
      return [x, y]
    }

    export function canvasToGeo(x: number, y: number, c: ProjectionConfig): [number, number] {
      const span = (c.lonMax - c.lonMin) * c.lonScale
      const lon = (x / c.mapW) * span / c.lonScale + c.lonMin
      const lat = c.latMax - (y / c.mapH) * (c.latMax - c.latMin)
      return [lon, lat]
    }

    export function geoRingToKonvaPoints(ring: [number, number][], c: ProjectionConfig): number[] {
      const out = new Array<number>(ring.length * 2)
      for (let i = 0; i < ring.length; i++) {
        const [x, y] = geoToCanvas(ring[i][0], ring[i][1], c)
        out[2 * i] = x; out[2 * i + 1] = y
      }
      return out
    }

    export function computeFitToView(
      bboxMapW: number, bboxMapH: number,
      viewportW: number, viewportH: number,
      paddingPct = 0.05,
    ): { scale: number; x: number; y: number } {
      const usableW = viewportW * (1 - paddingPct)
      const usableH = viewportH * (1 - paddingPct)
      const scale = Math.min(usableW / bboxMapW, usableH / bboxMapH)
      const x = (viewportW - bboxMapW * scale) / 2
      const y = (viewportH - bboxMapH * scale) / 2
      return { scale, x, y }
    }
    ```

    Create `frontend/src/lib/projection.test.ts` (tests unchanged from prior revision — round-trip, fit-to-view, ring length).

    Create `frontend/src/stores/uiStore.ts` (unchanged — D-09 defaults, select, toggleLayer).
    Create `frontend/src/stores/uiStore.test.ts` (unchanged).
    Create `frontend/src/context/ProjectionContext.tsx` (unchanged — ProjectionProvider + useProjection).

    Create `frontend/src/hooks/useCanvasArtifacts.ts` — NOW FETCHES BARONIES TOO. **Important TerritoryMetadataCondado change**: `neighbors` is typed as REQUIRED `string[]` (not optional) because plan 2.1 Task 1 emits it now. Comment the upstream origin:

    ```ts
    import { useQueries } from '@tanstack/react-query'
    import { geoRingToKonvaPoints, type ProjectionConfig } from '../lib/projection'

    export interface TerritoryRender {
      id: string
      name: string
      points: number[]
      neighbors: string[]
    }

    export interface BaronyRender {
      id: string
      name: string
      condado_id: string
      fill: string
      points: number[]
    }

    export interface TerritoryMetadataCondado {
      id: string
      name: string
      lon: number
      lat: number
      duchy: string
      kingdom: string
      pixel_center: [number, number]
      pixel_count: number
      baronies: string[]
      // neighbors is populated by Task 1 territories.geojson emission (we hoist it onto the
      // condado record client-side when we merge territories.geojson with metadata); always
      // string[] for Phase 2 condados, never undefined.
      neighbors: string[]
    }

    export interface TerritoryMetadata {
      region: string
      map_size: [number, number]
      bounds: { lon_min: number; lon_max: number; lat_min: number; lat_max: number }
      kingdoms: Record<string, string>
      duchies: Record<string, { kingdom: string; name: string }>
      condados: TerritoryMetadataCondado[]
      baronies: Array<{ name: string; condado_idx: number; duchy: string; pixel_count: number }>
    }

    interface CondadoFeature {
      type: 'Feature'; id: string
      geometry: { type: 'Polygon'; coordinates: [number, number][][] }
              | { type: 'MultiPolygon'; coordinates: [number, number][][][] }
      properties: { id: string; name: string; neighbors: string[] }
    }
    interface BaronyFeature {
      type: 'Feature'; id: string
      geometry: { type: 'Polygon'; coordinates: [number, number][][] }
              | { type: 'MultiPolygon'; coordinates: [number, number][][][] }
      properties: { id: string; name: string; condado_id: string; fill: string }
    }
    interface FC<F> { type: 'FeatureCollection'; features: F[] }

    async function fetchJson<T>(url: string): Promise<T> {
      const res = await fetch(url)
      if (!res.ok) {
        if (res.status === 404) throw new Error('MAP_NOT_GENERATED')
        throw new Error('FETCH_FAILED')
      }
      return res.json() as Promise<T>
    }

    function firstOuterRing(
      g: CondadoFeature['geometry'] | BaronyFeature['geometry'],
    ): [number, number][] {
      return g.type === 'Polygon' ? g.coordinates[0] : g.coordinates[0][0]
    }

    export function useCanvasArtifacts(projectId: string | undefined, projection: ProjectionConfig | null) {
      return useQueries({
        queries: [
          { // [0] territories.geojson → TerritoryRender[]
            queryKey: ['territories-geojson', projectId] as const,
            queryFn: () => fetchJson<FC<CondadoFeature>>(`/api/projects/${projectId}/preview/territories.geojson`),
            enabled: Boolean(projectId && projection),
            staleTime: Infinity, gcTime: Infinity,
            select: (raw): TerritoryRender[] => {
              if (!projection) return []
              return raw.features.map((f) => ({
                id: f.properties.id,
                name: f.properties.name,
                points: geoRingToKonvaPoints(firstOuterRing(f.geometry), projection),
                neighbors: f.properties.neighbors,
              }))
            },
          },
          { // [1] baronies.geojson → BaronyRender[]
            queryKey: ['baronies-geojson', projectId] as const,
            queryFn: () => fetchJson<FC<BaronyFeature>>(`/api/projects/${projectId}/preview/baronies.geojson`),
            enabled: Boolean(projectId && projection),
            staleTime: Infinity, gcTime: Infinity,
            select: (raw): BaronyRender[] => {
              if (!projection) return []
              return raw.features.map((f) => ({
                id: f.properties.id,
                name: f.properties.name,
                condado_id: f.properties.condado_id,
                fill: f.properties.fill,
                points: geoRingToKonvaPoints(firstOuterRing(f.geometry), projection),
              }))
            },
          },
          { // [2] lookup_condado_colors.json
            queryKey: ['condado-colors', projectId] as const,
            queryFn: () => fetchJson<Record<string, string>>(`/api/projects/${projectId}/preview/lookup_condado_colors.json`),
            enabled: Boolean(projectId), staleTime: Infinity, gcTime: Infinity,
          },
          { // [3] lookup_barony_colors.json (kept for fallback display paths)
            queryKey: ['barony-colors', projectId] as const,
            queryFn: () => fetchJson<Record<string, string>>(`/api/projects/${projectId}/preview/lookup_barony_colors.json`),
            enabled: Boolean(projectId), staleTime: Infinity, gcTime: Infinity,
          },
          { // [4] territory_metadata.json
            queryKey: ['territory-metadata', projectId] as const,
            queryFn: () => fetchJson<TerritoryMetadata>(`/api/projects/${projectId}/preview/territory_metadata.json`),
            enabled: Boolean(projectId), staleTime: Infinity, gcTime: Infinity,
          },
        ],
      })
    }
    ```

    **Consumer migration note for plans 2.2 and 2.3:** `useCanvasArtifacts` now returns a 5-tuple (territories, baronies, condadoColors, baronyColors, metadata). Plan 2.2 Task 3 destructures accordingly. Plan 2.3 Task 3 already uses array index `[0]`, `[3]` for meta — update to the new indices `[0]` territories, `[4]` metadata.

    Run: `cd frontend && npm run test -- --run`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- projection.test.ts uiStore.test.ts --run</automated>
  </verify>
  <acceptance_criteria>
    - `frontend/src/lib/projection.ts` exports the full set listed in `must_haves.artifacts`
    - `grep -n "int(" frontend/src/lib/projection.ts` returns 0 matches
    - `grep -n "neighbors: string\[\]" frontend/src/hooks/useCanvasArtifacts.ts` returns at least 2 matches (TerritoryRender + TerritoryMetadataCondado) AND `grep -n "neighbors\\?: string\[\]" frontend/src/hooks/useCanvasArtifacts.ts` returns 0 matches (required, not optional)
    - `grep -n "preview/baronies.geojson" frontend/src/hooks/useCanvasArtifacts.ts` returns a match
    - `grep -n "BaronyRender" frontend/src/hooks/useCanvasArtifacts.ts` returns matches (export + usage)
    - `cd frontend && npm run test -- projection.test.ts uiStore.test.ts --run` exits 0
  </acceptance_criteria>
  <done>Projection math round-trips within 1e-9; Zustand slice has the exact shape downstream plans consume; useCanvasArtifacts fetches BOTH condado and barony GeoJSONs and exposes `BaronyRender`; `neighbors` is a required `string[]` so downstream code never guards against undefined.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Mount CanvasViewer + BackgroundLayer inside ProjectDetail</name>
  <files>
    frontend/src/components/canvas/CanvasViewer.tsx (NEW),
    frontend/src/components/canvas/BackgroundLayer.tsx (NEW),
    frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx (NEW),
    frontend/src/pages/ProjectDetail.tsx (MODIFY — add canvas region for status in {generated, exported})
  </files>
  <read_first>
    - frontend/src/pages/ProjectDetail.tsx
    - frontend/src/api/client.ts
    - frontend/src/lib/projection.ts (Task 3)
    - frontend/src/context/ProjectionContext.tsx (Task 3)
    - frontend/src/hooks/useCanvasArtifacts.ts (Task 3 — note 5-tuple shape)
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Layout Architecture, §Konva Stage Architecture, §States and Transitions
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pattern 2, §Pitfall 1, §Pitfall 6
  </read_first>
  <behavior>
    - Test 1: When `status === 'generated'`, CanvasViewer mounts a `<Stage>` and a `<BackgroundLayer>` and renders without throwing.
    - Test 2: Loading state → "Loading map…".
    - Test 3: 404 error → "No map generated yet. Run the pipeline first."
    - Test 4: Other error → "Failed to load territory data. Check the server is running."
    - Test 5: BackgroundLayer has `listening={false}`.
    - Test 6: `<Stage>` has exactly ONE Layer in Task 4 (Background).
  </behavior>
  <action>
    Create `frontend/src/components/canvas/BackgroundLayer.tsx` (unchanged from prior version).

    Create `frontend/src/components/canvas/CanvasViewer.tsx` — update the destructure to match new 5-tuple:
    ```tsx
    // After calling const artifacts = useCanvasArtifacts(projectId, projection):
    const [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ] = artifacts
    // Plan 2.1 uses only metaQ for gating; plans 2.2/2.3 consume the rest.
    void territoriesQ; void baroniesQ; void condadoColorsQ; void baronyColorsQ
    ```

    Preserve all prior plan 2.1 structure: fetch metadata first with projection=null, build projection, then the Stage with BackgroundLayer. Modify ProjectDetail.tsx to mount CanvasViewer conditionally inside a fixed 600px Box (plan 2.2 replaces with full two-region layout). Keep tests aligned to the 5-tuple indexing.

    Update test mock fetch handler to include a `baronies.geojson` case returning `{ type: 'FeatureCollection', features: [] }` so no pending query stalls the `isPending` gate.

    Run: `cd frontend && npm run test -- CanvasViewer.test.tsx --run`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- CanvasViewer.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `frontend/src/components/canvas/CanvasViewer.tsx` imports `Stage` from `react-konva` and `ProjectionProvider`
    - `frontend/src/components/canvas/BackgroundLayer.tsx` contains `listening={false}` exactly once
    - `grep -c "TerritoryLayer\\|BaronyLayer\\|DecorationsLayer\\|InteractionLayer" frontend/src/components/canvas/CanvasViewer.tsx` returns 0 (those land in 2.2/2.3 — comments allowed but no imports)
    - `frontend/src/pages/ProjectDetail.tsx` imports and conditionally renders `<CanvasViewer>` for `status === 'generated' || status === 'exported'`
    - `cd frontend && npm run test -- CanvasViewer.test.tsx --run` exits 0
    - `cd frontend && npm run build` exits 0
  </acceptance_criteria>
  <done>`/projects/:id` renders a Konva Stage with terrain PNG. All 5 artifact queries (condados, baronies, 2 color lookups, metadata) resolve via TanStack Query. Error, loading, and not-generated states match UI-SPEC. Downstream layers are the plan 2.2 seam.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| frontend → FastAPI `/api/projects/{id}/preview/{filename}` | Untrusted `project_id` + `filename` cross into a file-serving route |
| generator.run_generation → filesystem | Writes `territories.geojson` + `baronies.geojson` into `~/.medieval-forge/projects/{uuid}/generated/` |
| browser → territories.geojson + baronies.geojson | Parsed as JSON into React state; rendered as Konva Line points |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01-01 | Tampering (path traversal) | `/api/projects/{id}/preview/{territories,baronies}.geojson` | mitigate | `is_valid_uuid(project_id)` + whitelist check. Task 1 appends both new filenames. No new route. |
| T-02-01-02 | Tampering (path traversal) | `build_*_geojson(project_id, ...)` | mitigate | `project_dir()` raises `ValueError` on bad UUID. Tested. |
| T-02-01-03 | Information disclosure | Generator exception paths | mitigate | generator.py `try/except` logs but does not fail the pipeline or expose internal paths to the client. |
| T-02-01-04 | DoS (generation time inflation) | rasterio.features.shapes + STRtree called twice (condados + baronies) | accept | Iberia scale (91 condados + ~200 baronies) is still milliseconds. |
| T-02-01-05 | Tampering (XSS via name/fill) | `fill` field in baronies.geojson is a color string from generator | accept | React auto-escapes; Konva uses `fill` as a color only (not as HTML). |
| T-02-01-06 | Tampering (configuration correctness — V14) | `frontend/src/index.css` Radix-before-Tailwind ordering | mitigate | Task 2 Playwright toHaveScreenshot visual regression + pngjs pixel sample both enforce. |
| T-02-01-07 | Spoofing (cross-project artifact read) | Frontend hands `projectId` from URL | accept | Single-user local tool. |
</threat_model>

<verification>
Plan-level checks after all 4 tasks complete:

1. `cd backend && pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py -q` → 5+ tests pass (Task 1)
2. `cd frontend && npm run test -- --run` → projection + uiStore + CanvasViewer green (Tasks 3, 4)
3. `cd frontend && npm run test:e2e -- smoke-tailwind-radix.spec.ts` → visual-regression + pngjs sample pass (Task 2)
4. `cd frontend && npm run build` → TypeScript compiles (all tasks)
5. Manual end-to-end: open a generated Iberia project → terrain PNG appears in a dark canvas, no console errors, `GET /api/projects/{id}/preview/baronies.geojson` returns 200
</verification>

<success_criteria>
Plan 2.1 is complete when:
- [ ] `territories.geojson` AND `baronies.geojson` are generated alongside PNGs on every `run_generation` and served by the existing `/preview/{filename}` whitelist route
- [ ] Vitest + Playwright test infrastructure installed; Pitfall 2 visual regression passes against a committed baseline PNG with a pngjs center-pixel RGB assertion as the secondary gate
- [ ] Projection math round-trips within 1e-9°
- [ ] Zustand `useUIStore` has the D-09 shape
- [ ] `useCanvasArtifacts` loads 5 artifacts (territories, baronies, condado-colors, barony-colors, metadata) with `staleTime: Infinity`; exports `BaronyRender`; `neighbors` on `TerritoryRender` + `TerritoryMetadataCondado` is required `string[]`
- [ ] `CanvasViewer` renders `<Stage>` + `<BackgroundLayer listening={false}>` in `/projects/:id`
- [ ] `konva` + `react-konva` installed without `--legacy-peer-deps`
- [ ] `inicio/map_generator.py` is UNCHANGED (vendored black-box constraint respected)
- [ ] All task acceptance_criteria satisfied
</success_criteria>

<output>
After completion, create `.planning/phases/02-read-only-canvas-viewer/02-01-SUMMARY.md` summarizing:
- `territories.geojson` + `baronies.geojson` read-back pipeline (via lookup PNGs + color JSONs)
- Contract exports from `projection.ts`, `uiStore.ts`, `ProjectionContext.tsx`, `useCanvasArtifacts.ts` (5-tuple shape)
- Vitest + Playwright commands + visual-regression baseline location
- Any deviations from UI-SPEC or CONTEXT
- Note the fixed 600px Box in ProjectDetail to be replaced by plan 2.2's two-region layout
</output>
</content>
</invoke>