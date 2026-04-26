"""Shared helper for bumping Project.updated_at on edit endpoints.

Disk-level GeoJSON writes (save_territories) do NOT touch the projects table,
so the SQLAlchemy `onupdate=_utcnow` hook never fires for Phase 4 mutations.
This helper issues an explicit UPDATE so clients/UI/tests can rely on
`Project.updated_at` as a reliable staleness signal after edits.

Closes orphan bug #5 from .planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Project


async def touch_project(session: AsyncSession, project_id: str) -> bool:
    """Bump Project.updated_at to now(UTC). No-op if project_id has no DB row.

    Returns True if a row was updated, False otherwise. Does NOT commit —
    caller owns the transaction so the bump can be batched with other writes
    in a single session.commit().

    Test fixtures using synthetic UUIDs without inserting a Project row
    rely on the no-op behavior to avoid spurious failures.
    """
    result = await session.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    return result.rowcount > 0
