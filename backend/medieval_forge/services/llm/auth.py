"""Credential resolution for LLM providers.

Provides:
- read_claude_cli_token()  — reads Anthropic OAuth token from claude-code credential store
- resolve_credentials(provider_id, app_state) — priority-ordered credential resolution

Priority chains per D-10..D-13 (CONTEXT.md):
  claude:  session → env ANTHROPIC_API_KEY → CLI piggyback (~/.claude/.credentials.json)
  gemini:  session → env GOOGLE_API_KEY / GEMINI_API_KEY
  openai:  session → env OPENAI_API_KEY
  ollama:  no auth

Security invariant (T-3-01): this module contains ZERO file-write calls.
All credentials remain in app.state.credentials (in-process dict) only.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any


def _credential_file_candidates() -> list[pathlib.Path]:
    """Return ordered candidate paths for the claude-code credential file.

    Evaluated lazily so monkeypatching pathlib.Path.home() in tests works.
    RESEARCH.md Pattern 4 verified these paths on Windows 11.
    """
    candidates: list[pathlib.Path] = [
        pathlib.Path.home() / ".claude" / ".credentials.json",
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(pathlib.Path(appdata) / "Claude" / "credentials.json")
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        candidates.append(pathlib.Path(xdg) / "claude" / "credentials.json")
    else:
        candidates.append(pathlib.Path.home() / ".config" / "claude" / "credentials.json")
    return candidates


def read_claude_cli_token() -> str | None:
    """Read Anthropic OAuth access token from claude-code credential store.

    Returns None if:
    - No candidate file exists
    - File is malformed JSON
    - Token is missing or expired

    Verified credential file structure on Windows 11 (RESEARCH.md Pattern 4):
        {
            "claudeAiOauth": {
                "accessToken": "sk-ant-oat01-...",
                "expiresAt": 1776790173634   # milliseconds epoch
            }
        }

    Security: never logs or prints file contents (T-3-05).
    """
    for path in _credential_file_candidates():
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        token_data = data.get("claudeAiOauth", {})
        access_token = token_data.get("accessToken")
        expires_at_ms = token_data.get("expiresAt", 0)
        if access_token and expires_at_ms > time.time() * 1000:
            return access_token
    return None


def resolve_credentials(provider_id: str, app_state: Any) -> dict[str, Any]:
    """Resolve credentials for a provider using the priority chain.

    Returns a dict describing the credential source, or empty dict if none found.

    Dict shapes:
      {"type": "api_key", "key": "...", "source": "session"|"env"|"cli"}
      {"type": "oauth_token", "key": "...", "source": "cli"|"oauth"}
      {"type": "none", "source": "none"}   — Ollama
      {}   — no credential found

    D-10 (claude):  session → env ANTHROPIC_API_KEY → CLI piggyback
    D-11 (gemini):  session → env GOOGLE_API_KEY / GEMINI_API_KEY
    D-12 (openai):  session → env OPENAI_API_KEY  (no OAuth, no CLI)
    D-13 (ollama):  always {"type": "none", "source": "none"}
    """
    session: dict | None = (getattr(app_state, "credentials", {}) or {}).get(provider_id)

    if provider_id == "claude":
        if session:
            return {**session, "source": session.get("source", "session")}
        env_key = os.getenv("ANTHROPIC_API_KEY")
        if env_key:
            return {"type": "api_key", "key": env_key, "source": "env"}
        cli_token = read_claude_cli_token()
        if cli_token:
            return {"type": "oauth_token", "key": cli_token, "source": "cli"}
        return {}

    if provider_id == "gemini":
        if session:
            return {**session, "source": session.get("source", "session")}
        env_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if env_key:
            return {"type": "api_key", "api_key": env_key, "source": "env"}
        return {}

    if provider_id == "openai":
        if session:
            return {**session, "source": session.get("source", "session")}
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            return {"type": "api_key", "key": env_key, "source": "env"}
        return {}

    if provider_id == "ollama":
        return {"type": "none", "source": "none"}

    return {}
