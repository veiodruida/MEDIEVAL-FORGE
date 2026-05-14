"""Wave 0 gate: schema validation for ResearchResult + MapResearchResult.

Covers the lenient-parse path (extra top-level keys stripped, then re-validated)
plus strict-rejection of missing required fields, plus a concrete
MapResearchResult fixture that exercises barony_assignments cross-ref validation.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from medieval_forge.services.llm.schemas import (
    MapResearchResult,
    ResearchResult,
    parse_research_json,
    validate_barony_assignments,
)


_BASE_RESEARCH_RESULT = {
    "kingdoms": {"K_LEON": "Reino de Leon"},
    "duchies": {"D_LEON": {"kingdom_id": "K_LEON", "name": "Ducado de Leon"}},
    "condados": [
        {
            "id": "C_LEON",
            "name": "Condado de Leon",
            "lon": -5.567,
            "lat": 42.598,
            "kingdom_id": "K_LEON",
            "duchy_id": "D_LEON",
        }
    ],
    "baronies": {
        "C_LEON": [
            {"name": "Astorga", "lon": -6.054, "lat": 42.457},
            {"name": "Sahagun", "lon": -5.029, "lat": 42.371},
        ]
    },
}


def test_parse_research_json_strips_extra_top_level_keys_added_by_local_models():
    payload = dict(_BASE_RESEARCH_RESULT)
    payload["regions"] = ["unknown extra"]            # qwen2.5:7b style noise
    payload["historical_names"] = {"foo": "bar"}      # llama3.2:3b style noise
    payload["description"] = "Free-form summary"

    result = parse_research_json(json.dumps(payload))

    assert isinstance(result, ResearchResult)
    assert result.kingdoms == {"K_LEON": "Reino de Leon"}
    assert len(result.condados) == 1
    assert result.condados[0].id == "C_LEON"
    assert len(result.baronies["C_LEON"]) == 2


def test_parse_research_json_rejects_missing_required_kingdoms_field_with_strict_error():
    payload = {k: v for k, v in _BASE_RESEARCH_RESULT.items() if k != "kingdoms"}

    with pytest.raises(ValidationError) as excinfo:
        parse_research_json(json.dumps(payload))

    # Strict-validator error surfaces (per parse_research_json docstring: original error preferred).
    errors = excinfo.value.errors()
    assert any(err["loc"] == ("kingdoms",) for err in errors), errors


def test_map_research_result_validates_barony_assignments_cross_reference():
    """barony_assignments must point at condado ids actually in condados[]."""
    valid = MapResearchResult(
        kingdoms={"K_LEON": "Reino de Leon"},
        duchies={"D_LEON": {"kingdom_id": "K_LEON", "name": "Ducado de Leon"}},
        condados=[
            {"id": "C_LEON", "name": "Condado de Leon", "kingdom_id": "K_LEON", "duchy_id": "D_LEON"}
        ],
        barony_assignments={"B_001": "C_LEON", "B_002": "C_LEON"},
    )
    assert len(valid.condados) == 1
    assert valid.barony_assignments == {"B_001": "C_LEON", "B_002": "C_LEON"}

    with pytest.raises(ValidationError):
        MapResearchResult(
            kingdoms={"K_LEON": "Reino de Leon"},
            duchies={"D_LEON": {"kingdom_id": "K_LEON", "name": "Ducado de Leon"}},
            condados=[
                {"id": "C_LEON", "name": "Condado de Leon", "kingdom_id": "K_LEON", "duchy_id": "D_LEON"}
            ],
            barony_assignments={"B_001": "C_GHOST"},  # not in condados[]
        )


def test_validate_barony_assignments_flags_unassigned_input_baronies():
    """Strict: every input barony id must appear in barony_assignments keys."""
    result = MapResearchResult(
        kingdoms={"K_LEON": "Reino de Leon"},
        duchies={"D_LEON": {"kingdom_id": "K_LEON", "name": "Ducado de Leon"}},
        condados=[
            {"id": "C_LEON", "name": "Condado de Leon", "kingdom_id": "K_LEON", "duchy_id": "D_LEON"}
        ],
        barony_assignments={"B_001": "C_LEON"},
    )
    input_baronies = [{"id": "B_001"}, {"id": "B_002"}]  # B_002 missing in assignments

    with pytest.raises(ValueError, match="unassigned"):
        validate_barony_assignments(result, input_baronies)
