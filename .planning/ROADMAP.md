# Roadmap: Medieval Forge v1.0

## Overview

Six phases take Medieval Forge from zero to a fully validated, Unity-ready map pipeline. Phase 1 lays the data and packaging foundation — the complete backend can be exercised headlessly before any UI exists. Phase 2 adds the read-only canvas so projections and layer architecture are proven stable before mutation is introduced. Phase 3 (LLM research) runs sequentially after Phase 2 but has no canvas dependency, so it can be developed in parallel if bandwidth allows. Phases 4 and 5 build canvas editing in two tiers: basic operations and undo infrastructure first, then advanced topology operations on top. Phase 6 closes the loop with the pre-export validation gate that is Medieval Forge's core competitive differentiator.

## Phases

- [ ] **Phase 1: Data Pipeline + Backend Scaffold** — Working CLI, project CRUD, Wikidata/OSM ingestion, headless map generation, SQLite persistence, basic Unity ZIP export
- [ ] **Phase 2: Read-Only Canvas Viewer** — Interactive Konva canvas with pan/zoom, territory polygons, layer toggles, click-to-inspect, fit-to-view
- [ ] **Phase 3: LLM Research Integration** — Claude API + Ollama adapter, SSE streaming, schema validation + retry, per-project cache
- [ ] **Phase 4: Canvas Editing — Basic** — Capital drag + Voronoi recalc <500ms, territory merge, undo/redo 50-step with partialize+diff
- [ ] **Phase 5: Canvas Editing — Advanced** — Territory split by cut line, border vertex drag, terrain paint brush with land mask
- [ ] **Phase 6: Validation Gate + Export Polish** — Pre-export validation UI, blocked export on errors, full 12-file Unity ZIP with lookup PNGs

## Phase Details

### Phase 1: Data Pipeline + Backend Scaffold
**Goal**: User can install Medieval Forge, start the server, create a project, ingest real geographic data, trigger headless map generation, and receive a Unity-ready ZIP — all without touching the canvas.
**Depends on**: Nothing (first phase)
**Requirements**: PROJ-01, PROJ-02, PROJ-03, PROJ-04, PROJ-05, INGEST-01, INGEST-02, INGEST-03, INGEST-04, GEN-01, GEN-02, GEN-03, GEN-04, PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, EXPORT-01, EXPORT-02
**UI hint**: no

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
- **1.1** Project scaffold + packaging seam — pyproject.toml, Vite config (`base: "./"`), FastAPI static SPA serving, `medieval-forge` CLI entry point, aiosqlite pin, Alembic async env.py
- **1.2** SQLite schema + project CRUD — SQLAlchemy models, Alembic migration, PROJ-01..05 FastAPI routes + Pydantic schemas
- **1.3** Data ingestion pipeline — Wikidata SPARQL paginated client (INGEST-01), OSM Overpass fallback (INGEST-02), GeoJSON storage (INGEST-03), SSE progress stream (INGEST-04)
- **1.4** Map generation wrapper — verify `map_generator.py` importability, `services/generator.py` thin wrapper, BackgroundTask generation endpoint, PNG preview FileResponse (GEN-01..04)
- **1.5** Basic export — Unity ZIP assembly with 12 files (EXPORT-01, EXPORT-02), headless validation stub

---

### Phase 2: Read-Only Canvas Viewer
**Goal**: User can open a generated project and explore all territories on an interactive canvas — pan, zoom, click to inspect, toggle layers — with pixel-accurate polygon rendering and no editing capability yet.
**Depends on**: Phase 1
**Requirements**: CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06
**UI hint**: yes

### Success Criteria
1. User can see all territory polygons rendered on the Konva canvas with correct hierarchy colors and visible borders matching the generated GeoJSON data.
2. User can pan the canvas by dragging and zoom with the mouse wheel; polygons remain pixel-aligned and do not re-project on zoom.
3. User can click any territory and see its name, type, and hierarchy properties appear in the right-side panel.
4. User can toggle each layer (terrain, territories, borders, capitals, labels) on and off independently; labels only appear at appropriate zoom levels.
5. User can press a "Fit to view" button and the canvas resets to show the full map centered in the viewport.

### Plans
- **2.1** Projection module + Konva scaffold — `lib/projection.ts` (`geoToCanvas` / `canvasToGeo` / `geoRingToKonvaPoints`), ProjectionConfig React context, 3-layer Konva Stage (background `listening=false`, territories, interaction), round-trip unit tests
- **2.2** Territory rendering + layer toggles — territory polygon components with `React.memo` geometry comparator, hierarchy color-coding, capitals layer, layer toggle panel (CANVAS-01, CANVAS-04)
- **2.3** Interaction + inspector panel — pan/zoom with wheel handler (CANVAS-02), click-to-select with properties panel (CANVAS-03), territory labels at zoom threshold (CANVAS-05), fit-to-view (CANVAS-06)

---

### Phase 3: LLM Research Integration
**Goal**: User can trigger historical research from inside a project and receive structured kingdoms/duchies/counties/baronies JSON assigned to territories, with progress feedback, caching, and automatic retry on invalid responses.
**Depends on**: Phase 1
**Requirements**: RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-04, RESEARCH-05
**UI hint**: yes

**Note**: No canvas dependency. Can be developed in parallel with Phase 2 if bandwidth allows. Develops against Phase 1 API contracts only.

### Success Criteria
1. User can open the research dialog, enter a country and period, select Claude API as the provider, and receive a structured political hierarchy response that is persisted to the project.
2. User can switch to Ollama as the LLM provider and trigger research using a locally running model with the same structured output format.
3. When the LLM returns malformed JSON, the system automatically retries up to 3 times with corrective prompting before surfacing an error to the user.
4. Triggering research on the same country+period a second time returns the cached result instantly without making a new API call.
5. The research dialog shows a spinner and streaming progress tokens while the LLM is responding; the UI does not freeze.

### Plans
- **3.1** LLM service layer — `services/llm.py` unified adapter interface, Claude async streaming client (Anthropic SDK 0.94.1), Ollama REST adapter (`stream: false`, `format: "json"`), Pydantic schema with `extra=forbid`, 3-retry validation loop (RESEARCH-01, RESEARCH-02, RESEARCH-03)
- **3.2** Research API + cache — `api/research.py` SSE endpoint, per-project result cache in SQLite, QID normalization, `zundo temporal.pause/resume` wrapping to prevent LLM polling from creating undo steps (RESEARCH-04)
- **3.3** Research UI — research trigger dialog, SSE token stream display, spinner/progress, provider selector, cached result display (RESEARCH-05)

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

### Plans
- **5.1** Terrain paint brush — brush tool Konva interaction, terrain type selector UI, `POST /api/edit/paint-terrain` with land mask guard, canvas re-render on terrain change (EDIT-05)
- **5.2** Reference overlay — file upload input, overlay Konva layer with opacity control, `useUIStore` opacity state (not undo-tracked), `clearCache()` on geometry change (EDIT-06)

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
| 2. Read-Only Canvas Viewer | 0/3 | Not started | - |
| 3. LLM Research Integration | 0/3 | Not started | - |
| 4. Canvas Editing — Basic | 0/4 | Not started | - |
| 5. Canvas Editing — Advanced | 0/2 | Not started | - |
| 6. Validation Gate + Export Polish | 0/3 | Not started | - |

---

## Requirement Coverage

**Total v1 requirements: 48**
**Mapped: 48/48**

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
*Created: 2026-04-16*
