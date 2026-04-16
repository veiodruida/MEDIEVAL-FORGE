"""FastAPI application factory for Medieval Forge.

Lifespan opens the async engine; SPA catch-all handles React Router deep links.
Per RESEARCH.md Pitfall 8: API routers MUST be registered before the catch-all.
Routers are added by plans 01-02 (projects), 01-03 (ingest), 01-04 (generate),
and 01-05 (export) via app.include_router(...).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import engine

STATIC_DIR: Path = Path(__file__).parent / "static"
INDEX_HTML: Path = STATIC_DIR / "index.html"
ASSETS_DIR: Path = STATIC_DIR / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate DB connectivity (tables come from Alembic).
    async with engine.begin() as conn:
        # No-op: just exercises the connection so a broken URL fails fast.
        pass
    yield
    # Shutdown: close pool.
    await engine.dispose()


app = FastAPI(
    title="Medieval Forge",
    version="0.1.0",
    lifespan=lifespan,
)

from .api.projects import router as projects_router  # noqa: E402
from .api.ingest import router as ingest_router  # noqa: E402
from .api.generate import router as generate_router  # noqa: E402

app.include_router(projects_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
app.include_router(generate_router, prefix="/api")

# /assets/* — JS/CSS bundles. Only mount if directory exists (frontend may
# not be built yet during early development).
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/{full_path:path}")
async def spa_catch_all(full_path: str):
    """Serve React SPA index.html for all unmatched paths.

    Per Pitfall 3: required for React Router deep-link refresh to work.
    Returns a 503 placeholder if frontend has not been built yet.
    """
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Frontend not built yet. Run `npm run build` from frontend/."
        },
    )
