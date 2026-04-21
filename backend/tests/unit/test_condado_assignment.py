"""Tests for condado assignment validation (D-09, RESEARCH-07).

Wave 0 test scaffolding — tests define the contract; implementation comes in Task 2.
"""
from __future__ import annotations

import pytest


def test_unknown_condado_id_raises_validation_error():
    """validate_assignment_against_condados raises ValueError when LLM returns unknown id."""
    from medieval_forge.services.research_runner import validate_assignment_against_condados
    from medieval_forge.services.llm.schemas import ResearchResult, CondadoAssignment

    result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": ("k1", "Duchy of Leon")},
        condados_assignment=[
            CondadoAssignment(condado_id="not-in-project", kingdom_id="k1", duchy_id="d1")
        ],
        baronies={},
    )
    with pytest.raises(ValueError):
        validate_assignment_against_condados(result, known_ids={"c1", "c2"})


def test_all_known_condado_ids_passes():
    """validate_assignment_against_condados does not raise when all ids are known."""
    from medieval_forge.services.research_runner import validate_assignment_against_condados
    from medieval_forge.services.llm.schemas import ResearchResult, CondadoAssignment

    result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": ("k1", "Duchy of Leon")},
        condados_assignment=[
            CondadoAssignment(condado_id="c1", kingdom_id="k1", duchy_id="d1"),
            CondadoAssignment(condado_id="c2", kingdom_id="k1", duchy_id="d1"),
        ],
        baronies={},
    )
    # Should not raise
    validate_assignment_against_condados(result, known_ids={"c1", "c2"})


def test_partial_assignment_allowed():
    """Not every known id needs to appear in the assignment — only referenced ids must be valid."""
    from medieval_forge.services.research_runner import validate_assignment_against_condados
    from medieval_forge.services.llm.schemas import ResearchResult, CondadoAssignment

    # LLM only assigned c1, but c2 and c3 also exist in the project (legitimate omission).
    result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": ("k1", "Duchy of Leon")},
        condados_assignment=[
            CondadoAssignment(condado_id="c1", kingdom_id="k1", duchy_id="d1"),
        ],
        baronies={},
    )
    # Should not raise — partial assignment is fine as long as referenced ids exist
    validate_assignment_against_condados(result, known_ids={"c1", "c2", "c3"})
