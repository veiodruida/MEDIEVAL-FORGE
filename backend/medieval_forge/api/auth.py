"""Auth endpoints for credential management and Google OAuth.

Endpoints:
  POST   /api/auth/credentials/{provider}        — store API key in session
  DELETE /api/auth/credentials/{provider}        — remove credential from session
  POST   /api/auth/oauth/{provider}/start        — begin OAuth flow (Gemini only)
  GET    /api/auth/oauth/{provider}/callback     — OAuth callback; exchanges code for token

Security model (T-3-01..T-3-06):
- Credentials stored in app.state.credentials only (in-process dict)
- POST returns 204 No Content (T-3-03: key never echoed)
- OAuth state param is cryptographically random 32-byte urlsafe token (T-3-02)
- State entries expire after OAUTH_STATE_TTL_SEC seconds
- Expired states cleaned on every /start call (T-3-06 / Pitfall 5)
- client_secret stays server-side only (T-3-04)
"""
from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel

from ..services.llm.registry import PROVIDERS

router = APIRouter(tags=["auth"])

OAUTH_STATE_TTL_SEC = 300

# Google OAuth client config for the "installed app" (desktop) flow.
# NOTE: Replace REPLACE_WITH_BUNDLED_CLIENT_ID with a real GCP-registered Desktop
# OAuth client before shipping. Plan 04 surfaces "OAuth not configured" gracefully
# when client_id still equals the placeholder (Open Question #2 in CONTEXT.md).
GOOGLE_CLIENT_CONFIG = {
    "installed": {
        "client_id": "REPLACE_WITH_BUNDLED_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "REPLACE_WITH_BUNDLED_CLIENT_SECRET",
        "redirect_uris": ["http://localhost:8000/api/auth/oauth/gemini/callback"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}
GEMINI_SCOPES = ["https://www.googleapis.com/auth/generative-language.retriever"]
OAUTH_REDIRECT_URI = "http://localhost:8000/api/auth/oauth/gemini/callback"


class CredentialPayload(BaseModel):
    api_key: str


def _clean_expired_states(app_state) -> None:
    """Remove OAuth state entries older than OAUTH_STATE_TTL_SEC (Pitfall 5)."""
    now = time.time()
    states = getattr(app_state, "oauth_states", {}) or {}
    expired = [k for k, v in states.items() if v.get("expires_at", 0) < now]
    for k in expired:
        states.pop(k, None)


@router.post("/auth/credentials/{provider}", status_code=204)
async def store_credential(
    provider: str, payload: CredentialPayload, request: Request
) -> Response:
    """Store an API key in the in-memory session store.

    Returns 204 No Content — key is never echoed back (T-3-03).
    Returns 404 for unknown providers (mistral, etc. not yet registered).
    """
    if provider not in PROVIDERS:
        raise HTTPException(404, f"Unknown provider: {provider}")

    creds = getattr(request.app.state, "credentials", None)
    if creds is None:
        creds = {}
        request.app.state.credentials = creds

    # Gemini stores api_key under "api_key" field; others under "key"
    # (matches what resolve_credentials() and provider adapters expect)
    if provider == "gemini":
        creds[provider] = {"type": "api_key", "api_key": payload.api_key, "source": "session"}
    else:
        creds[provider] = {"type": "api_key", "key": payload.api_key, "source": "session"}

    return Response(status_code=204)


@router.delete("/auth/credentials/{provider}", status_code=204)
async def clear_credential(provider: str, request: Request) -> Response:
    """Remove a credential from the in-memory session store."""
    if provider not in PROVIDERS:
        raise HTTPException(404, f"Unknown provider: {provider}")

    creds = getattr(request.app.state, "credentials", {}) or {}
    creds.pop(provider, None)
    return Response(status_code=204)


@router.post("/auth/oauth/{provider}/start")
async def oauth_start(provider: str, request: Request) -> dict:
    """Begin the Google OAuth installed-app flow for Gemini.

    Returns {"authorize_url": "https://accounts.google.com/...", "state": "..."}.
    The state token is stored server-side for CSRF validation in /callback (T-3-02).
    Only Gemini supports OAuth per D-12; all other providers return 404.
    """
    if provider != "gemini":
        raise HTTPException(404, f"OAuth not supported for provider: {provider}")

    states = getattr(request.app.state, "oauth_states", None)
    if states is None:
        states = {}
        request.app.state.oauth_states = states

    # Clean stale entries before adding a new one (T-3-06 / Pitfall 5)
    _clean_expired_states(request.app.state)

    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=GEMINI_SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI,
    )
    state = secrets.token_urlsafe(32)
    authorize_url, returned_state = flow.authorization_url(
        state=state,
        access_type="offline",
        prompt="consent",
    )
    # Use the state echo from authorization_url as the dict key so tests can
    # assert on a predictable value when the flow is mocked.
    state_key = returned_state or state
    states[state_key] = {
        "flow": flow,
        "provider": provider,
        "expires_at": time.time() + OAUTH_STATE_TTL_SEC,
    }
    return {"authorize_url": authorize_url, "state": state_key}


@router.get("/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str, code: str, state: str, request: Request
) -> dict:
    """Exchange OAuth authorization code for access token.

    Validates the state parameter to prevent CSRF attacks (T-3-02).
    Returns 400 for unknown, expired, or missing state tokens.
    Stores the access token in app.state.credentials[provider].
    """
    if provider != "gemini":
        raise HTTPException(404, f"OAuth not supported for provider: {provider}")

    states = getattr(request.app.state, "oauth_states", {}) or {}
    stored = states.pop(state, None)

    if stored is None:
        raise HTTPException(400, "Invalid or expired OAuth state")

    if stored.get("expires_at", 0) < time.time():
        raise HTTPException(400, "Expired OAuth state")

    flow = stored["flow"]
    flow.fetch_token(code=code)

    creds = getattr(request.app.state, "credentials", None)
    if creds is None:
        creds = {}
        request.app.state.credentials = creds

    creds[provider] = {
        "type": "oauth",
        "access_token": flow.credentials.token,
        "refresh_token": flow.credentials.refresh_token,
        "source": "oauth",
    }
    return {"status": "authenticated", "provider": provider}
