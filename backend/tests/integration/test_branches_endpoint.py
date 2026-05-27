"""Phase 08 plan 03a — Branch CRUD endpoint integration tests.

Covers: BRANCH-01, BRANCH-02, BRANCH-04, BRANCH-05
D-10: lazy-create main on GET, D-13: unique name, D-15: main delete-protected,
D-15: rename allowed on main.

9 tests per plan <behavior>; + 1 bonus test for D-15 rename-main.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    """AsyncClient with in-memory DB override."""
    async def _override():
        async with db_engine() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def project_id(db_engine):
    """Create a Project row and return its id."""
    async with db_engine() as session:
        proj = Project(name="Test Project", region_key="iberia_868")
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        return proj.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_branches_creates_branch_and_returns_201(client, project_id):
    """BRANCH-01: POST /api/v3/projects/{id}/branches → 201 + branch JSON with id."""
    resp = await client.post(
        f"/api/v3/projects/{project_id}/branches",
        json={"name": "experiment"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] == "experiment"
    assert data["is_main"] is False


@pytest.mark.asyncio
async def test_POST_branches_with_reserved_name_main_returns_400(client, project_id):
    """D-13: POST with name='main' returns 400 (reserved name)."""
    resp = await client.post(
        f"/api/v3/projects/{project_id}/branches",
        json={"name": "main"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_POST_branches_with_invalid_name_containing_space_returns_422(client, project_id):
    """D-13: POST with name='exp lab' (invalid chars) returns 422 from pydantic pattern."""
    resp = await client.post(
        f"/api/v3/projects/{project_id}/branches",
        json={"name": "exp lab"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_POST_branches_duplicate_name_returns_409(client, project_id):
    """D-13: POST with duplicate name returns 409 CONFLICT."""
    resp1 = await client.post(
        f"/api/v3/projects/{project_id}/branches",
        json={"name": "duplicate-branch"},
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/v3/projects/{project_id}/branches",
        json={"name": "duplicate-branch"},
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_GET_branches_returns_200_and_lazy_creates_main(client, project_id):
    """D-10: GET /api/v3/projects/{id}/branches lazy-creates main; returns list ordered by updated_at desc."""
    resp = await client.get(f"/api/v3/projects/{project_id}/branches")
    assert resp.status_code == 200
    branches = resp.json()
    assert isinstance(branches, list)
    # main was lazy-created
    names = [b["name"] for b in branches]
    assert "main" in names
    main = next(b for b in branches if b["name"] == "main")
    assert main["is_main"] is True


@pytest.mark.asyncio
async def test_PATCH_branch_rename_returns_200(client, project_id):
    """D-15: PATCH /api/v3/projects/{id}/branches/{bid} with new name returns 200."""
    create_resp = await client.post(
        f"/api/v3/projects/{project_id}/branches",
        json={"name": "to-rename"},
    )
    assert create_resp.status_code == 201
    branch_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v3/projects/{project_id}/branches/{branch_id}",
        json={"name": "renamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"


@pytest.mark.asyncio
async def test_PATCH_main_branch_rename_succeeds_per_D15(client, project_id):
    """D-15: rename is allowed on main branch (only delete is protected)."""
    # Lazy-create main via GET
    get_resp = await client.get(f"/api/v3/projects/{project_id}/branches")
    assert get_resp.status_code == 200
    main_branch = next(b for b in get_resp.json() if b["is_main"])

    resp = await client.patch(
        f"/api/v3/projects/{project_id}/branches/{main_branch['id']}",
        json={"name": "main-renamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "main-renamed"


@pytest.mark.asyncio
async def test_DELETE_main_branch_returns_409_with_BRANCH_PROTECTED_code(client, project_id):
    """D-15: DELETE on main branch returns 409 + error code BRANCH_PROTECTED."""
    # Lazy-create main via GET
    get_resp = await client.get(f"/api/v3/projects/{project_id}/branches")
    main_branch = next(b for b in get_resp.json() if b["is_main"])

    resp = await client.delete(
        f"/api/v3/projects/{project_id}/branches/{main_branch['id']}"
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "BRANCH_PROTECTED"


@pytest.mark.asyncio
async def test_DELETE_non_main_branch_returns_204(client, project_id):
    """BRANCH-05: DELETE a non-main branch returns 204 No Content."""
    create_resp = await client.post(
        f"/api/v3/projects/{project_id}/branches",
        json={"name": "to-delete"},
    )
    assert create_resp.status_code == 201
    branch_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v3/projects/{project_id}/branches/{branch_id}"
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_GET_branches_with_invalid_project_id_returns_400(client):
    """T-08-03a-02: is_valid_uuid guard rejects non-UUID project_id with 400."""
    resp = await client.get("/api/v3/projects/not-a-uuid/branches")
    assert resp.status_code == 400
