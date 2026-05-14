# Plan 07-04 Task 3 — sanitize.escape_condado_name unit tests (REVIEWS soft Qwen3).
"""Unit tests for the prompt-injection-sigil sanitizer."""
from __future__ import annotations

from medieval_forge.services.llm.sanitize import escape_condado_name


def test_escape_condado_name_strips_closing_html_tags():
    """`</script>` sigil stripped while preserving readable text after it.

    Contract: `</` literal two-char strip — `"Foo</script>"` -> `"Fooscript>"`.
    """
    assert escape_condado_name("Foo</script>") == "Fooscript>"
    assert escape_condado_name("a</b>") == "ab>"


def test_escape_condado_name_strips_double_braces():
    """Jinja/Handlebars-style `{{` and `}}` stripped."""
    assert escape_condado_name("{{system.prompt}}") == "system.prompt"
    assert escape_condado_name("Foo{{x}}Bar") == "FooxBar"


def test_escape_condado_name_preserves_normal_unicode_names():
    """Normal vernacular names (incl. accented chars) pass through unchanged."""
    assert escape_condado_name("Reino de Asturias") == "Reino de Asturias"
    assert escape_condado_name("Condado de Castela") == "Condado de Castela"
    assert escape_condado_name("Galícia") == "Galícia"


def test_escape_condado_name_handles_empty_and_whitespace_only_input():
    """Empty string -> empty; whitespace stripped at boundaries; None -> empty."""
    assert escape_condado_name("") == ""
    assert escape_condado_name("   ") == ""
    assert escape_condado_name("  Foo  ") == "Foo"
    assert escape_condado_name(None) == ""


def test_escape_condado_name_is_idempotent():
    """Sanitizing twice gives the same result as sanitizing once."""
    inputs = ["Foo</bar>", "{{evil}}", "Reino de Asturias", "  spaced  "]
    for name in inputs:
        once = escape_condado_name(name)
        twice = escape_condado_name(once)
        assert once == twice
