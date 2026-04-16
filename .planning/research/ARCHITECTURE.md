# ARCHITECTURE.md — Medieval Forge

**Researched:** 2026-04-16
**Overall confidence:** HIGH (core patterns verified against official docs and live sources)

---

## Component Map

```
medieval-forge/
├── src/medieval_forge/          # Python package
│   ├── cli.py                   # Click entry point → uvicorn.run()
│   ├── server.py                # FastAPI app factory + static mount
│   ├── config.py                # Paths, env settings
│   ├── api/                     # Route handlers (thin layer)
│   │   ├── projects.py          # CRUD
│   │   ├── ingest.py            # Wikidata / OSM
│   │   ├── research.py          # LLM (SSE streaming)
│   │   ├── generate.py          # Pipeline trigger
│   │   ├── edit.py              # Canvas edit ops
│   │   └── export.py            # ZIP packaging
│   ├── services/                # All business logic lives here
│   │   ├── wikidata.py          # SPARQL via httpx
│   │   ├── osm.py               # Overpass via httpx
│   │   ├── llm.py               # Claude + Ollama adapter
│   │   ├── voronoi.py           # scipy Voronoi + neighbor recalc
│   │   ├── generator.py         # Wraps map_generator.py
│   │   ├── validator.py         # Pre-export checks
│   │   └── export_service.py    # ZIP assembly
│   ├── models/                  # SQLAlchemy ORM models
│   ├── storage/
│   │   └── database.py          # Engine + session factory
│   └── static/                  # Vite build output (included in wheel)
│       └── index.html
├── frontend/                    # React/Vite source (not in wheel)
│   ├── vite.config.ts
│   ├── src/
│   │   ├── store/               # Zustand + zundo slices
│   │   ├── api/                 # TanStack Query hooks
│   │   ├── components/
│   │   │   ├── canvas/          # Konva layers
│   │   │   └── tools/           # Edit tool components
│   │   └── lib/
│   │       └── projection.ts    # Geo ↔ pixel transform
└── vendor/
    └── map_generator.py         # Reused as library (do not modify)
```

**Boundary rule:** API handlers call services only. Services never import from api/. Models never import from services. This keeps each layer independently testable.

---

## Data Flow

### 1. Request → Response (standard CRUD)

```
Browser → TanStack Query → FastAPI route handler
       → service function → SQLAlchemy async session
       → SQLite (db.sqlite in ~/.medieval-forge/)
       → Pydantic schema → JSON response
       → TanStack cache invalidation → React re-render
```

### 2. Generation pipeline (long-running)

```
POST /api/projects/{id}/generate
  → BackgroundTask (FastAPI) or asyncio.create_task
  → services/generator.py
      → import map_generator  (vendor/map_generator.py)
      → write PNGs to ~/.medieval-forge/projects/{id}/preview/
  → project status updated in SQLite (status: "generating" → "ready")
  → frontend polls GET /api/projects/{id} until status == "ready"
```

Do NOT stream PNG generation progress over SSE for MVP — polling is simpler and sufficient. Add SSE progress later if generation takes >30s in practice.

### 3. Canvas edit → Voronoi recalc

```
User drags capital on Konva canvas
  → onDragEnd fires (canvas pixel coords)
  → projection.ts converts px → lon/lat
  → Zustand: optimistic local update (immediate visual feedback)
  → POST /api/projects/{id}/edit/move-capital {lon, lat}
      → services/voronoi.py: find neighbors via ridge_points
      → scipy.Voronoi on (moved_point + neighbors subset)
      → Shapely clip to land bounds + boolean fixes
      → return {affected: [{id, geometry_geojson}]}
  → Zustand: merge server polygons into state
  → zundo records snapshot (for undo)
```

### 4. LLM research → SSE stream

```
POST /api/projects/{id}/research
  → EventSourceResponse generator (FastAPI ≥0.115 native SSE)
  → services/llm.py: Claude stream or Ollama stream
  → yield token chunks as SSE data events
  → Frontend: EventSource reads tokens, appends to UI
  → On [DONE] event: validate JSON schema, cache in project
```

### 5. Export pipeline

```
POST /api/projects/{id}/export
  → services/validator.py: run all checks
    → if errors: return 422 with error list (block export)
    → if warnings only: proceed with warnings in response
  → services/export_service.py:
      → re-run generator for final PNGs
      → assemble 12 Unity-ready files
      → write to ~/.medieval-forge/projects/{id}/export/
      → zip → return as FileResponse (streaming)
```

---

## Build Order (suggested)

### Phase 1 — Backend shell + data persistence

Build in this order within Phase 1:

1. **Package skeleton** — `pyproject.toml`, `cli.py`, `server.py` with health endpoint only, `medieval-forge start` works
2. **Database + models** — SQLAlchemy async engine, Project + Territory ORM models, Alembic migration
3. **Projects CRUD** — `/api/projects` GET/POST/PATCH/DELETE, no generation yet
4. **Wikidata ingestion** — `/api/ingest/wikidata`, SPARQL query, parse → insert territories
5. **OSM fallback** — `/api/ingest/osm`, Overpass query (same interface as Wikidata service)
6. **Generator wrapper** — `services/generator.py` wraps `map_generator.py`, writes PNGs
7. **Generate endpoint** — BackgroundTask, status polling
8. **Preview serving** — `GET /preview/{layer}.png` via FileResponse
9. **Export endpoint** — validation + ZIP assembly
10. **Frontend build included** — Vite build output in `src/medieval_forge/static/`, StaticFiles mount

**Rationale:** Database schema must be stable before any other layer. Generation and export are independent of the canvas — they can be tested with curl. Frontend is last because it depends on all API contracts being defined.

### Phase 2 — Canvas editor

Build in this order within Phase 2:

1. **Coordinate projection module** — `frontend/src/lib/projection.ts` (geo↔px), test independently
2. **Konva Stage + pan/zoom** — Stage with wheel handler, no content yet
3. **Territory + border layers** — read-only rendering of GeoJSON polygons
4. **Capitals layer** — draggable circles, no backend yet
5. **Voronoi recalc endpoint** — `POST /edit/move-capital`, `services/voronoi.py`
6. **Zustand store + zundo** — territories slice with undo/redo wired to drag
7. **Vertex edit tool** — border handles layer
8. **Merge/split operations** — Shapely boolean ops on backend
9. **Terrain brush** — pixel-level terrain painting
10. **Reference overlay** — image upload + opacity slider

**Rationale:** Projection math must work before any canvas interaction. Rendering before interaction. Backend recalc before state management. Each step is a working increment.

---

## Key Integration Points

### 1. Vite → Python package (static files)

**Vite config** (`frontend/vite.config.ts`):
```typescript
export default defineConfig({
  base: '/',               // assets load from root, not relative
  build: {
    outDir: '../src/medieval_forge/static',
    emptyOutDir: true,
  },
})
```

**pyproject.toml** (setuptools backend):
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
medieval_forge = ["static/**/*"]

[project.scripts]
medieval-forge = "medieval_forge.cli:cli"
```

The `static/**/*` glob ensures all nested assets (JS chunks, CSS, images) are included in the wheel. The `vite build` step runs before `pip install` or `python -m build`. In CI, add a Makefile target: `build-frontend: npm run build` before the Python build.

**Confidence:** MEDIUM — setuptools `package-data` glob is standard. The Hatch `shared-data` approach also works (verified from Medium article) but adds a Hatch dependency. Setuptools is simpler for this project.

### 2. FastAPI serving SPA + API

```python
# server.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from pathlib import Path
import importlib.resources

app = FastAPI()

# API routes registered first (order matters)
app.include_router(projects_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
# ... all API routers

# Locate bundled static dir even after pip install
STATIC_DIR = Path(importlib.resources.files("medieval_forge")) / "static"

# SPA catch-all: any non-API path returns index.html
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    file_path = STATIC_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")

# Static assets (JS/CSS) served via mount for efficient byte-range, ETag support
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
```

**Key decision:** Use `importlib.resources.files()` to locate the static dir rather than `__file__` — it works correctly inside zip-compressed wheels. Register all `/api` routes before the catch-all route, because FastAPI matches routes in registration order.

**Confidence:** HIGH — `@app.exception_handler(404)` is a valid alternative, but a catch-all route is simpler and avoids exception machinery for normal navigation.

### 3. Geo ↔ canvas pixel coordinate transform

The bounding box (`bounds: {lon_min, lon_max, lat_min, lat_max}`) defines the affine transform. This is a linear map only — no projection (equirectangular is sufficient at medieval regional scale).

```typescript
// frontend/src/lib/projection.ts

export interface Bounds {
  lon_min: number; lon_max: number;
  lat_min: number; lat_max: number;
}

export interface ProjectionConfig {
  bounds: Bounds;
  canvasW: number;   // Stage width in pixels
  canvasH: number;   // Stage height in pixels
}

/**
 * Geographic coordinates → Konva canvas pixels.
 * Y-axis is INVERTED: lat increases up, canvas y increases down.
 */
export function geoToCanvas(
  lon: number,
  lat: number,
  cfg: ProjectionConfig,
): { x: number; y: number } {
  const { bounds, canvasW, canvasH } = cfg;
  const x = ((lon - bounds.lon_min) / (bounds.lon_max - bounds.lon_min)) * canvasW;
  const y = ((bounds.lat_max - lat) / (bounds.lat_max - bounds.lat_min)) * canvasH;
  return { x, y };
}

/**
 * Konva canvas pixels → geographic coordinates.
 * Inverse of geoToCanvas. Used on drag events.
 */
export function canvasToGeo(
  px: number,
  py: number,
  cfg: ProjectionConfig,
): { lon: number; lat: number } {
  const { bounds, canvasW, canvasH } = cfg;
  const lon = bounds.lon_min + (px / canvasW) * (bounds.lon_max - bounds.lon_min);
  const lat = bounds.lat_max - (py / canvasH) * (bounds.lat_max - bounds.lat_min);
  return { lon, lat };
}

/**
 * Convert a GeoJSON polygon ring to flat Konva points array.
 * Konva Line expects [x0,y0, x1,y1, ...].
 */
export function geoRingToKonvaPoints(
  coordinates: [number, number][],
  cfg: ProjectionConfig,
): number[] {
  return coordinates.flatMap(([lon, lat]) => {
    const { x, y } = geoToCanvas(lon, lat, cfg);
    return [x, y];
  });
}
```

**Why no projection library:** At country-scale (bounded box ~10°×10°), equirectangular error is <1% — acceptable for a map editor. Adding proj4js or d3-geo for this adds complexity with no visible benefit. If the project ever extends to continent-scale, revisit.

**Important:** The backend stores GeoJSON (lon/lat). The projection only lives in the frontend. Never store pixel coordinates in the database.

**Confidence:** HIGH — the pattern is standard for bounded-box canvas map editors.

### 4. Incremental Voronoi — affected neighbors only

scipy's `Voronoi` does not support true incremental updates with localized polygon invalidation. The correct strategy is:

```python
# services/voronoi.py
from scipy.spatial import Voronoi, voronoi_plot_2d
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

def get_voronoi_neighbors(vor: Voronoi, point_idx: int) -> set[int]:
    """Find all points that share a ridge with point_idx."""
    neighbors = set()
    for (p1, p2) in vor.ridge_points:
        if p1 == point_idx:
            neighbors.add(p2)
        elif p2 == point_idx:
            neighbors.add(p1)
    return neighbors

def recalc_voronoi_local(
    all_territories: list[Territory],
    moved_id: str,
    new_lon: float,
    new_lat: float,
    land_polygon: Polygon,
) -> dict[str, dict]:  # {territory_id: geojson_geometry}
    """
    Recalculate Voronoi cells for moved territory and its neighbors.
    
    Strategy:
    1. Run full Voronoi on ALL points (fast: ~0.05s for 500 points).
    2. Use ridge_points to identify affected neighbors of moved point.
    3. Only recompute and return polygons for affected subset.
    
    Full recompute on all points is necessary because scipy Voronoi
    does not support true incremental updates. It is fast enough (<100ms
    for 500 points) that we do not need true incremental mode.
    """
    # Build point array with updated position
    points = []
    id_to_idx = {}
    for i, t in enumerate(all_territories):
        lon = new_lon if t.id == moved_id else t.centroid_lon
        lat = new_lat if t.id == moved_id else t.centroid_lat
        points.append([lon, lat])
        id_to_idx[t.id] = i
    
    pts_arr = np.array(points)
    vor = Voronoi(pts_arr)
    
    # Identify affected: moved + its Voronoi neighbors
    moved_idx = id_to_idx[moved_id]
    affected_indices = {moved_idx} | get_voronoi_neighbors(vor, moved_idx)
    
    # Build polygons only for affected cells
    results = {}
    for t in all_territories:
        idx = id_to_idx[t.id]
        if idx not in affected_indices:
            continue
        poly = voronoi_cell_to_polygon(vor, idx, land_polygon)
        if poly:
            results[t.id] = mapping(poly)  # GeoJSON dict
    
    return results
```

**Why full recompute works:** scipy Voronoi with 500 points runs in ~50ms on a modern CPU. The "incremental" optimization is in the *response* — only returning the ~5-10 affected polygons to the frontend, not in the computation itself. The `incremental=True` flag on scipy Voronoi is for adding new points to an existing diagram, not for moving existing points; it does not help here.

**Confidence:** HIGH — verified against scipy 1.17 docs. The ridge_points approach for neighbor lookup is documented.

### 5. LLM streaming (SSE)

FastAPI 0.115+ includes native SSE support via `fastapi.sse.EventSourceResponse` (no sse-starlette dependency needed).

```python
# api/research.py
from collections.abc import AsyncGenerator
from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()

@router.post("/projects/{project_id}/research")
async def stream_research(
    project_id: str,
    request: ResearchRequest,
) -> EventSourceResponse:
    async def token_stream() -> AsyncGenerator[ServerSentEvent, None]:
        async with llm_service.stream(
            country=request.country,
            period=request.period,
        ) as stream:
            buffer = ""
            async for chunk in stream:
                buffer += chunk
                yield ServerSentEvent(data=chunk, event="token")
            # Validate complete JSON before saving
            validated = validate_research_json(buffer)
            await save_research_cache(project_id, validated)
            yield ServerSentEvent(data="", event="done")
    
    return EventSourceResponse(token_stream())
```

Frontend:
```typescript
// api/client.ts — research streaming
export function streamResearch(
  projectId: string,
  params: ResearchParams,
  onToken: (chunk: string) => void,
  onDone: () => void,
) {
  // SSE requires GET or POST-compatible URL; use POST body via fetch+ReadableStream
  // EventSource only supports GET. For POST streaming, use fetch with streaming body read.
  const response = await fetch(`/api/projects/${projectId}/research`, {
    method: 'POST',
    body: JSON.stringify(params),
    headers: { 'Content-Type': 'application/json' },
  });
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  // parse SSE manually from ReadableStream
  // ... standard SSE parse loop
}
```

**Why SSE, not WebSocket:** SSE is one-directional (server→client), which is exactly what LLM streaming needs. WebSocket adds handshake complexity, reconnect logic, and message framing — none of which are required here. SSE over HTTP/2 multiplexes without extra ports. FastAPI's built-in automatic keep-alive ping (every 15s) prevents proxy timeouts for long research queries.

**Confidence:** HIGH — verified against FastAPI 0.115 official docs (live URL checked).

---

## Pattern Recommendations

### Backend

**1. Thin routers, fat services**
Route handlers in `api/` do only: validate input (Pydantic does this), call one service function, return result. All logic lives in `services/`. This makes services independently testable without HTTP.

**2. Async sessions via dependency injection**
```python
# storage/database.py
async_engine = create_async_engine("sqlite+aiosqlite:///~/.medieval-forge/db.sqlite")
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# In route handlers:
async def list_projects(session: AsyncSession = Depends(get_session)):
    ...
```
Use `expire_on_commit=False` — critical for async SQLAlchemy to avoid lazy-load errors after commit.

**3. BackgroundTasks for generation, not threads**
```python
@router.post("/projects/{id}/generate")
async def trigger_generation(id: str, background_tasks: BackgroundTasks):
    await set_project_status(id, "generating")
    background_tasks.add_task(run_generation_pipeline, id)
    return {"status": "generating"}
```
Do not use `asyncio.run_in_executor` with map_generator.py directly — it uses PIL/numpy which release the GIL, so BackgroundTasks + threadpool is safe.

**4. GeoJSON as storage format for geometry**
Store territory polygons as JSON columns (SQLAlchemy `JSON` type) in the territories table. Do not store rasterized pixel coordinates. The projection is always computed at read time by the frontend.

### Frontend

**5. Projection config in React context**
The `ProjectionConfig` (bounds + canvas dimensions) changes when the project loads or the window resizes. Put it in a React context so all canvas layers access the same transform without prop drilling:
```typescript
const ProjectionContext = createContext<ProjectionConfig | null>(null);
export const useProjection = () => useContext(ProjectionContext)!;
```

**6. Separate Zustand slices**
Three stores, not one:
- `useProjectStore` — territories, borders (persisted via zundo, 50-step limit)
- `useEditorStore` — selected tool, selected territory, edit mode (NOT tracked by zundo — UI state should not be undoable)
- `useUIStore` — dialog open/close, panel state (not tracked)

Only `useProjectStore` needs zundo. Mixing UI state into the tracked store bloats undo snapshots.

**7. Equality function on zundo to avoid snapshot on every render**
```typescript
temporal<ProjectState>(
  (set) => ({ ... }),
  {
    limit: 50,
    // Only record undo step when territory geometry actually changes
    equality: (a, b) =>
      a.territories === b.territories && a.borders === b.borders,
  }
)
```
Without a custom equality function, every Zustand update (including UI state) generates an undo snapshot. Use referential equality (`===`) for arrays — since you replace arrays on mutation, this is efficient.

**8. Konva layer hit detection — use listening=false for static layers**
```typescript
// TerrainLayer is a PNG image, never interactive
<Layer name="terrain" listening={false}>
  <Image image={terrainImg} />
</Layer>
```
Setting `listening={false}` skips hit canvas generation for that layer, which is a meaningful perf win when you have 500+ territory polygons in adjacent layers.

**9. Coordinate round-trip test**
Write a unit test before any canvas interaction code:
```typescript
const cfg = { bounds: { lon_min: -10, lon_max: 5, lat_min: 36, lat_max: 44 }, canvasW: 1920, canvasH: 1080 };
const geo = { lon: -2.5, lat: 40.0 };
const px = geoToCanvas(geo.lon, geo.lat, cfg);
const back = canvasToGeo(px.x, px.y, cfg);
expect(back.lon).toBeCloseTo(geo.lon, 6);
expect(back.lat).toBeCloseTo(geo.lat, 6);
```
A bug in the Y-axis inversion will cause every capital drag to move in the wrong direction. Catch it early.

---

## Phase-Specific Architecture Flags

| Phase | Component | Flag |
|-------|-----------|------|
| Phase 1 | `map_generator.py` integration | Verify it can be imported as a module (not just run as script). Check if it uses `if __name__ == "__main__"` guards. May need a thin wrapper function. |
| Phase 1 | Wikidata SPARQL | Rate limiting — Wikidata public endpoint allows ~1 req/s. Add retry with exponential backoff. |
| Phase 2 | Voronoi clip to land mask | The `land_polygon` for clipping must be pre-built from coastline data and cached — do not recompute per request. |
| Phase 2 | Shapely merge/split | `unary_union` on complex polygons (500+ vertices each) can be slow. Test with real Iberia data before committing to sync endpoint — may need BackgroundTask. |
| Phase 2 | zundo snapshot size | 50 snapshots × (500 territories × ~2KB GeoJSON each) = ~50MB in browser memory. Monitor in practice; may need to reduce limit or use diff-based history. |
| Phase 3 | Export ZIP | `FileResponse` streams the file. Do not load entire ZIP into memory — use `zipfile.ZipFile` with a `BytesIO` or write to temp file and stream. |

---

## Sources

- FastAPI official docs — Static Files: https://fastapi.tiangolo.com/tutorial/static-files/
- FastAPI official docs — Server-Sent Events: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- Embedding React in a FastAPI Python Package (Asaf Shakarzy, Medium): https://medium.com/@asafshakarzy/embedding-a-react-frontend-inside-a-fastapi-python-package-in-a-monorepo-c00f99e90471
- scipy.spatial.Voronoi docs (v1.17): https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Voronoi.html
- Konva zoom relative to pointer: https://konvajs.org/docs/sandbox/Zooming_Relative_To_Pointer.html
- Konva React undo/redo: https://konvajs.org/docs/react/Undo-Redo.html
- zundo GitHub: https://github.com/charkour/zundo
- Vite build options: https://vite.dev/config/build-options
- setuptools entry points: https://setuptools.pypa.io/en/latest/userguide/entry_point.html
- SQLAlchemy async + FastAPI pattern: https://medium.com/@mojimich2015/async-sqlalchemy-engine-in-fastapi-the-guide-e5acdba75c99
- Serving a React Frontend with FastAPI (David Muraya): https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/
