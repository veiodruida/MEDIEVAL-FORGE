"""Etapa 7b (master plan H.7b / quick-260428-h0p): research_runner map-path wiring.

These tests cover the new branching behavior in `run_research`:

- When a project has ``raw/baronies.geojson`` on disk, ``run_research`` must:
  * call ``build_map_research_prompt`` (markers: BARONIES section + barony ids)
  * pass ``MapResearchResult`` as the schema to the provider
  * run ``validate_barony_assignments`` inside the ``_ValidatingWrapper`` so
    bad LLM output triggers retry via ``run_with_retry``
  * cache the resulting payload (which has ``barony_assignments``, not legacy ``baronies``)

- When a project has NO ``raw/baronies.geojson``, the legacy ``ResearchResult``
  flow remains byte-identical (regression guard for the 234-test baseline).

Fixtures use explicit numeric coords (per project memory feedback-tests-descriptive)
and the in-memory async SQLite pattern from test_research_sse.py / test_baronies_endpoint.py.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.models import Base, Project, ResearchCache


PROJECT_ID = "feedface-cafe-4bee-8f00-aaaaaaaaaaaa"


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


@pytest_asyncio.fixture
async def project_paths(tmp_path, monkeypatch):
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


async def _seed_project(factory) -> None:
    async with factory() as session:
        session.add(Project(
            id=PROJECT_ID,
            name="Iberia",
            country_qid="Q29",
            period_start=868,
            period_end=900,
            status="baronies_built",
        ))
        await session.commit()


def _write_baronies_geojson(raw_dir, baronies: list[dict]) -> None:
    """baronies = [{id, name, lon, lat}] → write FeatureCollection at raw/baronies.geojson."""
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
    (raw_dir / "baronies.geojson").write_text(
        json.dumps(fc, ensure_ascii=False), encoding="utf-8"
    )


def _drain_queue(queue: asyncio.Queue) -> list[str]:
    """Drain a queue into a list of strings (skipping the None sentinel)."""
    out: list[str] = []
    while True:
        try:
            item = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if item is None:
            break
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_research_uses_map_prompt_and_schema_when_baronies_geojson_exists(
    project_paths, session_factory, monkeypatch
):
    """raw/baronies.geojson exists → MapResearchResult prompt + schema."""
    from medieval_forge.services import research_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.llm.schemas import MapResearchResult

    await _seed_project(session_factory)
    _write_baronies_geojson(project_paths, [
        {"id": "B_001", "name": "Baronia Norte", "lon": -8.40, "lat": 41.55},
        {"id": "B_002", "name": "Baronia Sul",   "lon": -8.60, "lat": 41.45},
    ])

    captured: dict[str, Any] = {}
    valid_result = MapResearchResult.model_validate({
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [{"id": "C_BRAGA", "name": "Braga",
                       "kingdom_id": "k_iberia", "duchy_id": "d_galicia"}],
        "barony_assignments": {"B_001": "C_BRAGA", "B_002": "C_BRAGA"},
    })

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            captured["prompt"] = prompt
            captured["schema"] = schema
            return valid_result

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    queue: asyncio.Queue = asyncio.Queue()
    await research_runner.run_research(
        PROJECT_ID, "claude", queue,
        db_session_factory=session_factory,
    )

    assert "BARONIES" in captured["prompt"]
    assert "B_001" in captured["prompt"] and "B_002" in captured["prompt"]
    assert captured["schema"] is MapResearchResult

    msgs = _drain_queue(queue)
    body = "\n".join(msgs)
    assert "barony_assignments" in body


@pytest.mark.asyncio
async def test_run_research_falls_back_to_legacy_when_no_baronies_geojson(
    project_paths, session_factory, monkeypatch
):
    """No baronies.geojson on disk → legacy ResearchResult flow."""
    from medieval_forge.services import research_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.llm.schemas import ResearchResult, Condado, Duchy

    await _seed_project(session_factory)
    # Intentionally no baronies.geojson written.

    captured: dict[str, Any] = {}
    legacy_result = ResearchResult(
        kingdoms={"k1": "Iberia"},
        duchies={"d1": Duchy(kingdom_id="k1", name="Galicia")},
        condados=[Condado(id="C_BRAGA", name="Braga", lon=-8.4, lat=41.5,
                          kingdom_id="k1", duchy_id="d1")],
        baronies={"C_BRAGA": []},
    )

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            captured["prompt"] = prompt
            captured["schema"] = schema
            return legacy_result

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    queue: asyncio.Queue = asyncio.Queue()
    await research_runner.run_research(
        PROJECT_ID, "claude", queue,
        db_session_factory=session_factory,
    )

    assert captured["schema"] is ResearchResult
    # The map-prompt's "BARONIES (pre-built from OSM" header must NOT appear
    # in the legacy prompt.
    assert "BARONIES (pre-built from OSM" not in captured["prompt"]
    assert "barony_assignments" not in captured["prompt"]


@pytest.mark.asyncio
async def test_run_research_map_path_validates_assignments_and_retries_on_mismatch(
    project_paths, session_factory, monkeypatch
):
    """Incomplete barony_assignments → ValueError → run_with_retry re-prompts."""
    from medieval_forge.services import research_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.llm.schemas import MapResearchResult

    await _seed_project(session_factory)
    _write_baronies_geojson(project_paths, [
        {"id": "B_001", "name": "Baronia Norte", "lon": -8.40, "lat": 41.55},
        {"id": "B_002", "name": "Baronia Sul",   "lon": -8.60, "lat": 41.45},
    ])

    incomplete_result = MapResearchResult.model_validate({
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [{"id": "C_BRAGA", "name": "Braga",
                       "kingdom_id": "k_iberia", "duchy_id": "d_galicia"}],
        # B_002 left unassigned → validate_barony_assignments raises
        "barony_assignments": {"B_001": "C_BRAGA"},
    })
    complete_result = MapResearchResult.model_validate({
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [{"id": "C_BRAGA", "name": "Braga",
                       "kingdom_id": "k_iberia", "duchy_id": "d_galicia"}],
        "barony_assignments": {"B_001": "C_BRAGA", "B_002": "C_BRAGA"},
    })

    call_count = {"n": 0}

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            call_count["n"] += 1
            return incomplete_result if call_count["n"] == 1 else complete_result

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    queue: asyncio.Queue = asyncio.Queue()
    await research_runner.run_research(
        PROJECT_ID, "claude", queue,
        db_session_factory=session_factory,
    )

    assert call_count["n"] == 2, "validate_barony_assignments should have triggered one retry"
    body = "\n".join(_drain_queue(queue))
    assert "B_001" in body and "B_002" in body and "barony_assignments" in body


@pytest.mark.asyncio
async def test_run_research_map_path_caches_payload_with_barony_assignments_key(
    project_paths, session_factory, monkeypatch
):
    """Stored cache payload has barony_assignments (not legacy 'baronies')."""
    from sqlalchemy import select
    from medieval_forge.services import research_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.llm.schemas import MapResearchResult

    await _seed_project(session_factory)
    _write_baronies_geojson(project_paths, [
        {"id": "B_001", "name": "Norte", "lon": -8.40, "lat": 41.55},
    ])

    valid_result = MapResearchResult.model_validate({
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [{"id": "C_BRAGA", "name": "Braga",
                       "kingdom_id": "k_iberia", "duchy_id": "d_galicia"}],
        "barony_assignments": {"B_001": "C_BRAGA"},
    })

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            return valid_result

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    queue: asyncio.Queue = asyncio.Queue()
    await research_runner.run_research(
        PROJECT_ID, "claude", queue,
        db_session_factory=session_factory,
    )

    async with session_factory() as session:
        rows = (await session.execute(select(ResearchCache))).scalars().all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert "barony_assignments" in payload
    assert "baronies" not in payload
    assert payload["barony_assignments"] == {"B_001": "C_BRAGA"}
