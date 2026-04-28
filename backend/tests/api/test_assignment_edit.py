"""Integration tests for PATCH /api/projects/{id}/research/assignments (Etapa 8 / quick-260428-h1t).

Six behaviors covered:
  1. Move a barony between condados (delta apply).
  2. Rename a condado + reparent it under a different duchy (kingdom_id re-derived).
  3. Create a brand-new condado via condado_renames + reassign barony to it.
  4. Reject unknown barony id with 400 — cache row UNCHANGED.
  5. Persist edit to research cache (overwrite same cache_key_hash).
  6. Edited cache feeds territory_builder.assemble_territory_data_from_baronies correctly.
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project, ResearchCache
from medieval_forge.services.research_cache import compute_cache_key, get_cached
from medieval_forge.services.territory_builder import assemble_territory_data_from_baronies


PROJECT_ID = "deadbeef-cafe-4bad-8f00-abcdef012345"
COUNTRY_QID = "Q29"
PERIOD_START = 868
PERIOD_END = 900


# Fixture payload — exact numeric centroids per plan.
INITIAL_PAYLOAD: dict = {
    "kingdoms": {"K_LEON": "Reino de León", "K_CASTILLA": "Reino de Castilla"},
    "duchies": {
        "D_LEON": {"kingdom_id": "K_LEON", "name": "Ducado de León"},
        "D_CAST": {"kingdom_id": "K_CASTILLA", "name": "Ducado de Castilla"},
    },
    "condados": [
        {"id": "C_LEON", "name": "Condado de León", "kingdom_id": "K_LEON", "duchy_id": "D_LEON"},
        {"id": "C_BURGOS", "name": "Condado de Burgos", "kingdom_id": "K_CASTILLA", "duchy_id": "D_CAST"},
    ],
    "barony_assignments": {
        "B_1": "C_LEON",
        "B_2": "C_LEON",
        "B_3": "C_BURGOS",
        "B_4": "C_BURGOS",
    },
}


BARONIES_GEOJSON: dict = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"id": "B_1", "name": "León", "centroid": [-5.5, 42.6]},
            "geometry": {"type": "Point", "coordinates": [-5.5, 42.6]},
        },
        {
            "type": "Feature",
            "properties": {"id": "B_2", "name": "Astorga", "centroid": [-5.4, 42.7]},
            "geometry": {"type": "Point", "coordinates": [-5.4, 42.7]},
        },
        {
            "type": "Feature",
            "properties": {"id": "B_3", "name": "Burgos", "centroid": [-3.7, 42.3]},
            "geometry": {"type": "Point", "coordinates": [-3.7, 42.3]},
        },
        {
            "type": "Feature",
            "properties": {"id": "B_4", "name": "Lerma", "centroid": [-3.6, 42.4]},
            "geometry": {"type": "Point", "coordinates": [-3.6, 42.4]},
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session_factory(async_engine):
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def project_root(tmp_path, monkeypatch):
    """Redirect DATA_DIR + PROJECTS_ROOT to a tmp dir; create raw/ for the project."""
    import medieval_forge.database as db_module
    import medieval_forge.services.paths as paths_module

    fake_data_dir = tmp_path / ".medieval-forge"
    fake_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(db_module, "DATA_DIR", fake_data_dir)
    monkeypatch.setattr(paths_module, "PROJECTS_ROOT", fake_data_dir / "projects")

    raw_dir = fake_data_dir / "projects" / PROJECT_ID / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


@pytest_asyncio.fixture
async def cached_project(async_session_factory, project_root):
    """Seed Project row + ResearchCache row + raw/baronies.geojson on disk."""
    cache_key = compute_cache_key(
        country_qid=COUNTRY_QID,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        provider="manual",
        model="manual",
    )
    async with async_session_factory() as session:
        session.add(Project(
            id=PROJECT_ID,
            name="Iberia 868-900",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bbox_lon_min=-9.5,
            bbox_lon_max=4.5,
            bbox_lat_min=36.0,
            bbox_lat_max=44.0,
            status="generated",
        ))
        session.add(ResearchCache(
            cache_key_hash=cache_key,
            payload=json.loads(json.dumps(INITIAL_PAYLOAD)),  # deep-copy
            provider="manual",
            model="manual",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        ))
        await session.commit()

    # Write baronies.geojson
    (project_root / "baronies.geojson").write_text(
        json.dumps(BARONIES_GEOJSON, ensure_ascii=False), encoding="utf-8",
    )
    return {"project_id": PROJECT_ID, "cache_key": cache_key}


@pytest_asyncio.fixture
async def async_client(async_session_factory, cached_project):
    async def _override():
        async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    app.state._test_session_factory = async_session_factory
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    if hasattr(app.state, "_test_session_factory"):
        del app.state._test_session_factory


URL = f"/api/projects/{PROJECT_ID}/research/assignments"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_assignments_moves_barony_between_condados(async_client):
    """Move B_2 from C_LEON → C_BURGOS; other keys untouched."""
    resp = await async_client.patch(URL, json={"barony_assignments": {"B_2": "C_BURGOS"}})
    assert resp.status_code == 200, resp.text

    result = resp.json()["result"]
    assert result["barony_assignments"] == {
        "B_1": "C_LEON",
        "B_2": "C_BURGOS",
        "B_3": "C_BURGOS",
        "B_4": "C_BURGOS",
    }
    # Other keys untouched
    assert result["kingdoms"] == INITIAL_PAYLOAD["kingdoms"]
    assert result["duchies"] == INITIAL_PAYLOAD["duchies"]
    assert result["condados"] == INITIAL_PAYLOAD["condados"]


@pytest.mark.asyncio
async def test_patch_assignments_renames_condado(async_client):
    """Rename C_LEON + reparent under D_CAST → kingdom_id MUST become K_CASTILLA."""
    resp = await async_client.patch(URL, json={
        "condado_renames": {
            "C_LEON": {"name": "Condado de León Renomeado", "duchy_id": "D_CAST"},
        },
    })
    assert resp.status_code == 200, resp.text

    result = resp.json()["result"]
    c_leon = next(c for c in result["condados"] if c["id"] == "C_LEON")
    assert c_leon["name"] == "Condado de León Renomeado"
    assert c_leon["duchy_id"] == "D_CAST"
    assert c_leon["kingdom_id"] == "K_CASTILLA"  # re-derived from new duchy
    # Assignments untouched
    assert result["barony_assignments"] == INITIAL_PAYLOAD["barony_assignments"]


@pytest.mark.asyncio
async def test_patch_assignments_creates_new_condado_split(async_client):
    """New condado via condado_renames + barony reassignment."""
    resp = await async_client.patch(URL, json={
        "condado_renames": {
            "C_NEW_OVIEDO": {"name": "Condado de Oviedo", "duchy_id": "D_LEON"},
        },
        "barony_assignments": {"B_2": "C_NEW_OVIEDO"},
    })
    assert resp.status_code == 200, resp.text

    result = resp.json()["result"]
    new = next((c for c in result["condados"] if c["id"] == "C_NEW_OVIEDO"), None)
    assert new is not None, "C_NEW_OVIEDO not appended to condados"
    assert new["name"] == "Condado de Oviedo"
    assert new["duchy_id"] == "D_LEON"
    assert new["kingdom_id"] == "K_LEON"  # derived from D_LEON.kingdom_id
    assert result["barony_assignments"]["B_2"] == "C_NEW_OVIEDO"

    # Re-parses cleanly through MapResearchResult
    from medieval_forge.services.llm.schemas import MapResearchResult
    MapResearchResult.model_validate(result)  # no exception


@pytest.mark.asyncio
async def test_patch_assignments_validates_unknown_barony_id(
    async_client, async_session_factory, cached_project
):
    """Unknown barony id → 400; cache row UNCHANGED."""
    resp = await async_client.patch(URL, json={
        "barony_assignments": {"B_NOT_REAL": "C_LEON"},
    })
    assert resp.status_code == 400, resp.text
    assert "B_NOT_REAL" in resp.json()["detail"]

    # Cache row UNCHANGED — re-fetch and deep-equal
    async with async_session_factory() as session:
        cached = await get_cached(session, cached_project["cache_key"])
    assert cached == INITIAL_PAYLOAD


@pytest.mark.asyncio
async def test_patch_assignments_persists_to_cache(
    async_client, async_session_factory, cached_project
):
    """PATCH overwrites the SAME cache_key_hash; no second row created."""
    resp = await async_client.patch(URL, json={"barony_assignments": {"B_3": "C_LEON"}})
    assert resp.status_code == 200, resp.text

    async with async_session_factory() as session:
        cached = await get_cached(session, cached_project["cache_key"])
    assert cached is not None
    assert cached["barony_assignments"]["B_3"] == "C_LEON"
    # Other assignments preserved
    assert cached["barony_assignments"]["B_1"] == "C_LEON"
    assert cached["barony_assignments"]["B_2"] == "C_LEON"
    assert cached["barony_assignments"]["B_4"] == "C_BURGOS"


@pytest.mark.asyncio
async def test_subsequent_generate_uses_edited_assignments(async_client):
    """After PATCH, territory_builder.assemble_territory_data_from_baronies sees edits."""
    resp = await async_client.patch(URL, json={"barony_assignments": {"B_2": "C_BURGOS"}})
    assert resp.status_code == 200, resp.text
    updated_payload = resp.json()["result"]

    territory_data = assemble_territory_data_from_baronies(updated_payload, BARONIES_GEOJSON)
    condados_by_id = {c[0]: c for c in territory_data["condados"]}

    leon = condados_by_id["C_LEON"]
    burgos = condados_by_id["C_BURGOS"]
    # Tuple shape: (id, name, lon, lat, duchy_id, baronies_list)
    assert len(leon[5]) == 1, f"C_LEON should have 1 barony, got {leon[5]}"
    assert len(burgos[5]) == 3, f"C_BURGOS should have 3 baronies, got {burgos[5]}"

    # Centroid for C_BURGOS = mean of B_2, B_3, B_4 centroids
    expected_lon = (-5.4 + -3.7 + -3.6) / 3
    expected_lat = (42.7 + 42.3 + 42.4) / 3
    assert abs(burgos[2] - expected_lon) < 1e-9
    assert abs(burgos[3] - expected_lat) < 1e-9
