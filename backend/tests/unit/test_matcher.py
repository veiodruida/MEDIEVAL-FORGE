"""Unit tests for services/research/matcher.py — Plan 07-06.

Six cases per plan <behavior>:
    1. build_pipeline_condado_list works on Iberia-curated slugs.
    2. build_pipeline_condado_list works on autogen `Condado_NNN` placeholders.
    3. llm_output_to_overlay collapses hierarchy keyed by condado id with
       name + kingdom_owner.
    4. llm_output_to_overlay drops unknown condado ids (T-07-06-01).
    5. llm_output_to_overlay handles empty/missing historical_notes.
    6. NIT 3: missing OR empty kingdom name -> kingdom_owner is None
       (NOT empty string).

Fixtures use explicit numeric/string values (user preference: tests with
descriptive names + explicit numeric fixtures).
"""
from __future__ import annotations

from medieval_forge.services.research.matcher import (
    build_pipeline_condado_list,
    llm_output_to_overlay,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

IBERIA_METADATA = {
    "condados": [
        {"id": "oviedo", "lon": -5.844, "lat": 43.362, "original_idx": 0},
        {"id": "leon", "lon": -5.567, "lat": 42.598, "original_idx": 1},
        {"id": "burgos", "lon": -3.701, "lat": 42.341, "original_idx": 2},
    ],
}

AUTOGEN_METADATA = {
    "condados": [
        {"id": "Condado_001", "lon": -1.234, "lat": 40.5, "original_idx": 0},
        {"id": "Condado_002", "lon": -1.456, "lat": 41.0, "original_idx": 1},
        {"id": "Condado_003", "lon": -1.789, "lat": 41.5, "original_idx": 2},
    ],
}

# Hierarchical LLM payload covering all three Iberia condados.
LLM_RESULT_IBERIA = {
    "kingdoms": [
        {
            "name": "Reino de Asturias",
            "duchies": [
                {
                    "name": "Ducado de Oviedo",
                    "condados": [
                        {
                            "id": "oviedo",
                            "name": "Condado de Oviedo",
                            "historical_notes": "Capital del reino tras 791.",
                        },
                        {
                            "id": "leon",
                            "name": "Condado de León",
                            "historical_notes": "Sede episcopal desde 854.",
                        },
                    ],
                },
            ],
        },
        {
            "name": "Reino de Castilla",
            "duchies": [
                {
                    "name": "Ducado de Burgos",
                    "condados": [
                        {
                            "id": "burgos",
                            "name": "Condado de Burgos",
                            "historical_notes": "Fundada 884 por Diego Rodríguez.",
                        },
                    ],
                },
            ],
        },
    ],
}

# LLM payload that contains an UNKNOWN condado id ("toledo") which is NOT in
# the pipeline_condado_ids set — must be dropped (T-07-06-01).
LLM_RESULT_WITH_UNKNOWN_ID = {
    "kingdoms": [
        {
            "name": "Reino de Asturias",
            "duchies": [
                {
                    "name": "Ducado X",
                    "condados": [
                        {"id": "oviedo", "name": "Condado de Oviedo", "historical_notes": "ok"},
                        {"id": "toledo", "name": "Condado de Toledo", "historical_notes": "drop me"},
                    ],
                },
            ],
        },
    ],
}

# LLM payload where one condado is missing `historical_notes` entirely and the
# other has an empty string. Both must yield non-error overlays (Task 1 Test 5).
LLM_RESULT_EMPTY_NOTES = {
    "kingdoms": [
        {
            "name": "Reino de Asturias",
            "duchies": [
                {
                    "name": "Ducado A",
                    "condados": [
                        {"id": "oviedo", "name": "Condado de Oviedo"},
                        {"id": "leon", "name": "Condado de León", "historical_notes": ""},
                    ],
                },
            ],
        },
    ],
}

# NIT 3: one kingdom has `name: ""` (empty string), the other has no `name`
# key at all. BOTH cases must collapse to kingdom_owner=None.
LLM_RESULT_MISSING_KINGDOM_NAME = {
    "kingdoms": [
        {
            "name": "",
            "duchies": [
                {
                    "name": "Ducado A",
                    "condados": [
                        {"id": "oviedo", "name": "Condado de Oviedo"},
                    ],
                },
            ],
        },
        {
            # no 'name' key at all
            "duchies": [
                {
                    "name": "Ducado B",
                    "condados": [
                        {"id": "leon", "name": "Condado de León"},
                    ],
                },
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# build_pipeline_condado_list
# ---------------------------------------------------------------------------

def test_build_pipeline_condado_list_extracts_id_lon_lat_per_condado_for_iberia():
    result = build_pipeline_condado_list(IBERIA_METADATA)
    assert result == [
        {"id": "oviedo", "lon": -5.844, "lat": 43.362},
        {"id": "leon", "lon": -5.567, "lat": 42.598},
        {"id": "burgos", "lon": -3.701, "lat": 42.341},
    ]


def test_build_pipeline_condado_list_extracts_id_lon_lat_per_condado_for_autogen_condado_nnn():
    result = build_pipeline_condado_list(AUTOGEN_METADATA)
    assert result == [
        {"id": "Condado_001", "lon": -1.234, "lat": 40.5},
        {"id": "Condado_002", "lon": -1.456, "lat": 41.0},
        {"id": "Condado_003", "lon": -1.789, "lat": 41.5},
    ]


# ---------------------------------------------------------------------------
# llm_output_to_overlay
# ---------------------------------------------------------------------------

def test_llm_output_to_overlay_collapses_hierarchy_keyed_by_condado_id_with_name_and_kingdom_owner():
    pipeline_ids = {"oviedo", "leon", "burgos"}
    overlay = llm_output_to_overlay(LLM_RESULT_IBERIA, pipeline_ids)
    assert overlay == {
        "oviedo": {
            "name": "Condado de Oviedo",
            "kingdom_owner": "Reino de Asturias",
            "historical_notes": "Capital del reino tras 791.",
        },
        "leon": {
            "name": "Condado de León",
            "kingdom_owner": "Reino de Asturias",
            "historical_notes": "Sede episcopal desde 854.",
        },
        "burgos": {
            "name": "Condado de Burgos",
            "kingdom_owner": "Reino de Castilla",
            "historical_notes": "Fundada 884 por Diego Rodríguez.",
        },
    }


def test_llm_output_to_overlay_drops_unknown_condado_ids():
    # pipeline only knows 'oviedo' — 'toledo' must be silently dropped.
    overlay = llm_output_to_overlay(LLM_RESULT_WITH_UNKNOWN_ID, {"oviedo"})
    assert "toledo" not in overlay
    assert set(overlay.keys()) == {"oviedo"}
    assert overlay["oviedo"]["historical_notes"] == "ok"


def test_llm_output_to_overlay_handles_empty_historical_notes():
    overlay = llm_output_to_overlay(LLM_RESULT_EMPTY_NOTES, {"oviedo", "leon"})
    # 'oviedo' had no historical_notes key at all -> None.
    assert overlay["oviedo"]["historical_notes"] is None
    # 'leon' had historical_notes == "" -> preserved as empty string (it IS
    # present; matcher does NOT collapse empty strings on this field — only
    # NIT 3's kingdom_owner has the empty-string-to-None semantics).
    assert overlay["leon"]["historical_notes"] == ""


def test_llm_output_to_overlay_sets_kingdom_owner_none_when_kingdom_name_missing():
    overlay = llm_output_to_overlay(LLM_RESULT_MISSING_KINGDOM_NAME, {"oviedo", "leon"})
    # NIT 3: both the empty-string case AND the missing-key case yield None.
    assert overlay["oviedo"]["kingdom_owner"] is None
    assert overlay["leon"]["kingdom_owner"] is None
