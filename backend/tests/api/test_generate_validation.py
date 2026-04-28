"""Pre-flight validation in /generate — surfaces friendly 422 instead of cryptic 'erro 0'."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.api.generate import _validate_territory_data_for_generation
from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project, ResearchCache
from medieval_forge.services.research_cache import compute_cache_key


PROJECT_ID = "fafafafa-fafa-4afa-aafa-fafafafafafa"
COUNTRY_QID = "Q29"
PERIOD_START = 800
PERIOD_END = 900


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(session_factory):
    async def _override():
        async with session_factory() as session:
            yield session
    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unit tests for the validator function
# ---------------------------------------------------------------------------

def test_validator_rejects_non_dict():
    from fastapi import HTTPException
    import pytest as _pytest
    with _pytest.raises(HTTPException) as exc_info:
        _validate_territory_data_for_generation("not a dict")
    assert exc_info.value.status_code == 422


def test_validator_rejects_empty_condados():
    from fastapi import HTTPException
    import pytest as _pytest
    with _pytest.raises(HTTPException) as exc_info:
        _validate_territory_data_for_generation({"kingdoms": {}, "duchies": {}, "condados": []})
    assert exc_info.value.status_code == 422
    assert "zero condados" in exc_info.value.detail


def test_validator_rejects_zero_zero_coords():
    from fastapi import HTTPException
    import pytest as _pytest
    bad = {
        "kingdoms": {"k": "K"},
        "duchies": {"d": ("k", "D")},
        "condados": [("c1", "C", 0.0, 0.0, "d", [])],
    }
    with _pytest.raises(HTTPException) as exc_info:
        _validate_territory_data_for_generation(bad)
    assert exc_info.value.status_code == 422
    assert "(0,0)" in exc_info.value.detail


def test_validator_rejects_nan_coords():
    from fastapi import HTTPException
    import pytest as _pytest
    bad = {
        "kingdoms": {"k": "K"}, "duchies": {"d": ("k", "D")},
        "condados": [("c1", "C", float("nan"), 40.0, "d", [])],
    }
    with _pytest.raises(HTTPException) as exc_info:
        _validate_territory_data_for_generation(bad)
    assert exc_info.value.status_code == 422
    assert "NaN" in exc_info.value.detail


def test_validator_accepts_valid_minimal_payload():
    valid = {
        "kingdoms": {"k": "K"}, "duchies": {"d": ("k", "D")},
        "condados": [("c1", "Coimbra", -8.43, 40.21, "d", [("B", -8.43, 40.21)])],
    }
    # Should not raise
    _validate_territory_data_for_generation(valid)


def test_validator_accepts_empty_baronies_list():
    """Empty baronies are tolerated — generator handles that path itself."""
    valid = {
        "kingdoms": {"k": "K"}, "duchies": {"d": ("k", "D")},
        "condados": [("c1", "C", -3.0, 40.0, "d", [])],
    }
    _validate_territory_data_for_generation(valid)


# ---------------------------------------------------------------------------
# Integration: 422 surfaces through the API
# ---------------------------------------------------------------------------

async def test_generate_rejects_zero_zero_coords_with_friendly_message(
    async_client, session_factory, tmp_path, monkeypatch
):
    """End-to-end: cached research with (0,0) coords → 422 with Portuguese explanation."""
    import medieval_forge.services.paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    bad_payload = {
        "kingdoms": {"k": "K"},
        "duchies": {"d": {"kingdom_id": "k", "name": "D"}},
        "condados": [
            {"id": "c1", "name": "Bad", "lon": 0.0, "lat": 0.0,
             "kingdom_id": "k", "duchy_id": "d"},
        ],
        "baronies": {"c1": [{"name": "B1", "lon": 0.0, "lat": 0.0}]},
    }

    async with session_factory() as session:
        session.add(Project(
            id=PROJECT_ID, name="Test", country_qid=COUNTRY_QID,
            period_start=PERIOD_START, period_end=PERIOD_END, status="created",
        ))
        session.add(ResearchCache(
            cache_key_hash=compute_cache_key(COUNTRY_QID, PERIOD_START, PERIOD_END, "manual", "manual"),
            payload=bad_payload, provider="manual", model="manual",
            country_qid=COUNTRY_QID, period_start=PERIOD_START, period_end=PERIOD_END,
            created_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
        ))
        await session.commit()

    captured: dict = {}
    async def _capture(project_id, config):
        captured["called"] = True

    with patch("medieval_forge.api.generate._run_and_update_status", new=_capture):
        resp = await async_client.post(f"/api/projects/{PROJECT_ID}/generate", json={})

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "Coordenadas inválidas" in detail
    assert "called" not in captured  # background task NOT scheduled


async def test_generate_rejects_empty_condados_with_friendly_message(
    async_client, session_factory, tmp_path, monkeypatch
):
    """Cached research with zero condados → 422 with rerun suggestion."""
    import medieval_forge.services.paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    empty_payload = {"kingdoms": {}, "duchies": {}, "condados": [], "baronies": {}}

    async with session_factory() as session:
        session.add(Project(
            id=PROJECT_ID, name="Test", country_qid=COUNTRY_QID,
            period_start=PERIOD_START, period_end=PERIOD_END, status="created",
        ))
        session.add(ResearchCache(
            cache_key_hash=compute_cache_key(COUNTRY_QID, PERIOD_START, PERIOD_END, "manual", "manual"),
            payload=empty_payload, provider="manual", model="manual",
            country_qid=COUNTRY_QID, period_start=PERIOD_START, period_end=PERIOD_END,
            created_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
        ))
        await session.commit()

    resp = await async_client.post(f"/api/projects/{PROJECT_ID}/generate", json={})
    assert resp.status_code == 422
    assert "zero condados" in resp.json()["detail"]
