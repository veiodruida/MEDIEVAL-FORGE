"""FastAPI application factory for Medieval Forge.

Lifespan opens the async engine; SPA catch-all handles React Router deep links.
Per RESEARCH.md Pitfall 8: API routers MUST be registered before the catch-all.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import engine

STATIC_DIR: Path = Path(__file__).parent / "static"
INDEX_HTML: Path = STATIC_DIR / "index.html"
ASSETS_DIR: Path = STATIC_DIR / "assets"


@asynccontextmanager
def _reconcile_added_columns(conn) -> None:
    """Additive column migration for SQLite.

    `create_all` creates missing tables but never adds columns to a table that
    already exists. When a model gains a NOT NULL column with a default (e.g.
    Phase 08 added branches.manual_edit_log_count / manual_edit_log_hash), an
    existing DB is left without it and every ORM SELECT on that table fails with
    "no such column". This walks each mapped table, compares its columns against
    the live schema, and issues ALTER TABLE ADD COLUMN for any that are missing.
    Only additive — never drops or alters existing columns.
    """
    from sqlalchemy import inspect, text

    from .models import Base

    insp = inspect(conn)
    existing_tables = set(insp.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all already made it with the full set of columns
        live_cols = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in live_cols:
                continue
            ddl_type = col.type.compile(dialect=conn.dialect)
            clause = f'ADD COLUMN "{col.name}" {ddl_type}'
            default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
            if not col.nullable:
                if isinstance(default, str):
                    clause += f" NOT NULL DEFAULT '{default}'"
                elif default is not None:
                    clause += f" NOT NULL DEFAULT {default}"
            conn.execute(text(f'ALTER TABLE "{table.name}" {clause}'))


async def lifespan(app: FastAPI):
    # Startup: ensure ORM tables exist (idempotent).
    from .models import Base  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_reconcile_added_columns)

    # UAT 2026-05-23 — auto-discover `.env` files under the user's home
    # directory so a fresh install picks up keys without forcing the
    # user to open the CredentialsManager. We NEVER overwrite a key the
    # user previously set via the UI — DB rows win over auto-imported
    # ones. Safe on first run because the DB has no rows yet.
    try:
        from .database import AsyncSessionLocal
        from .services.credential_store import (
            get_credentials,
            store_credentials,
        )
        from .services.llm.dotenv_import import discover_dotenv_keys
        from .services.llm.registry import PROVIDERS

        discovered, files_read = await asyncio.to_thread(discover_dotenv_keys)
        if discovered and files_read:
            async with AsyncSessionLocal() as session:
                imported: list[str] = []
                for provider_id, key in discovered.items():
                    if provider_id not in PROVIDERS:
                        continue
                    existing = await get_credentials(session, provider_id)
                    if existing and isinstance(existing, dict) and existing.get("key"):
                        # User-set DB row wins; don't clobber.
                        continue
                    await store_credentials(
                        session,
                        provider_id,
                        {"type": "api_key", "key": key.strip()},
                    )
                    imported.append(provider_id)
            if imported:
                logger.info(
                    "auto-imported %d credential(s) from %s: %s",
                    len(imported),
                    [str(p) for p in files_read],
                    sorted(imported),
                )
    except Exception:  # noqa: BLE001 — never break startup on auto-import
        logger.warning("dotenv auto-discover failed", exc_info=True)

    yield
    # D-08b: llama.cpp lifecycle shutdown (Phase 07.1)
    # review-fix #4: shutdown() is sync and returns bool; wrap with asyncio.to_thread
    # to avoid TypeError on `await bool`. The return value is logged but not surfaced.
    try:
        from .services.llm.llamacpp_launcher import shutdown as llamacpp_shutdown
        was_running = await asyncio.to_thread(llamacpp_shutdown)
        logger.info("llama.cpp shutdown on app exit: was_running=%s", was_running)
    except Exception:  # noqa: BLE001
        logger.warning("llama.cpp shutdown raised", exc_info=True)
    # Shutdown: close pool.
    await engine.dispose()


app = FastAPI(
    title="Medieval Forge",
    version="0.1.0",
    lifespan=lifespan,
)

from .api.projects import router as projects_router  # noqa: E402
# v1 export_router REMOVED in Phase 06 Plan 03 (D-04). See api/v3/export.py.
from .api import terrain as terrain_api  # noqa: E402
from .api.v3.ingest import router as v3_ingest_router  # noqa: E402
from .api.v3.artifacts import router as v3_artifacts_router  # noqa: E402
from .api.v3.status import router as v3_status_router  # noqa: E402
from .api.v3.generate import router as v3_generate_router  # noqa: E402
from .api.v3.render import router as v3_render_router  # noqa: E402
from .api.v3 import regions as v3_regions  # noqa: E402
from .api.v3 import projects as v3_projects  # noqa: E402
from .api.v3.export import router as v3_export_router  # noqa: E402
# Phase 07 Plan 07b — research SSE orchestrator + credentials CRUD.
from .api.v3.research import (  # noqa: E402
    router as research_router,
    overlay_router as research_overlay_router,
)
from .api.v3.credentials import router as credentials_router  # noqa: E402
# Phase 07.1 Plan 05 — llama.cpp launch/delete/status router.
from .api.v3 import llamacpp as llamacpp_v3  # noqa: E402
# UAT 2026-05-21 — Ollama daemon launcher (POST /api/v3/llm/ollama/launch).
from .api.v3 import ollama as ollama_v3  # noqa: E402
# Phase 08 plan 03a — Branch CRUD (D-10/D-11/D-13/D-15/D-22).
from .api.v3 import branches as branches_v3  # noqa: E402
# Phase 08 plan 06a — Editor validate endpoint (POST /editor/validate batch).
from .api.v3.editor import router as editor_router  # noqa: E402

app.include_router(projects_router, prefix="/api")
# v1 export_router mount REMOVED (D-04) -- replaced by v3_export_router below.
app.include_router(terrain_api.router, prefix="/api")
app.include_router(v3_ingest_router, prefix="/api")
app.include_router(v3_artifacts_router, prefix="/api")
app.include_router(v3_status_router, prefix="/api")
app.include_router(v3_generate_router, prefix="/api")
app.include_router(v3_render_router, prefix="/api")
app.include_router(v3_regions.router, prefix="/api")
app.include_router(v3_projects.router, prefix="/api")
app.include_router(v3_export_router, prefix="/api")
# Phase 07 Plan 07b mounts — order matters: research_router carries /v3/research,
# research_overlay_router carries /v3/projects/{id}/research/overlay,
# credentials_router carries /v3/credentials. main.py adds /api prefix.
app.include_router(research_router, prefix="/api")
app.include_router(research_overlay_router, prefix="/api")
app.include_router(credentials_router, prefix="/api")
# Phase 07.1 Plan 05 — llama.cpp router carries /v3/llm; main.py adds /api.
app.include_router(llamacpp_v3.router, prefix="/api")
# UAT 2026-05-21 — Ollama daemon launcher router (same /v3/llm prefix).
app.include_router(ollama_v3.router, prefix="/api")
# Phase 08 plan 03a — Branch CRUD router (/v3/projects/{id}/branches).
app.include_router(branches_v3.router, prefix="/api")
# Phase 08 plan 06a — Editor validate router (/v3/projects/{id}/editor/validate).
app.include_router(editor_router, prefix="/api")

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
