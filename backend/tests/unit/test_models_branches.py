"""Phase 08 plan 03a — Branch ORM model + service unit tests.

Covers: BRANCH-01, PERSIST-01
D-10: lazy main creation, D-11: explicit create, D-15: delete-protected main,
D-22: original_idx_high_water inheritance from parent.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medieval_forge.models import Base, Branch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite session with Branch table created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Wave-0 stub tests (scope: 08-03b — snapshot + edit_event tables)
# These stubs belong to plan 08-03b and remain skipped here.
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Snapshot model lands in plan 08-03b")
def test_snapshot_orm_roundtrip_stores_compressed_geojson():
    """PERSIST-01: Snapshot ORM stores compressed GeoJSON; decompressed == original."""
    pass


@pytest.mark.skip(reason="EditEvent model lands in plan 08-03b")
def test_edit_event_orm_roundtrip_preserves_operation_type_and_payload():
    """PERSIST-01: EditEvent ORM stores op_type + payload dict; round-trip eq."""
    pass


# ---------------------------------------------------------------------------
# Branch ORM tests (plan 08-03a)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_branch_orm_roundtrip_persists_and_retrieves_by_id(db):
    """BRANCH-01 + PERSIST-01: Branch row round-trips through AsyncSession.

    project_id='p1' used directly (no FK enforcement on in-memory SQLite).
    """
    from sqlalchemy import select

    branch = Branch(project_id="p1", name="main", is_main=True)
    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    fetched = (await db.execute(select(Branch).where(Branch.id == branch.id))).scalar_one()
    assert fetched.id == branch.id
    assert fetched.name == "main"
    assert fetched.is_main is True
    assert fetched.project_id == "p1"


@pytest.mark.asyncio
async def test_branch_original_idx_high_water_defaults_to_zero(db):
    """D-22: high-water-mark starts at 0 for a new branch."""
    branch = Branch(project_id="p2", name="main", is_main=True)
    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    assert branch.original_idx_high_water == 0


@pytest.mark.asyncio
async def test_branch_has_unique_constraint_on_project_id_and_name(db):
    """BRANCH-01: IntegrityError when inserting duplicate (project_id, name)."""
    b1 = Branch(project_id="p3", name="main", is_main=True)
    b2 = Branch(project_id="p3", name="main", is_main=False)
    db.add(b1)
    await db.commit()

    db.add(b2)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_main_branch_creates_main_when_absent(db):
    """D-10: ensure_main_branch lazy-creates is_main=True branch if none exists."""
    from medieval_forge.services.branches.service import ensure_main_branch

    branch = await ensure_main_branch(db, "proj-lazy-1")
    assert branch.name == "main"
    assert branch.is_main is True


@pytest.mark.asyncio
async def test_ensure_main_branch_is_idempotent(db):
    """D-10: calling ensure_main_branch twice returns the same row id."""
    from medieval_forge.services.branches.service import ensure_main_branch

    b1 = await ensure_main_branch(db, "proj-lazy-2")
    b2 = await ensure_main_branch(db, "proj-lazy-2")
    assert b1.id == b2.id


@pytest.mark.asyncio
async def test_create_branch_inherits_parent_original_idx_high_water(db):
    """D-22: child branch inherits parent's original_idx_high_water=42 exactly."""
    from sqlalchemy import select
    from medieval_forge.services.branches.service import ensure_main_branch, create_branch

    main = await ensure_main_branch(db, "proj-hw-1")
    # Set an explicit numeric fixture so the assertion is unambiguous (user feedback).
    main.original_idx_high_water = 42
    await db.commit()
    await db.refresh(main)

    child = await create_branch(db, "proj-hw-1", "experiment", parent_branch_id=main.id)
    assert child.original_idx_high_water == 42


@pytest.mark.asyncio
async def test_delete_branch_raises_branch_protected_error_for_main(db):
    """D-15: delete_branch raises BranchProtectedError when branch.is_main=True."""
    from medieval_forge.services.branches.service import (
        ensure_main_branch, delete_branch, BranchProtectedError
    )

    main = await ensure_main_branch(db, "proj-del-1")
    with pytest.raises(BranchProtectedError):
        await delete_branch(db, main.id)
