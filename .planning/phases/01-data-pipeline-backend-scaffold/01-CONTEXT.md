# Phase 1: Data Pipeline + Backend Scaffold - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers a fully functional headless pipeline: pip-installable package, project CRUD, Wikidata/OSM ingestion with SSE progress, map generation wrapping map_generator.py, and basic Unity ZIP export — all exercisable without the Konva canvas. A minimal React SPA (project manager UI) is included to satisfy the CRUD success criteria visually, but no canvas work is done here.

</domain>

<decisions>
## Implementation Decisions

### D-01: Repository & Package Structure
- **D-01:** Flat monorepo layout: `backend/` (Python package), `frontend/` (Vite app), `pyproject.toml` at root. No `src/` layer.
- **D-02:** Vite `outDir` is `../backend/medieval_forge/static/` — build output lands directly inside the Python package. `pyproject.toml` picks it up via `package_data`. No copy step required.
- **D-03:** Runtime data (SQLite DB + project files) lives in `~/.medieval-forge/`. DB at `~/.medieval-forge/medieval_forge.db`, projects at `~/.medieval-forge/projects/{uuid}/`.

### D-04: map_generator.py Integration
- **D-04:** Copy `inicio/map_generator.py` → `backend/medieval_forge/lib/map_generator.py`. Importable as `medieval_forge.lib.map_generator`. It has a `if __name__ == "__main__":` guard at line 941 — safe to import without executing. `inicio/` stays for reference only.
- **D-05:** `services/generator.py` exposes a single async function `run_generation(project_id: str, config: dict) -> dict`. Calls map_generator synchronously via `asyncio.to_thread()`. Writes outputs to project dir, returns file manifest. Used as a FastAPI `BackgroundTask`.

### D-06: Per-Project Data Layout
- **D-06:** Projects are identified by UUID (SQLite primary key + folder name).
- **D-07:** Per-project folder structure under `~/.medieval-forge/projects/{uuid}/`:
  - `raw/` — GeoJSON from ingestion (`raw/municipalities.geojson`)
  - `generated/` — PNG previews (terrain.png, territories.png, borders.png) + all map_generator outputs
  - `exports/` — Unity ZIP archives

### D-08: Minimal Frontend Scope
- **D-08:** Functional project manager SPA (not a bare shell, not a full app skeleton). Routes: `/projects`, `/projects/new`, `/projects/:id`. Tailwind v4 + Radix UI primitives for styling. No Konva, no canvas.
- **D-09:** Ingestion progress (SSE stream) displayed as an inline scrollable log panel below the Ingest button. Text area appending SSE event messages as they arrive. No progress bar — backend SSE events carry text messages, not percentages.
- **D-10:** Only Phase 1 routes defined (`/projects`, `/projects/new`, `/projects/:id`). Later phases add their own routes. No placeholder routes for canvas/research/etc.

### Claude's Discretion
- Exact Tailwind component styling and color choices for the project manager UI
- SQLAlchemy model column naming conventions (snake_case, standard)
- FastAPI router organization (whether to split by domain file or keep flat)
- Error response schema format (beyond Pydantic validation errors)
- Wikidata SPARQL query structure (within the 500-1000 item pagination constraint)
- OSM Overpass query format (standard for municipality polygons)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Critical Constraints (from ROADMAP.md Phase 1)
- `ROADMAP.md` Phase 1 section — critical constraints: `vite.config.ts` must set `base: "./"`, `aiosqlite>=0.20,<0.22`, Alembic `env.py` must use `asyncio.run()` + `run_sync()`, Wikidata pagination 500-1000 items max, verify map_generator.py importability before wrapping

### Stack Decisions (from CLAUDE.md)
- `CLAUDE.md` Technology Stack section — validated library versions and known issues: React 19 + react-konva 19.2.x, Vite 6, zundo 2.3.0 (`temporal` middleware, not v3), rasterio `>=1.4,<1.5`, Tailwind v4 CSS-first, Radix CSS must import before `@import "tailwindcss"`

### Reference Implementation
- `inicio/map_generator.py` — existing pipeline to copy into `backend/medieval_forge/lib/`. Has `__main__` guard at line 941. Dependencies: Pillow, scipy, numpy, shapely.
- `inicio/territory_data_v3.py` — example territory data structure (Iberia 868 AD, 91 condados) — reference for understanding generator inputs
- `inicio/mountain_river_data.json` — example geographic data format for generator inputs
- `inicio/BRIEFING_MEDIEVAL_FORGE.md` — full original project specification

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 1 requirements: PROJ-01..05, INGEST-01..04, GEN-01..04, PKG-01..05, EXPORT-01..02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `inicio/map_generator.py` — the entire generation pipeline (RegionConfig dataclass, Voronoi + Shapely pipeline, PNG output). Copy to `backend/medieval_forge/lib/`.
- `inicio/territory_data_v3.py` — reference data structure showing how territory hierarchy is organized (kingdoms → duchies → condados)

### Established Patterns
- No existing codebase patterns yet — blank slate. All patterns established in this phase become the baseline for subsequent phases.
- map_generator.py uses: `PIL.Image`, `scipy.spatial.cKDTree`, `scipy.ndimage.*`, numpy arrays. These are hard dependencies of the lib.

### Integration Points
- FastAPI will serve React SPA via `StaticFiles` mount from `medieval_forge/static/`
- `services/generator.py` is the seam between the FastAPI route layer and `medieval_forge.lib.map_generator`
- All project file I/O goes through `~/.medieval-forge/projects/{uuid}/` — no files written to the package directory at runtime

</code_context>

<specifics>
## Specific Ideas

- Project manager pages: `/projects` (list with create button), `/projects/new` (create form: name, country QID, period start/end, bounding box), `/projects/:id` (detail with Ingest / Generate / Export ZIP buttons + inline SSE log panel + PNG preview images)
- Wikidata QIDs for reference: PT=Q45, ES=Q29, GB=Q145, FR=Q142, IT=Q38, DE=Q183
- `medieval-forge start` CLI: start uvicorn + open browser tab to `http://localhost:8765` (or configurable port)
- `medieval-forge stop`: read PID file from `~/.medieval-forge/medieval_forge.pid`, send SIGTERM

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 1 scope.

</deferred>

---

*Phase: 01-data-pipeline-backend-scaffold*
*Context gathered: 2026-04-16*
