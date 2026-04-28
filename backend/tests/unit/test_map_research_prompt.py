"""Tests for build_map_research_prompt — the new baronies-aware prompt builder.

Locks in the contract that the LLM receives a concrete barony list and is told
to emit barony_assignments (not invent baronies). Three behavioral tests.
"""
import pytest

from medieval_forge.services.llm.prompt import build_map_research_prompt

# ---------------------------------------------------------------------------
# Shared fixture: 3 explicit baronies for Iberia 868 AD
# ---------------------------------------------------------------------------
BARONIES_3 = [
    {"id": "B_001", "name": "Braga",   "lon": -8.43, "lat": 41.55},
    {"id": "B_002", "name": "Porto",   "lon": -8.61, "lat": 41.15},
    {"id": "B_003", "name": "Coimbra", "lon": -8.42, "lat": 40.21},
]


def test_build_map_research_prompt_lists_every_input_barony_with_id_name_lon_lat():
    """Prompt must echo every input barony: id, name, lon (-2dp), lat (-2dp).

    The LLM needs the full list so it can assign baronies to condados.
    Fixture: Iberia 868 AD with 3 baronies — Braga (B_001), Porto (B_002), Coimbra (B_003).
    Coordinates supplied as float literals; prompt must contain them formatted to ≥2 decimals.
    """
    prompt = build_map_research_prompt(
        country_name="Iberia",
        period_start=868,
        baronies=BARONIES_3,
    )

    # All three barony ids must appear verbatim
    assert "B_001" in prompt
    assert "B_002" in prompt
    assert "B_003" in prompt

    # All three barony names must appear verbatim
    assert "Braga" in prompt
    assert "Porto" in prompt
    assert "Coimbra" in prompt

    # Coordinates must appear (formatted to at least 2 decimal places)
    assert "-8.43" in prompt
    assert "41.55" in prompt
    assert "-8.61" in prompt
    assert "41.15" in prompt
    assert "-8.42" in prompt
    assert "40.21" in prompt


def test_build_map_research_prompt_instructs_llm_to_emit_barony_assignments_dict_with_input_ids_only():
    """Prompt must instruct the LLM to fill barony_assignments using ONLY the supplied ids.

    Critical to prevent the LLM from inventing barony_ids that don't exist in the
    pre-built OSM barony list. The prompt must:
    - Name the 'barony_assignments' key explicitly.
    - Tell the LLM keys must come from the provided list (not invented).
    - Name the 4 allowed top-level keys (kingdoms, duchies, condados, barony_assignments).
    - NOT mention the legacy 'baronies' top-level key (old schema was replaced).
    """
    prompt = build_map_research_prompt(
        country_name="Iberia",
        period_start=868,
        baronies=BARONIES_3,
    )

    # Must name the output key
    assert "barony_assignments" in prompt

    # Must restrict barony_id keys to the supplied list.
    # Exact substring test: "MUST be one of the barony_ids listed above"
    assert "MUST be one of the barony_ids listed above" in prompt

    # All four allowed top-level keys must be present in prompt (so LLM schema is clear)
    assert "kingdoms" in prompt
    assert "duchies" in prompt
    assert "condados" in prompt

    # Legacy 'baronies' top-level key must NOT appear as an ALLOWED output key.
    # The old schema had "TOP-LEVEL KEYS ALLOWED: ... baronies" — the new schema replaces
    # it with barony_assignments. The prompt may mention "baronies" as a forbidden example
    # (e.g. "DO NOT emit keys like 'baronies'"), but must not list it under ALLOWED keys.
    # Negative check: the allowed-keys rule must not name "baronies" as permitted.
    assert "baronies" not in [
        k.strip().strip('"')
        for k in prompt.split("TOP-LEVEL KEYS ALLOWED:")[-1].split("\n")[0].split(",")
    ]


def test_build_map_research_prompt_uses_period_start_year_and_optional_bbox_when_supplied():
    """period_start, period_end, and bbox all appear in the prompt when provided.

    Ensures the LLM receives temporal anchoring (868 AD start, 1492 AD end) and
    geographic bounding box for coordinate accuracy.
    Fixture: bbox=(-9.5, 36.0, 3.3, 43.8) — Iberian Peninsula bounds.
    """
    single_barony = [{"id": "B_001", "name": "Braga", "lon": -8.43, "lat": 41.55}]

    prompt = build_map_research_prompt(
        country_name="Iberia",
        period_start=868,
        period_end=1492,
        baronies=single_barony,
        bbox=(-9.5, 36.0, 3.3, 43.8),
    )

    # Both years must appear
    assert "868" in prompt
    assert "1492" in prompt

    # Bounding box values must appear (formatted via :.2f so -9.5 → "-9.50")
    assert "-9.50" in prompt
    assert "43.80" in prompt
