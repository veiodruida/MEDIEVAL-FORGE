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
- [ ] **CANVAS-01**: User can view all territories on a Konva canvas with correct colors and borders
- [ ] **CANVAS-02**: User can pan and zoom the canvas (Stage drag + wheel zoom)
- [ ] **CANVAS-03**: User can click a territory to select it and see its properties in the right panel
- [ ] **CANVAS-04**: Canvas shows layer toggles (terrain, territories, borders, capitals, labels)
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

### VALIDATE — Validation
- [ ] **VALIDATE-01**: System detects orphan baronies (barony without a parent county)
- [ ] **VALIDATE-02**: System detects dark pixels in ocean areas (rendering bug indicator)
- [ ] **VALIDATE-03**: System detects territories without capitals
- [ ] **VALIDATE-04**: System detects territories smaller than minimum pixel threshold
- [ ] **VALIDATE-05**: System detects hierarchy integrity violations (counts mismatch)
- [ ] **VALIDATE-06**: Validation results are shown in the UI with severity (error/warning) and territory highlight
- [ ] **VALIDATE-07**: Export is blocked when errors exist; warnings can be overridden by user

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
- SRTM/elevation auto-download — user uploads manually in v1
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

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| PROJ-01..05 | Phase 1 | Core project CRUD before anything else |
| INGEST-01..04 | Phase 1 | Data pipeline foundation |
| GEN-01..04 | Phase 1 | Headless generation pipeline |
| PKG-01..05 | Phase 1 | Installable package from day 1 |
| CANVAS-01..06 | Phase 2 | Read-only canvas before editing |
| RESEARCH-01..05 | Phase 3 | LLM integration (parallel with Phase 2) |
| EDIT-01..08 | Phase 4+5 | Editing after canvas foundation is solid |
| VALIDATE-01..07 | Phase 6 | Validation gate before export polish |
| EXPORT-01..04 | Phase 1+6 | Basic export in Phase 1, polished in Phase 6 |
