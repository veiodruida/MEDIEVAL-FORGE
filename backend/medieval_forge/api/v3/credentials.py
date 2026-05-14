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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...services.credential_store import (
    delete_credentials,
    get_credentials,
    store_credentials,
)
from ...services.llm.registry import PROVIDERS

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
    """Return [{provider_id, configured}] for every registered provider.

    T-07-07b-01 mitigation: NEVER returns the payload — only the configured
    bool flag derived from row existence.
    """
    out: list[dict] = []
    for pid in PROVIDERS.keys():
        row = await get_credentials(db, pid)
        out.append({"provider_id": pid, "configured": row is not None})
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


__all__ = ["router"]
