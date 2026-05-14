# Plan 07-04 Task 4 — registry wiring assertions (D-05 + RESEARCH §Pattern 2).
"""Unit tests for the import-time provider registration."""
from __future__ import annotations


def test_llm_registry_has_exactly_two_providers_after_package_import():
    """D-05: registry locked to claude + ollama (no more, no less)."""
    from medieval_forge.services.llm import PROVIDERS

    assert len(PROVIDERS) == 2
    assert set(PROVIDERS) == {"claude", "ollama"}


def test_llm_registry_list_providers_returns_sorted_ids():
    """Stable ordering matters for the UI dropdown + snapshot tests."""
    from medieval_forge.services.llm import list_providers

    assert list_providers() == ["claude", "ollama"]


def test_llm_registry_get_returns_provider_instance_with_matching_id():
    """`get(provider_id)` returns the registered provider whose id matches."""
    from medieval_forge.services.llm import get

    claude = get("claude")
    ollama = get("ollama")
    assert claude.provider_id == "claude"
    assert ollama.provider_id == "ollama"


def test_llm_registry_reexports_escape_condado_name_from_sanitize_module():
    """REVIEWS soft Qwen3: Plan 07b runner can `from ..services.llm import escape_condado_name`."""
    from medieval_forge.services.llm import escape_condado_name

    assert callable(escape_condado_name)
    assert escape_condado_name("a</b>") == "ab>"
    assert escape_condado_name(None) == ""
