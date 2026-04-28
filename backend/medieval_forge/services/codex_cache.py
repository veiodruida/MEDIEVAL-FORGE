"""Codex cache helpers (Etapa 9 — quick-260428-l0l).

Cache key: SHA-256 of
  f"{country_qid}:{period_start}:{period_end}:{provider}:{model}:codex:{focus_csv}"

where focus_csv = "" when focus_sections is None else ",".join(sorted(focus_sections)).

Storage: codex_cache SQLite table (created via Alembic 0003 migration / Base.metadata.create_all).
Mirror of research_cache.py — kept as a sibling instead of a generic helper to keep
each pipeline's cache obviously independent (Codex evolves separately from Research).
"""
from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CodexCache


def compute_codex_cache_key(
    country_qid: str,
    period_start: int,
    period_end: int,
    provider: str,
    model: str,
    focus_sections: list[str] | None = None,
) -> str:
    """Return SHA-256 hex of the canonical codex cache key string.

    Key formula (verbatim):
      "{country_qid}:{period_start}:{period_end}:{provider}:{model}:codex:{focus_csv}"
    """
    focus_csv = "" if not focus_sections else ",".join(sorted(focus_sections))
    raw = f"{country_qid}:{period_start}:{period_end}:{provider}:{model}:codex:{focus_csv}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_codex_cached(
    session: AsyncSession, cache_key_hash: str
) -> dict[str, Any] | None:
    """Return cached codex payload for the given key, or None on cache miss."""
    row = await session.get(CodexCache, cache_key_hash)
    return row.payload if row is not None else None


async def set_codex_cached(
    session: AsyncSession,
    cache_key_hash: str,
    payload: dict[str, Any],
    provider: str,
    model: str,
    country_qid: str,
    period_start: int,
    period_end: int,
    focus_sections: list[str] | None = None,
) -> None:
    """Upsert a codex cache entry. Updates payload if key already exists."""
    focus_csv = None if not focus_sections else ",".join(sorted(focus_sections))
    existing = await session.get(CodexCache, cache_key_hash)
    if existing is not None:
        existing.payload = payload
        existing.focus_sections = focus_csv
    else:
        session.add(CodexCache(
            cache_key_hash=cache_key_hash,
            payload=payload,
            provider=provider,
            model=model,
            country_qid=country_qid,
            period_start=period_start,
            period_end=period_end,
            focus_sections=focus_csv,
        ))
    await session.commit()
