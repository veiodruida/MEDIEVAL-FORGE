"""Persistent credential store — DB-backed per-provider LLM credentials.

Writes/reads the llm_credentials table. Used by auth endpoints and by the
lifespan preloader to populate app.state.credentials at startup.

Security note: keys are stored in plaintext in the local SQLite file. This is
a deliberate tradeoff for a local single-user tool (user explicitly asked for
persistence across restarts). The DB lives in ~/.medieval-forge/ and is
user-scoped, so this is equivalent to the storage model of tools like gh/git.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LLMCredential


async def load_all(session: AsyncSession) -> dict[str, dict[str, Any]]:
    """Load all persisted credentials, returning the same shape used by
    resolve_credentials() / app.state.credentials.
    """
    result = await session.execute(select(LLMCredential))
    out: dict[str, dict[str, Any]] = {}
    for row in result.scalars().all():
        out[row.provider_id] = _row_to_dict(row)
    return out


def _row_to_dict(row: LLMCredential) -> dict[str, Any]:
    """Translate a DB row into the session-credentials dict shape."""
    if row.credential_type == "api_key":
        if row.provider_id == "gemini":
            return {"type": "api_key", "api_key": row.credential_value, "source": "disk"}
        return {"type": "api_key", "key": row.credential_value, "source": "disk"}
    if row.credential_type == "oauth":
        return {
            "type": "oauth",
            "access_token": row.credential_value,
            "refresh_token": row.refresh_token,
            "source": "disk",
        }
    if row.credential_type == "none":
        # Ollama: value stores the selected model.
        d: dict[str, Any] = {"type": "none", "source": "disk"}
        if row.model:
            d["model"] = row.model
        return d
    return {"type": row.credential_type, "source": "disk"}


async def save_api_key(session: AsyncSession, provider_id: str, key: str) -> None:
    existing = await session.get(LLMCredential, provider_id)
    if existing is None:
        session.add(LLMCredential(
            provider_id=provider_id,
            credential_type="api_key",
            credential_value=key,
        ))
    else:
        existing.credential_type = "api_key"
        existing.credential_value = key
        existing.refresh_token = None
        existing.model = None
    await session.commit()


async def save_oauth(
    session: AsyncSession,
    provider_id: str,
    access_token: str,
    refresh_token: str | None,
) -> None:
    existing = await session.get(LLMCredential, provider_id)
    if existing is None:
        session.add(LLMCredential(
            provider_id=provider_id,
            credential_type="oauth",
            credential_value=access_token,
            refresh_token=refresh_token,
        ))
    else:
        existing.credential_type = "oauth"
        existing.credential_value = access_token
        existing.refresh_token = refresh_token
        existing.model = None
    await session.commit()


async def save_ollama_model(session: AsyncSession, model: str) -> None:
    existing = await session.get(LLMCredential, "ollama")
    if existing is None:
        session.add(LLMCredential(
            provider_id="ollama",
            credential_type="none",
            credential_value="",
            model=model,
        ))
    else:
        existing.credential_type = "none"
        existing.credential_value = ""
        existing.refresh_token = None
        existing.model = model
    await session.commit()


async def delete_credential(session: AsyncSession, provider_id: str) -> None:
    existing = await session.get(LLMCredential, provider_id)
    if existing is not None:
        await session.delete(existing)
        await session.commit()
