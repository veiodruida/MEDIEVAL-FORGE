"""Tests for validate_barony_assignments — strict cross-check between LLM output
and the pre-built input barony list.

Locks in the contract: every input barony must be assigned, every assignment
key must be a real input barony id. ValueError is raised on violation so
run_with_retry re-prompts the LLM with the error message.
"""
import pytest

from medieval_forge.services.llm.schemas import MapResearchResult, validate_barony_assignments

# ---------------------------------------------------------------------------
# Shared fixture builder — 3 input baronies, 1 condado in a kingdom + duchy.
# ---------------------------------------------------------------------------
INPUT_BARONIES_3 = [
    {"id": "B_001", "name": "Braga",   "lon": -8.43, "lat": 41.55},
    {"id": "B_002", "name": "Porto",   "lon": -8.61, "lat": 41.15},
    {"id": "B_003", "name": "Coimbra", "lon": -8.42, "lat": 40.21},
]


def _make_result(barony_assignments: dict) -> MapResearchResult:
    """Build a minimal MapResearchResult with 1 kingdom, 1 duchy, 1 condado.

    The built-in model_validator only checks that assignment VALUES are known
    condado ids — so values MUST point to "C_BRAGA" here.
    """
    return MapResearchResult(
        kingdoms={"K_PORT": "Reino de Portugal"},
        duchies={"D_MINHO": {"kingdom_id": "K_PORT", "name": "Minho"}},
        condados=[
            {
                "id": "C_BRAGA",
                "name": "Condado de Braga",
                "kingdom_id": "K_PORT",
                "duchy_id": "D_MINHO",
            }
        ],
        barony_assignments=barony_assignments,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_validate_barony_assignments_passes_when_every_input_barony_is_assigned_to_known_condado():
    """Happy path: all 3 input baronies (B_001, B_002, B_003) mapped to C_BRAGA.

    validate_barony_assignments must return None and raise nothing.
    Fixture: B_001/B_002/B_003 → C_BRAGA (C_BRAGA is in condados[]).
    """
    result = _make_result(
        barony_assignments={
            "B_001": "C_BRAGA",
            "B_002": "C_BRAGA",
            "B_003": "C_BRAGA",
        }
    )

    outcome = validate_barony_assignments(result, INPUT_BARONIES_3)
    assert outcome is None  # strict: must return None, not True or any truthy object


def test_validate_barony_assignments_raises_when_assignment_key_is_not_an_input_barony_id():
    """Assignment key B_999_GHOST is not in the input barony list — must raise ValueError naming it.

    The error message must include the offending id so run_with_retry can append it
    to the correction text and steer the LLM on the next attempt.
    Fixture: assignments include B_999_GHOST which was never in INPUT_BARONIES_3.
    """
    result = _make_result(
        barony_assignments={
            "B_001": "C_BRAGA",
            "B_002": "C_BRAGA",
            "B_999_GHOST": "C_BRAGA",  # invented id — not in input list
        }
    )

    with pytest.raises(ValueError, match=r"B_999_GHOST"):
        validate_barony_assignments(result, INPUT_BARONIES_3)


def test_validate_barony_assignments_raises_when_at_least_one_input_barony_is_unassigned():
    """Coverage failure: B_002 and B_003 are in the input list but absent from assignments.

    Strict mode — even one missing barony is a validation failure so the LLM is
    re-prompted with the list of unassigned ids to fix on next attempt.
    Fixture: only B_001 assigned; B_002 and B_003 absent from barony_assignments.
    """
    result = _make_result(
        barony_assignments={
            "B_001": "C_BRAGA",
            # B_002 and B_003 deliberately omitted
        }
    )

    with pytest.raises(ValueError, match=r"unassigned|B_002|B_003"):
        validate_barony_assignments(result, INPUT_BARONIES_3)
