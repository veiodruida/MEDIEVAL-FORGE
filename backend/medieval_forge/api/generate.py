"""GEN-01..03: trigger generation (BackgroundTask) + serve PNG previews.

T-PATH: project_id validated; preview filename whitelisted.
T-DOS:  reject if project already generating.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import Project
from ..services.generator import GENERATED_FILE_WHITELIST, run_generation
from ..services.paths import is_valid_uuid, project_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["generate"])


_MEDIA_TYPES = {".png": "image/png", ".json": "application/json"}


async def _run_and_update_status(project_id: str, config: dict) -> None:
    """Background task body: runs generation; updates project.status atomically."""
    last_error: str | None = None
    try:
        manifest = await run_generation(project_id, config)
        new_status = "generated"
        logger.info("generation succeeded for %s: %d files", project_id, len(manifest))
    except Exception as exc:  # noqa: BLE001 — top of background task
        logger.exception("generation failed for %s", project_id)
        new_status = "error_generating"
        last_error = str(exc)

    # Open a fresh session — we are no longer inside the request scope.
    async with AsyncSessionLocal() as session:
        proj = await session.get(Project, project_id)
        if proj is not None:
            proj.status = new_status
            if last_error is not None:
                cfg = dict(proj.generator_config or {})
                cfg["last_error"] = last_error
                proj.generator_config = cfg
            await session.commit()


@router.post("/{project_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_generate(
    project_id: str,
    background_tasks: BackgroundTasks,
    body: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if project.status == "generating":
        raise HTTPException(
            status_code=409,
            detail="project is already generating; wait for that to finish",
        )

    # Compose config: project.generator_config overlaid with the request body.
    merged: dict = dict(project.generator_config or {})
    if body:
        merged.update(body)
    if "territory_data" not in merged:
        raise HTTPException(
            status_code=422,
            detail=(
                'territory_data is required (provide in request body as '
                '{"territory_data": {"kingdoms":..., "duchies":..., "condados":...}} '
                "or persist into project.generator_config first)"
            ),
        )

    project.status = "generating"
    await db.commit()

    background_tasks.add_task(_run_and_update_status, project_id, merged)
    return {"project_id": project_id, "status": "generating"}


@router.get("/{project_id}/preview/{filename}")
async def get_preview(project_id: str, filename: str) -> FileResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
    if filename not in GENERATED_FILE_WHITELIST:
        raise HTTPException(
            status_code=400,
            detail=f"filename not in whitelist; allowed: {sorted(GENERATED_FILE_WHITELIST)}",
        )
    generated_dir: Path = project_dir(project_id) / "generated"
    target = generated_dir / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"preview {filename!r} not generated yet")
    media_type = _MEDIA_TYPES.get(target.suffix, "application/octet-stream")
    return FileResponse(target, media_type=media_type)
