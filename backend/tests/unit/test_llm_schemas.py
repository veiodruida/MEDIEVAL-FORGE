"""Tests for ResearchResult Pydantic schema — RESEARCH-03."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from medieval_forge.services.llm.schemas import (
    Barony,
    Condado,
    MapCondado,
    MapResearchResult,
    ResearchResult,
)

_MINIMAL_VALID = {
    "kingdoms": {"k1": "Kingdom One"},
    "duchies": {"d1": {"kingdom_id": "k1", "name": "Duchy One"}},
    "condados": [
        {"id": "C_ONE", "name": "Condado One", "lon": -8.5, "lat": 42.3,
         "kingdom_id": "k1", "duchy_id": "d1"},
    ],
    "baronies": {"C_ONE": [{"name": "Baronia A", "lon": -8.5, "lat": 42.3}]},
}


def test_research_result_accepts_minimal_valid_payload():
    result = ResearchResult.model_validate(_MINIMAL_VALID)
    assert result.kingdoms == {"k1": "Kingdom One"}
    assert "d1" in result.duchies
    assert len(result.condados) == 1
    assert result.condados[0].id == "C_ONE"
    assert result.condados[0].kingdom_id == "k1"
    assert result.condados[0].duchy_id == "d1"


def test_research_result_rejects_unknown_top_level_field():
    bad = {**_MINIMAL_VALID, "extra_field": 1}
    with pytest.raises(ValidationError) as exc_info:
        ResearchResult.model_validate(bad)
    assert "extra_forbidden" in str(exc_info.value) or "extra" in str(
        exc_info.value
    ).lower()


def test_condado_rejects_unknown_field():
    bad_condado = {
        "id": "C_ONE", "name": "One", "lon": -8.5, "lat": 42.3,
        "kingdom_id": "k1", "duchy_id": "d1",
        "surprise_field": "oops",
    }
    with pytest.raises(ValidationError):
        Condado.model_validate(bad_condado)


def test_condado_requires_all_fields():
    # Missing lat
    with pytest.raises(ValidationError):
        Condado.model_validate({"id": "C_X", "name": "X", "lon": -8.5,
                                "kingdom_id": "k1", "duchy_id": "d1"})
    # Missing id
    with pytest.raises(ValidationError):
        Condado.model_validate({"name": "X", "lon": -8.5, "lat": 42.3,
                                "kingdom_id": "k1", "duchy_id": "d1"})
    # Missing duchy_id
    with pytest.raises(ValidationError):
        Condado.model_validate({"id": "C_X", "name": "X", "lon": -8.5, "lat": 42.3,
                                "kingdom_id": "k1"})


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


# ---------------------------------------------------------------------------
# Etapa 3 (hazy-hatching-abelson.md) — MapResearchResult schema split tests.
# Condados no longer carry coords; baronies are referenced via barony_assignments.
# ---------------------------------------------------------------------------

_MAP_MINIMAL_VALID = {
    "kingdoms": {"k_leon": "León"},
    "duchies": {"d_galicia": {"kingdom_id": "k_leon", "name": "Galícia"}},
    "condados": [
        {"id": "C_BRAGA", "name": "Braga",
         "kingdom_id": "k_leon", "duchy_id": "d_galicia"},
    ],
    "barony_assignments": {"B_001": "C_BRAGA", "B_002": "C_BRAGA"},
}

_MAP_TWO_CONDADOS = {
    "kingdoms": {"k_leon": "León"},
    "duchies": {"d_galicia": {"kingdom_id": "k_leon", "name": "Galícia"}},
    "condados": [
        {"id": "C_BRAGA", "name": "Braga",
         "kingdom_id": "k_leon", "duchy_id": "d_galicia"},
        {"id": "C_PORTO", "name": "Porto",
         "kingdom_id": "k_leon", "duchy_id": "d_galicia"},
    ],
    "barony_assignments": {
        "B_001": "C_BRAGA",
        "B_002": "C_PORTO",
        "B_003": "C_BRAGA",
    },
}


def test_map_research_result_accepts_minimal_valid_payload_with_two_baronies_assigned_to_condado_braga():
    result = MapResearchResult.model_validate(_MAP_MINIMAL_VALID)
    assert result.condados[0].id == "C_BRAGA"
    assert len(result.barony_assignments) == 2
    assert result.barony_assignments["B_001"] == "C_BRAGA"
    assert result.barony_assignments["B_002"] == "C_BRAGA"


def test_map_condado_rejects_lon_lat_fields_because_coords_are_no_longer_part_of_the_new_schema():
    with pytest.raises(ValidationError):
        MapCondado.model_validate({
            "id": "C_X", "name": "X",
            "kingdom_id": "k1", "duchy_id": "d1",
            "lon": -8.5, "lat": 42.3,
        })


def test_map_condado_requires_id_name_kingdom_id_and_duchy_id():
    # Missing id
    with pytest.raises(ValidationError):
        MapCondado.model_validate({"name": "X", "kingdom_id": "k1", "duchy_id": "d1"})
    # Missing name
    with pytest.raises(ValidationError):
        MapCondado.model_validate({"id": "C_X", "kingdom_id": "k1", "duchy_id": "d1"})
    # Missing duchy_id
    with pytest.raises(ValidationError):
        MapCondado.model_validate({"id": "C_X", "name": "X", "kingdom_id": "k1"})


def test_map_research_result_barony_assignments_accepts_empty_dict_when_no_baronies_yet():
    payload = {
        "kingdoms": {"k_leon": "León"},
        "duchies": {"d_galicia": {"kingdom_id": "k_leon", "name": "Galícia"}},
        "condados": [
            {"id": "C_BRAGA", "name": "Braga",
             "kingdom_id": "k_leon", "duchy_id": "d_galicia"},
        ],
        "barony_assignments": {},
    }
    result = MapResearchResult.model_validate(payload)
    assert result.barony_assignments == {}
    assert len(result.condados) == 1


def test_map_research_result_cross_reference_validator_raises_when_barony_assigned_to_unknown_condado_id():
    bad = {
        "kingdoms": {"k_leon": "León"},
        "duchies": {"d_galicia": {"kingdom_id": "k_leon", "name": "Galícia"}},
        "condados": [
            {"id": "C_BRAGA", "name": "Braga",
             "kingdom_id": "k_leon", "duchy_id": "d_galicia"},
        ],
        "barony_assignments": {"B_001": "C_BRAGA", "B_002": "C_TOLEDO"},
    }
    with pytest.raises(ValidationError) as exc_info:
        MapResearchResult.model_validate(bad)
    assert "C_TOLEDO" in str(exc_info.value)


def test_map_research_result_cross_reference_validator_passes_when_all_assignments_point_to_known_condados():
    result = MapResearchResult.model_validate(_MAP_TWO_CONDADOS)
    assert len(result.condados) == 2
    assert {c.id for c in result.condados} == {"C_BRAGA", "C_PORTO"}
    assert result.barony_assignments["B_002"] == "C_PORTO"


def test_legacy_research_result_still_works_after_schema_split():
    # Regression guard: adding MapResearchResult must NOT break the legacy path.
    result = ResearchResult.model_validate(_MINIMAL_VALID)
    assert result.condados[0].id == "C_ONE"
    assert result.condados[0].lon == -8.5
    assert result.condados[0].lat == 42.3
