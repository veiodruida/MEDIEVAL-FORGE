"""Phase 08 D-10..D-15 + D-12 + D-35 + D-37: Branch CRUD + snapshot + edit-event endpoints.

Local-only — no auth (RESEARCH §Security Domain V13).
All endpoints delegate to services/branches/service.py; router is thin.

Security mitigations (threat model 08-03a + 08-03b):
  T-08-03a-01: Pydantic pattern=r"^[a-zA-Z0-9_-]+$" rejects SQL/template-injection chars.
  T-08-03a-02: is_valid_uuid guard at every endpoint (path traversal via project_id).
  T-08-03b-01: SnapshotTooLargeError → 413 (zip-bomb cap, RESEARCH §V12).
  T-08-03b-02: EditLogFullError → 409 EDIT_LOG_FULL (10 000-op cap per branch).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Branch
from ...services.paths import is_valid_uuid
from ...services.branches.service import (
    AUTO_SNAPSHOT_EVERY_N_EDITS,
    BranchNameReservedError,
    BranchNameTakenError,
    BranchProtectedError,
    EditLogFullError,
    append_edit_event,
    create_branch,
    create_snapshot,
    delete_branch,
    ensure_main_branch,
    list_branches,
    list_snapshots,
    rename_branch,
    restore_snapshot,
)
from ...services.branches.snapshot import SnapshotTooLargeError

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


# ---------------------------------------------------------------------------
# Snapshot request/response models
# ---------------------------------------------------------------------------

class SnapshotCreateBody(BaseModel):
    trigger: str = Field(..., pattern=r"^(auto|manual|pre_slider_change)$")
    payload: dict[str, Any]  # SnapshotPayload shape; size guard at serialize()


class EditEventBody(BaseModel):
    op_type: str = Field(..., min_length=1, max_length=32)
    payload: dict[str, Any]
    # Frontend supplies full state when it knows the counter is at AUTO_SNAPSHOT_EVERY_N_EDITS - 1
    snapshot_payload_if_due: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Snapshot endpoints (D-12, PERSIST-01, PERSIST-02)
# ---------------------------------------------------------------------------

@router.post("/{branch_id}/snapshots", status_code=status.HTTP_201_CREATED)
async def create_snapshot_endpoint(
    project_id: str,
    branch_id: str,
    body: SnapshotCreateBody,
    db: AsyncSession = Depends(get_db),
):
    """D-12: create snapshot blob; trigger ∈ {auto, manual, pre_slider_change}.

    Returns 201 + {snapshot_id, seq, created_at}.
    Returns 413 if payload exceeds MAX_DECOMPRESSED_BYTES (T-08-03b-01).
    Per Pitfall 9: frontend ONLY opens restore modal if response is 201.
    """
    _guard_pid(project_id)
    try:
        snap = await create_snapshot(db, branch_id, body.payload, body.trigger)
    except SnapshotTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))

    # Phase 08.2 Plan 04 Rule 1 fix: when a manual snapshot contains vertex ops
    # (op:'move'/'add'/'delete'/'multi_delete' in edit_log), bump branch.manual_edit_log_hash
    # so _render_producer's hash gate passes and snapshot_loader is injected.
    #
    # Invariant preserved: hash non-empty ↔ snapshot exists for this branch.
    # BEZ-CONV-04 safety: the hash gate in _render_producer is: if branch_row and hash:
    #   → only set when vertex ops exist in the snapshot.
    # Landmask-only branches (no vertex ops) keep hash="", skipping replay. ✓
    _VERTEX_OPS = frozenset({"move", "add", "delete", "multi_delete"})
    edit_log = body.payload.get("edit_log", [])
    has_vertex_ops = any(
        isinstance(e, dict) and e.get("op") in _VERTEX_OPS
        for e in edit_log
    )
    if body.trigger == "manual" and has_vertex_ops:
        branch = (
            await db.execute(select(Branch).where(Branch.id == branch_id))
        ).scalar_one_or_none()
        if branch is not None:
            new_count = branch.manual_edit_log_count + 1
            payload_for_hash = {"edit_log": edit_log, "snap_seq": snap.seq}
            data = f"{branch_id}:{new_count}:{json.dumps(payload_for_hash, sort_keys=True)}"
            new_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
            branch.manual_edit_log_count = new_count
            branch.manual_edit_log_hash = new_hash
            await db.commit()

    return {
        "snapshot_id": snap.id,
        "seq": snap.seq,
        "created_at": snap.created_at.isoformat(),
    }


@router.get("/{branch_id}/snapshots")
async def list_snapshots_endpoint(
    project_id: str,
    branch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """PERSIST-02: list snapshots reverse-chronological by seq (highest first)."""
    _guard_pid(project_id)
    snaps = await list_snapshots(db, branch_id)
    return [
        {
            "id": s.id,
            "seq": s.seq,
            "trigger": s.trigger,
            "created_at": s.created_at.isoformat(),
            "size_bytes": len(s.blob),
        }
        for s in snaps
    ]


@router.post("/{branch_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot_endpoint(
    project_id: str,
    branch_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
):
    """PERSIST-02: decompress and return snapshot payload; frontend rehydrates store."""
    _guard_pid(project_id)
    payload = await restore_snapshot(db, snapshot_id)
    return payload


# ---------------------------------------------------------------------------
# Edit-event endpoint (D-35, D-37)
# ---------------------------------------------------------------------------

@router.post("/{branch_id}/edit-events", status_code=status.HTTP_201_CREATED)
async def edit_event_endpoint(
    project_id: str,
    branch_id: str,
    body: EditEventBody,
    db: AsyncSession = Depends(get_db),
):
    """D-35 + D-37: log edit op; auto-snapshot when counter reaches 25.

    Returns 201 + {event_id, auto_snapshot, edits_since_snapshot}.
    Returns 409 EDIT_LOG_FULL when branch has 10 000+ events (T-08-03b-02).
    """
    _guard_pid(project_id)
    try:
        evt = await append_edit_event(db, branch_id, body.op_type, body.payload)
    except EditLogFullError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "EDIT_LOG_FULL", "message": "branch edit log is full (10 000 ops)"},
        )

    # Re-query branch to get fresh edits_since_snapshot after commit
    branch = (
        await db.execute(select(Branch).where(Branch.id == branch_id))
    ).scalar_one()

    auto_snap = None
    if (
        branch.edits_since_snapshot >= AUTO_SNAPSHOT_EVERY_N_EDITS
        and body.snapshot_payload_if_due is not None
    ):
        try:
            snap = await create_snapshot(db, branch_id, body.snapshot_payload_if_due, "auto")
            auto_snap = {"snapshot_id": snap.id, "seq": snap.seq}
            # Refresh branch counter after snapshot reset
            await db.refresh(branch)
        except SnapshotTooLargeError:
            # Don't fail the edit event — frontend retries snapshot separately
            auto_snap = {"error": "SNAPSHOT_TOO_LARGE"}

    return {
        "event_id": evt.id,
        "auto_snapshot": auto_snap,
        "edits_since_snapshot": branch.edits_since_snapshot,
    }
