# Phase 1: Data Pipeline + Backend Scaffold — Research

**Researched:** 2026-04-16
**Domain:** Python/FastAPI backend scaffolding, pip packaging, SQLAlchemy async, Wikidata/OSM ingestion, SSE streaming, React SPA serving
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Flat monorepo layout: `backend/` (Python package), `frontend/` (Vite app), `pyproject.toml` at root. No `src/` layer.
- **D-02:** Vite `outDir` is `../backend/medieval_forge/static/` — build output lands directly inside the Python package. `pyproject.toml` picks it up via `package_data`. No copy step required.
- **D-03:** Runtime data (SQLite DB + project files) lives in `~/.medieval-forge/`. DB at `~/.medieval-forge/medieval_forge.db`, projects at `~/.medieval-forge/projects/{uuid}/`.
- **D-04:** Copy `inicio/map_generator.py` → `backend/medieval_forge/lib/map_generator.py`. Importable as `medieval_forge.lib.map_generator`. `if __name__ == "__main__":` guard confirmed at line 941 — safe to import.
- **D-05:** `services/generator.py` exposes `run_generation(project_id: str, config: dict) -> dict`. Calls map_generator synchronously via `asyncio.to_thread()`. Writes outputs to project dir, returns file manifest. Used as a FastAPI `BackgroundTask`.
- **D-06:** Projects identified by UUID (SQLite primary key + folder name).
- **D-07:** Per-project folder: `raw/`, `generated/`, `exports/` under `~/.medieval-forge/projects/{uuid}/`.
- **D-08:** Functional project manager SPA: `/projects`, `/projects/new`, `/projects/:id`. Tailwind v4 + Radix UI primitives. No Konva.
- **D-09:** SSE progress displayed as inline scrollable log panel; text appended per SSE event message. No percentages.
- **D-10:** Only Phase 1 routes. No placeholder routes for canvas/research.

### Claude's Discretion

- Exact Tailwind component styling and color choices for the project manager UI
- SQLAlchemy model column naming conventions (snake_case, standard)
- FastAPI router organization (whether to split by domain file or keep flat)
- Error response schema format (beyond Pydantic validation errors)
- Wikidata SPARQL query structure (within the 500-1000 item pagination constraint)
- OSM Overpass query format (standard for municipality polygons)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 1 scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROJ-01 | Create project (name, country, period, bbox, config) | SQLAlchemy model + FastAPI POST endpoint |
| PROJ-02 | List all projects | FastAPI GET /api/projects |
| PROJ-03 | Open/resume project | FastAPI GET /api/projects/{id} |
| PROJ-04 | Delete project with confirmation | FastAPI DELETE; frontend confirmation dialog |
| PROJ-05 | Update project settings | FastAPI PATCH /api/projects/{id} |
| INGEST-01 | Wikidata SPARQL paginated ingestion | SPARQLWrapper/httpx + pagination loop; 60s timeout |
| INGEST-02 | OSM Overpass API fallback | httpx + Overpass QL; `out geom;` for polygons |
| INGEST-03 | Store raw GeoJSON to disk | Write to `raw/municipalities.geojson` + SQLite record |
| INGEST-04 | Real-time progress feedback | FastAPI StreamingResponse SSE + asyncio.Queue |
| GEN-01 | Trigger full map generation | POST /api/projects/{id}/generate; BackgroundTask |
| GEN-02 | Generate PNG previews (terrain, territories, borders) | map_generator.generate_maps writes to `generated/` |
| GEN-03 | View PNG previews in browser | FastAPI FileResponse; frontend `<img>` tags |
| GEN-04 | Generation < 60s for standard country | asyncio.to_thread isolates blocking; target verified |
| PKG-01 | pip install medieval-forge | pyproject.toml [project.scripts] + setuptools |
| PKG-02 | medieval-forge start opens browser | uvicorn.run + webbrowser.open in subprocess |
| PKG-03 | medieval-forge start --no-browser | Click flag --no-browser |
| PKG-04 | medieval-forge stop via PID file | SIGTERM to PID in ~/.medieval-forge/medieval_forge.pid |
| PKG-05 | Frontend bundled in wheel | [tool.setuptools.package-data] glob `static/**/*` |
| EXPORT-01 | Export Unity-ready ZIP | zipfile.ZipFile from `generated/` files |
| EXPORT-02 | 12-file ZIP content spec | Confirmed files from map_generator output survey |

</phase_requirements>

---

## Summary

Phase 1 is a greenfield setup of a pip-packaged Python+React application. All critical architectural decisions are locked in CONTEXT.md. The research confirms all locked stack choices are sound and reveals several actionable implementation details: the Python environment is 3.12.6 (not 3.11), which unlocks rasterio 1.5.x; `map_generator.py` is confirmed importable with no side effects; the `load_territory_data` function uses `importlib.import_module` by bare module name, requiring a careful strategy for packaging territory data; and `aiosqlite>=0.20,<0.22` is correctly pinned due to a confirmed thread-hanging regression in 0.22.0.

The frontend stack is verified at exact current npm versions. The five-plan breakdown in ROADMAP.md is the correct execution order — scaffold and packaging seam must come first because every other plan depends on the Vite `base: "./"` setting and the Alembic async env.py.

**Primary recommendation:** Initialize Alembic with `-t async` flag from day one, pin `aiosqlite>=0.20,<0.22`, set `vite.config.ts base: "./"`, and use Python 3.12.6 (already installed) — this allows rasterio 1.5.x if needed rather than being pinned to 1.4.x.

---

## Project Constraints (from CLAUDE.md)

All directives extracted from CLAUDE.md that the planner must honor:

| Directive | Specifics |
|-----------|-----------|
| Python version | 3.11+ required; **3.12.6 is installed** [VERIFIED: `py --version`] |
| React version | 19 (not 18) — react-konva 19.x peer-dep alignment |
| Vite version | 6.x (not 5) — two majors behind |
| react-konva | 19.2.x (mirrors React 19 version scheme) |
| zundo | 2.3.0 — v3 does not exist; API uses `temporal` middleware |
| rasterio | `>=1.4,<1.5` if Python 3.11; `>=1.5` if Python 3.12 |
| Tailwind CSS | v4 with `@tailwindcss/vite` plugin (not PostCSS) |
| Radix UI CSS | Must import BEFORE `@import "tailwindcss"` to avoid transparency bug |
| aiosqlite | `>=0.20,<0.22` — v0.22.0 thread-hanging regression confirmed |
| Alembic env.py | Must use `asyncio.run()` + `run_sync()` from day one |
| Wikidata pagination | 500-1000 items max per SPARQL call (60s hard timeout) |
| map_generator.py | Verify importability before wrapping — CONFIRMED importable |
| Vite base | Must set `base: "./"` in vite.config.ts |
| LLM | Claude API (claude-sonnet-4-6) + Ollama adapter (Phase 3) |
| State | Zustand + zundo for undo/redo; TanStack Query v5 for cache |
| Packaging | pip-installable; `medieval-forge start` CLI entry point |
| Performance | Voronoi recalc <500ms (Phase 4); generation <60s (Phase 1) |

---

## Standard Stack

### Backend Core
| Library | Version | Purpose | Verified |
|---------|---------|---------|----------|
| Python | 3.12.6 | Runtime | [VERIFIED: `py --version`] |
| FastAPI | 0.135.3 | ASGI web framework | [VERIFIED: npm index] |
| uvicorn[standard] | 0.44.0 | ASGI server | [VERIFIED: pip index] |
| SQLAlchemy | 2.0.49 | ORM + async engine | [VERIFIED: pip index] |
| aiosqlite | 0.21.0 | Async SQLite driver (pinned <0.22) | [VERIFIED: pip index + bug confirmed] |
| alembic | 1.18.4 | DB migrations | [VERIFIED: pip index] |
| pydantic | 2.13.1 | Data validation (FastAPI default) | [VERIFIED: pip index] |
| httpx | latest | Async HTTP client for Wikidata/OSM | [ASSUMED: standard httpx] |
| anthropic | 0.95.0 | Claude API client (Phase 3 uses it) | [VERIFIED: pip index] |

### Backend Geometry (already installed)
| Library | Version | Purpose | Verified |
|---------|---------|---------|----------|
| scipy | 1.17.1 | Voronoi via cKDTree + spatial | [VERIFIED: `py -c "import scipy"`] |
| shapely | 2.1.2 | Boolean geometry ops | [VERIFIED: `py -c "import shapely"`] |
| numpy | 2.4.4 | Array ops | [VERIFIED: `py -c "import numpy"`] |
| Pillow | 12.2.0 | PNG image output | [VERIFIED: `py -c "import PIL"`] |
| rasterio | 1.5.0 or 1.4.4 | Raster I/O (if needed) | [VERIFIED: pip index; 1.5.0 available since Python 3.12 is installed] |

**rasterio note:** CLAUDE.md pins `>=1.4,<1.5` targeting Python 3.11. Since the installed Python is 3.12.6, rasterio 1.5.0 is available and compatible. The planner should use `>=1.4,<1.6` to allow 1.5.x. Phase 1 map_generator.py does NOT import rasterio — it only uses PIL, scipy, numpy, shapely — so rasterio is not a Phase 1 blocker at all.

### Frontend Core
| Library | Version | Purpose | Verified |
|---------|---------|---------|----------|
| react | 19.2.5 | UI framework | [VERIFIED: npm view] |
| react-dom | 19.2.5 | DOM renderer | [VERIFIED: npm view] |
| vite | 6.4.2 | Build tool | [VERIFIED: npm view] |
| @vitejs/plugin-react | 4.4.1 | React HMR + JSX | [VERIFIED: npm view] |
| typescript | 5.8.x | Type checking | [ASSUMED: latest 5.x] |
| react-router-dom | 7.14.1 | Client-side routing | [VERIFIED: npm view] |
| @tanstack/react-query | 5.99.0 | Server state cache | [VERIFIED: npm view] |
| zustand | 5.0.12 | Client state | [VERIFIED: npm view] |
| zundo | 2.3.0 | Undo/redo middleware | [VERIFIED: npm view] |
| tailwindcss | 4.2.2 | Utility CSS | [VERIFIED: npm view] |
| @tailwindcss/vite | 4.2.2 | Vite Tailwind plugin | [VERIFIED: npm view] |
| @radix-ui/themes | 3.3.0 | UI primitives | [VERIFIED: npm view] |
| konva | 10.2.5 | Canvas engine (Phase 2) | [VERIFIED: npm view] |
| react-konva | 19.2.3 | React bindings for Konva | [VERIFIED: npm view] |

**Phase 1 note:** react-konva and konva are NOT used in Phase 1 (no canvas). Install them so the project is set up, but no imports needed until Phase 2.

### Installation

```bash
# Backend — from repo root
pip install -e ".[dev]"

# Frontend — from frontend/
npm install
```

---

## Architecture Patterns

### Recommended Project Structure

```
medieval_forge/                  # repo root
├── pyproject.toml               # package + scripts + deps
├── backend/
│   └── medieval_forge/          # Python package
│       ├── __init__.py
│       ├── cli.py               # medieval-forge start/stop
│       ├── main.py              # FastAPI app factory
│       ├── database.py          # async engine + session factory
│       ├── models.py            # SQLAlchemy ORM models
│       ├── api/
│       │   ├── projects.py      # PROJ-01..05 routes
│       │   ├── ingest.py        # INGEST-01..04 routes + SSE
│       │   ├── generate.py      # GEN-01..04 routes
│       │   └── export.py        # EXPORT-01..02 routes
│       ├── services/
│       │   ├── generator.py     # run_generation() wrapper
│       │   ├── ingest_wikidata.py
│       │   └── ingest_osm.py
│       ├── lib/
│       │   └── map_generator.py # copied from inicio/
│       ├── schemas.py           # Pydantic request/response models
│       └── static/              # Vite build output lands here
│           └── (index.html, assets/, ...)
├── frontend/
│   ├── vite.config.ts           # base: "./" CRITICAL
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── ProjectList.tsx
│   │   │   ├── ProjectNew.tsx
│   │   │   └── ProjectDetail.tsx
│   │   └── api/
│   │       └── client.ts        # TanStack Query hooks
│   └── package.json
└── alembic/
    ├── env.py                   # asyncio.run() + run_sync() CRITICAL
    ├── script.py.mako
    └── versions/
```

### Pattern 1: FastAPI Async Session with Lifespan

```python
# backend/medieval_forge/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from pathlib import Path

DATA_DIR = Path.home() / ".medieval-forge"
DB_URL = f"sqlite+aiosqlite:///{DATA_DIR}/medieval_forge.db"

engine = create_async_engine(DB_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

```python
# backend/medieval_forge/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import engine
from .models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        # Tables created by Alembic, not here — but engine validates connection
        pass
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Alembic Async env.py (CRITICAL — must be right from day one)

```python
# alembic/env.py — the critical async pattern
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Import your models so autogenerate sees them
from medieval_forge.models import Base

config = context.config
target_metadata = Base.metadata

def run_migrations_online():
    async def _run():
        engine = create_async_engine(config.get_main_option("sqlalchemy.url"))
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda conn: context.configure(
                    connection=conn,
                    target_metadata=target_metadata,
                )
            )
            await conn.run_sync(lambda conn: context.run_migrations())
        await engine.dispose()
    asyncio.run(_run())

run_migrations_online()
```

**Initialize with async template:**
```bash
alembic init -t async alembic
```

### Pattern 3: SSE Progress Stream via asyncio.Queue

```python
# backend/medieval_forge/api/ingest.py
import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

router = APIRouter()

async def ingest_event_stream(project_id: str, source: str, queue: asyncio.Queue):
    """Runs ingestion, puts messages into queue, consumer yields SSE."""
    async def producer():
        # actual ingestion with httpx calls
        await queue.put("data: Starting Wikidata ingestion...\n\n")
        # ... paginated fetch loop ...
        await queue.put("data: DONE\n\n")
        await queue.put(None)  # sentinel

    asyncio.create_task(producer())

    while True:
        msg = await queue.get()
        if msg is None:
            break
        yield msg

@router.post("/projects/{project_id}/ingest")
async def ingest(project_id: str, source: str = "wikidata"):
    queue: asyncio.Queue = asyncio.Queue()
    return StreamingResponse(
        ingest_event_stream(project_id, source, queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### Pattern 4: Vite Config with base: "./" (CRITICAL)

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',   // CRITICAL: relative assets — absolute '/' breaks pip-packaged URLs
  build: {
    outDir: '../backend/medieval_forge/static',
    emptyOutDir: true,
  },
})
```

### Pattern 5: SPA Fallback — FastAPI Serving React

The standard pattern requires mounting static files AND a catch-all route. StaticFiles alone does NOT handle React Router deep links.

```python
# main.py — SPA serving pattern
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"

# Mount API routes first
app.include_router(projects_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
app.include_router(generate_router, prefix="/api")
app.include_router(export_router, prefix="/api")

# Static assets (JS/CSS bundles)
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

# SPA catch-all — must be LAST
@app.get("/{path:path}")
async def spa_fallback(path: str):
    return FileResponse(STATIC_DIR / "index.html")
```

**Why not `app.mount("/", StaticFiles(html=True))`:** This does not handle React Router paths that don't correspond to actual files. The catch-all FileResponse approach is required.

### Pattern 6: map_generator.py Wrapper with asyncio.to_thread

```python
# backend/medieval_forge/services/generator.py
import asyncio
from pathlib import Path
from ..lib import map_generator

async def run_generation(project_id: str, config: dict) -> dict:
    """
    Runs map_generator.generate_maps in a thread pool.
    config must contain: output_dir, and all RegionConfig fields.
    Returns manifest dict of written files.
    """
    def _sync_generate():
        cfg = map_generator.RegionConfig(
            output_dir=str(Path.home() / ".medieval-forge" / "projects" / project_id / "generated"),
            **{k: v for k, v in config.items() if k in map_generator.RegionConfig.__dataclass_fields__}
        )
        map_generator.generate_maps(cfg, territory_module=config.get("territory_module", "territory_data_v3"))
        return {
            "visual_condado": "generated/visual_condado.png",
            "visual_barony": "generated/visual_barony.png",
            "lookup_condado": "generated/lookup_condado.png",
            "lookup_barony": "generated/lookup_barony.png",
            "territory_metadata": "generated/territory_metadata.json",
            "lookup_condado_colors": "generated/lookup_condado_colors.json",
            "lookup_barony_colors": "generated/lookup_barony_colors.json",
            "mountains_mask": "generated/mountains_mask.png",
            "rivers_overlay": "generated/rivers_overlay.png",
        }

    return await asyncio.to_thread(_sync_generate)
```

**CRITICAL gotcha — `territory_module` uses `importlib.import_module` with a bare name:** The `load_territory_data` function calls `importlib.import_module(module_name)`. For Phase 1, the territory data is provided externally as a project config field (or as a Python dict converted to a temporary module). The generator wrapper must handle this — either by writing a temp module to sys.path, or by refactoring territory data loading to accept a dict directly. Recommend a thin adapter: write territory dict to a temp `.py` file in the project dir and add that dir to `sys.path` before calling `generate_maps`.

### Pattern 7: pyproject.toml Package Data

```toml
[tool.setuptools.package-data]
medieval_forge = ["static/**/*", "static/index.html"]
```

The `**/*` glob includes all files recursively in the `static/` directory. Forward slashes work on Windows too — setuptools converts them. [VERIFIED: setuptools docs]

### Pattern 8: CLI Entry Point

```python
# backend/medieval_forge/cli.py
import click
import uvicorn
import webbrowser
import os
import signal
from pathlib import Path

PID_FILE = Path.home() / ".medieval-forge" / "medieval_forge.pid"

@click.group()
def cli():
    pass

@cli.command()
@click.option("--port", default=8765, help="Port to listen on")
@click.option("--no-browser", is_flag=True, help="Skip opening browser")
def start(port, no_browser):
    """Start Medieval Forge server."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    if not no_browser:
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    uvicorn.run(
        "medieval_forge.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )

@cli.command()
def stop():
    """Stop Medieval Forge server."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        click.echo(f"Stopped process {pid}")
    else:
        click.echo("No running server found.")
```

```toml
# pyproject.toml
[project.scripts]
medieval-forge = "medieval_forge.cli:cli"
```

### Anti-Patterns to Avoid

- **Sync SQLAlchemy session in async FastAPI route:** Will block the event loop. Always use `async with AsyncSessionLocal() as session`.
- **Alembic with default (sync) env.py:** Produces empty migrations — `alembic revision --autogenerate` finds nothing. Use `-t async` from init.
- **aiosqlite 0.22.0:** Confirmed hanging thread issue (SQLAlchemy issue #13039). Pin `>=0.20,<0.22`.
- **Vite `base: "/"` (absolute):** Asset URLs like `/assets/index-abc.js` do NOT resolve when the file is served from FastAPI's StaticFiles at a sub-path after pip install. Always use `"./"`.
- **`app.mount("/", StaticFiles(html=True))` without catch-all:** React Router deep links return 404 on hard refresh. Use explicit catch-all route instead.
- **`load_territory_data` with a module not on sys.path:** Will raise `ModuleNotFoundError` at generation time. The generator wrapper must ensure the territory module is importable.
- **BackgroundTask for long-running generation:** FastAPI's `BackgroundTask` runs after the response is sent, which works for fire-and-forget. But for progress tracking, use an asyncio.Queue + SSE pattern for real-time feedback. Generation endpoint should return immediately, progress via a separate SSE stream endpoint.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client for Wikidata/OSM | Custom urllib loop | `httpx.AsyncClient` | Connection pooling, timeout handling, retries |
| Database migrations | Hand-crafted SQL ALTER TABLE | Alembic | Schema version tracking, autogenerate |
| Async SQLite | Direct sqlite3 in async code | `aiosqlite` via SQLAlchemy | Thread-safe async wrapper |
| SSE formatting | Manual `data:...\n\n` strings | SSE convention (`f"data: {msg}\n\n"`) | Format is simple but disconnect detection needs `await request.is_disconnected()` |
| ZIP creation | os.system zip | `zipfile.ZipFile` stdlib | No subprocess, pure Python, cross-platform |
| Config CLI | argparse | Click | Auto help, subcommands, flags |
| Browser open | subprocess | `webbrowser` stdlib | Cross-platform, no shell dependency |

---

## Common Pitfalls

### Pitfall 1: Alembic Generates Empty Migrations
**What goes wrong:** Running `alembic revision --autogenerate` produces a migration with no `op.*` calls despite models existing.
**Why it happens:** The default `alembic init` creates a sync `env.py`. The async engine is not queried correctly, so autogenerate sees no tables.
**How to avoid:** Use `alembic init -t async alembic`. Confirm `target_metadata = Base.metadata` is set and all model files are imported before `Base.metadata` is referenced.
**Warning signs:** Migration file says `# ### commands auto generated by Alembic - please adjust! ###` followed immediately by `pass`.

### Pitfall 2: aiosqlite Thread Hanging on Shutdown
**What goes wrong:** Server hangs on Ctrl+C / SIGTERM and never exits cleanly.
**Why it happens:** aiosqlite 0.22.0 changed `Connection` to not inherit from `Thread`, breaking SQLAlchemy's cleanup strategy of setting `connection.daemon = True`.
**How to avoid:** Pin `aiosqlite>=0.20,<0.22`. If 0.22+ is needed in future, call `await connection.close()` explicitly.
**Warning signs:** Process hangs after all requests complete; requires SIGKILL to terminate.

### Pitfall 3: React SPA Deep Links Return 404
**What goes wrong:** Navigating to `/projects/some-uuid` directly (or on page refresh) returns a 404 from FastAPI.
**Why it happens:** FastAPI looks for a file at that path on disk — it doesn't exist, so 404.
**How to avoid:** Add a `@app.get("/{path:path}")` catch-all that returns `FileResponse(STATIC_DIR / "index.html")`. This must come AFTER all API routes.
**Warning signs:** `/projects` works but `/projects/new` gives 404 on refresh.

### Pitfall 4: Vite Assets 404 After pip Install
**What goes wrong:** The browser gets `index.html` but all JS/CSS assets return 404.
**Why it happens:** `vite.config.ts` has `base: "/"` so assets are referenced as `/assets/index-abc.js`. FastAPI serves the file from a sub-path but the absolute URL doesn't resolve.
**How to avoid:** Set `base: "./"` in `vite.config.ts` so assets are referenced relatively.
**Warning signs:** Browser console shows `GET /assets/index-abc.js 404` after install.

### Pitfall 5: Wikidata SPARQL 60-Second Timeout
**What goes wrong:** Querying all municipalities for a large country (Spain, France) with a single SPARQL query times out after 60 seconds with HTTP 500 or empty result.
**Why it happens:** Wikidata SPARQL endpoint has a hard 60-second timeout. Spain has ~8,000 municipalities.
**How to avoid:** Paginate with `LIMIT 500 OFFSET N` in the SPARQL query. Loop until fewer than 500 results returned. Cache per QID to avoid repeat fetches.
**Warning signs:** Request hangs for 60 seconds then returns an error; result set is exactly 0 items or error response.

### Pitfall 6: map_generator territory_module Import Failure
**What goes wrong:** `generate_maps()` raises `ModuleNotFoundError: No module named 'territory_data_project_xyz'`.
**Why it happens:** `load_territory_data` calls `importlib.import_module(module_name)` which searches `sys.path`. A module written to a temp file in the project directory is not on `sys.path` by default.
**How to avoid:** Before calling `generate_maps`, either (a) add the directory containing the territory module to `sys.path`, or (b) write a wrapper that monkey-patches `sys.modules` with the territory data dict converted to a module object.
**Warning signs:** Works in the `inicio/` directory context (where `territory_data_v3.py` is present) but fails when called from `services/generator.py`.

### Pitfall 7: Tailwind v4 + Radix UI Transparency
**What goes wrong:** Radix UI Dropdown, Select, or Dialog renders transparent or has incorrect layering.
**Why it happens:** Tailwind v4's CSS layer ordering conflicts with Radix Themes' internal CSS specificity.
**How to avoid:** In the main CSS entry file, import Radix Themes CSS BEFORE `@import "tailwindcss"`:
```css
@import "@radix-ui/themes/styles.css";
@import "tailwindcss";
```
**Warning signs:** Dropdown menus appear invisible or show through other elements.

### Pitfall 8: FastAPI StaticFiles Mount Order
**What goes wrong:** API routes like `/api/projects` return 404 or HTML.
**Why it happens:** StaticFiles mount is registered before API routes, so it intercepts all requests.
**How to avoid:** Register all `app.include_router()` calls BEFORE any `app.mount()` or catch-all route. API routes must be added first.
**Warning signs:** `GET /api/projects` returns `index.html` content with 200 status.

---

## Code Examples

### Wikidata SPARQL Paginated Municipality Query

```python
# Source: Wikidata:SPARQL query service/query_limits documentation
import httpx
import asyncio

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "MedievalForge/1.0 (https://github.com/user/medieval-forge)"

def build_municipality_query(country_qid: str, limit: int, offset: int) -> str:
    return f"""
    SELECT ?item ?itemLabel ?lat ?lon WHERE {{
      ?item wdt:P31/wdt:P279* wd:Q15284 .   # instance of municipality
      ?item wdt:P17 wd:{country_qid} .       # country
      ?item wdt:P625 ?coords .               # coordinate location
      BIND(geof:latitude(?coords) AS ?lat)
      BIND(geof:longitude(?coords) AS ?lon)
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
    OFFSET {offset}
    """

async def fetch_municipalities_wikidata(
    country_qid: str,
    progress_queue: asyncio.Queue,
    page_size: int = 500,
) -> list:
    results = []
    offset = 0
    async with httpx.AsyncClient(timeout=70.0) as client:
        while True:
            await progress_queue.put(f"data: Fetching page offset={offset}...\n\n")
            query = build_municipality_query(country_qid, page_size, offset)
            resp = await client.get(
                WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            )
            resp.raise_for_status()
            bindings = resp.json()["results"]["bindings"]
            results.extend(bindings)
            if len(bindings) < page_size:
                break
            offset += page_size
    return results
```

### OSM Overpass Fallback Query

```python
# Source: OpenStreetMap Overpass API docs + osm2geojson pattern
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"

def build_overpass_query(country_iso: str, admin_level: int = 8) -> str:
    """Query admin boundaries at given level (8 = municipalities in most of Europe)."""
    return f"""
    [out:json][timeout:120];
    area["ISO3166-1"="{country_iso}"]->.country;
    (
      relation["admin_level"="{admin_level}"]["boundary"="administrative"](area.country);
    );
    out geom;
    """

async def fetch_municipalities_osm(
    country_iso: str,
    progress_queue: asyncio.Queue,
) -> dict:
    """Returns GeoJSON FeatureCollection."""
    query = build_overpass_query(country_iso)
    await progress_queue.put("data: Querying OSM Overpass API...\n\n")
    async with httpx.AsyncClient(timeout=130.0) as client:
        resp = await client.post(OVERPASS_ENDPOINT, data={"data": query})
        resp.raise_for_status()
    # Convert OSM JSON to GeoJSON using osm2geojson or manual conversion
    return resp.json()
```

### SQLAlchemy Project Model

```python
# backend/medieval_forge/models.py
import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_qid: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "Q29"
    period_start: Mapped[int] = mapped_column(nullable=False)
    period_end: Mapped[int] = mapped_column(nullable=False)
    bbox_lon_min: Mapped[float] = mapped_column(Float, nullable=True)
    bbox_lon_max: Mapped[float] = mapped_column(Float, nullable=True)
    bbox_lat_min: Mapped[float] = mapped_column(Float, nullable=True)
    bbox_lat_max: Mapped[float] = mapped_column(Float, nullable=True)
    generator_config: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="created")  # created|ingested|generated|exported
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Tailwind v4 CSS Setup (Radix-safe)

```css
/* frontend/src/index.css */
@import "@radix-ui/themes/styles.css";   /* MUST be first */
@import "tailwindcss";                    /* MUST be after Radix */

@theme {
  --color-primary: oklch(0.5 0.2 250);
  /* custom tokens here */
}
```

### Territory Module Adapter (sys.path injection)

```python
# services/generator.py — territory module strategy
import sys
import types
from pathlib import Path

def _inject_territory_module(module_name: str, data: dict):
    """Create a fake module in sys.modules so importlib.import_module finds it."""
    mod = types.ModuleType(module_name)
    mod.KINGDOMS = data["kingdoms"]
    mod.DUCHIES = data["duchies"]
    mod.CONDADOS = data["condados"]
    sys.modules[module_name] = mod
    return mod

def _cleanup_territory_module(module_name: str):
    sys.modules.pop(module_name, None)
```

---

## Runtime State Inventory

> Phase 1 is greenfield — no existing runtime state to migrate.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — blank slate | None |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | None — no .env files | None |
| Build artifacts | None — no prior builds | None |

**Nothing found in any category — verified by codebase inspection. Project root contains only `inicio/` reference files, `CLAUDE.md`, and planning artifacts.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Backend | Yes | 3.12.6 (`py` launcher) | — |
| pip | Package install | Yes | 24.2 | — |
| Node.js | Frontend build | Yes | 24.14.0 | — |
| npm | Frontend packages | Yes | 11.8.0 | — |
| scipy | map_generator.py | Yes | 1.17.1 | — |
| shapely | map_generator.py | Yes | 2.1.2 | — |
| numpy | map_generator.py | Yes | 2.4.4 | — |
| Pillow | map_generator.py | Yes | 12.2.0 | — |
| FastAPI | Backend framework | Not installed | 0.135.3 available | — |
| SQLAlchemy | ORM | Not installed | 2.0.49 available | — |
| aiosqlite | Async SQLite | Not installed | 0.21.0 (pinned) available | — |
| alembic | Migrations | Not installed | 1.18.4 available | — |
| uvicorn | ASGI server | Not installed | 0.44.0 available | — |
| httpx | HTTP client | Not installed | pip installable | — |
| React 19 | Frontend | Not installed | 19.2.5 on npm | — |
| Vite 6 | Frontend build | Not installed | 6.4.2 on npm | — |
| Tailwind v4 | CSS | Not installed | 4.2.2 on npm | — |

**Missing dependencies with no fallback:** FastAPI, SQLAlchemy, aiosqlite, alembic, uvicorn, httpx — all installable via `pip install`. React/Vite/Tailwind — installable via `npm install`. None block execution after install.

**Python environment note:** `python3` alias does NOT work on this machine; use `py` (Windows Python Launcher) or the full path. pyproject.toml scripts must be tested with `py -m pip install -e .` and then verified that the `medieval-forge` entry point resolves correctly. The Vite build step requires `npm run build` from `frontend/`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Alembic sync env.py | `alembic init -t async` template | Alembic 1.7+ | Autogenerate works with async engines |
| tailwind.config.js | CSS-first `@theme` directive | Tailwind v4 (Jan 2025) | No JS config file needed |
| PostCSS tailwind plugin | `@tailwindcss/vite` plugin | Tailwind v4 (Jan 2025) | Better Vite HMR performance |
| zundo `undoMiddleware` | `temporal` middleware | zundo v2 (2023) | API completely different from v1 |
| Pydantic v1 | Pydantic v2 (FastAPI default) | FastAPI 0.100+ (2023) | `model_validate`, `.model_dump()` |
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.95+ (2023) | Cleaner startup/shutdown |
| setup.py | pyproject.toml | PEP 517/518 (2020+) | Standard for 2025 greenfield |
| React 18 | React 19 | March 2025 | react-konva 19.x aligns with React 19 |

---

## Critical Integration: map_generator.py Analysis

**Confirmed importable:** [VERIFIED: `py -c "import map_generator"` from inicio/ directory succeeds]

**Public API exposed:**
- `RegionConfig` — dataclass for all generation parameters
- `generate_maps(cfg, territory_module, draw_names)` — main entry point
- `iberia_config()` — example config factory

**Output files written to `cfg.output_dir`:**
- `visual_condado.png`, `visual_barony.png` — visual maps
- `lookup_condado.png`, `lookup_barony.png` — Unity hit detection
- `lookup_condado_colors.json`, `lookup_barony_colors.json` — color→ID maps
- `territory_metadata.json` — full hierarchy JSON
- `mountains_mask.png` — optional (if mountain data provided)
- `rivers_overlay.png` — optional (if river data provided)

**The 12-file Unity spec (EXPORT-02)** maps to these files plus `terrain_lookup.png`, `terrain_types.json`, and `mountain_river_data.json`. Phase 1 headless export will copy whatever `generate_maps` produced into the ZIP. The 3 "terrain" files are generated by later map_generator steps that are currently hardcoded for Iberia. For Phase 1, include what's generated and flag missing files.

**CRITICAL territory_module mechanism:**
`load_territory_data` calls `importlib.import_module(module_name)` and expects `KINGDOMS`, `DUCHIES`, `CONDADOS` attributes on the module. For Phase 1, the generator service must inject a synthetic module into `sys.modules` before calling `generate_maps`. This is the only way to pass territory data dynamically without writing Python files to disk.

---

## Validation Architecture

> nyquist_validation is enabled in .planning/config.json.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + httpx (for async FastAPI testing) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` section |
| Install | `pip install pytest pytest-asyncio httpx` |
| Quick run command | `py -m pytest backend/tests/ -x -q` |
| Full suite command | `py -m pytest backend/tests/ -v --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROJ-01 | POST /api/projects creates project in DB | Integration | `pytest tests/test_projects.py::test_create_project -x` | Wave 0 |
| PROJ-02 | GET /api/projects returns list | Integration | `pytest tests/test_projects.py::test_list_projects -x` | Wave 0 |
| PROJ-03 | GET /api/projects/{id} returns single | Integration | `pytest tests/test_projects.py::test_get_project -x` | Wave 0 |
| PROJ-04 | DELETE /api/projects/{id} removes record | Integration | `pytest tests/test_projects.py::test_delete_project -x` | Wave 0 |
| PROJ-05 | PATCH /api/projects/{id} updates fields | Integration | `pytest tests/test_projects.py::test_update_project -x` | Wave 0 |
| INGEST-01 | Wikidata fetch returns GeoJSON features | Unit (mocked) | `pytest tests/test_ingest.py::test_wikidata_pagination -x` | Wave 0 |
| INGEST-02 | OSM fallback returns features | Unit (mocked) | `pytest tests/test_ingest.py::test_osm_fallback -x` | Wave 0 |
| INGEST-03 | GeoJSON written to raw/municipalities.geojson | Integration | `pytest tests/test_ingest.py::test_geojson_written -x` | Wave 0 |
| INGEST-04 | SSE endpoint streams messages | Integration | `pytest tests/test_ingest.py::test_sse_stream -x` | Wave 0 |
| GEN-01 | POST /generate queues background task | Integration | `pytest tests/test_generate.py::test_trigger_generation -x` | Wave 0 |
| GEN-02 | PNG files exist after generation | Integration (slow) | `pytest tests/test_generate.py::test_png_outputs -x -m slow` | Wave 0 |
| GEN-03 | GET /projects/{id}/preview/{file} returns image | Integration | `pytest tests/test_generate.py::test_png_fileresponse -x` | Wave 0 |
| GEN-04 | Generation completes in <60s | Performance (slow) | `pytest tests/test_generate.py::test_generation_time -x -m slow` | Wave 0 |
| PKG-01 | Package installs from wheel | Smoke (manual) | `pip install dist/*.whl && medieval-forge --help` | Manual |
| PKG-02 | CLI starts server | Smoke | `pytest tests/test_cli.py::test_start_no_browser -x` | Wave 0 |
| PKG-04 | PID file written + stop works | Unit | `pytest tests/test_cli.py::test_pid_file -x` | Wave 0 |
| PKG-05 | static/ included in wheel | Unit | `pytest tests/test_packaging.py::test_static_in_wheel -x` | Wave 0 |
| EXPORT-01 | ZIP download returns bytes | Integration | `pytest tests/test_export.py::test_zip_download -x` | Wave 0 |
| EXPORT-02 | ZIP contains expected files | Integration | `pytest tests/test_export.py::test_zip_contents -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `py -m pytest backend/tests/ -x -q --ignore=tests/test_generate.py` (skip slow generation tests)
- **Per wave merge:** `py -m pytest backend/tests/ -v --tb=short`
- **Phase gate:** Full suite green (including slow marks) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/__init__.py` — marks test directory
- [ ] `backend/tests/conftest.py` — shared async fixtures: in-memory SQLite DB, TestClient, project factory
- [ ] `backend/tests/test_projects.py` — PROJ-01..05
- [ ] `backend/tests/test_ingest.py` — INGEST-01..04 (with httpx mocks)
- [ ] `backend/tests/test_generate.py` — GEN-01..04 (GEN-02/04 marked `@pytest.mark.slow`)
- [ ] `backend/tests/test_export.py` — EXPORT-01..02
- [ ] `backend/tests/test_cli.py` — PKG-02..04
- [ ] `backend/tests/test_packaging.py` — PKG-05 (checks wheel manifest)
- [ ] Framework install: `pip install pytest pytest-asyncio httpx`

**conftest.py async pattern:**
```python
# backend/tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()

@pytest_asyncio.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

---

## Security Domain

> security_enforcement key absent from config.json — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Local-only tool, no auth |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Single-user local |
| V5 Input Validation | Yes | Pydantic schemas on all API inputs |
| V6 Cryptography | No | No sensitive data |
| V7 Error Handling | Yes | FastAPI exception handlers; no stack traces to browser |
| V13 API | Yes | Pydantic request validation; explicit 422 errors |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via project_id in file paths | Tampering | Validate UUID format; use `Path(base_dir) / uuid` with `.resolve()` check |
| SSRF via user-supplied Wikidata QID | Spoofing | Validate QID format `Q\d+`; hardcode endpoint URLs |
| DoS via unlimited generation requests | Denial of Service | Queue depth limit; check status != "generating" before starting |
| LLM API key exposure in logs | Info Disclosure | Never log API keys; session-only storage (Phase 3) |

**Phase 1 focus:** Path traversal is the primary risk. All file I/O must construct paths as `~/.medieval-forge/projects/{uuid}/{subpath}` and validate that the resolved path is within the base directory.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | httpx is the correct async HTTP client | Standard Stack | Low — httpx is the de-facto standard; aiohttp is an alternative |
| A2 | Click is preferred over argparse for CLI | Architecture Patterns | Low — either works; Click is standard for FastAPI ecosystem |
| A3 | Territory data for Phase 1 will be passed as a config dict (not a Python file) | Code Examples | Medium — if territory data format changes, generator wrapper needs redesign |
| A4 | rasterio is not needed in Phase 1 (map_generator.py only uses PIL/scipy/numpy/shapely) | Standard Stack | Low — confirmed by reading map_generator.py imports |
| A5 | `os.kill(pid, signal.SIGTERM)` works on Windows for stopping uvicorn | CLI Pattern | MEDIUM — Windows does not support SIGTERM the same way; may need `CTRL_C_EVENT` or `terminate()` via psutil |

**A5 is the highest-risk assumption:** On Windows, `os.kill(pid, signal.SIGTERM)` raises `OSError` unless the process was started in a compatible way. The `stop` command should use `psutil.Process(pid).terminate()` for cross-platform compatibility, or spawn uvicorn as a subprocess and store the handle.

---

## Open Questions

1. **Windows SIGTERM for CLI stop command**
   - What we know: `os.kill(pid, signal.SIGTERM)` is unreliable on Windows
   - What's unclear: Whether uvicorn started via `uvicorn.run()` in the same process can be stopped externally
   - Recommendation: Use `psutil` for cross-platform process termination, or start uvicorn as a subprocess so the parent can `.terminate()` it

2. **Territory data format for Phase 1**
   - What we know: `generate_maps` requires KINGDOMS/DUCHIES/CONDADOS as a Python module
   - What's unclear: Phase 1 ingests GeoJSON from Wikidata/OSM — how does this map to CONDADOS format?
   - Recommendation: Phase 1 generator service should treat territory data as user-provided config (pass as JSON in the API request). The `sys.modules` injection pattern handles this.

3. **EXPORT-02 12-file spec completeness**
   - What we know: `map_generator.generate_maps` produces 9 files; EXPORT-02 specifies 12
   - What's unclear: `terrain_lookup.png`, `terrain_types.json` are mentioned in EXPORT-02 but not produced by current generator
   - Recommendation: Phase 1 headless export includes the 9 generator-produced files and creates placeholder/empty stubs for the 3 missing terrain files. Full 12-file spec is polished in Phase 6.

---

## Sources

### Primary (HIGH confidence)
- npm registry (`npm view`) — verified react 19.2.5, vite 6.4.2, react-konva 19.2.3, zundo 2.3.0, @tanstack/react-query 5.99.0, zustand 5.0.12, tailwindcss 4.2.2
- pip index (`pip index versions`) — verified FastAPI 0.135.3, SQLAlchemy 2.0.49, alembic 1.18.4, uvicorn 0.44.0, aiosqlite 0.21.0, pydantic 2.13.1
- Python environment — verified Python 3.12.6, scipy 1.17.1, shapely 2.1.2, numpy 2.4.4, Pillow 12.2.0
- `inicio/map_generator.py` — verified importable, confirmed `__main__` guard at line 941, confirmed `generate_maps` signature
- SQLAlchemy issue #13039 — confirmed aiosqlite 0.22.0 thread-hanging regression

### Secondary (MEDIUM confidence)
- [Wikidata SPARQL Query Limits](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/query_limits) — 60s hard timeout confirmed
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — lifespan pattern confirmed
- [FastAPI Static Files](https://fastapi.tiangolo.com/tutorial/static-files/) — mount pattern
- [Alembic async template](https://github.com/sqlalchemy/alembic/blob/main/alembic/templates/async/env.py) — `-t async` flag
- [setuptools package-data docs](https://setuptools.pypa.io/en/latest/userguide/datafiles.html) — glob patterns

### Tertiary (LOW confidence)
- Windows SIGTERM behavior — [ASSUMED from training; needs empirical test on developer machine]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against npm registry and pip index in this session
- Architecture: HIGH — patterns verified against FastAPI official docs and SQLAlchemy 2.0 docs
- map_generator.py integration: HIGH — confirmed importable, signature extracted, output files enumerated
- Pitfalls: HIGH — aiosqlite bug confirmed via GitHub issue; Vite base="./" confirmed by CLAUDE.md; others from CLAUDE.md constraints
- Windows CLI stop: LOW — SIGTERM behavior assumed; needs empirical testing

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable ecosystem — 30-day validity)
