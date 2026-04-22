"""Integration tests for GET /research/prompt and POST /research/manual endpoints.

Six behaviors covered:
  1. GET /prompt with valid project + territories.geojson → 200 with non-empty prompt
     containing country name and at least one condado id.
  2. GET /prompt with malformed UUID → 400.
  3. GET /prompt with unknown project UUID → 404.
  4. POST /manual with well-formed JSON + valid condado_ids → 200 with result;
     subsequent GET /research/cached?provider=manual&model=manual returns same payload.
  5. POST /manual with invalid JSON → 400 with error message; no cache row created.
  6. POST /manual with JSON referencing unknown condado_id → 400 naming bad id; no cache row.
"""
from __future__ import annotations

import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base, Project


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
async def async_client(async_session_factory):
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


@pytest_asyncio.fixture
async def project_with_territories(async_session_factory, tmp_path, monkeypatch):
    """Create a Project row + a minimal territories.geojson under generated/."""
    import medieval_forge.services.paths as paths_mod

    fake_root = tmp_path / "projects"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

    pid = "cccccccc-cccc-4ccc-cccc-cccccccccccc"
    async with async_session_factory() as session:
        session.add(Project(
            id=pid,
            name="Test Kingdom",
            country_qid="Q29",
            period_start=868,
            period_end=900,
            status="generated",
        ))
        await session.commit()

    # Write territories.geojson to generated/ (matches load_condados path)
    gen_dir = fake_root / pid / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    territories = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "c1", "name": "Condado A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"id": "c2", "name": "Condado B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
                },
            },
        ],
    }
    (gen_dir / "territories.geojson").write_text(json.dumps(territories), encoding="utf-8")

    return pid


VALID_RESULT_JSON = json.dumps({
    "kingdoms": {"k1": "Leon"},
    "duchies": {"d1": {"kingdom_id": "k1", "name": "Duchy of Leon"}},
    "condados_assignment": [
        {"condado_id": "c1", "kingdom_id": "k1", "duchy_id": "d1"},
        {"condado_id": "c2", "kingdom_id": "k1", "duchy_id": "d1"},
    ],
    "baronies": {"c1": [], "c2": []},
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_get_prompt_returns_prompt_with_condado_ids(async_client, project_with_territories):
    """GET /prompt returns 200 with non-empty prompt containing country name + condado ids."""
    pid = project_with_territories
    resp = await async_client.get(f"/api/projects/{pid}/research/prompt")
    assert resp.status_code == 200
    data = resp.json()
    assert "prompt" in data
    prompt = data["prompt"]
    assert len(prompt) > 50
    assert "Test Kingdom" in prompt
    assert "c1" in prompt
    assert "c2" in prompt


async def test_get_prompt_bad_uuid_returns_400(async_client):
    """GET /prompt with malformed UUID returns 400."""
    resp = await async_client.get("/api/projects/not-a-uuid/research/prompt")
    assert resp.status_code == 400


async def test_get_prompt_unknown_project_returns_404(async_client, project_with_territories):
    """GET /prompt with unknown valid UUID returns 404."""
    unknown = "dddddddd-dddd-4ddd-dddd-dddddddddddd"
    resp = await async_client.get(f"/api/projects/{unknown}/research/prompt")
    assert resp.status_code == 404


async def test_post_manual_valid_json_returns_result_and_caches(
    async_client, async_session_factory, project_with_territories
):
    """POST /manual with valid JSON → 200 with result; GET /cached?provider=manual returns same payload."""
    pid = project_with_territories
    resp = await async_client.post(
        f"/api/projects/{pid}/research/manual",
        json={"content": VALID_RESULT_JSON},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    result = data["result"]
    assert result["kingdoms"] == {"k1": "Leon"}
    assert len(result["condados_assignment"]) == 2

    # Cache row created — GET /cached?provider=manual returns the same payload
    cached_resp = await async_client.get(
        f"/api/projects/{pid}/research/cached?provider=manual&model=manual"
    )
    assert cached_resp.status_code == 200
    cached = cached_resp.json()
    assert cached["kingdoms"] == {"k1": "Leon"}


async def test_post_manual_invalid_json_returns_400_no_cache(
    async_client, async_session_factory, project_with_territories
):
    """POST /manual with invalid JSON → 400 with error message; no cache row created."""
    pid = project_with_territories
    resp = await async_client.post(
        f"/api/projects/{pid}/research/manual",
        json={"content": "this is not json at all"},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail  # non-empty error message

    # No cache row should exist
    cached_resp = await async_client.get(
        f"/api/projects/{pid}/research/cached?provider=manual&model=manual"
    )
    assert cached_resp.status_code == 404


async def test_post_manual_unknown_condado_id_returns_400_no_cache(
    async_client, project_with_territories
):
    """POST /manual with unknown condado_id → 400 naming the bad id; no cache row created."""
    pid = project_with_territories
    bad_json = json.dumps({
        "kingdoms": {"k1": "Leon"},
        "duchies": {"d1": {"kingdom_id": "k1", "name": "Duchy of Leon"}},
        "condados_assignment": [
            {"condado_id": "FAKE_ID_999", "kingdom_id": "k1", "duchy_id": "d1"},
        ],
        "baronies": {},
    })
    resp = await async_client.post(
        f"/api/projects/{pid}/research/manual",
        json={"content": bad_json},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "FAKE_ID_999" in detail

    # No cache row should exist
    cached_resp = await async_client.get(
        f"/api/projects/{pid}/research/cached?provider=manual&model=manual"
    )
    assert cached_resp.status_code == 404
