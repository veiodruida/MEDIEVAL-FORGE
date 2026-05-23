"""v3 credentials CRUD endpoints (Plan 07-07b Task 2).

Three endpoints — all return `{configured: bool}` only (NO payload leakage,
T-07-07b-01 mitigation):

    GET    /api/v3/credentials                   -> list providers + configured flags
    POST   /api/v3/credentials/{provider}        -> upsert credential payload
    DELETE /api/v3/credentials/{provider}        -> delete credential row

The actual payload (api key, etc.) is plaintext-stored in the DB per
Discretion #1 (OS-keyring escrow deferred to v3.1). The runner reads it back
via `credential_store.get_credentials` — UI consumers NEVER see it.

REVIEWS fix #8: deleting a credential row does NOT cascade to ResearchCache
rows. Cache outlives keys by design.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import AsyncSessionLocal, get_db
from ...services.credential_store import (
    delete_credentials,
    get_credentials,
    store_credentials,
)
from ...services.llm.dotenv_import import (
    ENV_VAR_TO_PROVIDER,
    known_env_vars,
    parse_dotenv,
)
from ...services.llm.registry import PROVIDERS

# Provider-id → env var name used by each provider's `_resolve_key()` so the
# list endpoint can report `{source: "env"}` when the key lives in the shell
# environment but not in the DB.
_PROVIDER_ENV_VAR: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


def _accepts_api_key(provider_id: str) -> bool:
    """True iff the provider declares any non-NoAuth auth method."""
    p = PROVIDERS.get(provider_id)
    if p is None:
        return False
    for auth in getattr(p, "auth_methods", []) or []:
        if getattr(auth, "type", None) in ("api_key", "cli"):
            return True
    return False

logger = logging.getLogger(__name__)

# CRITICAL: prefix is /v3/credentials; main.py adds /api at mount time.
router = APIRouter(prefix="/v3/credentials", tags=["v3-credentials"])


class CredentialBody(BaseModel):
    """POST body — opaque key/value payload (type + key for api_key, etc.).

    The payload is persisted verbatim via `credential_store.store_credentials`.
    """

    payload: dict


# ---------------------------------------------------------------------------
# GET /api/v3/credentials  — list providers + configured flag
# ---------------------------------------------------------------------------
@router.get("")
async def list_credentials(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Return per-provider credential status. NEVER returns the raw key.

    Each row carries:
      - provider_id  / display_name
      - configured   — back-compat field (True iff a DB row exists)
      - has_key      — True iff a key is resolvable (DB OR env)
      - source       — "db" | "env" | "none"
      - env_var      — well-known env var name for this provider (or null)
      - accepts_api_key — False for NoAuth-only providers (llamacpp/ollama)

    T-07-07b-01 mitigation: NEVER returns the payload — only metadata.
    """
    out: list[dict] = []
    for pid, provider in PROVIDERS.items():
        row = await get_credentials(db, pid)
        db_has = bool(row and (row.get("key") if isinstance(row, dict) else None))
        env_var = _PROVIDER_ENV_VAR.get(pid)
        env_has = bool(env_var and os.getenv(env_var))
        source = "db" if db_has else ("env" if env_has else "none")
        out.append(
            {
                "provider_id": pid,
                "display_name": getattr(provider, "display_name", pid),
                "configured": row is not None,
                "has_key": db_has or env_has,
                "source": source,
                "env_var": env_var,
                "accepts_api_key": _accepts_api_key(pid),
            }
        )
    return out


# ---------------------------------------------------------------------------
# POST /api/v3/credentials/{provider}  — upsert credential
# ---------------------------------------------------------------------------
@router.post("/{provider}")
async def upsert_credential(
    provider: str,
    body: CredentialBody,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Persist credential payload for `provider`. Returns {configured: True}."""
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"unknown provider: {provider!r}"
        )
    await store_credentials(db, provider, body.payload)
    return {"configured": True}


# ---------------------------------------------------------------------------
# DELETE /api/v3/credentials/{provider}  — delete credential row
# ---------------------------------------------------------------------------
@router.delete("/{provider}")
async def delete_credential(
    provider: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Delete credential row. Returns {configured: False}.

    REVIEWS fix #8: does NOT cascade-delete ResearchCache rows.
    """
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"unknown provider: {provider!r}"
        )
    await delete_credentials(db, provider)
    return {"configured": False}


# ---------------------------------------------------------------------------
# PUT /api/v3/credentials/{provider}  — quick set with `{key}` body
# ---------------------------------------------------------------------------
class SetKeyBody(BaseModel):
    """Minimal `{key}` payload used by the new CredentialsManager UI.

    Equivalent to POSTing `{payload: {type: "api_key", key: "..."}}` but
    avoids forcing the frontend to know our internal payload shape.
    """

    key: str = Field(min_length=4, description="Raw API key.")


@router.put("/{provider}")
async def set_credential_key(
    provider: str,
    body: SetKeyBody,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set or replace the API key for a single provider.

    Wraps `store_credentials` with the conventional `{type, key}` shape so
    callers don't need to know the on-disk schema. Returns `{ok: True}` —
    the key is NEVER echoed.
    """
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"unknown provider: {provider!r}"
        )
    if not _accepts_api_key(provider):
        raise HTTPException(
            status_code=400,
            detail=f"provider {provider!r} does not accept API keys",
        )
    await store_credentials(db, provider, {"type": "api_key", "key": body.key.strip()})
    return {"ok": True, "provider_id": provider}


# ---------------------------------------------------------------------------
# POST /api/v3/credentials/import  — batch-import from a .env blob
# ---------------------------------------------------------------------------
class ImportResult(BaseModel):
    imported: list[str]
    skipped: list[str]
    known_env_vars: list[str]


@router.post("/import")
async def import_dotenv(payload: dict[str, Any] = Body(...)) -> ImportResult:
    """Batch-import API keys from a `.env`-style text blob.

    Body: `{"text": "ANTHROPIC_API_KEY=...\\nOPENROUTER_API_KEY=..."}`.

    Unknown env var names are surfaced in `skipped` so users can see why a
    given `MY_OBSCURE_KEY=...` line was ignored. The response NEVER echoes
    any key material — only the list of provider_ids that received a key
    plus our recognized env var catalog (for UI help copy).
    """
    text = (payload or {}).get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="body must include `text` with the .env file contents",
        )

    parsed = parse_dotenv(text)

    # Detect skipped lines (unknown KEY= entries) by re-scanning the raw text
    # — `parse_dotenv` already silently dropped them, but the UI wants to
    # tell the user "we ignored FOO_KEY". We dedupe by uppercase name.
    skipped: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        head = stripped.split("=", 1)[0].strip().removeprefix("export ").strip()
        if not head.isidentifier():
            continue
        head_upper = head.upper()
        if head_upper in seen:
            continue
        seen.add(head_upper)
        if head_upper not in ENV_VAR_TO_PROVIDER:
            skipped.append(head_upper)

    imported: list[str] = []
    if parsed:
        # Use an explicit context-managed session here (NOT Depends(get_db))
        # because parse_dotenv is sync + we want a single commit batch.
        async with AsyncSessionLocal() as session:
            for provider_id, key in parsed.items():
                if provider_id not in PROVIDERS:
                    # Mapped but not registered — happens during incremental
                    # rollouts (e.g. new provider in dotenv_import mapping
                    # before its module ships). Skip silently.
                    continue
                await store_credentials(
                    session, provider_id, {"type": "api_key", "key": key.strip()}
                )
                imported.append(provider_id)

    return ImportResult(
        imported=sorted(imported),
        skipped=sorted(set(skipped)),
        known_env_vars=known_env_vars(),
    )


__all__ = ["router"]
