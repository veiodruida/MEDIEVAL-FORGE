"""SC-2 review-fix #5 — runner.py resolves country_qid to display name for prompts.

Implemented in plan 07.1-04. Locks the contract introduced by review feedback
(Gemini MEDIUM): local LLMs hallucinate when given Wikidata Q-codes verbatim.
"""
import logging

import pytest

from medieval_forge.services.research.runner import (
    _QID_DISPLAY_NAMES,
    _resolve_country_display_name,
)
from medieval_forge.services.llm.prompt import build_research_prompt


def test_qid_display_names_dict_includes_known_qids() -> None:
    assert _QID_DISPLAY_NAMES["Q29"] == "Espanha"
    assert _QID_DISPLAY_NAMES["Q45"] == "Portugal"
    assert _QID_DISPLAY_NAMES["Q43175"] == "Ibéria"


def test_resolve_country_display_name_known_qid_returns_display_name() -> None:
    assert _resolve_country_display_name("Q29") == "Espanha"
    assert _resolve_country_display_name("Q45") == "Portugal"


def test_resolve_country_display_name_accepts_iso_2_alpha_aliases() -> None:
    """Projects persist ISO-3166 codes (ES/PT/FR/GB) in country_qid when
    created without a Wikidata lookup. Resolver must map them to the same
    PT-BR display name so prompts don't include raw ISO codes."""
    assert _resolve_country_display_name("ES") == "Espanha"
    assert _resolve_country_display_name("PT") == "Portugal"
    assert _resolve_country_display_name("FR") == "França"


def test_resolve_country_display_name_unknown_qid_falls_back_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    out = _resolve_country_display_name("Q99999")
    assert out == "Q99999"
    assert any(
        rec.levelno >= logging.WARNING and "Q99999" in rec.getMessage()
        for rec in caplog.records
    ), "expected WARNING log on unknown QID fallback"


def test_runner_resolves_qid_to_display_name_in_prompt() -> None:
    """End-to-end: feed the resolver output into build_research_prompt; assert
    the rendered prompt contains the display name and not the raw QID."""
    name = _resolve_country_display_name("Q29")
    prompt = build_research_prompt(
        country_name=name,
        period_start=868,
        period_end=1000,
        bbox=None,
    )
    assert "Espanha" in prompt
    assert "Q29" not in prompt
