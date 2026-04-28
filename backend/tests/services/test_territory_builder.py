"""Tests for territory_builder: assemble generator input from DB-cached research.

Covers the orphan bug #4 root-cause fix: the "Gerar mapa" pipeline must use the
ResearchCache row keyed by (country_qid, period_start, period_end), NOT a
hardcoded frontend template.

New architecture: the LLM generates condados with coordinates directly in the
research payload — no external geojson centroid file is needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.models import Base, Project, ResearchCache
from medieval_forge.services.research_cache import compute_cache_key
from medieval_forge.services.territory_builder import (
    assemble_territory_data,
    build_territory_data_from_cache,
    select_latest_cache_row,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COUNTRY_QID = "Q29,Q45"
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


def _make_91_research_payload() -> dict:
    """Synthetic ResearchResult-shaped payload with 91 condados, 4 duchies.

    Condados carry their own lon/lat — no separate centroid file needed.
    lon evenly spaced from -8.0; lat constant at 40.0.
    """
    duchy_ids = ["d_alpha", "d_beta", "d_gamma", "d_delta"]
    condados = [
        {
            "id": f"c_{i:03d}",
            "name": f"Condado {i:03d}",
            "lon": -8.0 + 0.1 * i,
            "lat": 40.0,
            "kingdom_id": "k_north" if i < 46 else "k_south",
            "duchy_id": duchy_ids[i % 4],
        }
        for i in range(1, 92)
    ]
    baronies = {
        c["id"]: [
            {"name": f"Baronia {c['id']}-1", "lon": c["lon"], "lat": c["lat"] + 0.05},
            {"name": f"Baronia {c['id']}-2", "lon": c["lon"] + 0.02, "lat": c["lat"]},
        ]
        for c in condados
    }
    return {
        "kingdoms": {"k_north": "Reino do Norte", "k_south": "Reino do Sul"},
        "duchies": {
            "d_alpha": {"kingdom_id": "k_north", "name": "Ducado Alfa"},
            "d_beta":  {"kingdom_id": "k_north", "name": "Ducado Beta"},
            "d_gamma": {"kingdom_id": "k_south", "name": "Ducado Gama"},
            "d_delta": {"kingdom_id": "k_south", "name": "Ducado Delta"},
        },
        "condados": condados,
        "baronies": baronies,
    }


# ---------------------------------------------------------------------------
# Test 1: select_latest_cache_row picks most-recent row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_latest_cache_row_returns_none_when_no_rows(session_factory):
    """No rows for the tuple → returns None."""
    async with session_factory() as session:
        row = await select_latest_cache_row(session, COUNTRY_QID, PERIOD_START, PERIOD_END)
    assert row is None


@pytest.mark.asyncio
async def test_select_latest_cache_row_picks_most_recent_across_providers(session_factory):
    """Multiple rows for same tuple across providers → newest created_at wins."""
    older = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 4, 22, 15, 30, 0, tzinfo=timezone.utc)

    async with session_factory() as session:
        session.add(ResearchCache(
            cache_key_hash=compute_cache_key(COUNTRY_QID, PERIOD_START, PERIOD_END, "claude", "claude-sonnet-4-6"),
            payload={"marker": "claude_older"},
            provider="claude",
            model="claude-sonnet-4-6",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            created_at=older,
        ))
        session.add(ResearchCache(
            cache_key_hash=compute_cache_key(COUNTRY_QID, PERIOD_START, PERIOD_END, "manual", "manual"),
            payload={"marker": "manual_newer"},
            provider="manual",
            model="manual",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            created_at=newer,
        ))
        session.add(ResearchCache(
            cache_key_hash=compute_cache_key("Q142", 1000, 1100, "claude", "claude-sonnet-4-6"),
            payload={"marker": "wrong_tuple"},
            provider="claude",
            model="claude-sonnet-4-6",
            country_qid="Q142",
            period_start=1000,
            period_end=1100,
            created_at=newer + timedelta(days=10),
        ))
        await session.commit()

    async with session_factory() as session:
        row = await select_latest_cache_row(session, COUNTRY_QID, PERIOD_START, PERIOD_END)
    assert row is not None
    assert row.payload == {"marker": "manual_newer"}
    assert row.provider == "manual"


# ---------------------------------------------------------------------------
# Test 2: assemble_territory_data produces correct shape
# ---------------------------------------------------------------------------

def test_assemble_territory_data_91_condados_correct_shape():
    """91-entry research payload → 91 condado tuples with baronies."""
    payload = _make_91_research_payload()

    td = assemble_territory_data(payload)

    assert td["kingdoms"] == payload["kingdoms"]
    assert td["duchies"] == payload["duchies"]
    assert isinstance(td["condados"], list)
    assert len(td["condados"]) == 91

    # Spot-check first entry: (id, name, lon, lat, duchy_id, baronies)
    first = td["condados"][0]
    assert first[0] == "c_001"
    assert first[1] == "Condado 001"
    assert first[2] == pytest.approx(-7.9)
    assert first[3] == pytest.approx(40.0)
    assert first[4] == "d_beta"   # i=1 → duchy_ids[1 % 4] = d_beta
    assert isinstance(first[5], list)
    assert len(first[5]) == 2
    # Barony tuple: (name, lon, lat)
    assert first[5][0] == ("Baronia c_001-1", pytest.approx(-7.9), pytest.approx(40.05))


def test_assemble_territory_data_empty_payload():
    """Empty payload → empty condados list, no error."""
    td = assemble_territory_data({})
    assert td["condados"] == []
    assert td["kingdoms"] == {}
    assert td["duchies"] == {}


def test_assemble_territory_data_barony_coords_correct():
    """Barony coordinates are read from the payload, not computed."""
    payload = {
        "kingdoms": {"k": "K"},
        "duchies": {"d": {"kingdom_id": "k", "name": "D"}},
        "condados": [
            {"id": "C_X", "name": "X", "lon": -3.5, "lat": 40.1,
             "kingdom_id": "k", "duchy_id": "d"},
        ],
        "baronies": {
            "C_X": [{"name": "Barão de X", "lon": -3.51, "lat": 40.12}],
        },
    }

    td = assemble_territory_data(payload)
    assert len(td["condados"]) == 1
    entry = td["condados"][0]
    assert entry[0] == "C_X"
    assert entry[2] == pytest.approx(-3.5)
    assert entry[3] == pytest.approx(40.1)
    assert entry[4] == "d"
    assert entry[5] == [("Barão de X", pytest.approx(-3.51), pytest.approx(40.12))]


# ---------------------------------------------------------------------------
# Test 3: build_territory_data_from_cache wires it all together
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_territory_data_from_cache_returns_none_on_miss(session_factory):
    """No cache row for project tuple → returns None."""
    project = Project(
        id="11111111-1111-4111-1111-111111111111",
        name="Iberia",
        country_qid=COUNTRY_QID,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status="created",
    )

    async with session_factory() as session:
        result = await build_territory_data_from_cache(session, project)
    assert result is None


@pytest.mark.asyncio
async def test_build_territory_data_from_cache_assembles_91_on_hit(session_factory):
    """Cache row → returns assembled territory_data with 91 condados (no geojson needed)."""
    project = Project(
        id="22222222-2222-4222-2222-222222222222",
        name="Iberia",
        country_qid=COUNTRY_QID,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status="created",
    )

    payload = _make_91_research_payload()
    async with session_factory() as session:
        session.add(ResearchCache(
            cache_key_hash=compute_cache_key(COUNTRY_QID, PERIOD_START, PERIOD_END, "manual", "manual"),
            payload=payload,
            provider="manual",
            model="manual",
            country_qid=COUNTRY_QID,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        ))
        await session.commit()

    async with session_factory() as session:
        td = await build_territory_data_from_cache(session, project)

    assert td is not None
    assert len(td["condados"]) == 91
    assert td["kingdoms"] == payload["kingdoms"]
    # Verify shape of one entry
    first = td["condados"][0]
    assert first[0] == "c_001"
    assert first[4] == "d_beta"   # i=1 → duchy_ids[1 % 4] = d_beta
    assert len(first[5]) == 2
