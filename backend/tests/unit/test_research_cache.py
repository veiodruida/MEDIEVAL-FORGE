"""Unit tests for services.research.cache (Phase 07 Plan 07a, D-11).

Each test uses explicit dict literals (no hidden-fixture magic) per project
memory feedback-tests-descriptive. The db_session fixture comes from the
backend/tests/conftest.py async in-memory SQLite engine.

REVIEWS replan 2026-05-14 deltas exercised by this file:
- fix #2 — `generated_at` column (renamed from `created_at`)
- fix #4 Codex — `condado_ids_digest` in cache key (geometry-aware miss)
- fix #4 Qwen3 — `SCHEMA_VERSION` in cache key (migration-aware miss)
- fix #8 Qwen3 — cache outlives credentials (no FK cascade)
- soft Codex — `PROMPT_DIGEST` replaces manual `PROMPT_VERSION`
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from medieval_forge.models import ResearchCache
from medieval_forge.services.credential_store import (
    delete_credentials,
    store_credentials,
)
from medieval_forge.services.research.cache import (
    PROMPT_DIGEST,
    SCHEMA_VERSION,
    cache_get,
    cache_get_with_generated_at,
    cache_key,
    cache_put,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test 1 — Pitfall 6: canonical strip+lower on country_qid;
#                     condado_ids order-insensitive via sorted-then-hashed
#                     D-04 (Phase 07.1): period is now int start+end, no case normalization needed.
# ---------------------------------------------------------------------------
async def test_cache_key_sha256_normalizes_case_and_whitespace():
    key_a = cache_key(
        "Q29",
        868,
        1000,
        "Claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    key_b = cache_key(
        "q29",
        868,
        1000,
        "Claude",
        "claude-sonnet-4-6",
        condado_ids=["leon", "oviedo"],
    )
    assert key_a == key_b

    # Also strip whitespace on country_qid
    key_c = cache_key(
        "  Q29 ",
        868,
        1000,
        "Claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    assert key_a == key_c


# ---------------------------------------------------------------------------
# Test 2 — Pure SHA-256 hex digest contract (64 chars)
# ---------------------------------------------------------------------------
async def test_cache_key_returns_64_char_hex_string():
    key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    assert len(key) == 64
    int(key, 16)  # must parse as hex; raises ValueError otherwise


# ---------------------------------------------------------------------------
# Test 3 — REVIEWS soft Codex: prompt-template edit auto-invalidates the cache
# ---------------------------------------------------------------------------
async def test_cache_key_includes_prompt_digest_so_prompt_template_edit_invalidates():
    base = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
        prompt_digest=PROMPT_DIGEST,
    )
    bumped = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
        prompt_digest="deadbeef",
    )
    assert base != bumped


# ---------------------------------------------------------------------------
# Test 4 — REVIEWS fix #4 Codex: condado_ids change ⇒ different key
# (prevents stale cache reuse across incompatible region geometries)
# ---------------------------------------------------------------------------
async def test_cache_key_differs_when_condado_ids_differ_even_with_same_country_and_period():
    iberia_north = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon", "burgos"],
    )
    iberia_south = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["sevilla", "cordoba"],
    )
    assert iberia_north != iberia_south


# ---------------------------------------------------------------------------
# Test 5 — REVIEWS fix #4 Qwen3: SCHEMA_VERSION bump forces miss
# ---------------------------------------------------------------------------
async def test_cache_key_includes_schema_version_to_force_miss_on_schema_migration():
    v1_key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
        schema_version=1,
    )
    v2_key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
        schema_version=2,
    )
    assert v1_key != v2_key
    # Sanity: the default SCHEMA_VERSION constant matches v1
    default_key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    assert default_key == v1_key
    assert SCHEMA_VERSION == 1


# ---------------------------------------------------------------------------
# Test 6 — Hit path: stored payload returns intact
# ---------------------------------------------------------------------------
async def test_cache_hit_returns_payload_without_calling_provider(db_session):
    key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    payload = {
        "kingdoms": {"K_LEON": "Reino de Leon"},
        "condados": [{"id": "C_OVIEDO", "name": "Condado de Oviedo"}],
    }
    await cache_put(
        db_session, key, payload, provider="claude", model="claude-sonnet-4-6"
    )

    result = await cache_get(db_session, key)
    assert result == payload


# ---------------------------------------------------------------------------
# Test 7 — Force-refresh: second cache_put overwrites first
# ---------------------------------------------------------------------------
async def test_force_refresh_overwrites_cache_entry_on_success(db_session):
    key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    first = {"condados": [{"id": "C_OLD", "name": "Old"}]}
    second = {"condados": [{"id": "C_NEW", "name": "New"}]}

    await cache_put(db_session, key, first, provider="claude", model="claude-sonnet-4-6")
    await cache_put(db_session, key, second, provider="claude", model="claude-sonnet-4-6")

    result = await cache_get(db_session, key)
    assert result == second
    assert result != first


# ---------------------------------------------------------------------------
# Test 8 — Miss path on fresh DB returns None
# ---------------------------------------------------------------------------
async def test_cache_miss_returns_none_for_unknown_key(db_session):
    result = await cache_get(db_session, "0" * 64)
    assert result is None


# ---------------------------------------------------------------------------
# Test 9 — REVIEWS fix #2: row exposes `generated_at` (not `created_at`)
# ---------------------------------------------------------------------------
async def test_research_cache_row_uses_generated_at_column_not_created_at(db_session):
    key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    payload = {"condados": [{"id": "C_OVIEDO", "name": "Oviedo"}]}
    await cache_put(
        db_session, key, payload, provider="claude", model="claude-sonnet-4-6"
    )

    row = await db_session.scalar(
        select(ResearchCache).where(ResearchCache.cache_key == key)
    )
    assert row is not None
    assert hasattr(row, "generated_at")
    assert isinstance(row.generated_at, datetime)
    # Defensive: the legacy `created_at` attribute MUST NOT exist on this model.
    assert not hasattr(row, "created_at")

    # cache_get_with_generated_at returns (payload, generated_at) tuple
    got = await cache_get_with_generated_at(db_session, key)
    assert got is not None
    got_payload, got_dt = got
    assert got_payload == payload
    assert isinstance(got_dt, datetime)
    assert got_dt == row.generated_at


# ---------------------------------------------------------------------------
# Test 10 — REVIEWS fix #8 Qwen3: cache outlives credentials
# ---------------------------------------------------------------------------
async def test_cache_row_outlives_credential_row_deletion(db_session):
    # Seed credential
    await store_credentials(
        db_session, "claude", {"key": "sk-ant-test", "type": "api_key"}
    )

    # Seed cache row via the real cache_put path
    key = cache_key(
        "Q29",
        868,
        1000,
        "claude",
        "claude-sonnet-4-6",
        condado_ids=["oviedo", "leon"],
    )
    payload = {"condados": [{"id": "oviedo", "name": "Oviedo"}]}
    await cache_put(
        db_session, key, payload, provider="claude", model="claude-sonnet-4-6"
    )

    # Delete the credential
    await delete_credentials(db_session, "claude")

    # Cache STILL returns the payload (no FK cascade)
    result = await cache_get(db_session, key)
    assert result is not None
    assert result == payload
    assert result["condados"][0]["name"] == "Oviedo"
