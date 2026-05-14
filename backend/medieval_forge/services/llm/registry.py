"""Plugin registry for LLM providers (Phase 07-03 Task 3, D-05 + Discretion #10).

Deferred-population shim: PROVIDERS starts empty. Plan 04 lands
claude.py + ollama.py and calls `register()` at module-import time for each.

D-05 lock: exactly 2 providers will be registered (claude + ollama).
OAuthAuth / Gemini / GPT are out of scope for v3 (see 07-RESEARCH §Deferred).

Pattern 2 (RESEARCH §Pattern 2): import-time registration so the dict is
populated before any consumer (UI, runner) reads it.
"""
from __future__ import annotations

from .base import LLMProvider

# Deferred-population: empty at Plan 03 end; Plan 04 fills both slots.
PROVIDERS: dict[str, LLMProvider] = {}


def register(provider: LLMProvider) -> None:
    """Register an LLMProvider under its `provider_id`.

    Idempotent on re-import (overwrites in place). Plan 04 calls this at the
    module top of claude.py and ollama.py so PROVIDERS is populated as soon
    as `medieval_forge.services.llm` is imported.
    """
    PROVIDERS[provider.provider_id] = provider


def get(provider_id: str) -> LLMProvider:
    """Return the registered provider by id.

    Raises KeyError if the id is unknown — callers must validate
    provider_id against `list_providers()` before calling.
    """
    return PROVIDERS[provider_id]


def list_providers() -> list[str]:
    """Return the sorted list of currently-registered provider ids.

    Stable ordering matters for the UI dropdown and snapshot tests.
    """
    return sorted(PROVIDERS.keys())
