"""Unit tests for services.credential_store (Phase 07 D-06 + D-07 step 2).

Each test uses explicit dict literals (no hidden-fixture magic) per project
memory feedback-tests-descriptive. The session fixture comes from the
backend/tests/conftest.py async in-memory SQLite engine.

Test 5 enforces REVIEWS fix #8: deleting an llm_credentials row does NOT
cascade to ResearchCache (cache rows are content-addressable, outlive keys).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from medieval_forge.models import ResearchCache
from medieval_forge.services.credential_store import (
    delete_credentials,
    get_credentials,
    store_credentials,
)

pytestmark = pytest.mark.unit


async def test_store_then_get_round_trips_payload_for_claude(db_session):
    await store_credentials(
        db_session, "claude", {"key": "sk-ant-test", "type": "api_key"}
    )
    result = await get_credentials(db_session, "claude")
    assert result == {"key": "sk-ant-test", "type": "api_key"}


async def test_get_credentials_returns_none_when_provider_absent(db_session):
    result = await get_credentials(db_session, "claude")
    assert result is None


async def test_delete_credentials_deletes_row(db_session):
    await store_credentials(
        db_session, "claude", {"key": "sk-ant-test", "type": "api_key"}
    )
    assert (await get_credentials(db_session, "claude")) is not None
    await delete_credentials(db_session, "claude")
    assert (await get_credentials(db_session, "claude")) is None


async def test_store_credentials_upserts_existing_row(db_session):
    await store_credentials(
        db_session, "claude", {"key": "sk-ant-FIRST", "type": "api_key"}
    )
    await store_credentials(
        db_session, "claude", {"key": "sk-ant-SECOND", "type": "api_key"}
    )
    result = await get_credentials(db_session, "claude")
    assert result == {"key": "sk-ant-SECOND", "type": "api_key"}


async def test_delete_credentials_does_not_cascade_to_research_cache(db_session):
    """REVIEWS fix #8: cache outlives credentials (content-addressable)."""
    # Seed both rows
    await store_credentials(
        db_session, "claude", {"key": "sk-ant-test", "type": "api_key"}
    )
    cache_key = "abc123" + "0" * 58  # 64 hex chars
    db_session.add(
        ResearchCache(
            cache_key=cache_key,
            payload={"condados": [{"id": "oviedo", "name": "Oviedo"}]},
            provider="claude",
            model="claude-sonnet-4-6",
            generated_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    # Delete credentials
    await delete_credentials(db_session, "claude")

    # Credentials are gone
    assert (await get_credentials(db_session, "claude")) is None

    # ResearchCache row STILL exists with unchanged payload (no cascade)
    row = await db_session.scalar(
        select(ResearchCache).where(ResearchCache.cache_key == cache_key)
    )
    assert row is not None
    assert row.payload == {"condados": [{"id": "oviedo", "name": "Oviedo"}]}
    assert row.provider == "claude"
    assert row.model == "claude-sonnet-4-6"
