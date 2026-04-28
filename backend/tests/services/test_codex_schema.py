"""Etapa 9 (master plan H.9 / quick-260428-l0l): CodexResult Pydantic schema.

The CodexResult schema is a 12-category historical-narrative payload generated
by the Codex pipeline. Each category holds a free-text summary plus a list of
CodexEntity objects whose .description field carries markdown-rendered prose.

extra='forbid' is the critical guarantee: small local models that bolt on extra
top-level keys like "weather" must fail validation so retry can re-prompt.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


_CATEGORIES_12 = (
    "currency", "attributes", "health", "traits",
    "feudal", "politics", "dynasty", "religion",
    "culture", "economy", "military", "events",
)


def _empty_payload() -> dict:
    return {cat: {} for cat in _CATEGORIES_12}


def test_codex_result_accepts_minimal_payload_with_all_12_category_keys():
    """All 12 category keys present (each empty: summary='' + entries=[]) → parses."""
    from medieval_forge.services.llm.schemas import CodexResult

    result = CodexResult.model_validate(_empty_payload())
    # Sentinels: first + last category in the canonical order.
    assert result.currency is not None
    assert result.events is not None
    # Default shape: empty entries list + empty summary.
    assert result.currency.entries == []
    assert result.events.summary == ""


def test_codex_result_rejects_unknown_top_level_key():
    """Adding a non-canonical key like 'weather' triggers ValidationError (extra='forbid')."""
    from medieval_forge.services.llm.schemas import CodexResult

    payload = _empty_payload()
    payload["weather"] = {"summary": "rainy"}

    with pytest.raises(ValidationError) as exc_info:
        CodexResult.model_validate(payload)
    # Pydantic v2 reports extra-key violations with type 'extra_forbidden'.
    err_text = str(exc_info.value)
    assert "weather" in err_text
    assert ("extra" in err_text.lower() or "not permitted" in err_text.lower())


def test_codex_entity_requires_id_name_description_markdown():
    """CodexEntity needs id+name+description; missing description raises."""
    from medieval_forge.services.llm.schemas import CodexEntity

    ok = CodexEntity.model_validate({
        "id": "DYN_HOUSE_OF_LEON",
        "name": "Casa de Leão",
        "description": "**Fundada** em 910 por Garcia I.",
    })
    assert ok.id == "DYN_HOUSE_OF_LEON"
    assert ok.name == "Casa de Leão"
    assert "**Fundada**" in ok.description

    with pytest.raises(ValidationError):
        CodexEntity.model_validate({
            "id": "DYN_HOUSE_OF_LEON",
            "name": "Casa de Leão",
            # description deliberately missing
        })


def test_codex_dynasty_category_holds_list_of_entities_with_markdown_descriptions():
    """The dynasty category stores entries: list[CodexEntity], parses 2-entry input."""
    from medieval_forge.services.llm.schemas import CodexResult

    payload = _empty_payload()
    payload["dynasty"] = {
        "summary": "Duas casas dominantes em 868 AD.",
        "entries": [
            {"id": "DYN_LEON",  "name": "Casa de Leão",
             "description": "**Casa real** de Leão."},
            {"id": "DYN_PORT",  "name": "Casa de Portucale",
             "description": "_Linhagem condal_ portucalense."},
        ],
    }

    result = CodexResult.model_validate(payload)
    assert isinstance(result.dynasty.entries, list)
    assert len(result.dynasty.entries) == 2
    assert result.dynasty.entries[0].id == "DYN_LEON"
    assert "**Casa real**" in result.dynasty.entries[0].description


def test_codex_result_round_trips_through_model_dump_and_validate():
    """1 entry per category (12 entries total) → dump → re-validate → equality."""
    from medieval_forge.services.llm.schemas import CodexResult

    payload: dict = {}
    for i, cat in enumerate(_CATEGORIES_12):
        payload[cat] = {
            "summary": f"summary-of-{cat}",
            "entries": [{
                "id": f"ENT_{cat.upper()}_{i:02d}",
                "name": f"Entry {i} for {cat}",
                "description": f"**markdown** for {cat} #{i}.",
            }],
        }

    first = CodexResult.model_validate(payload)
    dumped = first.model_dump()
    second = CodexResult.model_validate(dumped)
    assert first == second
    # Sanity: 12 entries total round-trip cleanly.
    total_entries = sum(len(getattr(second, c).entries) for c in _CATEGORIES_12)
    assert total_entries == 12
