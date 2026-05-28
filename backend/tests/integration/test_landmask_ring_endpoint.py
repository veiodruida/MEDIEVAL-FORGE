"""Phase 08 Plan 16 — integration tests for GET /editor/landmask_ring.

Covers REQ-IDs: LANDMASK-01 (Path B — landmask ring source)

Tests:
  T1: Returns 400 on bad project UUID.
  T2: Without branch_id and no edit_events → returns Natural Earth ring (source='natural_earth').
  T3: With branch_id that has a landmask_replace event → returns edit event coords (source='branch_edit_event').
  T4: With branch_id that has NO landmask_replace event → falls back to Natural Earth ring.
  T5: Ring is a list of [lon, lat] pairs (len >= 3).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from medieval_forge.main import app
from medieval_forge.models import Base, Branch, EditEvent, Project
from medieval_forge.database import get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

SAMPLE_RING = [
    [-9.0, 36.9],
    [-6.0, 44.0],
    [-1.5, 43.5],
    [3.0, 42.0],
    [-9.0, 36.9],
]


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def test_app_with_db(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def project_and_branch(db_session):
    project = Project(name="Landmask Ring Test")
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


class TestLandmaskRingEndpoint:

    async def test_bad_uuid_returns_400(self, test_app_with_db):
        """T1: bad project UUID → 400."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v3/projects/not-a-uuid/editor/landmask_ring")
        assert resp.status_code == 400

    async def test_no_branch_id_returns_natural_earth_ring(
        self, test_app_with_db, project_and_branch
    ):
        """T2: no branch_id → Natural Earth fallback → source='natural_earth'."""
        pid, _bid = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v3/projects/{pid}/editor/landmask_ring")
        # Natural Earth dataset ships with the package; expect 200 in CI
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "natural_earth"
        assert isinstance(data["ring"], list)
        assert len(data["ring"]) >= 3

    async def test_branch_with_edit_event_returns_event_coords(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """T3: branch has landmask_replace event → returns branch edit event coords."""
        pid, bid = project_and_branch
        # Insert a landmask_replace event
        evt = EditEvent(
            branch_id=bid,
            op_type="landmask_replace",
            payload={"new_landmask_coords": SAMPLE_RING},
        )
        db_session.add(evt)
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v3/projects/{pid}/editor/landmask_ring",
                params={"branch_id": bid},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "branch_edit_event"
        assert data["ring"] == SAMPLE_RING

    async def test_branch_without_event_falls_back_to_natural_earth(
        self, test_app_with_db, project_and_branch
    ):
        """T4: branch with no landmask_replace event → Natural Earth fallback."""
        pid, bid = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v3/projects/{pid}/editor/landmask_ring",
                params={"branch_id": bid},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "natural_earth"

    async def test_ring_is_list_of_lon_lat_pairs(
        self, test_app_with_db, project_and_branch
    ):
        """T5: ring field is [[lon, lat], ...] with at least 3 entries."""
        pid, _bid = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v3/projects/{pid}/editor/landmask_ring")
        assert resp.status_code == 200
        ring = resp.json()["ring"]
        assert len(ring) >= 3
        for pt in ring[:5]:  # spot-check first 5 points
            assert len(pt) == 2
            lon, lat = pt
            assert -180.0 <= lon <= 180.0
            assert -90.0 <= lat <= 90.0
