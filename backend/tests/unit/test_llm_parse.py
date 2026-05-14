"""Wave 0 gate: markdown fence-stripping wrapper around schemas.parse_research_json.

Manual-paste flow: external chat UIs (Claude.ai, ChatGPT, Gemini web) wrap JSON
output in ```json ... ``` fences. parse.parse_research_json strips fences first,
then delegates to the canonical lenient parser in schemas.py.
"""
from __future__ import annotations

import json

import pytest

from medieval_forge.services.llm.parse import (
    ResearchParseError,
    parse_research_json,
)
from medieval_forge.services.llm.schemas import ResearchResult


_VALID_JSON = json.dumps(
    {
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
            "C_LEON": [{"name": "Astorga", "lon": -6.054, "lat": 42.457}]
        },
    }
)


def test_parse_research_json_accepts_raw_json_without_markdown_fences():
    result = parse_research_json(_VALID_JSON)
    assert isinstance(result, ResearchResult)
    assert result.kingdoms == {"K_LEON": "Reino de Leon"}
    assert result.condados[0].id == "C_LEON"


def test_parse_research_json_strips_triple_backtick_json_fences_added_by_chat_uis():
    fenced = f"```json\n{_VALID_JSON}\n```"
    result = parse_research_json(fenced)
    assert isinstance(result, ResearchResult)
    assert result.condados[0].name == "Condado de Leon"


def test_parse_research_json_strips_plain_triple_backtick_fences_without_language_tag():
    fenced = f"```\n{_VALID_JSON}\n```"
    result = parse_research_json(fenced)
    assert isinstance(result, ResearchResult)
    assert len(result.condados) == 1


def test_parse_research_json_raises_research_parse_error_on_malformed_payload():
    """Malformed JSON wrapped in fences yields ResearchParseError, not a raw ValidationError."""
    with pytest.raises(ResearchParseError):
        parse_research_json("```json\n{not valid json}\n```")
