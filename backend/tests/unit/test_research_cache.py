"""Tests for research cache helpers (RESEARCH-04).

Wave 0 test scaffolding — tests define the contract; implementation comes in Task 2.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def in_memory_session():
    """Provide an async SQLAlchemy session backed by in-memory SQLite."""
    from medieval_forge.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_compute_cache_key_deterministic():
    """Same args → same SHA-256 hex; different provider → different key."""
    from medieval_forge.services.research_cache import compute_cache_key

    k1 = compute_cache_key("Q29", 868, 900, "claude", "claude-sonnet-4-6")
    k2 = compute_cache_key("Q29", 868, 900, "claude", "claude-sonnet-4-6")
    assert k1 == k2
    assert len(k1) == 64  # SHA-256 hex is 64 chars

    k_other = compute_cache_key("Q29", 868, 900, "openai", "gpt-4o")
    assert k1 != k_other


async def test_get_cached_returns_none_for_missing_key(in_memory_session):
    """Cache miss returns None."""
    from medieval_forge.services.research_cache import get_cached

    result = await get_cached(in_memory_session, "nonexistent-key-hash")
    assert result is None


async def test_set_then_get_cached_round_trips(in_memory_session):
    """set_cached then get_cached returns the same payload."""
    from medieval_forge.services.research_cache import (
        compute_cache_key,
        get_cached,
        set_cached,
    )

    key = compute_cache_key("Q29", 868, 900, "claude", "claude-sonnet-4-6")
    payload = {"kingdoms": {"k1": "Leon"}, "duchies": {}, "condados_assignment": [], "baronies": {}}

    await set_cached(
        in_memory_session, key, payload,
        provider="claude", model="claude-sonnet-4-6",
        country_qid="Q29", period_start=868, period_end=900,
    )

    result = await get_cached(in_memory_session, key)
    assert result == payload


def test_cache_key_changes_per_provider_and_model():
    """Distinct keys for different (provider, model) combos."""
    from medieval_forge.services.research_cache import compute_cache_key

    k_claude_sonnet = compute_cache_key("Q29", 868, 900, "claude", "claude-sonnet-4-6")
    k_claude_gpt = compute_cache_key("Q29", 868, 900, "claude", "gpt-4o")
    k_openai_gpt = compute_cache_key("Q29", 868, 900, "openai", "gpt-4o")

    assert k_claude_sonnet != k_claude_gpt
    assert k_claude_gpt != k_openai_gpt
    assert k_claude_sonnet != k_openai_gpt
