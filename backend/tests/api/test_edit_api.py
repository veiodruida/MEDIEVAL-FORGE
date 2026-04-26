"""
Wave 0 RED contract tests for backend/medieval_forge/api/edit.py.

These tests fail at collection time because edit.py does not exist yet.
That is the expected RED state. Implementations come in P04.

Uses the shared conftest fixtures (client, db_session) from backend/tests/conftest.py.
A local project_id constant stands in for a real loaded project — sufficient for RED.

[P04 Rule 3 fix] PROJECT_ID changed to a valid UUID and a territory_files fixture
added so the edit endpoints can load/save territories.geojson from disk.
"""
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base

# ---------------------------------------------------------------------------
# Local fixtures (augment shared conftest to add a loaded project)
# ---------------------------------------------------------------------------

# Valid UUID v4 required by paths.is_valid_uuid (T-PATH enforcement)
PROJECT_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

# Minimal territory geometry for request payloads
LEON_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-6.0, 42.0], [-5.0, 42.0], [-5.0, 43.0], [-6.0, 43.0], [-6.0, 42.0]]],
}

CASTELA_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-4.0, 39.0], [-3.0, 39.0], [-3.0, 40.0], [-4.0, 40.0], [-4.0, 39.0]]],
}

# A bisecting cut line for LEON_POLYGON (horizontal split at lat=42.5)
BISECTING_CUT_LINE = [[-6.1, 42.5], [-4.9, 42.5]]

# A non-bisecting line (entirely outside LEON_POLYGON)
NON_BISECTING_CUT_LINE = [[-10.0, 50.0], [-9.0, 51.0]]


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
    """Seed a minimal territories.geojson under a temp PROJECTS_ROOT so that
    load_territories(PROJECT_ID) returns {"leon": {...}, "castela": {...}}.

    Monkeypatches medieval_forge.database.DATA_DIR so project_dir() resolves
    inside tmp_path instead of ~/.medieval-forge/.
    """
    import medieval_forge.database as db_module
    import medieval_forge.services.paths as paths_module

    fake_data_dir = tmp_path / ".medieval-forge"
    fake_data_dir.mkdir(parents=True, exist_ok=True)

    # Patch DATA_DIR in both the database module and paths module
    monkeypatch.setattr(db_module, "DATA_DIR", fake_data_dir)
    monkeypatch.setattr(paths_module, "PROJECTS_ROOT", fake_data_dir / "projects")

    proj_generated = fake_data_dir / "projects" / PROJECT_ID / "generated"
    proj_generated.mkdir(parents=True, exist_ok=True)

    # scipy Voronoi requires >= 4 non-coplanar seeds; include 4 territories.
    territories_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "leon",
                "geometry": LEON_POLYGON,
                "properties": {
                    "id": "leon",
                    "name": "León",
                    "lon": -5.5,
                    "lat": 42.5,
                    "neighbors": ["castela"],
                    "duchy_id": "d_leon",
                    "baronies": [],
                },
            },
            {
                "type": "Feature",
                "id": "castela",
                "geometry": CASTELA_POLYGON,
                "properties": {
                    "id": "castela",
                    "name": "Castela",
                    "lon": -3.5,
                    "lat": 39.5,
                    "neighbors": ["leon"],
                    "duchy_id": "d_castela",
                    "baronies": [],
                },
            },
            {
                "type": "Feature",
                "id": "galiza",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-9.0, 43.0], [-8.0, 43.0], [-8.0, 44.0], [-9.0, 44.0], [-9.0, 43.0]]],
                },
                "properties": {
                    "id": "galiza",
                    "name": "Galiza",
                    "lon": -8.5,
                    "lat": 43.5,
                    "neighbors": [],
                    "duchy_id": "d_galiza",
                    "baronies": [],
                },
            },
            {
                "type": "Feature",
                "id": "aragon",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-1.0, 41.0], [0.0, 41.0], [0.0, 42.0], [-1.0, 42.0], [-1.0, 41.0]]],
                },
                "properties": {
                    "id": "aragon",
                    "name": "Aragón",
                    "lon": -0.5,
                    "lat": 41.5,
                    "neighbors": [],
                    "duchy_id": "d_aragon",
                    "baronies": [],
                },
            },
        ],
    }
    (proj_generated / "territories.geojson").write_text(
        json.dumps(territories_data, ensure_ascii=False),
        encoding="utf-8",
    )

    # qlo-01: write a minimal territory_metadata.json so move_capital
    # can derive a bbox via load_land_mask_and_bbox.  No lookup_condado.png
    # is written → the helper degrades gracefully to (None, bbox), which
    # still triggers bbox-based clipping in recalc_neighbors.
    metadata = {
        "region": "test",
        "map_size": [1920, 1080],
        "bounds": {
            "lon_min": -10.0, "lon_max": 5.0,
            "lat_min": 35.0, "lat_max": 45.0,
        },
        "kingdoms": {},
        "duchies": {},
        "condados": [
            {"id": "leon", "name": "León", "lon": -5.5, "lat": 42.5, "duchy": "d_leon"},
            {"id": "castela", "name": "Castela", "lon": -3.5, "lat": 39.5, "duchy": "d_castela"},
            {"id": "galiza", "name": "Galiza", "lon": -8.5, "lat": 43.5, "duchy": "d_galiza"},
            {"id": "aragon", "name": "Aragón", "lon": -0.5, "lat": 41.5, "duchy": "d_aragon"},
        ],
        "baronies": [],
    }
    (proj_generated / "territory_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )
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
# POST /recalc — move capital + Voronoi recalc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_recalc_move_capital_returns_200_with_updated_territories(client: AsyncClient):
    """
    POST /api/projects/{id}/territories/{condado_id}/recalc
    Body: {"lon": -5.57, "lat": 42.6}
    Expect: 200, body contains updated_territories (dict) and affected_ids (list).
    """
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/territories/leon/recalc",
        json={"lon": -5.57, "lat": 42.6},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert "updated_territories" in body, "Response must contain updated_territories"
    assert "affected_ids" in body, "Response must contain affected_ids"
    assert isinstance(body["updated_territories"], dict), "updated_territories must be a dict"
    assert isinstance(body["affected_ids"], list), "affected_ids must be a list"


@pytest.mark.asyncio
async def test_move_capital_clips_returned_polygons_to_bbox(client: AsyncClient):
    """qlo-01 regression: after move_capital, every returned polygon's exterior
    coords must lie within the project's bbox (loaded from
    territory_metadata.json by load_land_mask_and_bbox).  This guards against
    the previous behavior where Voronoi cells could extend into the ocean.
    """
    # Bounds from territory_files fixture: lon ∈ [-10, 5], lat ∈ [35, 45].
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/territories/leon/recalc",
        json={"lon": -5.5, "lat": 42.5},
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    body = response.json()
    updated = body["updated_territories"]
    assert len(updated) >= 1, "Recalc must return at least the moved cell"

    def _walk_coords(geom):
        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                yield from ring
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    yield from ring

    # Slack tolerance for floating-point boundary touching.
    EPS = 1e-6
    for cid, geom in updated.items():
        for x, y in _walk_coords(geom):
            assert -10.0 - EPS <= x <= 5.0 + EPS, (
                f"{cid}: lon {x} outside bbox [-10, 5]"
            )
            assert 35.0 - EPS <= y <= 45.0 + EPS, (
                f"{cid}: lat {y} outside bbox [35, 45]"
            )


@pytest.mark.asyncio
async def test_post_recalc_rejects_lon_out_of_range(client: AsyncClient):
    """
    Longitude outside [-180, 180] must return 422 (Pydantic validation).
    """
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/territories/leon/recalc",
        json={"lon": 999, "lat": 0},
    )
    assert response.status_code == 422, f"Expected 422 for out-of-range lon, got {response.status_code}"


# ---------------------------------------------------------------------------
# POST /merge — merge N condados into one
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_merge_returns_200_with_merged_territory(client: AsyncClient):
    """
    POST /api/projects/{id}/territories/merge
    Body: {"condado_ids": ["leon", "castela"], "primary_id": "leon"}
    Expect: 200, merged_id == "leon", removed_ids is non-empty.
    """
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/territories/merge",
        json={"condado_ids": ["leon", "castela"], "primary_id": "leon"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["merged_id"] == "leon", f"merged_id should be 'leon', got {body.get('merged_id')!r}"
    assert "merged_territory" in body, "Response must contain merged_territory"
    assert "removed_ids" in body, "Response must contain removed_ids"
    assert "castela" in body["removed_ids"], "castela must be in removed_ids after merge"


@pytest.mark.asyncio
async def test_post_merge_rejects_length_lt_2(client: AsyncClient):
    """
    Merge request with fewer than 2 condado_ids must return 422.
    """
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/territories/merge",
        json={"condado_ids": ["leon"], "primary_id": "leon"},
    )
    assert response.status_code == 422, (
        f"Expected 422 for single condado_ids, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# POST /split — split territory by cut line
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_split_returns_200_with_two_territories(client: AsyncClient):
    """
    POST /api/projects/{id}/territories/{id}/split
    Body: {"cut_line": [...bisecting...], "mode": "polyline"}
    Expect: 200, original_id set, new_territory_a and new_territory_b present.
    """
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/territories/leon/split",
        json={"cut_line": BISECTING_CUT_LINE, "mode": "polyline"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["original_id"] == "leon"
    assert "new_territory_a" in body, "Response must contain new_territory_a"
    assert "new_territory_b" in body, "Response must contain new_territory_b"
    assert "id" in body["new_territory_a"]
    assert "geometry" in body["new_territory_a"]
    assert "id" in body["new_territory_b"]
    assert "geometry" in body["new_territory_b"]


@pytest.mark.asyncio
async def test_post_split_rejects_non_bisecting_line_as_422(client: AsyncClient):
    """
    CRITICAL — Pitfall 4: cut line that does not bisect the polygon must
    return 422 with detail mentioning 'bisect' (not silently fail or 500).
    """
    response = await client.post(
        f"/api/projects/{PROJECT_ID}/territories/leon/split",
        json={"cut_line": NON_BISECTING_CUT_LINE, "mode": "polyline"},
    )
    assert response.status_code == 422, (
        f"Expected 422 for non-bisecting cut line, got {response.status_code}"
    )
    detail = response.json().get("detail", "")
    detail_text = detail if isinstance(detail, str) else str(detail)
    assert any(
        word in detail_text.lower() for word in ("bisect", "cross", "intersect", "split")
    ), f"422 detail must mention bisect/cross/intersect/split, got: {detail_text!r}"


# ---------------------------------------------------------------------------
# PATCH /geometry — reshape geometry (vertex drag persist)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_geometry_returns_200(client: AsyncClient):
    """
    PATCH /api/projects/{id}/territories/{id}/geometry
    Body: {"geometry": <valid GeoJSONPolygon>}
    Expect: 200 with updated geometry confirmed.
    """
    response = await client.patch(
        f"/api/projects/{PROJECT_ID}/territories/leon/geometry",
        json={"geometry": LEON_POLYGON},
    )
    assert response.status_code == 200, (
        f"Expected 200 for valid reshape request, got {response.status_code}: {response.text}"
    )
