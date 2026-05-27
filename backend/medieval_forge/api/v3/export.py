"""Phase 06: POST /api/v3/projects/{id}/export with validation gate (D-01..D-08).

Replaces v1 api/export.py. Supports ?dry_run=true for gate-only execution
(D-03). On gate failure returns 422 with the structured error envelope (D-08).
On gate pass returns 201 + zip metadata or 200 + dry-run report.

Phase 06 frontend swap is deferred per D-19 -- the React Export button still
calls v1 /api/projects/{id}/export until Phase 06.1 / 07. That button is
TEMPORARILY broken between this PR merge and the UI swap. Acceptable per
CONTEXT.md (tools-first delivery).

Phase 08 Plan 10 (D-16): POST body extended with optional branch_id. When set,
endpoint resolves active branch + latest snapshot and passes branch metadata
into build_unity_zip. Non-branch callers (no body / branch_id=null) are
unaffected — backward-compat preserved (Pitfall 4).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Branch, Project, Snapshot
from ...services.export import (
    ValidationFailedError,
    build_unity_zip,
    validate_export,
)
from ...services.export.zip import UNITY_ZIP_SPEC, resolve_generated_dir
from ...services.paths import is_valid_uuid, project_dir
from ...services.pipeline.region_loader import load_region
from ...services.branches.service import list_snapshots

logger = logging.getLogger(__name__)

# CRITICAL: prefix is /v3/projects, NOT /api/v3/projects. main.py adds /api at mount time.
router = APIRouter(prefix="/v3/projects", tags=["v3-export"])


class ExportRequestBody(BaseModel):
    """Phase 08 Plan 10 D-16: optional branch context for branch-aware export.

    Omitting body or setting branch_id=null produces a non-branch export
    (backward-compat with all existing callers).
    """
    branch_id: Optional[str] = None

_ALLOWED_PRE_EXPORT_STATUSES: frozenset[str] = frozenset({"generated", "exported"})


@router.post("/{project_id}/export")
async def trigger_v3_export(
    project_id: str,
    dry_run: bool = False,
    body: ExportRequestBody = None,
    db: AsyncSession = Depends(get_db),
):
    """POST /api/v3/projects/{id}/export?dry_run=<bool>

    Body (optional, Phase 08 D-16):
      {"branch_id": "<uuid>"}  -- export with branch metadata in MANIFEST
      {}  or omitted           -- non-branch export (backward-compat)

    Returns:
      201 + {project_id, zip_filename, size_bytes, download_url}     -- gate passed, zip written
      200 + {dry_run: true, passed: true, errors: [], warnings: []}  -- dry_run=true, gate passed
      422 + {detail: {summary, errors, warnings}}                     -- gate failed (D-08 envelope)
      422 + {dry_run: true, detail: {summary, errors, warnings}}      -- dry_run=true, gate failed
      400 -- invalid UUID / invalid branch_id
      404 -- project not found
      409 -- wrong status (run /generate first)
      409 -- no pipeline output (FileNotFoundError from build_unity_zip)
      409 -- branch has no snapshots (branch_id supplied but no snapshot exists)
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

    # Phase 08 Plan 10 D-16: resolve branch metadata when branch_id is supplied.
    # T-08-10-01 mitigate: validate UUID format + 404 if branch missing.
    branch_name: str | None = None
    snapshot_id: str | None = None
    snapshot_timestamp = None

    branch_id = (body.branch_id if body is not None else None)
    if branch_id is not None:
        if not is_valid_uuid(branch_id):
            raise HTTPException(status_code=400, detail="branch_id must be a valid UUID")
        from sqlalchemy import select
        branch = (
            await db.execute(select(Branch).where(Branch.id == branch_id))
        ).scalar_one_or_none()
        if branch is None:
            raise HTTPException(status_code=404, detail=f"branch {branch_id!r} not found")
        # Fetch latest snapshot (list_snapshots returns reverse-chron; [0] = latest)
        snapshots = await list_snapshots(db, branch_id)
        if not snapshots:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"branch {branch.name!r} has no snapshots; "
                    "create a snapshot before exporting with branch context"
                ),
            )
        latest = snapshots[0]
        branch_name = branch.name
        snapshot_id = latest.id
        snapshot_timestamp = latest.created_at

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
        zip_path = build_unity_zip(
            project_id,
            cfg=cfg,
            region_key=project.region_key,
            branch_name=branch_name,
            snapshot_id=snapshot_id,
            snapshot_timestamp=snapshot_timestamp,
        )
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
