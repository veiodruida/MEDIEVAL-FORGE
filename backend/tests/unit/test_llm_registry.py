"""Tests for PROVIDERS registry — RESEARCH-09."""
from __future__ import annotations

import inspect

import pytest

from medieval_forge.services.llm import LLMProvider
from medieval_forge.services.llm.registry import PROVIDERS


def test_providers_dict_has_four_entries():
    assert len(PROVIDERS) == 4
    assert set(PROVIDERS.keys()) == {"claude", "openai", "gemini", "ollama"}


def test_each_provider_implements_protocol():
    for name, provider in PROVIDERS.items():
        assert isinstance(provider, LLMProvider), f"{name} does not implement LLMProvider"
        assert provider.provider_id, f"{name}.provider_id is empty"
        assert provider.display_name, f"{name}.display_name is empty"
        assert provider.auth_methods is not None, f"{name}.auth_methods is None"


@pytest.mark.asyncio
async def test_each_provider_has_async_research_and_health_check():
    for name, provider in PROVIDERS.items():
        assert inspect.iscoroutinefunction(provider.research), (
            f"{name}.research is not async"
        )
        assert inspect.iscoroutinefunction(provider.health_check), (
            f"{name}.health_check is not async"
        )
