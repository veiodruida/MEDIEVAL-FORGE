# services/credential_store.py — D-06 + D-07 step 2 (DB link of Claude auth chain).
# Plaintext payload per Discretion #1; OS-keyring escrow is v3.1 hardening.
#
# REVIEWS fix #8 (2026-05-14, Qwen3): cascade behavior on provider deletion.
# Providers are enum-string-keyed (provider_id TEXT PK), NOT a FK from a
# `providers` table. There is no `providers` table to cascade from.
#
# The ONLY deletion path is delete_credentials(session, provider: str). Deleting
# an llm_credentials row does NOT cascade to ResearchCache rows. Cache rows are
# content-addressable (sha256 cache_key) and outlive credentials by design:
# a user can rotate Claude keys without invalidating prior research payloads.
#
# If a future admin action wants to wipe a provider's cached payloads, it must
# do so explicitly via DELETE FROM research_cache WHERE provider = :provider.
"""DB-backed credential CRUD for LLM providers.

One link of the D-07 Claude auth resolution chain
(CLI -> DB -> ANTHROPIC_API_KEY env -> dialog). This module is step 2 of 4.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LLMCredential


async def get_credentials(session: AsyncSession, provider_id: str) -> dict | None:
    """Read credentials from DB. Returns None if not stored.

    One link in the D-07 chain. For Claude, the full chain (CLI -> DB -> env -> dialog)
    is composed in services/llm/claude.py:_resolve_key (Plan 04). DB is step 2 of 4.
    """
    row = await session.scalar(
        select(LLMCredential).where(LLMCredential.provider_id == provider_id)
    )
    if row is None:
        return None
    return json.loads(row.payload) if isinstance(row.payload, str) else row.payload


async def store_credentials(
    session: AsyncSession, provider_id: str, payload: dict
) -> None:
    """Upsert credentials. Payload stored as plaintext JSON per Discretion #1."""
    existing = await session.scalar(
        select(LLMCredential).where(LLMCredential.provider_id == provider_id)
    )
    if existing:
        existing.payload = payload
        existing.credential_type = payload.get("type", "api_key")
    else:
        session.add(
            LLMCredential(
                provider_id=provider_id,
                credential_type=payload.get("type", "api_key"),
                payload=payload,
            )
        )
    await session.commit()


async def delete_credentials(session: AsyncSession, provider_id: str) -> None:
    """Delete credentials for a provider.

    REVIEWS fix #8: does NOT cascade-delete ResearchCache rows. Cache rows outlive
    credentials by design (content-addressable). To wipe a provider's cached payloads,
    a future admin action must DELETE FROM research_cache WHERE provider = :provider.
    """
    row = await session.scalar(
        select(LLMCredential).where(LLMCredential.provider_id == provider_id)
    )
    if row:
        await session.delete(row)
        await session.commit()


# Back-compat alias for legacy callers that imported `clear_credentials`.
# New code MUST use delete_credentials.
clear_credentials = delete_credentials
