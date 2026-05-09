"""v3 status manifest endpoint (D-21).

Returns `{status, has_artifacts, last_generated_at}`. Frontend reads this
on mount to decide which UI state to render (empty / generating / ready /
error).

`has_artifacts` is a per-file boolean across the 14-file allowlist defined
in `artifacts.py` (single source of truth).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Project
from ...services.paths import is_valid_uuid, project_dir
from .artifacts import ARTIFACT_FILES

router = APIRouter(prefix="/v3/projects", tags=["v3-status"])


class StatusResponse(BaseModel):
    status: str
    has_artifacts: dict[str, bool]
    last_generated_at: str | None


@router.get("/{project_id}/status", response_model=StatusResponse)
async def get_status(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> StatusResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    try:
        out = project_dir(project_id) / "output"
    except ValueError:
        raise HTTPException(status_code=404, detail="project not found")

    has = {f: (out / f).is_file() for f in ARTIFACT_FILES}

    return StatusResponse(
        status=project.status,
        has_artifacts=has,
        last_generated_at=(
            project.updated_at.isoformat() if project.status == "generated" else None
        ),
    )


__all__ = ["router"]
