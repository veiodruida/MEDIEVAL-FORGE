"""Smoke tests for services/llm/base.py (Phase 07-02 Task 2).

NEW v3 file: validates LLMProvider Protocol runtime_checkable behavior,
HealthStatus round-trip, and the 3 auth-method shapes (ApiKeyAuth, CliAuth, NoAuth).
OAuthAuth is deferred to v3.1 and MUST NOT appear in the union.
"""
from __future__ import annotations

import pytest

from medieval_forge.services.llm.base import (
    ApiKeyAuth,
    AuthMethod,
    CliAuth,
    HealthStatus,
    LLMProvider,
    NoAuth,
)


def test_health_status_round_trips_with_healthy_true_and_message_string():
    hs = HealthStatus(healthy=True, message="Credentials present")
    dumped = hs.model_dump()
    assert dumped == {"healthy": True, "message": "Credentials present"}
    reconstructed = HealthStatus.model_validate(dumped)
    assert reconstructed.healthy is True
    assert reconstructed.message == "Credentials present"


def test_health_status_message_defaults_to_empty_string_when_omitted():
    hs = HealthStatus(healthy=False)
    assert hs.healthy is False
    assert hs.message == ""


def test_api_key_auth_cli_auth_no_auth_construct_with_documented_shapes():
    api = ApiKeyAuth(env_var="ANTHROPIC_API_KEY")
    assert api.type == "api_key"
    assert api.env_var == "ANTHROPIC_API_KEY"

    api_dialog = ApiKeyAuth(env_var=None)
    assert api_dialog.env_var is None

    cli = CliAuth(cli_command="claude", auth_file_path="~/.claude/.credentials.json")
    assert cli.type == "cli"
    assert cli.cli_command == "claude"
    assert cli.auth_file_path == "~/.claude/.credentials.json"

    none_auth = NoAuth()
    assert none_auth.type == "none"


def test_llm_provider_protocol_is_runtime_checkable_against_a_stub():
    """A duck-typed class with the right attrs + methods satisfies isinstance()."""

    class StubProvider:
        provider_id = "stub"
        display_name = "Stub Provider"
        auth_methods: list[AuthMethod] = [NoAuth()]

        async def health_check(self, credentials):  # type: ignore[override]
            return HealthStatus(healthy=True, message="stub")

        async def research(self, prompt, schema, credentials, queue):  # type: ignore[override]
            return None

    assert isinstance(StubProvider(), LLMProvider)


def test_auth_method_union_excludes_oauth_auth_deferred_to_v3_1():
    """OAuthAuth is explicitly dropped per 07-RESEARCH §Deferred; ensure no leak."""
    import medieval_forge.services.llm.base as base_mod

    assert not hasattr(base_mod, "OAuthAuth"), "OAuthAuth must not be exported (v3.1 backlog)"
