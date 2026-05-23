"""Parse `.env` text into a provider_id -> api_key map.

UAT 2026-05-23 — user asked to load all API keys at once from a `.env`
file instead of pasting each manually. This module owns the mapping
between well-known env var names and our internal provider_id slugs.

Adding a new cloud provider is a one-line change in `ENV_VAR_TO_PROVIDER`
— callers don't need to know which env var names are aliases (we keep
both GOOGLE_API_KEY and GEMINI_API_KEY mapping to `gemini`, for example).
"""
from __future__ import annotations

import re
from typing import Iterable

# Well-known env var names that ship API keys. Keep this dict the single
# source of truth — UI copy ("paste your .env containing X") reads from
# `known_env_vars()` so it stays in sync automatically.
ENV_VAR_TO_PROVIDER: dict[str, str] = {
    "ANTHROPIC_API_KEY": "claude",
    "OPENROUTER_API_KEY": "openrouter",
    "OPENAI_API_KEY": "openai",
    # Both Google variants are accepted — AI Studio docs use both names.
    "GOOGLE_API_KEY": "gemini",
    "GEMINI_API_KEY": "gemini",
}

# Strip surrounding single or double quotes a user might have copy-pasted
# straight from a shell-style `.env` (e.g. KEY="sk-...").
_QUOTED_VALUE = re.compile(r"""^['"](.*)['"]$""")
# Matches `export KEY=VALUE`, `KEY=VALUE`, with optional whitespace and
# inline comments after the value (` # comment`). Multiline values are not
# supported — kept deliberately simple to avoid the parsing surface of
# python-dotenv when all we want is `KEY=VALUE` pairs.
_LINE = re.compile(
    r"""^\s*(?:export\s+)?(?P<key>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<val>.*?)\s*(?:#.*)?$""",
    re.IGNORECASE,
)


def known_env_vars() -> list[str]:
    """Return the sorted list of env var names this module understands.

    Used by the UI to render help copy ("paste a .env containing X, Y, Z").
    """
    return sorted(ENV_VAR_TO_PROVIDER.keys())


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse `.env`-style text into a `provider_id -> api_key` map.

    Unknown env vars are silently dropped — we never persist keys for
    providers we don't ship. Empty values are dropped too (treat as
    explicit "no key" rather than committing a blank credential). When
    both GOOGLE_API_KEY and GEMINI_API_KEY are present, the LAST one in
    the file wins (matches dotenv's last-write-wins semantics).

    Args:
        text: Raw `.env` file contents.

    Returns:
        Dict keyed by provider_id (e.g. `openrouter`, `claude`) with the
        extracted key as value. Empty when the file held no recognized vars.
    """
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        if not raw_line or raw_line.lstrip().startswith("#"):
            continue
        m = _LINE.match(raw_line)
        if not m:
            continue
        key = m.group("key").upper()
        provider_id = ENV_VAR_TO_PROVIDER.get(key)
        if provider_id is None:
            continue
        value = m.group("val").strip()
        quoted = _QUOTED_VALUE.match(value)
        if quoted is not None:
            value = quoted.group(1)
        if not value:
            continue
        out[provider_id] = value
    return out


def filter_supported(env_vars: Iterable[str]) -> list[str]:
    """Return the subset of `env_vars` that map to a registered provider."""
    return [v for v in env_vars if v.upper() in ENV_VAR_TO_PROVIDER]


__all__ = [
    "ENV_VAR_TO_PROVIDER",
    "filter_supported",
    "known_env_vars",
    "parse_dotenv",
]
