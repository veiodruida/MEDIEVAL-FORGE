"""Research cache helpers (RESEARCH-04, D-23..D-25).

Cache key: SHA-256 of f"{country_qid}:{period_start}:{period_end}:{provider}:{model}"
Storage: research_cache SQLite table (created on app startup via Base.metadata.create_all).
"""
from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ResearchCache


def compute_cache_key(
    country_qid: str,
    period_start: int,
    period_end: int,
    provider: str,
    model: str,
) -> str:
    """Return SHA-256 hex of the canonical cache key string.

    Key formula (verbatim): "{country_qid}:{period_start}:{period_end}:{provider}:{model}"
    """
    raw = f"{country_qid}:{period_start}:{period_end}:{provider}:{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_cached(
    session: AsyncSession, cache_key_hash: str
) -> dict[str, Any] | None:
    """Return cached payload for the given key, or None on cache miss."""
    row = await session.get(ResearchCache, cache_key_hash)
    return row.payload if row is not None else None


async def set_cached(
    session: AsyncSession,
    cache_key_hash: str,
    payload: dict[str, Any],
    provider: str,
    model: str,
    country_qid: str,
    period_start: int,
    period_end: int,
) -> None:
    """Upsert a cache entry. Updates payload if key already exists."""
    existing = await session.get(ResearchCache, cache_key_hash)
    if existing is not None:
        existing.payload = payload
    else:
        session.add(ResearchCache(
            cache_key_hash=cache_key_hash,
            payload=payload,
            provider=provider,
            model=model,
            country_qid=country_qid,
            period_start=period_start,
            period_end=period_end,
        ))
    await session.commit()
