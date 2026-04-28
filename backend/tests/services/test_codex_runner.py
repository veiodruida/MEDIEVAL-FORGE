"""Etapa 9 (master plan H.9 / quick-260428-l0l): codex_runner SSE producer.

run_codex mirrors run_research:
  - validate provider
  - load project
  - cache lookup (unless force_refresh)
  - call provider.research(prompt, CodexResult, ...) via run_with_retry
  - emit "starting" + RESULT + DONE on success
  - ALWAYS terminate the queue with None (Pitfall 6)
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.models import Base, Project


PROJECT_ID = "abcdabcd-abcd-4abc-8abc-aaaaaaaaaaaa"


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


async def _seed_project(factory) -> None:
    async with factory() as session:
        session.add(Project(
            id=PROJECT_ID,
            name="Iberia",
            country_qid="Q29",
            period_start=868,
            period_end=1100,
            status="generated",
        ))
        await session.commit()


def _drain_queue(queue: asyncio.Queue) -> tuple[list[str], bool]:
    """Drain a queue into (messages_list, saw_none_sentinel)."""
    out: list[str] = []
    saw_none = False
    while True:
        try:
            item = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if item is None:
            saw_none = True
            break
        out.append(item)
    return out, saw_none


def _empty_codex_payload() -> dict:
    cats = ("currency", "attributes", "health", "traits", "feudal", "politics",
            "dynasty", "religion", "culture", "economy", "military", "events")
    return {c: {"summary": "", "entries": []} for c in cats}


def _payload_with_summary(summary: str) -> dict:
    p = _empty_codex_payload()
    p["currency"]["summary"] = summary
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_codex_emits_starting_then_result_then_done_on_happy_path(
    session_factory, monkeypatch,
):
    """Stub provider returns a 12-category CodexResult → starting + RESULT + DONE + None."""
    from medieval_forge.services import codex_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.llm.schemas import CodexResult

    await _seed_project(session_factory)

    valid_result = CodexResult.model_validate(_payload_with_summary("happy-path"))

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            return valid_result

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    # Provide credentials via app_state stub so resolve_credentials succeeds.
    class _AppState:
        credentials = {"claude": {"api_key": "test-key"}}

    queue: asyncio.Queue = asyncio.Queue()
    await codex_runner.run_codex(
        PROJECT_ID, "claude", queue,
        db_session_factory=session_factory,
        app_state=_AppState(),
    )

    msgs, saw_none = _drain_queue(queue)
    body = "\n".join(msgs)
    assert "starting claude" in body
    assert "RESULT" in body
    assert "happy-path" in body
    assert "DONE" in body
    assert saw_none, "queue must terminate with None sentinel"


@pytest.mark.asyncio
async def test_run_codex_returns_cached_payload_without_calling_provider_when_cache_hit(
    session_factory, monkeypatch,
):
    """Cache pre-populated → provider.research NEVER called; emits cached + RESULT + DONE."""
    from medieval_forge.services import codex_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.codex_cache import compute_codex_cache_key, set_codex_cached

    await _seed_project(session_factory)

    pre_cached_payload = _payload_with_summary("pre-cached")
    # Default codex routing for claude → high tier → "claude-opus-4-7".
    expected_model = "claude-opus-4-7"
    key = compute_codex_cache_key("Q29", 868, 1100, "claude", expected_model)
    async with session_factory() as session:
        await set_codex_cached(
            session, key, pre_cached_payload, "claude", expected_model,
            "Q29", 868, 1100,
        )

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            raise AssertionError("provider.research must NOT be called on cache hit")

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    queue: asyncio.Queue = asyncio.Queue()
    await codex_runner.run_codex(
        PROJECT_ID, "claude", queue,
        db_session_factory=session_factory,
    )

    msgs, saw_none = _drain_queue(queue)
    body = "\n".join(msgs)
    assert "cached" in body
    assert "pre-cached" in body
    assert "DONE" in body
    assert saw_none


@pytest.mark.asyncio
async def test_run_codex_force_refresh_bypasses_cache(
    session_factory, monkeypatch,
):
    """force_refresh=True → provider.research IS called; payload is fresh, not stale cache."""
    from medieval_forge.services import codex_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.llm.schemas import CodexResult
    from medieval_forge.services.codex_cache import compute_codex_cache_key, set_codex_cached

    await _seed_project(session_factory)

    expected_model = "claude-opus-4-7"
    stale_payload = _payload_with_summary("stale-pre-cached")
    key = compute_codex_cache_key("Q29", 868, 1100, "claude", expected_model)
    async with session_factory() as session:
        await set_codex_cached(
            session, key, stale_payload, "claude", expected_model,
            "Q29", 868, 1100,
        )

    fresh_result = CodexResult.model_validate(_payload_with_summary("fresh-result"))
    call_count = {"n": 0}

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            call_count["n"] += 1
            return fresh_result

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    class _AppState:
        credentials = {"claude": {"api_key": "test-key"}}

    queue: asyncio.Queue = asyncio.Queue()
    await codex_runner.run_codex(
        PROJECT_ID, "claude", queue,
        force_refresh=True,
        db_session_factory=session_factory,
        app_state=_AppState(),
    )

    assert call_count["n"] == 1, "provider.research must run exactly once on force_refresh"
    msgs, saw_none = _drain_queue(queue)
    body = "\n".join(msgs)
    assert "fresh-result" in body
    assert "stale-pre-cached" not in body
    assert saw_none


@pytest.mark.asyncio
async def test_run_codex_emits_error_and_sentinel_on_unknown_provider(session_factory):
    """provider_id='nonexistent' → single ERROR message followed by None sentinel."""
    from medieval_forge.services import codex_runner

    queue: asyncio.Queue = asyncio.Queue()
    await codex_runner.run_codex(
        PROJECT_ID, "nonexistent", queue,
        db_session_factory=session_factory,
    )

    msgs, saw_none = _drain_queue(queue)
    body = "\n".join(msgs)
    assert "ERROR" in body
    assert "nonexistent" in body
    assert saw_none, "queue must terminate with None even on error"


@pytest.mark.asyncio
async def test_run_codex_terminates_with_none_sentinel_even_on_internal_exception(
    session_factory, monkeypatch,
):
    """Provider raises RuntimeError('boom') → ERROR emitted; queue STILL ends with None."""
    from medieval_forge.services import codex_runner
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus

    await _seed_project(session_factory)

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = PROVIDERS["claude"].auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            raise RuntimeError("boom")

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    class _AppState:
        credentials = {"claude": {"api_key": "test-key"}}

    queue: asyncio.Queue = asyncio.Queue()
    await codex_runner.run_codex(
        PROJECT_ID, "claude", queue,
        db_session_factory=session_factory,
        app_state=_AppState(),
    )

    msgs, saw_none = _drain_queue(queue)
    body = "\n".join(msgs)
    assert "ERROR" in body
    assert saw_none, "Pitfall 6: queue MUST terminate with None even on RuntimeError"
