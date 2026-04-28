"""Etapa 9 (master plan H.9 / quick-260428-l0l): build_codex_prompt.

The Codex prompt instructs the LLM to emit JSON matching CodexResult — 12
categories of medieval narrative entries, each with markdown descriptions.
"""
from __future__ import annotations


_CATEGORIES_12 = (
    "currency", "attributes", "health", "traits",
    "feudal", "politics", "dynasty", "religion",
    "culture", "economy", "military", "events",
)


def test_build_codex_prompt_includes_country_period_and_all_12_categories():
    """Country name, both period years, and every category label appear."""
    from medieval_forge.services.llm.prompt import build_codex_prompt

    prompt = build_codex_prompt(
        country_name="Ibéria",
        period_start=868,
        period_end=1100,
        map_summary="3 reinos, 12 condados, 250 baronies",
    )

    assert "Ibéria" in prompt
    assert "868" in prompt
    assert "1100" in prompt
    for cat in _CATEGORIES_12:
        assert cat in prompt, f"category '{cat}' missing from prompt"


def test_build_codex_prompt_focus_sections_filters_when_provided():
    """focus_sections=['dynasty','religion'] → FOCUS line names ONLY those two."""
    from medieval_forge.services.llm.prompt import build_codex_prompt

    prompt = build_codex_prompt(
        country_name="Ibéria",
        period_start=868,
        period_end=1100,
        map_summary="map-summary-here",
        focus_sections=["dynasty", "religion"],
    )

    assert "FOCUS" in prompt
    # The FOCUS hint must mention the two requested sections.
    focus_line = next(
        (ln for ln in prompt.splitlines() if ln.startswith("FOCUS")),
        "",
    )
    assert "dynasty" in focus_line
    assert "religion" in focus_line
    # And must NOT name unrelated categories on that focus line.
    assert "currency" not in focus_line
    assert "military" not in focus_line
    # The full schema (all 12 keys) is still listed elsewhere for shape reference.
    for cat in _CATEGORIES_12:
        assert cat in prompt


def test_build_codex_prompt_includes_json_example_matching_codex_result_shape():
    """Prompt embeds an EXAMPLE OUTPUT block with first+last category sentinels."""
    from medieval_forge.services.llm.prompt import build_codex_prompt

    prompt = build_codex_prompt(
        country_name="Ibéria",
        period_start=868,
        period_end=1100,
        map_summary="ms",
    )

    assert "EXAMPLE OUTPUT" in prompt
    # The example payload contains the first+last category names in the canonical order.
    # Use them as sentinels for "JSON example reflects CodexResult shape".
    assert '"currency"' in prompt
    assert '"events"' in prompt
