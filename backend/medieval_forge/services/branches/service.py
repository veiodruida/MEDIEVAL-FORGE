"""Phase 08 D-10/D-11/D-15/D-22: Branch CRUD + lazy main creation + idx inheritance."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Branch


class BranchProtectedError(Exception):
    """D-15: main branch cannot be deleted via UI."""


class BranchNameTakenError(Exception):
    """D-13: unique constraint on (project_id, name)."""


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
        raise BranchNameTakenError("'main' is reserved; created lazily by ensure_main_branch")
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
