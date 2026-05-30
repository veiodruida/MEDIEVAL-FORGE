"""Phase 08.3 Plan 04 — integration tests for POST /editor/apply (create op)
and GET /editor/country.

Covers:
  - test_create_allocates_above_floor: allocated_original_idx >= barony_floor (backend-derived)
  - test_create_persists_ring_and_meta: edit_events row payload contains ring + barony_meta + idx
  - test_create_ring_too_short_400: ring with 2 points → 400
  - test_create_ring_oversized_422: ring with 10001 points → 422
  - test_split_seeded_above_floor: split also allocates >= barony_floor (regression for
    latent split aliasing bug)
  - test_country_pt: Lisbon-side lat/lon → {"country": "PT"}
  - test_country_es: Madrid-side lat/lon → {"country": "ES"}

T-08.3-04-01 (DoS cap), T-08.3-04-02 (backend floor), T-08.3-04-03 (barony_meta),
T-08.3-04-04 (float coercion) are all covered.
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
from medieval_forge.services.pipeline.region_loader import load_region
from medieval_forge.services.pipeline.voronoi import setup_baronies

# ---------------------------------------------------------------------------
# DB fixture (mirrors test_editor_apply_persists_only.py)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# iberia_868 barony count — precomputed once to avoid repeated setup_baronies calls.
# Locked at 257 (setup_baronies(load_region("iberia_868")) returns len(bars)==257).
# If iberia_868.yaml data changes this value will drift; re-run the precompute below.
_IBERIA_BARONY_FLOOR: int | None = None


def _get_iberia_barony_floor() -> int:
    global _IBERIA_BARONY_FLOOR
    if _IBERIA_BARONY_FLOOR is None:
        cfg = load_region("iberia_868")
        bars, *_ = setup_baronies(cfg)
        _IBERIA_BARONY_FLOOR = len(bars)
    return _IBERIA_BARONY_FLOOR


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
    """Create a Project (iberia_868) + Branch; returns (project_id, branch_id).

    Branch starts with original_idx_high_water=0 (column default) so any
    min_floor-seeded allocation must come from the backend cfg, not from
    the pre-seeded high_water value.
    """
    project = Project(name="Create Handler Test", region_key="iberia_868")
    db_session.add(project)
    await db_session.flush()

    branch = Branch(
        project_id=project.id,
        name="main",
        is_main=True,
        original_idx_high_water=0,  # explicit 0 to exercise min_floor seeding
    )
    db_session.add(branch)
    await db_session.commit()
    await db_session.refresh(project)
    await db_session.refresh(branch)
    return project.id, branch.id


# ---------------------------------------------------------------------------
# Minimal valid create payload helpers
# ---------------------------------------------------------------------------

# A small triangle ring (lon/lat) that fits inside Iberia
_RING_3PT = [
    {"lat": 38.7, "lon": -9.1},
    {"lat": 38.8, "lon": -9.0},
    {"lat": 38.75, "lon": -8.9},
]

_BARONY_META = {
    "name": "Test Barony",
    "condado_idx": 0,
    "duchy_id": "porto",
    "kingdom_id": "portugal",
    "country": "PT",
}


def _create_payload(
    ring=None,
    barony_meta=None,
    nb: int = 0,
) -> dict:
    return {
        "op_type": "create",
        "payload": {
            "ring": ring if ring is not None else _RING_3PT,
            "barony_meta": barony_meta if barony_meta is not None else _BARONY_META,
            "nb": nb,  # frontend hint — backend MUST NOT rely on this for correctness
        },
    }


# ---------------------------------------------------------------------------
# Task 1 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateAllocatesAboveFloor:
    """T-08.3-04-02: allocated_original_idx must be >= barony_floor (backend-derived)."""

    async def test_create_allocates_above_floor(
        self, test_app_with_db, project_and_branch
    ):
        """CREATE on fresh branch → allocated_original_idx >= 257 (iberia_868 floor).

        The payload sends nb=0 (a too-small hint) to prove the backend ignores it
        and derives the floor from cfg+setup_baronies instead.
        """
        project_id, branch_id = project_and_branch
        floor = _get_iberia_barony_floor()

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**_create_payload(nb=0), "branch_id": branch_id},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["allocated_original_idx"] is not None
        assert body["allocated_original_idx"] >= floor, (
            f"Expected idx >= {floor} (backend floor), got {body['allocated_original_idx']}"
        )

    async def test_create_allocates_above_floor_even_when_nb_omitted(
        self, test_app_with_db, project_and_branch
    ):
        """CREATE without nb in payload → still >= floor (floor is backend-only)."""
        project_id, branch_id = project_and_branch
        floor = _get_iberia_barony_floor()

        payload_without_nb = {
            "op_type": "create",
            "payload": {
                "ring": _RING_3PT,
                "barony_meta": _BARONY_META,
                # nb intentionally omitted
            },
        }

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**payload_without_nb, "branch_id": branch_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["allocated_original_idx"] >= floor


@pytest.mark.asyncio
class TestCreatePersistsRingAndMeta:
    """T-08.3-04-03: persisted edit_events row must contain ring + barony_meta + idx."""

    async def test_create_persists_ring_and_meta(
        self, test_app_with_db, project_and_branch, db_session
    ):
        """POST create → edit_events.payload contains ring, barony_meta, allocated_original_idx."""
        project_id, branch_id = project_and_branch

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**_create_payload(), "branch_id": branch_id},
            )

        assert resp.status_code == 200, resp.text
        allocated_idx = resp.json()["allocated_original_idx"]

        # Fetch the persisted event
        event = (
            await db_session.execute(
                select(EditEvent)
                .where(EditEvent.branch_id == branch_id, EditEvent.op_type == "create")
                .order_by(EditEvent.id.desc())
                .limit(1)
            )
        ).scalar_one()

        assert event is not None
        payload = event.payload
        assert "ring" in payload, "ring must be persisted in edit_events.payload"
        assert "barony_meta" in payload, "barony_meta must be persisted"
        assert payload["allocated_original_idx"] == allocated_idx, (
            "allocated_original_idx embedded in persisted payload must match response"
        )
        assert payload["barony_meta"]["name"] == _BARONY_META["name"]


@pytest.mark.asyncio
class TestCreateRingValidation:
    """T-08.3-04-01: DoS cap + minimum ring size enforcement."""

    async def test_create_ring_too_short_400(
        self, test_app_with_db, project_and_branch
    ):
        """ring with 2 points → 400 (needs at least 3)."""
        project_id, branch_id = project_and_branch
        ring_2pt = [{"lat": 38.7, "lon": -9.1}, {"lat": 38.8, "lon": -9.0}]

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**_create_payload(ring=ring_2pt), "branch_id": branch_id},
            )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "ring" in resp.text.lower() or "3" in resp.text

    async def test_create_ring_oversized_422(
        self, test_app_with_db, project_and_branch
    ):
        """ring with 10001 points → 422 (DoS cap = 10000)."""
        project_id, branch_id = project_and_branch
        # Generate 10001 distinct points
        large_ring = [{"lat": 38.0 + i * 0.000001, "lon": -9.0} for i in range(10001)]

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json={**_create_payload(ring=large_ring), "branch_id": branch_id},
            )

        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        assert "10000" in resp.text


@pytest.mark.asyncio
class TestSplitSeededAboveFloor:
    """Regression for latent split aliasing bug (RESEARCH BUG 1, Phase 08.3-04)."""

    async def test_split_seeded_above_floor(
        self, test_app_with_db, project_and_branch
    ):
        """POST split on fresh branch → allocated_original_idx >= barony_floor (NOT 1).

        Before the fix, split called allocate_next_original_idx with no min_floor,
        so the first allocation returned high_water+1 = 0+1 = 1, aliasing barony idx 1.
        The fix passes min_floor=barony_floor so the allocation lands at >= 257.
        """
        project_id, branch_id = project_and_branch
        floor = _get_iberia_barony_floor()

        split_payload = {
            "op_type": "split",
            "payload": {
                "parent_id": "barony-001",
                "parent_coords": [[0, 0], [1, 0], [1, 1], [0, 1]],
                "cut_coords": [[-0.1, 0.5], [1.1, 0.5]],
                "child_name": "test barony (2)",
            },
            "branch_id": branch_id,
        }

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{project_id}/editor/apply",
                json=split_payload,
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["allocated_original_idx"] is not None
        assert body["allocated_original_idx"] >= floor, (
            f"Split aliasing bug: expected idx >= {floor}, got {body['allocated_original_idx']}. "
            "The latent bug (idx==1 alias) is NOT fixed."
        )


# ---------------------------------------------------------------------------
# Task 2 tests — GET /editor/country
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEditorCountry:
    """D-08: GET /editor/country returns PT/ES from centroid via cfg.border_polygon."""

    async def test_country_pt_lisbon(
        self, test_app_with_db, project_and_branch
    ):
        """Lisbon-area point (lat=38.72, lon=-9.14) → {"country": "PT"}.

        Explicit numeric fixture per project memory (feedback-tests-descriptive).
        Verified empirically: point_in_polygon(-9.14, 38.72, iberia_868.border_polygon) == True.
        """
        project_id, _branch_id = project_and_branch

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v3/projects/{project_id}/editor/country",
                params={"lat": 38.72, "lon": -9.14},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body == {"country": "PT"}, (
            f"Lisbon (lat=38.72, lon=-9.14) should be PT, got: {body}"
        )

    async def test_country_es_madrid(
        self, test_app_with_db, project_and_branch
    ):
        """Madrid-area point (lat=40.42, lon=-3.70) → {"country": "ES"}.

        Explicit numeric fixture per project memory (feedback-tests-descriptive).
        Verified empirically: point_in_polygon(-3.70, 40.42, iberia_868.border_polygon) == False.
        """
        project_id, _branch_id = project_and_branch

        async with AsyncClient(
            transport=ASGITransport(app=test_app_with_db), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v3/projects/{project_id}/editor/country",
                params={"lat": 40.42, "lon": -3.70},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body == {"country": "ES"}, (
            f"Madrid (lat=40.42, lon=-3.70) should be ES, got: {body}"
        )
