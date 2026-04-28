"""Integration tests for POST /api/projects/{id}/baronies (Etapa 2).

Mirrors the fixture pattern from test_paint_terrain.py:
- httpx AsyncClient + in-memory SQLite override
- monkeypatch DATA_DIR + PROJECTS_ROOT to a tmp directory
- seed a Project row + raw/municipalities.geojson with 6 unit-square polygons
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from shapely.geometry import Polygon, mapping
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project


PROJECT_ID = "deadbeef-cafe-4bad-8f00-1234567890ab"
OSM_IDS: list[int] = [101, 102, 103, 104, 105, 106]
LON_OFFSETS: list[float] = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
LAT_BASE: float = 40.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def project_root(tmp_path, monkeypatch):
    """Redirect DATA_DIR + PROJECTS_ROOT to a tmp dir; create project_dir/raw/."""
    import medieval_forge.database as db_module
    import medieval_forge.services.paths as paths_module

    fake_data_dir = tmp_path / ".medieval-forge"
    fake_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(db_module, "DATA_DIR", fake_data_dir)
    monkeypatch.setattr(paths_module, "PROJECTS_ROOT", fake_data_dir / "projects")

    raw_dir = fake_data_dir / "projects" / PROJECT_ID / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def _write_municipalities_fixture(raw_dir, n: int = 6) -> None:
    features = []
    for osm_id, lon0 in zip(OSM_IDS[:n], LON_OFFSETS[:n]):
        poly = Polygon([
            (lon0, LAT_BASE),
            (lon0 + 1, LAT_BASE),
            (lon0 + 1, LAT_BASE + 1),
            (lon0, LAT_BASE + 1),
            (lon0, LAT_BASE),
        ])
        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": osm_id,
                "name": f"Muni{osm_id}",
                "admin_level": "6",
            },
            "geometry": mapping(poly),
        })
    fc = {"type": "FeatureCollection", "features": features}
    (raw_dir / "municipalities.geojson").write_text(
        json.dumps(fc, ensure_ascii=False),
        encoding="utf-8",
    )


async def _seed_project(db_session) -> None:
    db_session.add(Project(
        id=PROJECT_ID,
        name="baronies-test",
        country_qid="Q29",
        period_start=800,
        period_end=900,
        status="created",
    ))
    await db_session.commit()


@pytest_asyncio.fixture
async def client(db_session, project_root):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_baronies_with_all_returns_n_features(client: AsyncClient, db_session, project_root):
    await _seed_project(db_session)
    _write_municipalities_fixture(project_root, n=6)

    response = await client.post(f"/api/projects/{PROJECT_ID}/baronies?count=all")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["baronies_count"] == 6
    assert body["municipalities_count"] == 6


@pytest.mark.asyncio
async def test_post_baronies_with_count_returns_n_clusters(client: AsyncClient, db_session, project_root):
    await _seed_project(db_session)
    _write_municipalities_fixture(project_root, n=6)

    response = await client.post(f"/api/projects/{PROJECT_ID}/baronies?count=3")

    assert response.status_code == 200, response.text
    assert response.json()["baronies_count"] == 3


@pytest.mark.asyncio
async def test_post_baronies_404_when_no_municipalities(client: AsyncClient, db_session, project_root):
    """Project exists but raw/municipalities.geojson does NOT → 404."""
    await _seed_project(db_session)
    # Do NOT write municipalities.geojson

    response = await client.post(f"/api/projects/{PROJECT_ID}/baronies?count=all")

    assert response.status_code == 404
    assert "municipalities" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_post_baronies_422_when_invalid_count(client: AsyncClient, db_session, project_root):
    await _seed_project(db_session)
    _write_municipalities_fixture(project_root, n=6)

    response = await client.post(f"/api/projects/{PROJECT_ID}/baronies?count=foo")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_baronies_writes_raw_baronies_geojson(client: AsyncClient, db_session, project_root):
    await _seed_project(db_session)
    _write_municipalities_fixture(project_root, n=6)

    response = await client.post(f"/api/projects/{PROJECT_ID}/baronies?count=all")
    assert response.status_code == 200, response.text

    baronies_path = project_root / "baronies.geojson"
    assert baronies_path.exists()
    data = json.loads(baronies_path.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 6
    # First feature should have the expected schema
    f0 = data["features"][0]
    assert "id" in f0["properties"]
    assert "centroid" in f0["properties"]
    assert "municipality_ids" in f0["properties"]
    assert f0["geometry"]["type"] in ("Polygon", "MultiPolygon")
