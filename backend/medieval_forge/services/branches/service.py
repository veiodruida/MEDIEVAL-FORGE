"""Phase 08 D-10/D-11/D-15/D-22/D-35/D-37: Branch CRUD + snapshot + edit-event helpers."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Branch, EditEvent, Snapshot
from .snapshot import SnapshotPayload, SnapshotTooLargeError, deserialize, serialize

# D-37: auto-snapshot every N edits
AUTO_SNAPSHOT_EVERY_N_EDITS = 25

# T-08-03b-02 mitigate: cap edit log per branch to avoid unbounded growth
MAX_EDIT_EVENTS_PER_BRANCH = 10_000


class BranchProtectedError(Exception):
    """D-15: main branch cannot be deleted via UI."""


class BranchNameTakenError(Exception):
    """D-13: unique constraint on (project_id, name) — duplicate name in DB."""


class BranchNameReservedError(BranchNameTakenError):
    """'main' is a reserved name; creation is only via ensure_main_branch."""


async def ensure_main_branch(db: AsyncSession, project_id: str) -> Branch:
    """D-10 lazy-create: every project must have a 'main' branch on first touch.

    Idempotent — returns existing main if present.
    """
    existing = (
        await db.execute(
            select(Branch).where(
                Branch.project_id == project_id,
                Branch.is_main == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    branch = Branch(project_id=project_id, name="main", is_main=True)
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch


async def create_branch(
    db: AsyncSession,
    project_id: str,
    name: str,
    parent_branch_id: str | None,
) -> Branch:
    """D-11: explicit create. D-22: inherits original_idx_high_water from parent."""
    if name == "main":
        raise BranchNameReservedError("'main' is reserved; created lazily by ensure_main_branch")
    branch = Branch(project_id=project_id, name=name, is_main=False)
    if parent_branch_id:
        parent = (
            await db.execute(select(Branch).where(Branch.id == parent_branch_id))
        ).scalar_one()
        branch.original_idx_high_water = parent.original_idx_high_water
    db.add(branch)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BranchNameTakenError(f"branch name '{name}' already exists") from exc
    await db.refresh(branch)
    return branch


async def list_branches(db: AsyncSession, project_id: str) -> list[Branch]:
    """D-13: sorted by updated_at desc (most-recent-edit first)."""
    return list(
        (
            await db.execute(
                select(Branch)
                .where(Branch.project_id == project_id)
                .order_by(Branch.updated_at.desc())
            )
        ).scalars()
    )


async def rename_branch(db: AsyncSession, branch_id: str, new_name: str) -> Branch:
    """D-15: rename allowed on main (not delete-protected, just delete-protected)."""
    branch = (
        await db.execute(select(Branch).where(Branch.id == branch_id))
    ).scalar_one()
    branch.name = new_name
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BranchNameTakenError(f"branch name '{new_name}' already exists") from exc
    await db.refresh(branch)
    return branch


async def delete_branch(db: AsyncSession, branch_id: str) -> None:
    """D-15: main is delete-protected."""
    branch = (
        await db.execute(select(Branch).where(Branch.id == branch_id))
    ).scalar_one()
    if branch.is_main:
        raise BranchProtectedError("main branch cannot be deleted")
    await db.execute(delete(Branch).where(Branch.id == branch_id))
    await db.commit()


# ---------------------------------------------------------------------------
# Snapshot helpers (D-12, D-37)
# ---------------------------------------------------------------------------

class EditLogFullError(Exception):
    """T-08-03b-02: branch has reached MAX_EDIT_EVENTS_PER_BRANCH (10 000)."""


async def create_snapshot(
    db: AsyncSession,
    branch_id: str,
    payload: SnapshotPayload,
    trigger: str,
) -> Snapshot:
    """D-12: gzip+json blob stored in snapshots table.

    trigger must be one of: "auto", "manual", "pre_slider_change".
    Resets Branch.edits_since_snapshot to 0 on success (D-37).
    Raises SnapshotTooLargeError if payload exceeds 10 MB (T-08-03b-01).
    """
    if trigger not in {"auto", "manual", "pre_slider_change"}:
        raise ValueError(f"invalid trigger: {trigger!r}")

    # Determine next seq (1-based, monotonic per branch)
    last_seq = (
        await db.execute(
            select(Snapshot.seq)
            .where(Snapshot.branch_id == branch_id)
            .order_by(Snapshot.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none() or 0
    next_seq = last_seq + 1

    # serialize raises SnapshotTooLargeError if payload > 10 MB
    blob = serialize(payload)

    snap = Snapshot(branch_id=branch_id, seq=next_seq, blob=blob, trigger=trigger)
    db.add(snap)

    # Reset cadence counter on branch (D-37)
    branch = (
        await db.execute(select(Branch).where(Branch.id == branch_id))
    ).scalar_one()
    branch.edits_since_snapshot = 0

    await db.commit()
    await db.refresh(snap)
    return snap


async def list_snapshots(db: AsyncSession, branch_id: str) -> list[Snapshot]:
    """PERSIST-02: reverse-chronological by seq (highest first)."""
    return list(
        (
            await db.execute(
                select(Snapshot)
                .where(Snapshot.branch_id == branch_id)
                .order_by(Snapshot.seq.desc())
            )
        ).scalars()
    )


async def restore_snapshot(db: AsyncSession, snapshot_id: str) -> SnapshotPayload:
    """PERSIST-02: decompress and decode snapshot blob."""
    snap = (
        await db.execute(select(Snapshot).where(Snapshot.id == snapshot_id))
    ).scalar_one()
    return deserialize(snap.blob)


# ---------------------------------------------------------------------------
# Edit-event helpers (D-35, D-37, T-08-03b-02)
# ---------------------------------------------------------------------------

async def append_edit_event(
    db: AsyncSession,
    branch_id: str,
    op_type: str,
    payload: dict,
) -> EditEvent:
    """D-35 + D-37: log edit op, increment edits_since_snapshot counter.

    Raises EditLogFullError when branch already has MAX_EDIT_EVENTS_PER_BRANCH rows
    (T-08-03b-02 mitigate disposition).
    """
    # T-08-03b-02: cap at 10 000 ops per branch
    current_count = (
        await db.execute(
            select(func.count()).select_from(EditEvent).where(EditEvent.branch_id == branch_id)
        )
    ).scalar_one()
    if current_count >= MAX_EDIT_EVENTS_PER_BRANCH:
        raise EditLogFullError(
            f"branch {branch_id!r} has reached the {MAX_EDIT_EVENTS_PER_BRANCH}-event cap"
        )

    evt = EditEvent(branch_id=branch_id, op_type=op_type, payload=payload)
    db.add(evt)

    branch = (
        await db.execute(select(Branch).where(Branch.id == branch_id))
    ).scalar_one()
    branch.edits_since_snapshot += 1

    await db.commit()
    await db.refresh(evt)
    return evt
