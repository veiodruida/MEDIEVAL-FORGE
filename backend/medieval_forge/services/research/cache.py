"""SQLite-backed research cache (D-11).

Key derivation per RESEARCH §Example 2 + §Pitfall 6 + REVIEWS fix #4: canonical
form is
``{country_qid_lower}|{period_start}|{period_end}|{provider}|{model}|{PROMPT_DIGEST}|{SCHEMA_VERSION}|{condado_ids_digest}``.
SHA-256 hex digest gives a fixed-width 64-char key.

D-04 (Phase 07.1): period_start/end integers replace the v0.5 string period component.
Cache rows from the pre-Phase-07.1 schema are truncated by Alembic 0007 (D-04 forward-only).

REVIEWS fix #2: row column is ``generated_at`` (the original LLM-output
timestamp). Plan 07b reads this and copies it into
``research_overlay.meta.json::generated_at``; the runner-write timestamp lives
in ``research_overlay.meta.json::applied_at`` instead.

REVIEWS fix #4 Codex: cache key includes ``condado_ids_digest`` so two regions
sharing country + period but different condado lists DO NOT share cached
payloads.

REVIEWS fix #4 Qwen3: cache key includes ``SCHEMA_VERSION`` constant. Bump on
semantic changes to cached fields (e.g., if ``historical_notes`` semantics
change). Forces a cache miss for all rows at the previous schema version.

REVIEWS soft Codex: ``PROMPT_DIGEST`` replaces manual ``PROMPT_VERSION``
discipline. It is a sha256 of the literal-port prompt.py template, computed at
import time. Any edit to the template auto-invalidates the cache.

REVIEWS fix #8 Qwen3: cache rows outlive credential rows. Deleting an
``LLMCredential`` row does NOT cascade-delete ``ResearchCache`` rows. The cache
key is provider-string-keyed (not FK-keyed), so cache hits work even after
credentials are rotated.

Re-ingestion does NOT invalidate the cache (D-24 carried from v1). The
force-refresh checkbox in the UI dialog bypasses cache by calling
``cache_put`` with the new payload regardless of a pre-existing hit.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...services.llm.prompt import PROMPT_TEMPLATE  # literal-port source (Plan 03)
from ...models import ResearchCache as ResearchCacheModel

# REVIEWS soft Codex — PROMPT_DIGEST replaces manual PROMPT_VERSION.
# Computed at import time from the literal-port prompt template; any edit forces
# a cache miss. 8-hex-char prefix is enough to disambiguate prompt revisions
# while keeping the canonical form short.
PROMPT_DIGEST: str = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()[:8]

# REVIEWS fix #4 Qwen3 — bump on semantic changes to cached fields (e.g.,
# historical_notes contract change, new required field). Forces cache miss for
# all rows at the previous schema version.
SCHEMA_VERSION: int = 1

# Back-compat alias for legacy callers / tests still expecting PROMPT_VERSION.
# New code MUST use PROMPT_DIGEST directly. Remove this alias in v3.1.
PROMPT_VERSION: str = PROMPT_DIGEST


def _condado_ids_digest(condado_ids: list[str]) -> str:
    """REVIEWS fix #4 Codex — order-insensitive hash of the condado-id list.

    Sorting guarantees Iberia 868 with ``{oviedo, leon}`` and
    ``{leon, oviedo}`` share a key. Truncated to 16 hex chars to keep the
    canonical form short.
    """
    joined = ",".join(sorted(condado_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def cache_key(
    country_qid: str,
    period_start: int,
    period_end: int,
    provider: str,
    model: str,
    condado_ids: list[str],
    prompt_digest: str = PROMPT_DIGEST,
    schema_version: int = SCHEMA_VERSION,
) -> str:
    """Derive a deterministic SHA-256 cache key.

    8 components: country_qid + period_start + period_end + provider + model + prompt_digest
    + schema_version + condado_ids_digest. Normalizes country_qid to lowercase + stripped
    (Pitfall 6). Provider + model case preserved (some Ollama tags are case-sensitive,
    e.g. ``llama3.1:8b`` vs. ``Llama3.1:8b``).

    D-04 (Phase 07.1): period_start/end integers replace the v0.5 string period component.
    Cache rows from the pre-Phase-07.1 schema are truncated by Alembic 0007 (D-04 forward-only).
    """
    canonical = (
        f"{country_qid.strip().lower()}|"
        f"{period_start}|{period_end}|"
        f"{provider}|"
        f"{model}|"
        f"{prompt_digest}|"
        f"{schema_version}|"
        f"{_condado_ids_digest(condado_ids)}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def cache_get(session: AsyncSession, key: str) -> dict | None:
    """Read a cached payload by key. Returns None on miss."""
    row = await session.scalar(
        select(ResearchCacheModel).where(ResearchCacheModel.cache_key == key)
    )
    if row is None:
        return None
    return json.loads(row.payload) if isinstance(row.payload, str) else row.payload


async def cache_get_with_generated_at(
    session: AsyncSession, key: str
) -> tuple[dict, datetime] | None:
    """REVIEWS fix #2 — used by Plan 07b runner to populate
    ``research_overlay.meta.json::generated_at`` on the cache-hit path.
    Returns None on miss; otherwise ``(payload, generated_at)``.
    """
    row = await session.scalar(
        select(ResearchCacheModel).where(ResearchCacheModel.cache_key == key)
    )
    if row is None:
        return None
    payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
    return payload, row.generated_at


async def cache_put(
    session: AsyncSession,
    key: str,
    payload: dict,
    provider: str,
    model: str,
) -> None:
    """Upsert a cached payload by key.

    Force-refresh path: the runner calls ``cache_put`` with the latest payload;
    if a row exists it is overwritten (provider + model updated; generated_at
    is NOT auto-bumped on overwrite — the runner explicitly assigns it when
    semantically meaningful).
    """
    existing = await session.scalar(
        select(ResearchCacheModel).where(ResearchCacheModel.cache_key == key)
    )
    if existing:
        existing.payload = payload
        existing.provider = provider
        existing.model = model
        # generated_at NOT updated on overwrite: force-refresh resets the
        # generation timestamp via explicit assignment in the runner path
        # (Plan 07b). Leaving it alone preserves the original-generation
        # semantics on no-op rewrites.
    else:
        session.add(
            ResearchCacheModel(
                cache_key=key,
                payload=payload,
                provider=provider,
                model=model,
            )
        )
    await session.commit()
