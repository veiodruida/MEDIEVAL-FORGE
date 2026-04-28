"""Regression for orphan bug #4: /generate must use DB-cached research, not the body.

The bug: clicking "Gerar mapa" on an Iberia (Q29,Q45) project with cached
91-condado manual research produced a map with only 4 condados because the
frontend posted a stale template that the server blindly accepted.

The fix: api/generate.py prefers the latest ResearchCache row over the body.
The body is a power-user override gated by `force_body_territory_data: true`.

New architecture: research payload carries condados with coordinates directly —
no geojson centroid file is needed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project, ResearchCache
from medieval_forge.services.research_cache import compute_cache_key


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ID = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
COUNTRY_QID = "Q29,Q45"
PERIOD_START = 800
PERIOD_END = 900


@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(async_engine):
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def async_client(session_factory):
    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    app.state._test_session_factory = session_factory
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    if hasattr(app.state, "_test_session_factory"):
        del app.state._test_session_factory


def _build_research_payload_91() -> dict:
    """91-condado research payload using the new condados list format."""
    duchy_ids = ["d_alpha", "d_beta", "d_gamma", "d_delta"]
    condados = [
        {
            "id": f"c_{i:03d}",
            "name": f"Condado {i:03d}",
            "lon": -8.0 + 0.1 * i,
            "lat": 40.0,
            "kingdom_id": "k_north",
            "duchy_id": duchy_ids[i % 4],
        }
        for i in range(1, 92)
    ]
    return {
        "kingdoms": {"k_north": "Reino Norte"},
        "duchies": {"d_alpha": {"kingdom_id": "k_north", "name": "Ducado Alfa"},
                    "d_beta":  {"kingdom_id": "k_north", "name": "Ducado Beta"},
                    "d_gamma": {"kingdom_id": "k_north", "name": "Ducado Gama"},
                    "d_delta": {"kingdom_id": "k_north", "name": "Ducado Delta"}},
        "condados": condados,
        "baronies": {c["id"]: [] for c in condados},
    }


@pytest_asyncio.fixture
async def project_with_cache(session_factory, tmp_path, monkeypatch):
    """Project + 91-condado cache row. No geojson needed."""
    import medieval_forge.services.paths as paths_mod
    fake_root = tmp_path / "projects"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

    payload = _build_research_payload_91()

    async with session_factory() as session:
        session.add(Project(
            id=PROJECT_ID,
            name="Iberia",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bbox_lon_min=-9.5,
            bbox_lon_max=4.5,
            bbox_lat_min=36.0,
            bbox_lat_max=44.0,
            status="created",
        ))
        session.add(ResearchCache(
            cache_key_hash=compute_cache_key(COUNTRY_QID, PERIOD_START, PERIOD_END, "manual", "manual"),
            payload=payload,
            provider="manual",
            model="manual",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            created_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
        ))
        await session.commit()

    return PROJECT_ID


@pytest_asyncio.fixture
async def project_no_cache(session_factory, tmp_path, monkeypatch):
    """Project with NO cache row."""
    import medieval_forge.services.paths as paths_mod
    fake_root = tmp_path / "projects"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

    async with session_factory() as session:
        session.add(Project(
            id=PROJECT_ID,
            name="Iberia",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            status="created",
        ))
        await session.commit()

    return PROJECT_ID


# Stale 4-condado body that the frontend currently sends.
STALE_BODY_4 = {
    "territory_data": {
        "kingdoms": {"k_stale": "Stale Kingdom"},
        "duchies": {"d_stale": {"kingdom_id": "k_stale", "name": "Stale Duchy"}},
        "condados": [
            ["coimbra", "Coimbra", -8.43, 40.21, "d_stale", []],
            ["braga", "Braga", -8.43, 41.55, "d_stale", []],
            ["porto", "Porto", -8.61, 41.15, "d_stale", []],
            ["viana", "Viana", -8.83, 41.69, "d_stale", []],
        ],
    },
}


# ---------------------------------------------------------------------------
# Test 1: REGRESSION — empty body + 91-cache → 91 condados (not 4)
# ---------------------------------------------------------------------------

async def test_generate_with_empty_body_uses_91_condado_cache(
    async_client, project_with_cache
):
    """The bug: cached 91-condado research must populate territory_data, not be ignored."""
    pid = project_with_cache

    captured: dict = {}

    async def _capture(project_id, config):
        captured["project_id"] = project_id
        captured["config"] = config

    with patch("medieval_forge.api.generate._run_and_update_status", new=_capture):
        resp = await async_client.post(f"/api/projects/{pid}/generate", json={})

    assert resp.status_code == 202, resp.text
    assert captured["project_id"] == pid
    td = captured["config"]["territory_data"]
    assert len(td["condados"]) == 91, f"expected 91 condados from cache, got {len(td['condados'])}"


# ---------------------------------------------------------------------------
# Test 2: cache wins over body when no override flag
# ---------------------------------------------------------------------------

async def test_generate_cache_wins_over_stale_body(
    async_client, project_with_cache
):
    """Even if body posts 4-condado template, cache row supersedes it."""
    pid = project_with_cache

    captured: dict = {}

    async def _capture(project_id, config):
        captured["config"] = config

    with patch("medieval_forge.api.generate._run_and_update_status", new=_capture):
        resp = await async_client.post(f"/api/projects/{pid}/generate", json=STALE_BODY_4)

    assert resp.status_code == 202, resp.text
    assert len(captured["config"]["territory_data"]["condados"]) == 91


# ---------------------------------------------------------------------------
# Test 3: empty body + no cache → 422 with "research" in detail
# ---------------------------------------------------------------------------

async def test_generate_no_cache_no_body_returns_422(
    async_client, project_no_cache, session_factory
):
    """Empty body and no cache row → 422 mentioning research; project status untouched."""
    pid = project_no_cache

    captured: dict = {}

    async def _capture(project_id, config):
        captured["config"] = config

    with patch("medieval_forge.api.generate._run_and_update_status", new=_capture):
        resp = await async_client.post(f"/api/projects/{pid}/generate", json={})

    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "research" in detail.lower()

    assert "config" not in captured
    async with session_factory() as session:
        proj = await session.get(Project, pid)
        assert proj.status == "created"


# ---------------------------------------------------------------------------
# Test 4: explicit force_body override → body wins (4 condados)
# ---------------------------------------------------------------------------

async def test_generate_force_body_override_uses_body(
    async_client, project_with_cache
):
    """Power-user escape hatch: force_body_territory_data=true → body wins."""
    pid = project_with_cache

    captured: dict = {}

    async def _capture(project_id, config):
        captured["config"] = config

    body = {**STALE_BODY_4, "force_body_territory_data": True}
    with patch("medieval_forge.api.generate._run_and_update_status", new=_capture):
        resp = await async_client.post(f"/api/projects/{pid}/generate", json=body)

    assert resp.status_code == 202, resp.text
    td = captured["config"]["territory_data"]
    assert len(td["condados"]) == 4
    assert "force_body_territory_data" not in captured["config"]
