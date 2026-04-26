"""Tests for territory_builder: assemble generator input from DB cache + geojson centroids.

Covers the orphan bug #4 root-cause fix: the "Gerar mapa" pipeline must use the
ResearchCache row keyed by (country_qid, period_start, period_end), NOT a
hardcoded frontend template.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def _make_91_condados_centroids() -> list[dict]:
    """Synthetic 91-entry centroid list with explicit ids c_001..c_091.

    lon evenly spaced from -8.0; lat constant at 40.0 — explicit numerics so
    test failures point at concrete values (per project test conventions).
    """
    return [
        {
            "id": f"c_{i:03d}",
            "name": f"Condado {i:03d}",
            "lon": -8.0 + 0.1 * i,
            "lat": 40.0,
        }
        for i in range(1, 92)
    ]


def _make_91_research_payload() -> dict:
    """Synthetic ResearchResult-shaped payload with 91 condados across 4 duchies."""
    centroids = _make_91_condados_centroids()
    duchy_ids = ["d_alpha", "d_beta", "d_gamma", "d_delta"]
    payload = {
        "kingdoms": {"k_north": "Reino do Norte", "k_south": "Reino do Sul"},
        "duchies": {
            "d_alpha": {"kingdom_id": "k_north", "name": "Ducado Alfa"},
            "d_beta": {"kingdom_id": "k_north", "name": "Ducado Beta"},
            "d_gamma": {"kingdom_id": "k_south", "name": "Ducado Gama"},
            "d_delta": {"kingdom_id": "k_south", "name": "Ducado Delta"},
        },
        "condados_assignment": [
            {
                "condado_id": c["id"],
                "kingdom_id": "k_north" if i < 46 else "k_south",
                "duchy_id": duchy_ids[i % 4],
            }
            for i, c in enumerate(centroids)
        ],
        "baronies": {
            c["id"]: [
                {"name": f"Baronia {c['id']}-1", "lon": c["lon"], "lat": c["lat"] + 0.05},
                {"name": f"Baronia {c['id']}-2", "lon": c["lon"] + 0.02, "lat": c["lat"]},
            ]
            for c in centroids
        },
    }
    return payload


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
        # Row 1: claude provider, older
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
        # Row 2: manual provider, newer
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
        # Row 3: irrelevant tuple — must be ignored
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
    """91-entry research payload + 91 centroids → 91 condado tuples with baronies."""
    payload = _make_91_research_payload()
    centroids = _make_91_condados_centroids()

    td = assemble_territory_data(payload, centroids)

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
    assert first[4] == "d_alpha"  # i=0, duchy_ids[0 % 4]
    assert isinstance(first[5], list)
    assert len(first[5]) == 2
    # Barony tuple: (name, lon, lat)
    assert first[5][0] == ("Baronia c_001-1", pytest.approx(-7.9), pytest.approx(40.05))


# ---------------------------------------------------------------------------
# Test 3: assignment referencing unknown id → ValueError
# ---------------------------------------------------------------------------

def test_assemble_raises_when_assignment_references_unknown_centroid():
    """condado_id in assignment but not in centroids → ValueError listing missing ids."""
    centroids = [
        {"id": "c_001", "name": "A", "lon": 0.0, "lat": 0.0},
        {"id": "c_002", "name": "B", "lon": 1.0, "lat": 0.0},
    ]
    payload = {
        "kingdoms": {"k": "K"},
        "duchies": {"d": {"kingdom_id": "k", "name": "D"}},
        "condados_assignment": [
            {"condado_id": "c_001", "kingdom_id": "k", "duchy_id": "d"},
            {"condado_id": "GHOST_42", "kingdom_id": "k", "duchy_id": "d"},
        ],
        "baronies": {},
    }

    with pytest.raises(ValueError) as exc_info:
        assemble_territory_data(payload, centroids)
    assert "GHOST_42" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 4: centroid without assignment → included with duchy_id=None
# ---------------------------------------------------------------------------

def test_assemble_includes_unassigned_centroids_with_none_duchy():
    """Centroid id missing from assignment → included with duchy_id=None and empty baronies."""
    centroids = [
        {"id": "c_001", "name": "A", "lon": 0.0, "lat": 0.0},
        {"id": "c_002", "name": "B", "lon": 1.0, "lat": 0.0},
        {"id": "c_003", "name": "C", "lon": 2.0, "lat": 0.0},  # no assignment
    ]
    payload = {
        "kingdoms": {"k": "K"},
        "duchies": {"d": {"kingdom_id": "k", "name": "D"}},
        "condados_assignment": [
            {"condado_id": "c_001", "kingdom_id": "k", "duchy_id": "d"},
            {"condado_id": "c_002", "kingdom_id": "k", "duchy_id": "d"},
        ],
        "baronies": {"c_001": [{"name": "B1", "lon": 0.1, "lat": 0.1}]},
    }

    td = assemble_territory_data(payload, centroids)
    assert len(td["condados"]) == 3
    by_id = {c[0]: c for c in td["condados"]}
    assert by_id["c_003"][4] is None
    assert by_id["c_003"][5] == []
    assert by_id["c_001"][4] == "d"
    assert by_id["c_001"][5] == [("B1", pytest.approx(0.1), pytest.approx(0.1))]


# ---------------------------------------------------------------------------
# Test 5: build_territory_data_from_cache wires it all together
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_territory_data_from_cache_returns_none_on_miss(session_factory, tmp_path):
    """No cache row for project tuple → returns None."""
    project = Project(
        id="11111111-1111-4111-1111-111111111111",
        name="Iberia",
        country_qid=COUNTRY_QID,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status="created",
    )
    # Need a territories.geojson on disk for the function to even attempt the lookup;
    # but on cache miss we expect early return without touching disk.
    project_path = tmp_path / project.id
    project_path.mkdir(parents=True, exist_ok=True)

    async with session_factory() as session:
        result = await build_territory_data_from_cache(session, project, project_path)
    assert result is None


@pytest.mark.asyncio
async def test_build_territory_data_from_cache_assembles_91_on_hit(session_factory, tmp_path):
    """Cache row + matching geojson → returns assembled territory_data with 91 condados."""
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

    # Write 91-feature territories.geojson
    project_path = tmp_path / project.id
    gen_dir = project_path / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    centroids = _make_91_condados_centroids()
    features = [
        {
            "type": "Feature",
            "properties": {"id": c["id"], "name": c["name"], "centroid": [c["lon"], c["lat"]]},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [c["lon"], c["lat"]],
                    [c["lon"] + 0.01, c["lat"]],
                    [c["lon"] + 0.01, c["lat"] + 0.01],
                    [c["lon"], c["lat"] + 0.01],
                    [c["lon"], c["lat"]],
                ]],
            },
        }
        for c in centroids
    ]
    (gen_dir / "territories.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )

    async with session_factory() as session:
        td = await build_territory_data_from_cache(session, project, project_path)

    assert td is not None
    assert len(td["condados"]) == 91
    assert td["kingdoms"] == payload["kingdoms"]
    # Verify shape of one entry
    first = td["condados"][0]
    assert first[0] == "c_001"
    assert first[4] == "d_alpha"
    assert len(first[5]) == 2
