"""SC-3 schema gate: HealthStatus.available_models field (D-09 Phase 07.1).

Implements the schema-extension contract added in plan 07.1-01. The Wave 0
scaffold backend/tests/unit/test_llamacpp_provider.py covers the provider's
runtime *behavior*; this file covers the pydantic model contract itself so any
future rename or removal breaks the build immediately.
"""
import pytest
from pydantic import ValidationError

from medieval_forge.services.llm.base import HealthStatus


def test_health_status_available_models_defaults_to_none_when_omitted() -> None:
    h = HealthStatus(healthy=True)
    assert h.available_models is None


def test_health_status_accepts_empty_list_for_available_models() -> None:
    h = HealthStatus(healthy=True, available_models=[])
    assert h.available_models == []


def test_health_status_accepts_list_of_filename_strings_for_available_models() -> None:
    models = ["Qwen3-7B-Q4.gguf", "Llama3.1-8B-Q4.gguf"]
    h = HealthStatus(healthy=True, available_models=models)
    assert h.available_models == models


def test_health_status_rejects_string_for_available_models() -> None:
    with pytest.raises(ValidationError):
        HealthStatus(healthy=True, available_models="not-a-list")  # type: ignore[arg-type]


def test_health_status_rejects_non_string_elements_in_available_models() -> None:
    with pytest.raises(ValidationError):
        HealthStatus(healthy=True, available_models=[1, 2])  # type: ignore[list-item]


def test_health_status_existing_two_field_construction_stays_compatible() -> None:
    """SC-6 regression: existing Phase 07 callers omit the new field."""
    h = HealthStatus(healthy=False, message="not configured")
    assert h.healthy is False
    assert h.message == "not configured"
    assert h.available_models is None
