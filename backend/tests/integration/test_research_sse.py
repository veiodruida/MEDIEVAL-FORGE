"""Wave 0 gate — services.research.runner SSE orchestrator (Plan 07-07b Task 1).

Eight TDD cases:
1. SSE stream emits 4 stage events (kingdoms / duchies / condados / baronies).
2. Single-flight gate — second start_research for same project returns 409.
3. /stop aborts in-flight run + evicts queue (WR-02 / Pitfall 7).
4. Cache-hit short-circuits provider.research (D-11).
5. research_overlay.json written atomically via tmp+replace (Pitfall 1).
6. research_overlay.meta.json sidecar carries provider/model/timestamps
   (BLOCKER 2, REVIEWS fix #2).
7. REVIEWS fix #2 — fresh-run: meta.generated_at == meta.applied_at.
8. REVIEWS fix #2 — cache-hit: meta.generated_at < meta.applied_at (loaded
   from cache row).

Mocking strategy: replace PROVIDERS[provider_id] entry with a stub object whose
`research()` returns a HIERARCHICAL dict shape (kingdoms list with nested
duchies + condados), matching `matcher.llm_output_to_overlay`'s contract. We
SKIP the schemas.MapResearchResult round-trip because the matcher consumes the
hierarchical dict directly (provider returns Pydantic in real life — Plan 09b
will normalize via .model_dump() + flat→hierarchical adapter; out of scope
here).
"""
from __future__ import annotations

import asyncio
import json
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from medieval_forge.models import ResearchCache
from medieval_forge.services import paths as paths_module
from medieval_forge.services.research.cache import (
    PROMPT_DIGEST,
    SCHEMA_VERSION,
    cache_key,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def tmp_project_dir(monkeypatch, tmp_path):
    """Monkeypatch PROJECTS_ROOT and return (project_id, project_dir Path)."""
    monkeypatch.setattr(paths_module, "PROJECTS_ROOT", tmp_path / "projects")
    pid = str(_uuid.uuid4())
    pdir = paths_module.project_dir(pid)
    return pid, pdir


@pytest.fixture
def hierarchical_payload():
    """Hierarchical LLM-output dict consumed by matcher.llm_output_to_overlay."""
    return {
        "kingdoms": [
            {
                "name": "Reino de Leon",
                "duchies": [
                    {
                        "name": "Leon",
                        "condados": [
                            {
                                "id": "C_LEON",
                                "name": "Condado de Leon",
                                "historical_notes": "Capital do reino.",
                            },
                            {
                                "id": "C_OVIEDO",
                                "name": "Condado de Oviedo",
                                "historical_notes": "Sede do bispado.",
                            },
                        ],
                    }
                ],
            }
        ]
    }


@pytest.fixture
def condado_ids():
    return ["C_LEON", "C_OVIEDO"]


def _make_stub_provider(payload, sleep_seconds: float = 0.0, fail: bool = False):
    """Build a stub LLMProvider whose research() returns `payload` after optional sleep."""

    class _Stub:
        provider_id = "stub"
        display_name = "Stub"
        auth_methods = []
        called = 0

        async def health_check(self, credentials):
            from medieval_forge.services.llm.base import HealthStatus

            return HealthStatus(healthy=True, message="stub")

        async def research(self, prompt, schema, credentials, queue):
            type(self).called += 1
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
            if fail:
                raise RuntimeError("stub failure")
            return payload

    stub = _Stub()
    return stub


def _patch_providers(monkeypatch, stub):
    from medieval_forge.services.llm import registry as llm_registry

    monkeypatch.setitem(llm_registry.PROVIDERS, "stub", stub)


async def _drain_queue(queue, timeout: float = 5.0):
    """Drain SSE queue until terminal None sentinel; return list of payload dicts."""
    events = []
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise asyncio.TimeoutError("queue drain timeout")
        msg = await asyncio.wait_for(queue.get(), timeout=remaining)
        if msg is None:
            break
        # SSE frames are "data: <json>\n\n"
        if isinstance(msg, str) and msg.startswith("data: "):
            payload = msg[len("data: "):].rstrip("\n\n")
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                events.append({"raw": payload})
        else:
            events.append({"raw": msg})
    return events


# ---------------------------------------------------------------------------
# Test 1 — 4 stage events
# ---------------------------------------------------------------------------
async def test_research_stream_emits_4_stage_events_kingdoms_duchies_condados_baronies(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.runner import (
        _RUN_QUEUES,
        get_stream,
        start_research,
    )

    stub = _make_stub_provider(hierarchical_payload)
    _patch_providers(monkeypatch, stub)

    project_id, pdir = tmp_project_dir

    await start_research(
        project_id=project_id,
        provider="stub",
        model="stub-model",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    queue = _RUN_QUEUES[project_id]
    events = await _drain_queue(queue)

    stages_seen = [e.get("stage") for e in events if e.get("event_type") == "stage_done"]
    assert "kingdoms" in stages_seen
    assert "duchies" in stages_seen
    assert "condados" in stages_seen
    assert "baronies" in stages_seen


# ---------------------------------------------------------------------------
# Test 2 — single-flight 409 gate
# ---------------------------------------------------------------------------
async def test_research_stream_returns_409_when_run_already_in_flight_for_project(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.runner import (
        SingleFlightError,
        start_research,
    )

    # First run takes long enough for second start_research to see it alive
    stub = _make_stub_provider(hierarchical_payload, sleep_seconds=0.5)
    _patch_providers(monkeypatch, stub)

    project_id, _ = tmp_project_dir

    await start_research(
        project_id=project_id,
        provider="stub",
        model="m",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    with pytest.raises(SingleFlightError):
        await start_research(
            project_id=project_id,
            provider="stub",
            model="m",
            country_qid="Q29",
            period_label="868 AD",
            condado_ids=condado_ids,
            force_refresh=False,
            session_factory=lambda: db_session,
        )


# ---------------------------------------------------------------------------
# Test 3 — /stop aborts + evicts queue (WR-02)
# ---------------------------------------------------------------------------
async def test_research_stop_aborts_in_flight_run_and_evicts_queue(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.runner import (
        _RUN_QUEUES,
        _RUN_TASKS,
        start_research,
        stop_research,
    )

    stub = _make_stub_provider(hierarchical_payload, sleep_seconds=2.0)
    _patch_providers(monkeypatch, stub)

    project_id, _ = tmp_project_dir
    await start_research(
        project_id=project_id,
        provider="stub",
        model="m",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    assert project_id in _RUN_QUEUES
    # Allow the runner to start and produce at least one event
    await asyncio.sleep(0.05)
    aborted = await stop_research(project_id)
    assert aborted is True
    # Drain queue & await task completion
    queue = _RUN_QUEUES.get(project_id)
    if queue is not None:
        try:
            await asyncio.wait_for(_drain_queue(queue, timeout=3.0), timeout=3.0)
        except asyncio.TimeoutError:
            pass
    task = _RUN_TASKS.get(project_id)
    if task is not None:
        try:
            await asyncio.wait_for(task, timeout=3.0)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass

    # WR-02: after finally-block, both maps evicted
    assert project_id not in _RUN_QUEUES
    assert project_id not in _RUN_TASKS


# ---------------------------------------------------------------------------
# Test 4 — cache hit short-circuits provider
# ---------------------------------------------------------------------------
async def test_research_cache_hit_short_circuits_provider_call(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.cache import cache_put
    from medieval_forge.services.research.runner import (
        _RUN_QUEUES,
        start_research,
    )

    # Seed cache row
    ck = cache_key(
        "Q29",
        "868 AD",
        "stub",
        "stub-model",
        condado_ids=condado_ids,
    )
    await cache_put(
        db_session, ck, hierarchical_payload, provider="stub", model="stub-model"
    )

    stub = _make_stub_provider(hierarchical_payload)
    _patch_providers(monkeypatch, stub)
    type(stub).called = 0

    project_id, _ = tmp_project_dir
    await start_research(
        project_id=project_id,
        provider="stub",
        model="stub-model",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    queue = _RUN_QUEUES[project_id]
    await _drain_queue(queue)

    assert type(stub).called == 0, "Provider must NOT be called on cache hit"


# ---------------------------------------------------------------------------
# Test 5 — atomic overlay write via tmp+replace
# ---------------------------------------------------------------------------
async def test_research_overlay_written_atomically_via_tmp_replace(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.runner import (
        _RUN_QUEUES,
        _write_json_atomic,
        start_research,
    )

    # Spy on the atomic writer to assert it was used.
    call_log: list[Path] = []
    real_writer = _write_json_atomic

    def spy(path, data):
        call_log.append(Path(path))
        return real_writer(path, data)

    # Patch via module attribute so the runner picks up the spy
    monkeypatch.setattr(
        "medieval_forge.services.research.runner._write_json_atomic", spy
    )

    stub = _make_stub_provider(hierarchical_payload)
    _patch_providers(monkeypatch, stub)

    project_id, pdir = tmp_project_dir
    await start_research(
        project_id=project_id,
        provider="stub",
        model="stub-model",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    queue = _RUN_QUEUES[project_id]
    await _drain_queue(queue)

    overlay_path = pdir / "research_overlay.json"
    assert overlay_path.exists()
    # Overlay loads back as the matcher-shape dict
    data = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert "C_LEON" in data
    assert data["C_LEON"]["kingdom_owner"] == "Reino de Leon"

    # _write_json_atomic was called for both overlay AND meta (Test 6 verifies file)
    assert any(p.name == "research_overlay.json" for p in call_log)


# ---------------------------------------------------------------------------
# Test 6 — meta sidecar with provider/model/timestamps (BLOCKER 2)
# ---------------------------------------------------------------------------
async def test_research_overlay_meta_sidecar_written_with_provider_model_timestamps(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.runner import (
        _RUN_QUEUES,
        start_research,
    )

    stub = _make_stub_provider(hierarchical_payload)
    _patch_providers(monkeypatch, stub)

    project_id, pdir = tmp_project_dir
    await start_research(
        project_id=project_id,
        provider="stub",
        model="stub-model",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    queue = _RUN_QUEUES[project_id]
    await _drain_queue(queue)

    meta_path = pdir / "research_overlay.meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    for k in (
        "provider",
        "model",
        "generated_at",
        "applied_at",
        "prompt_digest",
        "schema_version",
        "country",
        "period",
    ):
        assert k in meta, f"meta sidecar missing key {k!r}: {meta}"

    assert meta["provider"] == "stub"
    assert meta["model"] == "stub-model"
    assert meta["country"] == "Q29"
    assert meta["period"] == "868 AD"
    assert meta["prompt_digest"] == PROMPT_DIGEST
    assert meta["schema_version"] == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Test 7 — REVIEWS fix #2: fresh-run path, generated_at == applied_at
# ---------------------------------------------------------------------------
async def test_meta_sidecar_generated_at_equals_applied_at_on_fresh_run(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.runner import (
        _RUN_QUEUES,
        start_research,
    )

    stub = _make_stub_provider(hierarchical_payload)
    _patch_providers(monkeypatch, stub)

    project_id, pdir = tmp_project_dir
    await start_research(
        project_id=project_id,
        provider="stub",
        model="stub-model",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    queue = _RUN_QUEUES[project_id]
    await _drain_queue(queue)

    meta = json.loads((pdir / "research_overlay.meta.json").read_text())
    # Fresh run: both timestamps are the same (the runner-write moment).
    assert meta["generated_at"] == meta["applied_at"]


# ---------------------------------------------------------------------------
# Test 8 — REVIEWS fix #2: cache-hit path, generated_at < applied_at
# ---------------------------------------------------------------------------
async def test_meta_sidecar_generated_at_predates_applied_at_on_cache_hit(
    monkeypatch, tmp_project_dir, hierarchical_payload, condado_ids, db_session
):
    from medieval_forge.services.research.cache import cache_put
    from medieval_forge.services.research.runner import (
        _RUN_QUEUES,
        start_research,
    )

    # Seed cache row directly with a backdated generated_at.
    ck = cache_key(
        "Q29",
        "868 AD",
        "stub",
        "stub-model",
        condado_ids=condado_ids,
    )
    await cache_put(
        db_session, ck, hierarchical_payload, provider="stub", model="stub-model"
    )
    # Backdate the row's generated_at to 2026-05-01 12:00:00 UTC
    t0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    row = await db_session.scalar(
        select(ResearchCache).where(ResearchCache.cache_key == ck)
    )
    assert row is not None
    # SQLAlchemy DateTime column may be naive on SQLite — store naive UTC.
    row.generated_at = t0.replace(tzinfo=None)
    await db_session.commit()

    stub = _make_stub_provider(hierarchical_payload)
    _patch_providers(monkeypatch, stub)

    project_id, pdir = tmp_project_dir
    await start_research(
        project_id=project_id,
        provider="stub",
        model="stub-model",
        country_qid="Q29",
        period_label="868 AD",
        condado_ids=condado_ids,
        force_refresh=False,
        session_factory=lambda: db_session,
    )
    queue = _RUN_QUEUES[project_id]
    await _drain_queue(queue)

    meta = json.loads((pdir / "research_overlay.meta.json").read_text())
    # The cache-hit path propagates generated_at from the DB row (T0)
    # while applied_at is the runner-write moment (T1 > T0).
    assert meta["generated_at"] == "2026-05-01T12:00:00+00:00"
    assert meta["generated_at"] != meta["applied_at"]
    assert meta["applied_at"] > meta["generated_at"]
