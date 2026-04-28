"""Unit tests for the model routing layer (Etapa 4 — quick-260428-f9x).

Locks in the contract for ``resolve_model(provider_id, task, effort_override=None)``:
the function maps a (provider, task, effort) triple to a concrete model id, using
the task's default effort tier unless an override is provided.

Each test uses descriptive names + explicit literal model ids in the assertions
(per the project's "tests-descriptive" convention) so a reader can lock in the
contract from the test name alone, without parsing fixture builders.
"""
from __future__ import annotations

import pytest

from medieval_forge.services.llm.model_routing import (
    TASK_DEFAULT_EFFORT,
    TASK_MODEL_TIERS,
    resolve_model,
)


def test_task_default_effort_resolves_correct_model_for_claude_provider_when_no_override():
    # map_research_full → default effort "high" → claude-opus-4-7
    assert resolve_model("claude", "map_research_full") == "claude-opus-4-7"
    # codex_population_economy → default effort "low" → claude-haiku-4-5-20251001
    assert (
        resolve_model("claude", "codex_population_economy")
        == "claude-haiku-4-5-20251001"
    )
    # Sanity-check the static tables themselves so the test acts as a
    # contract-snapshot for the verbatim values from plan B.1/B.2.
    assert TASK_DEFAULT_EFFORT["map_research_full"] == "high"
    assert TASK_DEFAULT_EFFORT["codex_population_economy"] == "low"
    assert TASK_MODEL_TIERS["claude"]["high"] == "claude-opus-4-7"
    assert TASK_MODEL_TIERS["claude"]["low"] == "claude-haiku-4-5-20251001"


def test_user_override_effort_takes_precedence_over_task_default_effort():
    # map_research_full's default is "high" — override to "low" must win.
    assert (
        resolve_model("claude", "map_research_full", effort_override="low")
        == "claude-haiku-4-5-20251001"
    )
    # codex_population_economy's default is "low" — override to "high" must win.
    assert (
        resolve_model("openai", "codex_population_economy", effort_override="high")
        == "gpt-4-turbo"
    )


def test_llamacpp_provider_returns_server_default_marker_for_any_effort_tier():
    # llamacpp is a local server; the routing layer must hand back the
    # sentinel "(server-default)" regardless of effort tier so the provider
    # adapter can use whatever model the server has loaded.
    assert resolve_model("llamacpp", "map_research_full") == "(server-default)"
    assert (
        resolve_model("llamacpp", "codex_genealogy", effort_override="low")
        == "(server-default)"
    )
    assert (
        resolve_model("llamacpp", "codex_culture_religion", effort_override="medium")
        == "(server-default)"
    )


def test_resolve_model_raises_clear_error_for_unknown_provider_id():
    # Unknown provider — error must mention the offending provider id.
    with pytest.raises((KeyError, ValueError)) as exc_info:
        resolve_model("nonexistent_provider", "map_research_full")
    assert "nonexistent_provider" in str(exc_info.value)

    # Unknown task on a known provider — error must mention the offending task.
    with pytest.raises((KeyError, ValueError)) as exc_info:
        resolve_model("claude", "unknown_task_xyz")
    assert "unknown_task_xyz" in str(exc_info.value)
