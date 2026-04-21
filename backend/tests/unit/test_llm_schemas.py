"""Tests for ResearchResult Pydantic schema — RESEARCH-03."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from medieval_forge.services.llm.schemas import (
    Barony,
    CondadoAssignment,
    ResearchResult,
)

_MINIMAL_VALID = {
    "kingdoms": {"k1": "Kingdom One"},
    "duchies": {"d1": ["k1", "Duchy One"]},
    "condados_assignment": [
        {"condado_id": "c1", "kingdom_id": "k1", "duchy_id": "d1"}
    ],
    "baronies": {"c1": [{"name": "Baronia A", "lon": -8.5, "lat": 42.3}]},
}


def test_research_result_accepts_minimal_valid_payload():
    result = ResearchResult.model_validate(_MINIMAL_VALID)
    assert result.kingdoms == {"k1": "Kingdom One"}
    assert "d1" in result.duchies
    assert len(result.condados_assignment) == 1
    assert result.condados_assignment[0].condado_id == "c1"


def test_research_result_rejects_unknown_top_level_field():
    bad = {**_MINIMAL_VALID, "extra_field": 1}
    with pytest.raises(ValidationError) as exc_info:
        ResearchResult.model_validate(bad)
    assert "extra_forbidden" in str(exc_info.value) or "extra" in str(
        exc_info.value
    ).lower()


def test_condado_assignment_rejects_unknown_field():
    bad_assignment = {
        "condado_id": "c1",
        "kingdom_id": "k1",
        "duchy_id": "d1",
        "surprise_field": "oops",
    }
    with pytest.raises(ValidationError):
        CondadoAssignment.model_validate(bad_assignment)


def test_barony_requires_lon_lat_name():
    # Missing lat
    with pytest.raises(ValidationError):
        Barony.model_validate({"name": "B", "lon": 1.0})
    # Missing name
    with pytest.raises(ValidationError):
        Barony.model_validate({"lon": 1.0, "lat": 2.0})
    # Missing lon
    with pytest.raises(ValidationError):
        Barony.model_validate({"name": "B", "lat": 2.0})
