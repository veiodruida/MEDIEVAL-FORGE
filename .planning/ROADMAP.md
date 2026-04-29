# Roadmap: Medieval Forge v1.0

## Overview

Six phases take Medieval Forge from zero to a fully validated, Unity-ready map pipeline. Phase 1 lays the data and packaging foundation — the complete backend can be exercised headlessly before any UI exists. Phase 2 adds the read-only canvas so projections and layer architecture are proven stable before mutation is introduced. Phase 3 (LLM research) runs sequentially after Phase 2 but has no canvas dependency, so it can be developed in parallel if bandwidth allows. Phases 4 and 5 build canvas editing in two tiers: basic operations and undo infrastructure first, then advanced topology operations on top. Phase 6 closes the loop with the pre-export validation gate that is Medieval Forge's core competitive differentiator.

## Phases

- [ ] **Phase 1: Data Pipeline + Backend Scaffold** — Working CLI, project CRUD, Wikidata/OSM ingestion, headless map generation, SQLite persistence, basic Unity ZIP export
- [ ] **Phase 2: Read-Only Canvas Viewer** — Interactive Konva canvas with pan/zoom, territory polygons, layer toggles, click-to-inspect, fit-to-view
- [ ] **Phase 2.1: Extended Terrain Ingestion** — OSM rivers/peaks/coast via Overpass, HydroSHEDS basin polygons (vendored), Copernicus DEM 90m download + ridge derivation
- [ ] **Phase 2.2: Geometry-First Territories** — Constrained hierarchical clustering produces condados/duchies/kingdoms from geometry; generator decoupled from LLM; LLM research becomes political-paint-only
- [ ] **Phase 3: LLM Research Integration** — Claude API + Ollama adapter, SSE streaming, schema validation + retry, per-project cache (political paint only — geometry fixed by Phase 2.2)
- [ ] **Phase 4: Canvas Editing — Basic** — Capital drag + Voronoi recalc <500ms, territory merge, undo/redo 50-step with partialize+diff
- [ ] **Phase 5: Canvas Editing — Advanced** — Territory split by cut line, border vertex drag, terrain paint brush with land mask
- [ ] **Phase 6: Validation Gate + Export Polish** — Pre-export validation UI, blocked export on errors, full 12-file Unity ZIP with lookup PNGs

## Phase Details

### Phase 1: Data Pipeline + Backend Scaffold
**Goal**: User can install Medieval Forge, start the server, create a project, ingest real geographic data, trigger headless map generation, and receive a Unity-ready ZIP — all without touching the canvas.
**Depends on**: Nothing (first phase)
**Requirements**: PROJ-01, PROJ-02, PROJ-03, PROJ-04, PROJ-05, INGEST-01, INGEST-02, INGEST-03, INGEST-04, GEN-01, GEN-02, GEN-03, GEN-04, PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, EXPORT-01, EXPORT-02
**UI hint**: no
**Plans**: 5 plans

**Critical constraints resolved in this phase:**
- `vite.config.ts` must set `base: "./"` (absolute `/` breaks pip-packaged asset URLs)
- `aiosqlite>=0.20,<0.22` (v0.22.0 hanging thread regression — issue #13039)
- Alembic `env.py` must use `asyncio.run()` + `run_sync()` from day one (sync default produces empty migrations)
- Wikidata ingestion must paginate at 500-1000 items max (60s hard timeout on large countries)
- `map_generator.py` importability must be verified before building `generator.py` wrapper

### Success Criteria
1. `pip install medieval-forge` succeeds from a clean virtualenv and `medieval-forge start` opens the browser to the React SPA served by FastAPI.
2. User can create, list, open, update, and delete a project via the UI (all five project CRUD operations complete without error).
3. User can trigger Wikidata SPARQL ingestion for Spain (Q29) and see real-time progress feedback; raw GeoJSON is written to `raw/municipalities.geojson` and stored in SQLite.
4. User can trigger map generation from ingested data and view the three PNG previews (terrain, territories, borders) in the browser without downloading files.
5. User can download a Unity ZIP containing all 12 standardized files from a generated project.

### Plans
- [ ] `01-01-project-scaffold-packaging.md` — pyproject.toml, async FastAPI shell, Alembic async env.py, `medieval-forge` Click CLI (PKG-01..05), Wave 0 test scaffold
- [ ] `01-02-sqlite-schema-project-crud.md` — Project SQLAlchemy model + initial migration, 5 CRUD routes, Pydantic schemas, T-PATH `paths.py` guard, full minimal React SPA (Vite 6 + Tailwind v4 + Radix Themes + TanStack Query) with 3 pages (PROJ-01..05)
- [ ] `01-03-data-ingestion-pipeline.md` — Wikidata SPARQL paginated client + OSM Overpass fallback (T-SSRF guards), atomic GeoJSON write, asyncio.Queue/SSE progress endpoint, frontend Ingest button wired to streaming log panel (INGEST-01..04)
- [ ] `01-04-map-generation-wrapper.md` — Verbatim copy of map_generator.py into package, sys.modules territory injector (Pitfall 6), POST /generate BackgroundTask + status polling, GET /preview/{filename} with whitelist (T-PATH), 3 preview `<img>` tags + GEN-04 <60s slow assertion (GEN-01..04)
- [ ] `01-05-unity-export.md` — services/export.py with 12-file Unity spec + placeholder generator + MANIFEST.json, POST /export + GET /export/download FileResponse, frontend Export button + auto-download anchor (EXPORT-01, EXPORT-02)

---

### Phase 2: Read-Only Canvas Viewer
**Goal**: User can open a generated project and explore all territories on an interactive canvas — pan, zoom, click to inspect, toggle layers — with pixel-accurate polygon rendering and no editing capability yet.
**Depends on**: Phase 1
**Requirements**: CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06
**UI hint**: yes
**Plans:** 5 plans

### Success Criteria
1. User can see all territory polygons rendered on the Konva canvas with correct hierarchy colors and visible borders matching the generated GeoJSON data.
2. User can pan the canvas by dragging and zoom with the mouse wheel; polygons remain pixel-aligned and do not re-project on zoom.
3. User can click any territory and see its name, type, and hierarchy properties appear in the right-side panel.
4. User can toggle each layer (terrain, territories, borders, capitals, labels) on and off independently; labels only appear at appropriate zoom levels.
5. User can press a "Fit to view" button and the canvas resets to show the full map centered in the viewport.

### Plans
- [x] `02-01-projection-stage-scaffold-PLAN.md` — backend `territories.geojson` + neighbors emission (closes RESEARCH Open Questions 1 & 2), Wave-0 Vitest/Playwright infra + Tailwind-v4 + Radix Pitfall-2 smoke, projection module (`geoToCanvas` / `canvasToGeo` / `geoRingToKonvaPoints`), Zustand `useUIStore`, ProjectionContext, `useCanvasArtifacts`, Konva Stage + BackgroundLayer mounted in `/projects/:id` (CANVAS-01)
- [x] `02-02-territory-rendering-layer-toggles-PLAN.md` — React.memo `TerritoryPolygon`, `TerritoryLayer` driven by `lookup_condado_colors.json` with D-03 read-only contract, `BaronyLayer` fallback, floating Radix Card `LayerTogglePanel` with 5 checkboxes, UI-SPEC two-region layout in ProjectDetail (CANVAS-01, CANVAS-04)
- [x] `02-03-interaction-inspector-PLAN.md` — cursor-anchored wheel zoom + pan clamp + `dragBoundFunc`, Esc / Ctrl+0 keyboard hook, `DecorationsLayer` (capitals + labels gated at 2× minScale), `InteractionLayer` gold outline, `FitToViewButton`, `InspectorSidebar` (4 property groups + project overview + neighbor chips) (CANVAS-02, CANVAS-03, CANVAS-05, CANVAS-06)
- [x] `02-04-e2e-pipeline-fix-PLAN.md` — gap closure for G-01/G-02/G-03: adapter rewrite in `services/territories_geojson.py` + `services/baronies_geojson.py` for real `{"r,g,b": idx}` format, silent try/except removal in `_run_pipeline_sync`, `condado_colors.json`/`barony_colors.json` sidecar emission, [BLOCKING] integration test (CANVAS-01, CANVAS-03, CANVAS-04)
- [ ] `02-05-canvas-sizing-color-ux-fixes-PLAN.md` — gap closure for GAP-04/05/06/07/08: CanvasViewer ResizeObserver + viewport-relative ProjectDetail canvas region (keystone fix for Stage 800×600 bug), GAP-04 diagnose-then-fix decision tree (H1/H2/H3/H4), label threshold 1.5× + Radix Tooltip, InspectorSidebar ErrorBoundary (CANVAS-01..06)

---

### Phase 2.1: Extended Terrain Ingestion
**Goal**: The system can fetch all natural-boundary data needed for geometry-first territory construction — rivers, peaks, coastline, parishes, HydroSHEDS basin polygons, and DEM elevation raster — for any project bbox, storing each dataset as a GeoJSON or raster file in `raw/`. The Game Designer triggers each step from the UI pipeline panel and sees real-time progress.
**Depends on**: Phase 1
**Requirements**: GEO-01, GEO-02, GEO-03, GEO-04, GEO-05, GEO-06, GEO-07, GEO-08
**UI hint**: yes

### Success Criteria
1. After triggering "Ingestão alargada" for a Spain project, `raw/rivers.geojson`, `raw/topography.geojson`, `raw/coastline.geojson`, and `raw/parishes.geojson` are written with non-empty feature collections.
2. `raw/basins.geojson` is written containing HydroSHEDS level-6 basin polygons clipped to the project bbox (Iberia: at least Tejo, Douro, Guadalquivir basins visible).
3. `raw/dem.tif` is downloaded (Copernicus DEM 90m tiles) and mosaiced for the project bbox; `raw/ridges.geojson` is derived from it with at least one ridge polygon per major mountain range (Pyrenees, Sierra Nevada for Iberia).
4. Each ingestion step (rivers, terrain, HydroSHEDS, DEM+ridges) shows a live progress log in the UI pipeline panel; the step can be re-triggered independently without re-running the others.
5. All new `raw/*.geojson` files are valid FeatureCollections passable to `shapely.from_geojson()` without errors.

### Plans
- [ ] TBD — to be planned via `/gsd-plan-phase 2.1`

---

### Phase 2.2: Geometry-First Territories
**Goal**: Territory construction is driven entirely by geography — no LLM required. A new `territories_builder.py` clusters baronies into condados (~8–12 per condado), condados into duchies, and duchies into kingdoms using constrained hierarchical clustering that respects rivers, ridges, and HydroSHEDS basin divides. The generation pipeline reads these GeoJSON files directly and builds maps with placeholder names when no research exists. LLM research (Phase 3) is scoped to political-paint-only: it assigns names and ownership to geometrically-fixed territories, never creating or moving them.
**Depends on**: Phase 2.1
**Requirements**: TERR-01, TERR-02, TERR-03, TERR-04, TERR-05, TERR-06
**UI hint**: yes

**Critical constraints:**
- `AgglomerativeClustering` linkage must use adjacency matrix derived from `shapely.touches` + hard-infinite-distance for cross-river/cross-ridge pairs — not just centroid distance
- `territories_builder.build_all()` must be idempotent: re-running produces the same GeoJSON files without changing IDs (stable IDs required so LLM research patches don't become stale)
- Decoupling generator from LLM must NOT break existing projects that already have `territory_data` — migrate gracefully (read from GeoJSON if exists, fall back to `territory_data` in config)

### Success Criteria
1. Running `territories_builder.build_all('<iberia_project_id>')` produces `raw/condados.geojson` with 80–100 features, `raw/duchies.geojson` with 15–25 features, `raw/kingdoms.geojson` with 4–8 features — purely from geometry, with no LLM call.
2. Inspection of condado polygons confirms that none cross a principal river (any polygon in `raw/condados.geojson` does not intersect `raw/rivers.geojson` features classified `waterway=river`).
3. Map generation succeeds and renders the canvas with placeholder names (`"Condado_001"` etc.) when no LLM research has been run; `KeyError: 0` and similar hierarchy-mismatch errors do not occur.
4. After LLM research runs (Phase 3), the research response assigns names/owners to existing territory IDs — the condado polygon coordinates are unchanged by research; only `name` and `kingdom_owner` properties are updated.
5. Barony polygons in `raw/baronies.geojson` do not span principal rivers; visual inspection on the canvas shows river lines align with barony borders.

### Plans
- [ ] TBD — to be planned via `/gsd-plan-phase 2.2`

---

### Phase 3: LLM Research Integration
**Goal**: User can trigger historical research from inside a project and receive a structured kingdoms/duchies/counties/baronies JSON assigned to territories, using one of several LLM providers (Claude, OpenAI, Gemini, Ollama) via a plugin-style architecture that supports browser OAuth where available, local CLI piggyback for Claude, and API-key paste as fallback — with progress feedback, caching, and automatic retry on invalid responses.
**Depends on**: Phase 1, Phase 2.2
**Requirements**: RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-04, RESEARCH-05, RESEARCH-06, RESEARCH-07, RESEARCH-08, RESEARCH-09
**UI hint**: yes

**Note**: No canvas dependency. Scope expanded on 2026-04-20 to include OpenAI + Gemini providers, browser OAuth (Google), `claude-code` CLI auth piggyback, and a plugin architecture for future provider additions.

### Success Criteria
1. User can open the research dialog, enter a country and period, select any of the four built-in providers (Claude, OpenAI, Gemini, Ollama), and receive a structured political hierarchy response persisted to the project.
2. User can switch providers on a per-research basis; each provider uses its natural auth flow (Anthropic: env var / `claude-code` CLI / session key; Google: env var / OAuth / session key; OpenAI: env var / session key; Ollama: no auth).
3. When the LLM returns malformed JSON, the system automatically retries up to 3 times with corrective prompting before surfacing an error to the user; failure path allows manual JSON edit.
4. Triggering research on the same country+period+provider+model a second time returns the cached result instantly without making a new API call.
5. The research dialog shows a spinner (or streaming tokens where supported) while the LLM is responding; the UI does not freeze.
6. Adding a new LLM provider in the future requires only a new adapter class plus a registry entry — no core code or UI changes required.

**Plans:** 4 plans

### Plans
- [ ] `03-01-PLAN.md` — Multi-provider LLM adapter layer (services/llm/ package: base Protocol, registry, claude/openai/gemini/ollama modules, Pydantic schema with extra=forbid, 3-retry validation loop) (RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-06, RESEARCH-07, RESEARCH-09)
- [ ] `03-02-PLAN.md` — Auth layer (in-memory credential store on app.state, API-key endpoints, Google OAuth installed-app flow with PKCE + state TTL, claude-code CLI credential piggyback) (RESEARCH-08)
- [ ] `03-03-PLAN.md` — Research API + SQLite cache (POST /api/projects/{id}/research SSE, /api/llm/providers + /api/llm/health discovery endpoints, research_cache table created in lifespan, condado_id validation triggering retry on mismatch) (RESEARCH-04, RESEARCH-05)
- [ ] `03-04-PLAN.md` — Research UI (Radix Dialog + per-provider AuthSetupSheet auto-populated from /api/llm/providers, useResearchStream SSE hook, cached badge + force-refresh, failure recovery with manual JSON editor, ProjectDetail Pipeline tab integration) (RESEARCH-05)

---

### Phase 4: Canvas Editing — Basic
**Goal**: User can drag a capital marker to reshape Voronoi territories in under 500ms, merge adjacent territories into one, and undo/redo all operations with a 50-step history that groups compound side effects as single steps.
**Depends on**: Phase 2
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-07, EDIT-08
**UI hint**: yes

**Critical constraints resolved in this phase:**
- `zundo` must use `partialize` (exclude transient UI state) + `diff` (store changed keys only); full snapshots at 800 territories = 100-250MB — this is not a retrofit, it must be designed in at undo implementation time
- Voronoi adjacency lookup must be rebuilt from scratch after every merge (ridge_points indices shift after seed point removal)
- Each user action (e.g., capital drag + 6 neighbor Voronoi recalcs) must register as ONE undo step via `handleSet` batching

### Success Criteria
1. User can drag a capital marker and watch the affected neighbor territory polygons recalculate and re-render in under 500ms, with the new Voronoi geometry persisted to SQLite.
2. User can drag individual border vertices to reshape a territory polygon; the change is reflected immediately on canvas and saved to the project.
3. User can select two or more adjacent territories and merge them; the result is one polygon with preserved exterior topology and no orphaned interior boundaries.
4. User can press Ctrl+Z after a capital drag (which triggered multiple neighbor recalculations) and the entire compound operation is undone as a single step.
5. Undo/redo history supports 50 steps and browser memory usage does not grow unboundedly during a session with 800+ territories.

### Plans
- **4.1** Zustand store + zundo configuration — three slices: `useProjectStore` (zundo `temporal`, `partialize`, `diff`, `limit: 50`), `useEditorStore` (tool state, not tracked), `useUIStore` (panels, not tracked); compound action batching via `handleSet`
- **4.2** Voronoi recalc service — `services/voronoi.py` full scipy recompute + Shapely land-mask clip, neighbor filter via `ridge_points`, uuid-to-index map rebuilt per computation, `POST /api/edit/move-capital` endpoint (EDIT-01)
- **4.3** Border vertex drag + merge — vertex drag Konva interaction handles, `POST /api/edit/reshape-territory`, Shapely `unary_union` merge, adjacency rebuild post-merge, `POST /api/edit/merge` (EDIT-02, EDIT-03)
- **4.4** Split infrastructure + undo wiring — cut-line draw tool, Shapely boolean partition, `shapely.orient()` post-split, undo/redo keyboard bindings Ctrl+Z/Ctrl+Y, undo UI controls (EDIT-04, EDIT-07, EDIT-08)
- [ ] `04-11-PLAN.md` — gap closure: wire `useProjectStore.hydrate()` in CanvasViewer (data adapter + re-hydrate on projectId/cacheVersion) — closes UAT T1/T2/T4/T5 + primary T3 guard (EDIT-01, EDIT-02, EDIT-03, EDIT-07, EDIT-08)
- [ ] `04-12-PLAN.md` — gap closure: shift-click multi-select in territory click handler (toggles rubberBandSelectionIds in edit mode) — closes UAT T3 secondary (EDIT-03)

---

### Phase 5: Canvas Editing — Advanced
**Goal**: User can split a territory by drawing a cut line, drag individual border vertices, paint terrain types with a brush that respects the land mask, and upload a reference overlay with adjustable opacity.
**Depends on**: Phase 4
**Requirements**: EDIT-05, EDIT-06
**UI hint**: yes

**Note**: EDIT-02 (vertex drag) and EDIT-04 (split) infrastructure is built in Phase 4. Phase 5 completes the terrain and overlay features which are independent of the undo transaction model.

**Critical constraints resolved in this phase:**
- Always call `shapely.orient(geom, sign=1.0)` after any `set_precision()` call (winding order reversal not caught by `is_valid`)
- Terrain paint brush must check `if land[y,x]` before painting (prevents dark ocean pixels — known lesson from original workflow)
- Konva shape cache must be cleared (`clearCache()`) after geometry changes to prevent hit canvas desync

### Success Criteria
1. User can select the terrain paint brush, choose a terrain type (mountain, river, forest, plains, arid), paint strokes on the canvas, and see the terrain type change reflected immediately; ocean cells cannot be painted.
2. User can upload a reference image (SRTM/custom) and an opacity slider appears; adjusting the slider blends the overlay behind the territory polygons in real time.

**Plans:** 3 plans

### Plans
- [ ] `05-01-PLAN.md` — Foundation: TerrainType contract + useProjectStore terrain_types undo slice + uiStore overlay/terrain layer + useEditorStore brush state + paintTerrain API client + backend POST /api/edit/paint-terrain with land mask guard + GeoJSON terrain_type persistence + Wave 0 RED tests (EDIT-05, EDIT-06)
- [ ] `05-02-PLAN.md` — Terrain paint UI: TerrainBadgesLayer, EditToolbar paint controls (button + SegmentedControl + brush slider), CanvasViewer paint handlers + brush cursor + P shortcut + hydrate, LayerTogglePanel Terreno entry, TerritoryLayer terrain color mode (EDIT-05)
- [ ] `05-03-PLAN.md` — Reference overlay: TerrainOverlayLayer Konva Image, ReferenceOverlayPanel Card with file input + opacity slider + Remover, CanvasViewer mount between BackgroundLayer and TerritoryLayer (EDIT-06)

---

### Phase 6: Validation Gate + Export Polish
**Goal**: User cannot accidentally export a broken map — the system runs a full pre-export validation check, displays errors and warnings with territory highlights, blocks export on errors, and produces a complete 12-file Unity ZIP with correct lookup PNG encoding and coordinate system.
**Depends on**: Phase 5
**Requirements**: VALIDATE-01, VALIDATE-02, VALIDATE-03, VALIDATE-04, VALIDATE-05, VALIDATE-06, VALIDATE-07, EXPORT-03, EXPORT-04
**UI hint**: yes

**Critical constraints resolved in this phase:**
- Lookup PNG export must use NEAREST upscale (BICUBIC spreads border colors and breaks Unity shader)
- Land mask must be applied at 2x resolution AFTER upscale to avoid black ocean pixels
- `visual_*.png` is 3840x2160 — Unity PPU must be 200, not 100
- `pixel_center` in metadata is Y-down (numpy); Unity is Y-up — convert on export

### Success Criteria
1. User clicks "Export" and the system runs all five validation checks; orphan baronies, dark ocean pixels, territories without capitals, undersized territories, and hierarchy mismatches are all reported with error/warning severity.
2. When validation errors exist, the export button is disabled and the UI highlights the offending territories on the canvas; the user cannot download a broken ZIP.
3. User can override warnings (but not errors) and proceed to export; the ZIP downloads with all 12 standardized files in correct format.
4. The export dialog shows a pre-export validation summary and estimated file sizes before the user confirms the download.
5. Exported lookup PNGs use unique sequential RGB values per territory with NEAREST upscale, and `territory_metadata.json` contains Unity Y-up pixel centers.

### Plans
- **6.1** Validation service — `services/validator.py` with five typed checks (VALIDATE-01..05), structured error/warning response, `GET /api/validate` endpoint
- **6.2** Validation UI — validation results panel with severity badges, territory highlight overlay on canvas for offending territories, error vs. warning distinction (VALIDATE-06, VALIDATE-07)
- **6.3** Export polish — final PNG regeneration from current state (EXPORT-03), NEAREST upscale enforcement, land mask at 2x post-upscale, unique RGB assignment, Unity Y-up coordinate conversion, export dialog with validation summary + file size estimates (EXPORT-04)

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Pipeline + Backend Scaffold | 0/5 | Not started | - |
| 2. Read-Only Canvas Viewer | 4/5 | Gap closure planning (02-05) | - |
| 2.1 Extended Terrain Ingestion | 0/? | Not planned | - |
| 2.2 Geometry-First Territories | 0/? | Not planned | - |
| 3. LLM Research Integration | 0/4 | Not started | - |
| 4. Canvas Editing — Basic | 10/12 | Gap closure planning (04-11, 04-12) | - |
| 5. Canvas Editing — Advanced | 0/3 | Plans drafted | - |
| 6. Validation Gate + Export Polish | 0/3 | Not started | - |

---

## Requirement Coverage

**Total v1 requirements: 62**
**Mapped: 62/62**

| REQ-ID | Phase |
|--------|-------|
| PROJ-01 | Phase 1 |
| PROJ-02 | Phase 1 |
| PROJ-03 | Phase 1 |
| PROJ-04 | Phase 1 |
| PROJ-05 | Phase 1 |
| INGEST-01 | Phase 1 |
| INGEST-02 | Phase 1 |
| INGEST-03 | Phase 1 |
| INGEST-04 | Phase 1 |
| GEN-01 | Phase 1 |
| GEN-02 | Phase 1 |
| GEN-03 | Phase 1 |
| GEN-04 | Phase 1 |
| PKG-01 | Phase 1 |
| PKG-02 | Phase 1 |
| PKG-03 | Phase 1 |
| PKG-04 | Phase 1 |
| PKG-05 | Phase 1 |
| EXPORT-01 | Phase 1 |
| EXPORT-02 | Phase 1 |
| CANVAS-01 | Phase 2 |
| GEO-01 | Phase 2.1 |
| GEO-02 | Phase 2.1 |
| GEO-03 | Phase 2.1 |
| GEO-04 | Phase 2.1 |
| GEO-05 | Phase 2.1 |
| GEO-06 | Phase 2.1 |
| GEO-07 | Phase 2.1 |
| GEO-08 | Phase 2.1 |
| TERR-01 | Phase 2.2 |
| TERR-02 | Phase 2.2 |
| TERR-03 | Phase 2.2 |
| TERR-04 | Phase 2.2 |
| TERR-05 | Phase 2.2 |
| TERR-06 | Phase 2.2 |
| CANVAS-02 | Phase 2 |
| CANVAS-03 | Phase 2 |
| CANVAS-04 | Phase 2 |
| CANVAS-05 | Phase 2 |
| CANVAS-06 | Phase 2 |
| RESEARCH-01 | Phase 3 |
| RESEARCH-02 | Phase 3 |
| RESEARCH-03 | Phase 3 |
| RESEARCH-04 | Phase 3 |
| RESEARCH-05 | Phase 3 |
| RESEARCH-06 | Phase 3 |
| RESEARCH-07 | Phase 3 |
| RESEARCH-08 | Phase 3 |
| RESEARCH-09 | Phase 3 |
| EDIT-01 | Phase 4 |
| EDIT-02 | Phase 4 |
| EDIT-03 | Phase 4 |
| EDIT-04 | Phase 4 |
| EDIT-07 | Phase 4 |
| EDIT-08 | Phase 4 |
| EDIT-05 | Phase 5 |
| EDIT-06 | Phase 5 |
| VALIDATE-01 | Phase 6 |
| VALIDATE-02 | Phase 6 |
| VALIDATE-03 | Phase 6 |
| VALIDATE-04 | Phase 6 |
| VALIDATE-05 | Phase 6 |
| VALIDATE-06 | Phase 6 |
| VALIDATE-07 | Phase 6 |
| EXPORT-03 | Phase 6 |
| EXPORT-04 | Phase 6 |

---

## Backlog

Unsequenced ideas captured outside the active phase plan. Promote with `/gsd-review-backlog`.

### Phase 999.1: Output Resolution + Aspect Ratio Control (BACKLOG)

**Goal:** [Captured for future planning] Allow Game Designer to configure output resolution AND aspect ratio (1:1, 4:3, 16:9, 3:2, 9:16) for the generated map artifacts. Compatibility target: AI image generators upstream that produce maps in those ratios.

**Scope (3 layers):**
1. Internal Voronoi raster resolution (`map_w`/`map_h` in `map_generator.py` — affects polygon granularity)
2. Output PNG resolution (`terrain.png`, `lookup_condado.png`, `lookup_barony.png`, etc. — affects visual detail)
3. Unity export presets per platform (mobile / desktop / console)

**UI:** Named presets (Small / Medium / Large / Custom) + aspect-ratio dropdown + free numeric input fallback. Per-project setting, persisted in project metadata.

**Constraints:**
- Touches `backend/medieval_forge/lib/map_generator.py` — D-04 black-box must be renegotiated (current rule: do not modify; this feature breaks that rule).
- Also touches `services/generator.py`, `api/generate.py` (params), frontend project-creation UI.
- Likely needs new requirement(s) `EXPORT-05+` in REQUIREMENTS.md.

**Blocked by:** Phase 02 (canvas viewer) gap closure.

**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with `/gsd-review-backlog` when ready)

---
*Created: 2026-04-16*
