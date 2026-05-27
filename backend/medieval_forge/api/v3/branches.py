"""Phase 08 D-10..D-15: Branch CRUD endpoints.

Local-only — no auth (RESEARCH §Security Domain V13).
All endpoints delegate to services/branches/service.py; router is thin.

Security mitigations (threat model 08-03a):
  T-08-03a-01: Pydantic pattern=r"^[a-zA-Z0-9_-]+$" rejects SQL/template-injection chars.
  T-08-03a-02: is_valid_uuid guard at every endpoint (path traversal via project_id).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...services.paths import is_valid_uuid
from ...services.branches.service import (
    BranchNameReservedError,
    BranchNameTakenError,
    BranchProtectedError,
    create_branch,
    delete_branch,
    ensure_main_branch,
    list_branches,
    rename_branch,
)

router = APIRouter(
    prefix="/v3/projects/{project_id}/branches",
    tags=["v3-branches"],
)


class BranchCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$")
    parent_branch_id: str | None = None


class BranchRenameBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$")


def _guard_pid(project_id: str) -> None:
    """T-08-03a-02: reject non-UUID project_id with 400."""
    if not is_valid_uuid(project_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="project_id must be a valid UUID")


def _branch_dict(b) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "is_main": b.is_main,
        "original_idx_high_water": b.original_idx_high_water,
        "edits_since_snapshot": b.edits_since_snapshot,
        "created_at": b.created_at.isoformat(),
        "updated_at": b.updated_at.isoformat(),
    }


@router.get("")
async def list_branches_endpoint(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """D-10: lazy-creates main on first hit; returns list ordered by updated_at desc."""
    _guard_pid(project_id)
    await ensure_main_branch(db, project_id)
    branches = await list_branches(db, project_id)
    return [_branch_dict(b) for b in branches]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_branch_endpoint(
    project_id: str,
    body: BranchCreateBody,
    db: AsyncSession = Depends(get_db),
):
    """D-11: explicit branch creation; D-22: inherits parent original_idx_high_water."""
    _guard_pid(project_id)
    try:
        branch = await create_branch(db, project_id, body.name, body.parent_branch_id)
    except BranchNameReservedError as exc:
        # 'main' is reserved — bad request (caller error, not conflict)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except BranchNameTakenError as exc:
        # Duplicate name already in DB — conflict
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    return {"id": branch.id, "name": branch.name, "is_main": branch.is_main}


@router.patch("/{branch_id}")
async def rename_branch_endpoint(
    project_id: str,
    branch_id: str,
    body: BranchRenameBody,
    db: AsyncSession = Depends(get_db),
):
    """D-15: rename is allowed on main. Returns updated branch."""
    _guard_pid(project_id)
    try:
        branch = await rename_branch(db, branch_id, body.name)
    except BranchNameTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    return {"id": branch.id, "name": branch.name}


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch_endpoint(
    project_id: str,
    branch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """D-15: main branch is delete-protected; returns 409 + BRANCH_PROTECTED code."""
    _guard_pid(project_id)
    try:
        await delete_branch(db, branch_id)
    except BranchProtectedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "BRANCH_PROTECTED", "message": "main branch cannot be deleted"},
        )
    return None
