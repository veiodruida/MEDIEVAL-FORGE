"""
Wave 0 RED contract tests for POST /api/projects/{id}/edit/paint-terrain.

Tests fail at collection / runtime because the endpoint does not exist yet.
That is the expected RED state. Implementation comes in Plan 5.1 Task 3.

Mirrors the fixture pattern from test_edit_api.py (httpx AsyncClient +
tmp project_dir monkeypatch + in-memory SQLite).

Land-mask fixture:
  - 100x100 PNG (white = land, black = ocean) with bounds lon [-12, 4], lat [35, 45].
  - c1: lon=-3.7, lat=40.4 (Madrid area — maps to ~pixel (52, 46) which is WHITE = land).
  - c2: lon=-9.5, lat=37.0 (Atlantic — maps to ~pixel (16, 80) which is BLACK = ocean).
  - Pixel formula (lon_scale cancels in round-trip):
      px = (lon - lon_min) / (lon_max - lon_min) * W   => c1≈52, c2≈16
      py = (lat_max - lat) / (lat_max - lat_min) * H   => c1≈46, c2≈80
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base, Project
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid UUID v4 (different from test_edit_api.py to keep test isolation)
PROJECT_ID = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"

C1_ID = "c1"  # lon=-3.7, lat=40.4 — land (Madrid area)
C2_ID = "c2"  # lon=-9.5, lat=37.0 — ocean (Atlantic)

C1_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-4.0, 40.0], [-3.5, 40.0], [-3.5, 40.5], [-4.0, 40.5], [-4.0, 40.0]]],
}
C2_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-10.0, 36.5], [-9.0, 36.5], [-9.0, 37.5], [-10.0, 37.5], [-10.0, 36.5]]],
}

# Bounds used for both metadata and land_mask pixel projection
LON_MIN, LON_MAX = -12.0, 4.0
LAT_MIN, LAT_MAX = 35.0, 45.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def territory_files(tmp_path, monkeypatch):
    """Seed project files under a temp PROJECTS_ROOT.

    Writes:
    - territories.geojson  with c1 (land) and c2 (ocean)
    - territory_metadata.json  with bounds for land_mask projection
    - lookup_condado.png  100x100 white (land) except pixel (16,80) black (c2 ocean area)
    """
    import medieval_forge.database as db_module
    import medieval_forge.services.paths as paths_module

    fake_data_dir = tmp_path / ".medieval-forge"
    fake_data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(db_module, "DATA_DIR", fake_data_dir)
    monkeypatch.setattr(paths_module, "PROJECTS_ROOT", fake_data_dir / "projects")

    proj_generated = fake_data_dir / "projects" / PROJECT_ID / "generated"
    proj_generated.mkdir(parents=True, exist_ok=True)

    # --- territories.geojson ---
    territories_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": C1_ID,
                "geometry": C1_POLYGON,
                "properties": {
                    "id": C1_ID,
                    "name": "Condado 1",
                    "lon": -3.7,
                    "lat": 40.4,
                    "neighbors": [C2_ID],
                    "duchy_id": "d1",
                    "baronies": [],
                },
            },
            {
                "type": "Feature",
                "id": C2_ID,
                "geometry": C2_POLYGON,
                "properties": {
                    "id": C2_ID,
                    "name": "Condado 2",
                    "lon": -9.5,
                    "lat": 37.0,
                    "neighbors": [C1_ID],
                    "duchy_id": "d2",
                    "baronies": [],
                },
            },
        ],
    }
    (proj_generated / "territories.geojson").write_text(
        json.dumps(territories_data, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- territory_metadata.json (needed by load_land_mask_and_bbox) ---
    metadata = {
        "region": "test",
        "map_size": [1920, 1080],
        "bounds": {
            "lon_min": LON_MIN,
            "lon_max": LON_MAX,
            "lat_min": LAT_MIN,
            "lat_max": LAT_MAX,
        },
        "kingdoms": {},
        "duchies": {},
        "condados": [
            {"id": C1_ID, "name": "Condado 1", "lon": -3.7, "lat": 40.4, "duchy": "d1"},
            {"id": C2_ID, "name": "Condado 2", "lon": -9.5, "lat": 37.0, "duchy": "d2"},
        ],
        "baronies": [],
    }
    (proj_generated / "territory_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- lookup_condado.png ---
    # 100x100 all-white image (land), except pixel at (col=16, row=80) is black (ocean).
    # c1 maps to ~(col=52, row=46) → white → land.
    # c2 maps to ~(col=16, row=80) → black → ocean.
    # We paint a small 5x5 black patch around (16, 80) to ensure the centroid
    # point falls within the ocean region after Shapely polygon extraction.
    # The entire rest of the image is white so c1 is solidly land.
    from PIL import Image
    import numpy as np

    img_array = np.ones((100, 100, 3), dtype=np.uint8) * 255  # all white
    # Black patch around c2 ocean pixel (row=80, col=16)
    # Use a generous patch (10x10) so the Shapely polygon definitely covers (16, 80)
    r0, r1 = 75, 86
    c0, c1_col = 11, 22
    img_array[r0:r1, c0:c1_col] = 0  # black = ocean
    img = Image.fromarray(img_array, mode="RGB")
    img.save(str(proj_generated / "lookup_condado.png"))

    yield proj_generated


@pytest_asyncio.fixture
async def client(db_session, territory_files):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _seed_project(db_session) -> datetime:
    initial = datetime(2020, 1, 1, tzinfo=timezone.utc)
    project = Project(
        id=PROJECT_ID,
        name="paint-test",
        country_qid="Q29",
        period_start=800,
        period_end=900,
        status="created",
        created_at=initial,
        updated_at=initial,
    )
    db_session.add(project)
    await db_session.commit()
    return initial


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paint_terrain_returns_painted_ids(client: AsyncClient, db_session):
    """Both c1 centroids are land → painted_ids contains both; skipped_ids empty."""
    await _seed_project(db_session)
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/edit/paint-terrain",
        json={"territory_ids": [C1_ID], "terrain_type": "forest"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert C1_ID in body["painted_ids"], f"c1 should be painted (land); got {body}"
    assert C1_ID not in body["skipped_ids"], f"c1 should NOT be skipped; got {body}"
    assert body["skipped_ids"] == [], f"skipped_ids should be empty for land territory; got {body}"


@pytest.mark.asyncio
async def test_paint_terrain_excludes_ocean(client: AsyncClient, db_session):
    """c2 centroid is in the ocean black zone → skipped_ids contains c2; painted_ids has c1."""
    await _seed_project(db_session)
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/edit/paint-terrain",
        json={"territory_ids": [C1_ID, C2_ID], "terrain_type": "forest"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert C1_ID in body["painted_ids"], f"c1 (land) should be in painted_ids; got {body}"
    assert C2_ID in body["skipped_ids"], f"c2 (ocean) should be in skipped_ids; got {body}"
    assert C2_ID not in body["painted_ids"], f"c2 should NOT be painted; got {body}"


@pytest.mark.asyncio
async def test_paint_terrain_persists_to_geojson(client: AsyncClient, db_session, territory_files):
    """After success, territories.geojson shows terrain_type == 'forest' for painted IDs."""
    await _seed_project(db_session)
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/edit/paint-terrain",
        json={"territory_ids": [C1_ID], "terrain_type": "forest"},
    )
    assert response.status_code == 200, f"Expected 200: {response.text}"

    # Re-read the file from disk
    geojson_path = territory_files / "territories.geojson"
    raw = json.loads(geojson_path.read_text(encoding="utf-8"))
    features_by_id = {f["id"]: f for f in raw["features"]}
    assert features_by_id[C1_ID]["properties"]["terrain_type"] == "forest", (
        f"c1 terrain_type should be 'forest' in geojson; got {features_by_id[C1_ID]['properties']}"
    )


@pytest.mark.asyncio
async def test_paint_terrain_invalid_terrain_type(client: AsyncClient, db_session):
    """POST with terrain_type='lava' → 422 from Pydantic Literal validation."""
    await _seed_project(db_session)
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/edit/paint-terrain",
        json={"territory_ids": [C1_ID], "terrain_type": "lava"},
    )
    assert response.status_code == 422, (
        f"Expected 422 for invalid terrain_type 'lava', got {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_paint_terrain_unknown_territory_id_filtered(client: AsyncClient, db_session):
    """IDs not in project's territories appear in skipped_ids (cross-project injection guard)."""
    await _seed_project(db_session)
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/edit/paint-terrain",
        json={"territory_ids": ["unknown_id_xyz", C1_ID], "terrain_type": "plains"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert "unknown_id_xyz" in body["skipped_ids"], (
        f"Unknown ID should be in skipped_ids; got {body}"
    )
    assert C1_ID in body["painted_ids"], f"c1 (land) should still be painted; got {body}"
