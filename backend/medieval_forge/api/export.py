"""EXPORT-01 + EXPORT-02: trigger ZIP build + serve download."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Project
from ..services.export import build_unity_zip
from ..services.paths import is_valid_uuid, project_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["export"])

_ALLOWED_PRE_EXPORT_STATUSES: frozenset[str] = frozenset({"generated", "exported"})


@router.post("/{project_id}/export", status_code=status.HTTP_201_CREATED)
async def trigger_export(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if project.status not in _ALLOWED_PRE_EXPORT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"project.status is {project.status!r}; export requires "
                f"status in {sorted(_ALLOWED_PRE_EXPORT_STATUSES)} "
                "(run /generate first)"
            ),
        )

    try:
        zip_path = build_unity_zip(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    project.status = "exported"
    await db.commit()

    return {
        "project_id": project_id,
        "zip_filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "download_url": f"/api/projects/{project_id}/export/download",
    }


@router.get("/{project_id}/export/download")
async def download_export(project_id: str) -> FileResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
    exports_dir = project_dir(project_id) / "exports"
    if not exports_dir.is_dir():
        raise HTTPException(status_code=404, detail="no exports for this project")
    candidates = sorted(
        exports_dir.glob(f"medieval-forge-{project_id}-*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise HTTPException(status_code=404, detail="no exports for this project")
    target = candidates[0]
    return FileResponse(
        target,
        media_type="application/zip",
        filename=target.name,
        headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
    )
