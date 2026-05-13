"""Phase 06: POST /api/v3/projects/{id}/export with validation gate (D-01..D-08).

Replaces v1 api/export.py. Supports ?dry_run=true for gate-only execution
(D-03). On gate failure returns 422 with the structured error envelope (D-08).
On gate pass returns 201 + zip metadata or 200 + dry-run report.

Phase 06 frontend swap is deferred per D-19 -- the React Export button still
calls v1 /api/projects/{id}/export until Phase 06.1 / 07. That button is
TEMPORARILY broken between this PR merge and the UI swap. Acceptable per
CONTEXT.md (tools-first delivery).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Project
from ...services.export import (
    ValidationFailedError,
    build_unity_zip,
    validate_export,
)
from ...services.export.zip import UNITY_ZIP_SPEC, resolve_generated_dir
from ...services.paths import is_valid_uuid, project_dir
from ...services.pipeline.region_loader import load_region

logger = logging.getLogger(__name__)

# CRITICAL: prefix is /v3/projects, NOT /api/v3/projects. main.py adds /api at mount time.
router = APIRouter(prefix="/v3/projects", tags=["v3-export"])

_ALLOWED_PRE_EXPORT_STATUSES: frozenset[str] = frozenset({"generated", "exported"})


@router.post("/{project_id}/export")
async def trigger_v3_export(
    project_id: str,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """POST /api/v3/projects/{id}/export?dry_run=<bool>

    Returns:
      201 + {project_id, zip_filename, size_bytes, download_url}     -- gate passed, zip written
      200 + {dry_run: true, passed: true, errors: [], warnings: []}  -- dry_run=true, gate passed
      422 + {detail: {summary, errors, warnings}}                     -- gate failed (D-08 envelope)
      422 + {dry_run: true, detail: {summary, errors, warnings}}      -- dry_run=true, gate failed
      400 -- invalid UUID
      404 -- project not found
      409 -- wrong status (run /generate first)
      409 -- no pipeline output (FileNotFoundError from build_unity_zip)
    """
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
                f"status in {sorted(_ALLOWED_PRE_EXPORT_STATUSES)} (run /generate first)"
            ),
        )
    if not project.region_key:
        raise HTTPException(
            status_code=409,
            detail="project has no region_key; cannot load cfg for validator",
        )

    cfg = load_region(project.region_key)

    if dry_run:
        # D-03: gate-only, no zip written. Status not flipped.
        # Use shared resolve_generated_dir (same logic as build_unity_zip):
        # prefers project_dir/output only when non-empty; falls back to /generated.
        # This avoids dry-run validating an empty /output dir while real export
        # would use /generated (WR-02 fix).
        generated = resolve_generated_dir(project_id)
        any_generated = any((generated / fname).exists() for fname in UNITY_ZIP_SPEC)
        if not any_generated:
            raise HTTPException(
                status_code=409,
                detail=f"no pipeline output in {generated} -- run /generate first",
            )
        report, _sha = validate_export(generated, cfg)
        if report.passed:
            return JSONResponse(
                status_code=200,
                content={"dry_run": True, **report.model_dump()},
            )
        # WR-01: wrap failure in the same D-08 envelope as the real-export 422
        # so callers parse both 422 shapes identically.
        return JSONResponse(
            status_code=422,
            content={
                "dry_run": True,
                "detail": {
                    "summary": f"{len(report.errors)} errors blocked export",
                    "errors": [e.model_dump() for e in report.errors],
                    "warnings": [w.model_dump() for w in report.warnings],
                },
            },
        )

    # Real export: validator -> zip -> status flip
    try:
        zip_path = build_unity_zip(project_id, cfg=cfg, region_key=project.region_key)
    except ValidationFailedError as exc:
        # D-08 structured envelope
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "summary": f"{len(exc.report.errors)} errors blocked export",
                    "errors": [e.model_dump() for e in exc.report.errors],
                    "warnings": [w.model_dump() for w in exc.report.warnings],
                }
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    project.status = "exported"
    await db.commit()

    return JSONResponse(
        status_code=201,
        content={
            "project_id": project_id,
            "zip_filename": zip_path.name,
            "size_bytes": zip_path.stat().st_size,
            "download_url": f"/api/v3/projects/{project_id}/export/download",
        },
    )


@router.get("/{project_id}/export/download")
async def download_v3_export(project_id: str):
    """GET /api/v3/projects/{id}/export/download -- returns the most recent zip."""
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
