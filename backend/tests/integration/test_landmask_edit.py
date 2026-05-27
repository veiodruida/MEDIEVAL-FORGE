"""Phase 08 Plan 08 — integration tests for landmask_replace op.

Covers REQ-IDs: LANDMASK-01, LANDMASK-02, DAG-04

WARNING-4 fix: contracts.py gains landmask_override field;
dag.py STAGE_READS['landmask'] includes 'landmask_override' so
version_token invalidates on edit.

CLAUDE.md Rule #3 (per-country KD-tree) preserved:
  After landmask edit, voronoi stage uses per-country trees built
  from condados (not a global tree). Number of trees = number of
  distinct countries in condados data.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from medieval_forge.main import app
from medieval_forge.models import Base, Branch, EditEvent, Project
from medieval_forge.database import get_db

# ---------------------------------------------------------------------------
# In-memory SQLite fixture (mirrors test_editor_apply_persists_only.py)
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
    """Create a Project + Branch row; returns (project_id, branch_id)."""
    project = Project(name="Landmask Test Project")
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


# A minimal landmask polygon with 5 valid coords (lon, lat)
LANDMASK_COORDS_5PTS = [
    [-9.0, 36.9],
    [-6.0, 44.0],
    [-1.5, 43.5],
    [3.0, 42.0],
    [-9.0, 36.9],  # closed ring
]

# Distinct landmask with slightly shifted coords (used to verify change propagates)
LANDMASK_COORDS_SHIFTED = [
    [-9.1, 36.8],
    [-6.1, 43.9],
    [-1.6, 43.4],
    [3.1, 41.9],
    [-9.1, 36.8],
]


# ---------------------------------------------------------------------------
# Tests: POST /editor/apply op_type='landmask_replace'
# ---------------------------------------------------------------------------

class TestLandmaskReplaceEndpoint:

    async def test_landmask_replace_returns_standard_apply_response_keys(
        self, test_app_with_db, project_and_branch
    ):
        """POST landmask_replace returns the standard BLOCKER-1 response shape.

        LANDMASK-01: landmask edit endpoint persists without breaking contract.
        Response must have exactly the 5 standard keys — no geometry.
        """
        project_id, branch_id = project_and_branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={
                    "op_type": "landmask_replace",
                    "payload": {"new_landmask_coords": LANDMASK_COORDS_5PTS},
                    "branch_id": branch_id,
                },
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert set(data.keys()) == {
            "snapshot_id",
            "edits_since_snapshot",
            "new_hash",
            "new_count",
            "allocated_original_idx",
        }

    async def test_landmask_replace_bumps_manual_edit_log_count(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """landmask_replace increments branch.manual_edit_log_count by 1.

        LANDMASK-01 + WARNING-4: hash/count update signals downstream DAG
        that landmask token has changed.
        """
        project_id, branch_id = project_and_branch

        # Read count before
        branch_before = (
            await db_session.execute(select(Branch).where(Branch.id == branch_id))
        ).scalar_one()
        count_before = branch_before.manual_edit_log_count

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={
                    "op_type": "landmask_replace",
                    "payload": {"new_landmask_coords": LANDMASK_COORDS_5PTS},
                    "branch_id": branch_id,
                },
            )

        await db_session.refresh(branch_before)
        assert branch_before.manual_edit_log_count == count_before + 1

    async def test_landmask_replace_appends_edit_event_row(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """landmask_replace appends an edit_events row with op_type='landmask_replace'.

        D-35: edit ops logged to edit_events table.
        """
        project_id, branch_id = project_and_branch

        count_before = (
            await db_session.execute(
                select(EditEvent).where(EditEvent.branch_id == branch_id)
            )
        ).scalars().all()

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={
                    "op_type": "landmask_replace",
                    "payload": {"new_landmask_coords": LANDMASK_COORDS_5PTS},
                    "branch_id": branch_id,
                },
            )

        events = (
            await db_session.execute(
                select(EditEvent).where(EditEvent.branch_id == branch_id)
            )
        ).scalars().all()
        assert len(events) == len(count_before) + 1
        assert events[-1].op_type == "landmask_replace"

    async def test_landmask_replace_stores_coords_in_payload(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """Persisted payload contains new_landmask_coords for downstream replay.

        LANDMASK-01: coords persisted verbatim in edit_events for DAG replay.
        """
        project_id, branch_id = project_and_branch

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={
                    "op_type": "landmask_replace",
                    "payload": {"new_landmask_coords": LANDMASK_COORDS_5PTS},
                    "branch_id": branch_id,
                },
            )

        events = (
            await db_session.execute(
                select(EditEvent).where(EditEvent.branch_id == branch_id)
            )
        ).scalars().all()
        assert events[-1].op_type == "landmask_replace"
        assert "new_landmask_coords" in events[-1].payload

    async def test_landmask_replace_with_oversized_coords_rejected(
        self, test_app_with_db, project_and_branch
    ):
        """Coords array with >50000 entries is rejected (T-08-08-02 DoS guard).

        Threat T-08-08-02: Pydantic max_length=50000 cap on new_landmask_coords.
        """
        project_id, branch_id = project_and_branch
        # Build a polygon with 50001 coords (exceeds cap)
        huge_coords = [[float(i % 10), float(i % 8)] for i in range(50001)]
        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={
                    "op_type": "landmask_replace",
                    "payload": {"new_landmask_coords": huge_coords},
                    "branch_id": branch_id,
                },
            )
        assert resp.status_code == 422  # Pydantic validation error


# ---------------------------------------------------------------------------
# Tests: contracts.py landmask_override + dag.py version_token invalidation
# ---------------------------------------------------------------------------

class TestLandmaskOverrideContracts:

    def test_region_config_has_landmask_override_field(self):
        """RegionConfig gains landmask_override field (WARNING-4 fix).

        DAG-04: STAGE_READS['landmask'] must include 'landmask_override'
        so version_token changes when override is set.
        """
        from medieval_forge.services.pipeline.contracts import RegionConfig
        cfg = RegionConfig()
        assert hasattr(cfg, "landmask_override")
        assert cfg.landmask_override is None

    def test_dag_stage_reads_landmask_includes_landmask_override(self):
        """STAGE_READS['landmask'] includes 'landmask_override' (DAG-04).

        This ensures the version_token for the landmask stage changes
        when cfg.landmask_override is set — triggering downstream invalidation.
        """
        from medieval_forge.services.pipeline.dag import STAGE_READS
        assert "landmask_override" in STAGE_READS["landmask"]

    def test_landmask_version_token_changes_when_override_set(self):
        """Landmask version_token differs between override=None and override=coords.

        DAG-04: Without token change, the cache would return stale geometry
        even after a landmask edit (Pitfall 5 analogue for landmask).
        """
        from medieval_forge.services.pipeline.contracts import RegionConfig
        from medieval_forge.services.pipeline.dag import (
            compute_version_token,
            STAGE_READS,
        )

        cfg_no_override = RegionConfig()
        cfg_with_override = RegionConfig(
            landmask_override=[(-9.0, 36.9), (-6.0, 44.0), (-1.5, 43.5)]
        )

        token_none = compute_version_token(
            "landmask", STAGE_READS["landmask"], cfg_no_override, []
        )
        token_with = compute_version_token(
            "landmask", STAGE_READS["landmask"], cfg_with_override, []
        )
        assert token_none != token_with, (
            "landmask version_token must differ when landmask_override is set"
        )

    def test_landmask_version_token_stable_across_runs(self):
        """Landmask token is deterministic for the same override coords.

        DAG-04: same coords → same token on every call (no random salt).
        """
        from medieval_forge.services.pipeline.contracts import RegionConfig
        from medieval_forge.services.pipeline.dag import (
            compute_version_token,
            STAGE_READS,
        )

        coords = [(-9.0, 36.9), (-6.0, 44.0), (-1.5, 43.5)]
        cfg = RegionConfig(landmask_override=coords)

        token_a = compute_version_token("landmask", STAGE_READS["landmask"], cfg, [])
        token_b = compute_version_token("landmask", STAGE_READS["landmask"], cfg, [])
        assert token_a == token_b

    def test_per_country_kd_tree_invariant_preserved(self):
        """CLAUDE.md Rule #3: voronoi uses per-country KD-trees, never global.

        After a landmask edit, voronoi.py rebuilds trees per-country.
        Verify the number of KD-trees equals the number of distinct countries
        in the condados data (at minimum 1 per country key in condados list).
        """
        from medieval_forge.services.pipeline.voronoi import build_per_country_trees

        # Minimal condados list with 2 distinct countries (PT and ES)
        condados = [
            {"country": "PT", "id": "c1", "lon": -8.0, "lat": 39.5},
            {"country": "PT", "id": "c2", "lon": -7.0, "lat": 39.0},
            {"country": "ES", "id": "c3", "lon": -5.0, "lat": 40.0},
            {"country": "ES", "id": "c4", "lon": -4.0, "lat": 40.5},
        ]
        trees = build_per_country_trees(condados)
        # Must have one tree per distinct country (CLAUDE.md Rule #3)
        assert len(trees) == 2
        assert "PT" in trees
        assert "ES" in trees
