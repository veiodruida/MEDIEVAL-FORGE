"""Tests for validate_condados_self_consistency (replaces old condado_assignment validator).

The LLM now generates condados freely. Validation checks internal referential
integrity: duchy/condado kingdom_id refs, condado duchy_id refs, barony keys.
"""
from __future__ import annotations

import pytest

from medieval_forge.services.research_runner import validate_condados_self_consistency
from medieval_forge.services.llm.schemas import ResearchResult, Condado, Duchy


def _make_valid_result(**overrides) -> ResearchResult:
    data = {
        "kingdoms": {"k1": "Leon"},
        "duchies": {"d1": {"kingdom_id": "k1", "name": "Duchy of Leon"}},
        "condados": [
            {"id": "C_ONE", "name": "Condado One", "lon": -5.5, "lat": 42.6,
             "kingdom_id": "k1", "duchy_id": "d1"},
        ],
        "baronies": {"C_ONE": []},
    }
    data.update(overrides)
    return ResearchResult.model_validate(data)


def test_valid_result_passes():
    validate_condados_self_consistency(_make_valid_result())


def test_duchy_references_unknown_kingdom_raises():
    result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": Duchy(kingdom_id="K_GHOST", name="Bad Duchy")},
        condados=[
            Condado(id="C_ONE", name="One", lon=-5.5, lat=42.6,
                    kingdom_id="k1", duchy_id="d1"),
        ],
        baronies={},
    )
    with pytest.raises(ValueError, match="kingdom_id"):
        validate_condados_self_consistency(result)


def test_condado_references_unknown_kingdom_raises():
    result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": Duchy(kingdom_id="k1", name="Duchy of Leon")},
        condados=[
            Condado(id="C_ONE", name="One", lon=-5.5, lat=42.6,
                    kingdom_id="K_GHOST", duchy_id="d1"),
        ],
        baronies={},
    )
    with pytest.raises(ValueError, match="kingdom_id"):
        validate_condados_self_consistency(result)


def test_condado_references_unknown_duchy_raises():
    result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": Duchy(kingdom_id="k1", name="Duchy of Leon")},
        condados=[
            Condado(id="C_ONE", name="One", lon=-5.5, lat=42.6,
                    kingdom_id="k1", duchy_id="D_GHOST"),
        ],
        baronies={},
    )
    with pytest.raises(ValueError, match="duchy_id"):
        validate_condados_self_consistency(result)


def test_barony_key_not_matching_condado_raises():
    result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": Duchy(kingdom_id="k1", name="Duchy of Leon")},
        condados=[
            Condado(id="C_ONE", name="One", lon=-5.5, lat=42.6,
                    kingdom_id="k1", duchy_id="d1"),
        ],
        baronies={"C_GHOST": []},
    )
    with pytest.raises(ValueError, match="baronies key"):
        validate_condados_self_consistency(result)


def test_multiple_condados_all_valid_passes():
    result = ResearchResult(
        kingdoms={"k1": "Leon", "k2": "Portugal"},
        duchies={
            "d1": Duchy(kingdom_id="k1", name="Duchy Leon"),
            "d2": Duchy(kingdom_id="k2", name="Duchy Minho"),
        },
        condados=[
            Condado(id="C_ONE", name="One", lon=-5.5, lat=42.6,
                    kingdom_id="k1", duchy_id="d1"),
            Condado(id="C_TWO", name="Two", lon=-8.4, lat=41.5,
                    kingdom_id="k2", duchy_id="d2"),
        ],
        baronies={"C_ONE": [], "C_TWO": []},
    )
    validate_condados_self_consistency(result)
