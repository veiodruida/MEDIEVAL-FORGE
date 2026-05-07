# Requirements — Medieval Forge v1.0

## v1 Requirements

### PROJ — Project Management
- [ ] **PROJ-01**: User can create a project (name, country, period start/end, bounding box, generator config)
- [ ] **PROJ-02**: User can list all existing projects
- [ ] **PROJ-03**: User can open an existing project and resume work
- [ ] **PROJ-04**: User can delete a project (with confirmation)
- [ ] **PROJ-05**: User can update project settings (name, config params) after creation

### INGEST — Data Ingestion
- [ ] **INGEST-01**: User can ingest municipalities via Wikidata SPARQL (with pagination, deduplication, rate-limit compliance)
- [ ] **INGEST-02**: User can ingest municipalities via OSM Overpass API as fallback
- [ ] **INGEST-03**: System stores raw ingested GeoJSON to disk (`raw/municipalities.geojson`)
- [ ] **INGEST-04**: Ingestion shows real-time progress feedback

### GEN — Map Generation
- [ ] **GEN-01**: User can trigger the full map generation pipeline (wraps map_generator.py)
- [ ] **GEN-02**: System generates PNG previews: terrain, territories, borders
- [ ] **GEN-03**: User can view PNG previews in the browser without downloading
- [ ] **GEN-04**: Generation runs in <60s for a standard country dataset

### CANVAS — Canvas Viewer
- [x] **CANVAS-01**: User can view all territories on a Konva canvas with correct colors and borders
- [ ] **CANVAS-02**: User can pan and zoom the canvas (Stage drag + wheel zoom)
- [x] **CANVAS-03**: User can click a territory to select it and see its properties in the right panel
- [x] **CANVAS-04**: Canvas shows layer toggles (terrain, territories, borders, capitals, labels)
- [ ] **CANVAS-05**: Canvas shows territory labels at appropriate zoom levels
- [ ] **CANVAS-06**: User can fit the map to view (reset zoom/pan)

### EDIT — Canvas Editing
- [ ] **EDIT-01**: User can drag a capital marker; neighbors recalculate Voronoi in <500ms
- [ ] **EDIT-02**: User can select border vertices and drag individual nodes to reshape a polygon
- [ ] **EDIT-03**: User can select 2+ adjacent territories and merge them into one
- [ ] **EDIT-04**: User can split a territory by drawing a cut line across it
- [ ] **EDIT-05**: User can paint terrain type on the map (mountain, river, forest, plains, arid) with a brush
- [ ] **EDIT-06**: User can upload a reference overlay image with adjustable opacity
- [ ] **EDIT-07**: All edit operations support Ctrl+Z (undo) and Ctrl+Y (redo) with 50-step history
- [ ] **EDIT-08**: Undo/redo groups compound side effects as single steps (e.g., Voronoi recalc is one undo with its capital move)

### RESEARCH — Historical Research via LLM
- [ ] **RESEARCH-01**: User can trigger historical research via Claude API (returns kingdoms/duchies/counties/baronies as structured JSON)
- [ ] **RESEARCH-02**: User can use Ollama (local LLM) as alternative research provider
- [ ] **RESEARCH-03**: System validates LLM response against Pydantic schema and retries up to 3 times on invalid JSON
- [ ] **RESEARCH-04**: Research results are cached per project (no re-fetch for same country+period)
- [ ] **RESEARCH-05**: Research dialog shows progress / spinner while waiting for LLM
- [ ] **RESEARCH-06**: User can use OpenAI (GPT-4o/5) as an additional cloud LLM provider
- [ ] **RESEARCH-07**: User can use Google Gemini (1.5 Pro / 2.0) as an additional cloud LLM provider
- [ ] **RESEARCH-08**: User can sign in via browser OAuth where the provider supports it (Google for Gemini; piggyback on local `claude-code` CLI auth for Anthropic if installed); API-key paste is always available as fallback
- [ ] **RESEARCH-09**: Provider architecture is plugin-based — adding a new LLM provider requires only a new adapter class + registry entry; no core changes, no UI hardcoding

### VALIDATE — Validation
- [ ] **VALIDATE-01**: System detects orphan baronies (barony without a parent county)
- [ ] **VALIDATE-02**: System detects dark pixels in ocean areas (rendering bug indicator)
- [ ] **VALIDATE-03**: System detects territories without capitals
- [ ] **VALIDATE-04**: System detects territories smaller than minimum pixel threshold
- [ ] **VALIDATE-05**: System detects hierarchy integrity violations (counts mismatch)
- [ ] **VALIDATE-06**: Validation results are shown in the UI with severity (error/warning) and territory highlight
- [ ] **VALIDATE-07**: Export is blocked when errors exist; warnings can be overridden by user

### GEO — Geographic Terrain Ingestion (Phase 2.1)
- [x] **GEO-01**: System fetches river and stream geometries via OSM Overpass (`waterway=river`, `waterway=stream`) for the project bbox and stores to `raw/rivers.geojson`
- [x] **GEO-02**: System fetches mountain peaks and ridges via OSM Overpass (`natural=peak`, `natural=ridge`, `natural=cliff`) and stores to `raw/topography.geojson`
- [x] **GEO-03**: System fetches coastline via OSM Overpass (`natural=coastline`) at ~10m precision for land/sea boundary, stores to `raw/coastline.geojson`
- [x] **GEO-04**: System fetches sub-municipal boundaries (`admin_level=8` parishes/freguesias) via Overpass where available, stores to `raw/parishes.geojson`
- [x] **GEO-05**: System extracts HydroSHEDS river basin polygons (from vendored shapefiles) for the project bbox and stores filtered result to `raw/basins.geojson`
- [x] **GEO-06**: System downloads DEM elevation raster tiles (Copernicus DEM 90m) for the project bbox with local tile cache (`data/dem_cache/`), mosaics and stores to `raw/dem.tif`
- [x] **GEO-07**: System derives ridge lines from DEM via slope+curvature analysis (thresholded laplacian + skeletonization) and stores to `raw/ridges.geojson`
- [x] **GEO-08**: User can trigger each extended ingestion step (rivers, terrain, HydroSHEDS, DEM) from the UI pipeline panel; each step shows real-time progress feedback

### TERR — Geometry-First Territory Construction (Phase 2.2)
- [ ] **TERR-01**: System clusters baronies into condados using hierarchical clustering constrained by rivers, ridges, and HydroSHEDS basins (no cluster crosses a principal river or watershed divide); target ~8–12 baronies per condado; output in `raw/condados.geojson`
- [ ] **TERR-02**: System aggregates condados into duchies and kingdoms using the same constrained hierarchical approach; outputs `raw/duchies.geojson` and `raw/kingdoms.geojson`
- [ ] **TERR-03**: Barony polygon construction is refined so that no barony polygon spans a principal river (Strahler ≥ 4 or `waterway=river` without `intermittent=yes`) or a classified ridge line
- [ ] **TERR-04**: Map generation pipeline builds `territory_data` directly from geometric GeoJSON files (`condados.geojson`, `duchies.geojson`, `kingdoms.geojson`) without requiring LLM research; placeholder names (e.g. `"Condado_001"`) are used when no research has run
- [ ] **TERR-05**: LLM research (Phase 3) functions as a "political paint" operation — assigns historical names, kingdom ownership, and political relationships to already-geometrically-defined territories; research never creates, removes, or repositions territory polygons
- [ ] **TERR-06**: User can trigger territory construction from the UI pipeline panel; the system reports barony/condado/duchy/kingdom counts after completion

### EXPORT — Unity Export
- [ ] **EXPORT-01**: User can export a Unity-ready ZIP containing all 12 standardized files
- [ ] **EXPORT-02**: Export ZIP includes: lookup_barony.png, lookup_condado.png, lookup_barony_colors.json, lookup_condado_colors.json, terrain_lookup.png, terrain_types.json, territory_metadata.json, mountains_mask.png, rivers_overlay.png, visual_barony.png, visual_condado.png, mountain_river_data.json
- [ ] **EXPORT-03**: Export regenerates final PNGs from current state before packaging
- [ ] **EXPORT-04**: Export dialog shows validation report and estimated file sizes

### PKG — Packaging & CLI
- [ ] **PKG-01**: Tool is installable via `pip install medieval-forge`
- [ ] **PKG-02**: CLI command `medieval-forge start` starts FastAPI server and opens browser
- [ ] **PKG-03**: CLI command `medieval-forge start --no-browser` starts without opening browser
- [ ] **PKG-04**: CLI command `medieval-forge stop` stops the running server (via PID file)
- [ ] **PKG-05**: Frontend build is bundled inside the Python package (pyproject.toml package_data)

---

## v2 Requirements (Deferred)

- Minimap (separate Konva Stage at reduced scale) — complex, not essential for v1
- WebSocket live preview (real-time generation progress) — polling is sufficient for v1
- Multi-user / cloud sync — single-user local tool by design for v1
- GPU acceleration for canvas — Konva handles up to 1000 territories without it
- History branching (named snapshots) — linear 50-step undo sufficient for v1

---

## Out of Scope

- Tauri/Electron packaging — webapp + localhost is sufficient; avoids binary distribution complexity
- SSR / Next.js — Vite SPA is enough for a local single-user tool
- Direct Unity integration (no Unity plugin) — user copies files to StreamingAssets manually
- Persisting LLM API keys to disk — session memory only (security requirement)
- Rewriting map_generator.py — used as imported library, not rewritten (regression risk)
- Online/cloud hosting — tool is explicitly local-first
- Mobile browser support — Game Designer workflow is desktop-only

---

## Traceability

| REQ-ID | Phase | Status | Notes |
|--------|-------|--------|-------|
| PROJ-01 | Phase 1 | Pending | Core project CRUD before anything else |
| PROJ-02 | Phase 1 | Pending | Core project CRUD before anything else |
| PROJ-03 | Phase 1 | Pending | Core project CRUD before anything else |
| PROJ-04 | Phase 1 | Pending | Core project CRUD before anything else |
| PROJ-05 | Phase 1 | Pending | Core project CRUD before anything else |
| INGEST-01 | Phase 1 | Pending | Data pipeline foundation — Wikidata paginated |
| INGEST-02 | Phase 1 | Pending | Data pipeline foundation — OSM fallback |
| INGEST-03 | Phase 1 | Pending | Data pipeline foundation — GeoJSON storage |
| INGEST-04 | Phase 1 | Pending | Data pipeline foundation — SSE progress |
| GEN-01 | Phase 1 | Pending | Headless generation pipeline |
| GEN-02 | Phase 1 | Pending | Headless generation pipeline — PNG output |
| GEN-03 | Phase 1 | Pending | Headless generation pipeline — browser preview |
| GEN-04 | Phase 1 | Pending | Headless generation pipeline — <60s target |
| PKG-01 | Phase 1 | Pending | Installable package from day 1 |
| PKG-02 | Phase 1 | Pending | CLI start with browser open |
| PKG-03 | Phase 1 | Pending | CLI start --no-browser |
| PKG-04 | Phase 1 | Pending | CLI stop via PID file |
| PKG-05 | Phase 1 | Pending | Frontend bundled in wheel via package_data |
| EXPORT-01 | Phase 1 | Pending | Headless ZIP assembly (polished in Phase 6) |
| EXPORT-02 | Phase 1 | Pending | 12-file ZIP content spec (polished in Phase 6) |
| CANVAS-01 | Phase 2 | Complete | Read-only canvas before editing |
| CANVAS-02 | Phase 2 | Pending | Pan + zoom |
| CANVAS-03 | Phase 2 | Complete | Click-to-inspect sidebar |
| CANVAS-04 | Phase 2 | Complete | Layer toggle panel |
| CANVAS-05 | Phase 2 | Pending | Labels at zoom threshold |
| CANVAS-06 | Phase 2 | Pending | Fit-to-view reset |
| RESEARCH-01 | Phase 3 | Pending | Claude API streaming |
| RESEARCH-02 | Phase 3 | Pending | Ollama local LLM adapter |
| RESEARCH-03 | Phase 3 | Pending | Pydantic schema validation + 3-retry |
| RESEARCH-04 | Phase 3 | Pending | Per-project cache |
| RESEARCH-05 | Phase 3 | Pending | Progress spinner / SSE stream UI |
| RESEARCH-06 | Phase 3 | Pending | OpenAI provider (GPT-4o/5) |
| RESEARCH-07 | Phase 3 | Pending | Google Gemini provider (1.5 Pro / 2.0) |
| RESEARCH-08 | Phase 3 | Pending | OAuth (Google) + CLI piggyback (Anthropic); API-key fallback |
| RESEARCH-09 | Phase 3 | Pending | Plugin architecture — registry + adapter pattern |
| EDIT-01 | Phase 4 | Pending | Capital drag + Voronoi recalc <500ms |
| EDIT-02 | Phase 4 | Pending | Border vertex drag |
| EDIT-03 | Phase 4 | Pending | Territory merge |
| EDIT-04 | Phase 4 | Pending | Territory split by cut line |
| EDIT-07 | Phase 4 | Pending | Undo/redo Ctrl+Z/Y 50-step |
| EDIT-08 | Phase 4 | Pending | Compound undo step grouping |
| EDIT-05 | Phase 5 | Pending | Terrain paint brush with land mask |
| EDIT-06 | Phase 5 | Pending | Reference overlay + opacity slider |
| VALIDATE-01 | Phase 6 | Pending | Orphan barony detection |
| VALIDATE-02 | Phase 6 | Pending | Dark ocean pixel detection |
| VALIDATE-03 | Phase 6 | Pending | Missing capital detection |
| VALIDATE-04 | Phase 6 | Pending | Undersized territory detection |
| VALIDATE-05 | Phase 6 | Pending | Hierarchy integrity check |
| VALIDATE-06 | Phase 6 | Pending | Validation UI with severity + territory highlight |
| VALIDATE-07 | Phase 6 | Pending | Export blocked on errors, warn-override on warnings |
| EXPORT-03 | Phase 6 | Pending | Final PNG regeneration before ZIP packaging |
| EXPORT-04 | Phase 6 | Pending | Export dialog with validation summary + file sizes |
