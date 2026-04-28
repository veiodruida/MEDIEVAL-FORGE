"""Etapa 7b (master plan H.7b / quick-260428-h0p): build_territory_data_from_cache dispatch.

build_territory_data_from_cache must dispatch by payload shape:
  - payload has "barony_assignments" → assemble_territory_data_from_baronies
    (Etapa 7 path; reads raw/baronies.geojson under project_path)
  - payload has legacy "baronies" dict → assemble_territory_data (legacy path,
    no geojson lookup needed)

Tests use explicit numeric centroids so the dispatch boundary is checked with
deterministic values (per project memory feedback-tests-descriptive).
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.models import Base, Project, ResearchCache
from medieval_forge.services.research_cache import compute_cache_key
from medieval_forge.services.territory_builder import build_territory_data_from_cache


PROJECT_ID = "deadc0de-cafe-4bee-8f00-bbbbbbbbbbbb"
COUNTRY_QID = "Q29"
PERIOD_START = 868
PERIOD_END = 900


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _seed_cache_row(payload: dict) -> ResearchCache:
    return ResearchCache(
        cache_key_hash=compute_cache_key(COUNTRY_QID, PERIOD_START, PERIOD_END, "claude", "claude-sonnet-4-6"),
        payload=payload,
        provider="claude",
        model="claude-sonnet-4-6",
        country_qid=COUNTRY_QID,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )


def _project_row() -> Project:
    return Project(
        id=PROJECT_ID,
        name="Iberia",
        country_qid=COUNTRY_QID,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status="baronies_built",
    )


def _write_baronies_geojson(raw_dir, baronies: list[dict]) -> None:
    features = [
        {
            "type": "Feature",
            "properties": {
                "id": b["id"],
                "name": b["name"],
                "centroid": [b["lon"], b["lat"]],
                "municipality_ids": [],
            },
            "geometry": {"type": "Polygon", "coordinates": [[
                [b["lon"], b["lat"]],
                [b["lon"] + 0.1, b["lat"]],
                [b["lon"] + 0.1, b["lat"] + 0.1],
                [b["lon"], b["lat"] + 0.1],
                [b["lon"], b["lat"]],
            ]]},
        }
        for b in baronies
    ]
    fc = {"type": "FeatureCollection", "features": features}
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "baronies.geojson").write_text(
        json.dumps(fc, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_territory_data_from_cache_uses_baronies_aggregator_when_payload_has_assignments(
    session_factory, tmp_path
):
    """MapResearchResult-shaped payload → assemble_territory_data_from_baronies."""
    project_path = tmp_path / "projects" / PROJECT_ID
    raw_dir = project_path / "raw"
    _write_baronies_geojson(raw_dir, [
        {"id": "B_001", "name": "Norte", "lon": -8.40, "lat": 41.55},
        {"id": "B_002", "name": "Sul",   "lon": -8.60, "lat": 41.45},
    ])

    payload = {
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [
            {"id": "C_BRAGA", "name": "Braga",
             "kingdom_id": "k_iberia", "duchy_id": "d_galicia"},
        ],
        "barony_assignments": {"B_001": "C_BRAGA", "B_002": "C_BRAGA"},
    }

    project = _project_row()
    async with session_factory() as session:
        session.add(project)
        session.add(_seed_cache_row(payload))
        await session.commit()
        td = await build_territory_data_from_cache(session, project, project_path)

    assert td is not None
    assert len(td["condados"]) == 1
    cid, name, lon, lat, duchy_id, baronies = td["condados"][0]
    assert cid == "C_BRAGA"
    assert lon == pytest.approx(-8.50, rel=1e-9)
    assert lat == pytest.approx(41.50, rel=1e-9)
    assert duchy_id == "d_galicia"
    assert len(baronies) == 2


@pytest.mark.asyncio
async def test_build_territory_data_from_cache_uses_legacy_assembler_when_payload_lacks_assignments(
    session_factory, tmp_path
):
    """Legacy ResearchResult payload (with 'baronies' dict + condados with lon/lat) → legacy path."""
    project_path = tmp_path / "projects" / PROJECT_ID
    # Intentionally do NOT write baronies.geojson — legacy path doesn't need it.

    payload = {
        "kingdoms": {"k1": "Iberia"},
        "duchies": {"d1": {"kingdom_id": "k1", "name": "Galicia"}},
        "condados": [
            {"id": "C_BRAGA", "name": "Braga",
             "lon": -8.43, "lat": 41.55,
             "kingdom_id": "k1", "duchy_id": "d1"},
        ],
        "baronies": {"C_BRAGA": [{"name": "Baronia de Braga", "lon": -8.43, "lat": 41.55}]},
    }

    project = _project_row()
    async with session_factory() as session:
        session.add(project)
        session.add(_seed_cache_row(payload))
        await session.commit()
        td = await build_territory_data_from_cache(session, project, project_path)

    assert td is not None
    cid, name, lon, lat, duchy_id, baronies = td["condados"][0]
    assert cid == "C_BRAGA"
    assert lon == pytest.approx(-8.43, rel=1e-9)
    assert lat == pytest.approx(41.55, rel=1e-9)
    assert len(baronies) == 1
