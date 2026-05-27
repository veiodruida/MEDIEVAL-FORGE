"""Phase 08 Plan 07 — integration tests for POST /api/v3/projects/{id}/editor/apply.

BLOCKER-1 contract:
  - Response MUST have EXACTLY keys: {snapshot_id, edits_since_snapshot, new_hash,
    new_count, allocated_original_idx}
  - Response MUST NOT contain geometry/polygon/coords/coordinates keys
  - branch.manual_edit_log_count bumped +1 on each successful apply
  - branch.manual_edit_log_hash changes on each apply
  - Non-adjacent merge → 400 NOT_ADJACENT AND edit_events row NOT created

Covers REQ-IDs: EDIT-POLYGON-01, EDIT-POLYGON-02, EDIT-POLYGON-03, PERSIST-01
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from medieval_forge.main import app
from medieval_forge.models import Base, Branch, EditEvent, Project
from medieval_forge.database import get_db

# ---------------------------------------------------------------------------
# In-memory SQLite fixture for isolation
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Create isolated in-memory DB per test."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_app_with_db(db_session):
    """Override FastAPI dependency to use the test DB session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def project_and_branch(db_session):
    """Create a Project + Branch row for tests; returns (project_id, branch_id)."""
    project = Project(name="Test Project")
    db_session.add(project)
    await db_session.flush()

    branch = Branch(
        project_id=project.id,
        name="main",
        is_main=True,
        original_idx_high_water=10,
    )
    db_session.add(branch)
    await db_session.commit()
    await db_session.refresh(project)
    await db_session.refresh(branch)
    return project.id, branch.id


# ---------------------------------------------------------------------------
# Fixtures — geometry payloads
# ---------------------------------------------------------------------------

SPLIT_PAYLOAD = {
    "op_type": "split",
    "payload": {
        "parent_id": "barony-001",
        "parent_coords": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "cut_coords": [[-0.1, 0.5], [1.1, 0.5]],
        "child_name": "test barony (2)",
    },
}

MERGE_ADJACENT_PAYLOAD = {
    "op_type": "merge",
    "payload": {
        "first_id": "barony-001",
        "first_coords": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "second_id": "barony-002",
        "second_coords": [[1, 0], [2, 0], [2, 1], [1, 1]],
    },
}

MERGE_NON_ADJACENT_PAYLOAD = {
    "op_type": "merge",
    "payload": {
        "first_id": "barony-001",
        "first_coords": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "second_id": "barony-far",
        "second_coords": [[5, 5], [6, 5], [6, 6], [5, 6]],
    },
}

TRANSLATE_PAYLOAD = {
    "op_type": "translate",
    "payload": {
        "polygon_id": "barony-001",
        "d_lat": 0.5,
        "d_lon": 0.3,
    },
}


# ---------------------------------------------------------------------------
# BLOCKER-1 contract: exact response key set
# ---------------------------------------------------------------------------

EXPECTED_RESPONSE_KEYS = {
    "snapshot_id",
    "edits_since_snapshot",
    "new_hash",
    "new_count",
    "allocated_original_idx",
}

FORBIDDEN_GEOMETRY_KEYS = {
    "geometry", "polygon", "coords", "coordinates",
    "updated_baronies", "freed_idxs",
}


@pytest.mark.asyncio
class TestEditorApplyResponseShape:
    """BLOCKER-1: /editor/apply response must have exactly the declared keys."""

    async def test_split_response_has_exactly_required_keys(
        self, test_app_with_db, project_and_branch
    ):
        """POST split op → response keys == {snapshot_id, edits_since_snapshot, new_hash,
        new_count, allocated_original_idx} (set equality — no extras, no missing)."""
        project_id, branch_id = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert set(resp.json().keys()) == EXPECTED_RESPONSE_KEYS, (
            f"Key mismatch: got {set(resp.json().keys())}"
        )

    async def test_split_response_has_no_geometry_keys(
        self, test_app_with_db, project_and_branch
    ):
        """BLOCKER-1: split response must NOT contain any geometry keys."""
        project_id, branch_id = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )
        assert resp.status_code == 200
        response_keys = set(resp.json().keys())
        forbidden_found = response_keys & FORBIDDEN_GEOMETRY_KEYS
        assert not forbidden_found, f"Forbidden geometry keys in response: {forbidden_found}"

    async def test_merge_response_has_allocated_original_idx_as_none(
        self, test_app_with_db, project_and_branch
    ):
        """Merge op: allocated_original_idx must be present but None (not omitted)."""
        project_id, branch_id = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**MERGE_ADJACENT_PAYLOAD, "branch_id": branch_id},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "allocated_original_idx" in body
        assert body["allocated_original_idx"] is None

    async def test_translate_response_has_allocated_original_idx_as_none(
        self, test_app_with_db, project_and_branch
    ):
        """Translate op: allocated_original_idx must be present but None."""
        project_id, branch_id = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**TRANSLATE_PAYLOAD, "branch_id": branch_id},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["allocated_original_idx"] is None


# ---------------------------------------------------------------------------
# BLOCKER-1 contract: persistence + counter bump
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEditorApplyPersistence:
    """BLOCKER-1 persistence: manual_edit_log_count +1 and hash changes per apply."""

    async def test_split_bumps_manual_edit_log_count_by_one(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """After POST split, branch.manual_edit_log_count == 0 + 1 == 1."""
        project_id, branch_id = project_and_branch

        # Verify initial count
        branch_before = (
            await db_session.execute(select(Branch).where(Branch.id == branch_id))
        ).scalar_one()
        count_before = branch_before.manual_edit_log_count

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )

        await db_session.refresh(branch_before)
        assert branch_before.manual_edit_log_count == count_before + 1

    async def test_split_changes_manual_edit_log_hash(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """After POST split, branch.manual_edit_log_hash != '' (was empty before)."""
        project_id, branch_id = project_and_branch

        branch_before = (
            await db_session.execute(select(Branch).where(Branch.id == branch_id))
        ).scalar_one()
        hash_before = branch_before.manual_edit_log_hash

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )

        await db_session.refresh(branch_before)
        assert branch_before.manual_edit_log_hash != hash_before

    async def test_split_allocates_next_original_idx_atomically(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """Split op allocates original_idx = high_water + 1 = 10 + 1 = 11."""
        project_id, branch_id = project_and_branch

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )

        assert resp.status_code == 200
        body = resp.json()
        # Branch started with original_idx_high_water=10 → new idx = 11
        assert body["allocated_original_idx"] == 11

    async def test_two_splits_allocate_consecutive_original_idxs(
        self, test_app_with_db, project_and_branch
    ):
        """Two successive splits get idx=11 then idx=12 (monotonically increasing)."""
        project_id, branch_id = project_and_branch

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp1 = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )
            resp2 = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )

        assert resp1.json()["allocated_original_idx"] == 11
        assert resp2.json()["allocated_original_idx"] == 12

    async def test_response_new_count_matches_branch_count(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """Response new_count == branch.manual_edit_log_count after commit."""
        project_id, branch_id = project_and_branch

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**SPLIT_PAYLOAD, "branch_id": branch_id},
            )

        assert resp.status_code == 200
        body = resp.json()

        branch = (
            await db_session.execute(select(Branch).where(Branch.id == branch_id))
        ).scalar_one()
        await db_session.refresh(branch)
        assert body["new_count"] == branch.manual_edit_log_count


# ---------------------------------------------------------------------------
# BLOCKER-1 + Pitfall 2: non-adjacent merge → 400 + NO edit_events row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEditorApplyNonAdjacentMerge:
    """Server-side adjacency re-validation: non-adjacent → 400 + NO row created."""

    async def test_non_adjacent_merge_returns_400(
        self, test_app_with_db, project_and_branch
    ):
        """POST merge with non-adjacent polygons → HTTP 400."""
        project_id, branch_id = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**MERGE_NON_ADJACENT_PAYLOAD, "branch_id": branch_id},
            )
        assert resp.status_code == 400

    async def test_non_adjacent_merge_error_code_is_NOT_ADJACENT(
        self, test_app_with_db, project_and_branch
    ):
        """400 response body contains error code 'NOT_ADJACENT'."""
        project_id, branch_id = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**MERGE_NON_ADJACENT_PAYLOAD, "branch_id": branch_id},
            )
        assert resp.status_code == 400
        assert "NOT_ADJACENT" in resp.text

    async def test_non_adjacent_merge_does_not_create_edit_event_row(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """BLOCKER-1 + Pitfall 2: edit_events count unchanged after rejected merge."""
        project_id, branch_id = project_and_branch

        count_before = (
            await db_session.execute(
                select(func.count()).select_from(EditEvent).where(
                    EditEvent.branch_id == branch_id
                )
            )
        ).scalar_one()

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**MERGE_NON_ADJACENT_PAYLOAD, "branch_id": branch_id},
            )

        count_after = (
            await db_session.execute(
                select(func.count()).select_from(EditEvent).where(
                    EditEvent.branch_id == branch_id
                )
            )
        ).scalar_one()
        assert count_after == count_before, (
            f"edit_events count changed from {count_before} to {count_after} "
            "after rejected non-adjacent merge"
        )

    async def test_non_adjacent_merge_does_not_bump_log_count(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """manual_edit_log_count unchanged after rejected non-adjacent merge."""
        project_id, branch_id = project_and_branch

        branch = (
            await db_session.execute(select(Branch).where(Branch.id == branch_id))
        ).scalar_one()
        count_before = branch.manual_edit_log_count

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**MERGE_NON_ADJACENT_PAYLOAD, "branch_id": branch_id},
            )

        await db_session.refresh(branch)
        assert branch.manual_edit_log_count == count_before
