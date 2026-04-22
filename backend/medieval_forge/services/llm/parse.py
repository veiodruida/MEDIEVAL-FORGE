"""Manual endpoint JSON parser — fence-stripping wrapper around schemas.parse_research_json.

The manual flow accepts pasted LLM output that may be wrapped in markdown code fences
(```json ... ```) since external chat UIs (Claude.ai, ChatGPT, Gemini web) add them
automatically. This module strips the fences before delegating to the canonical
lenient parser in schemas.py, so SSE and manual paths use identical validation logic.
"""
from __future__ import annotations

from pydantic import ValidationError

from .schemas import ResearchResult, parse_research_json as _parse_strict


class ResearchParseError(ValueError):
    """Raised when raw text cannot be parsed into a ResearchResult."""


def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences (``` or ```json)."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    # Drop the opening fence line
    first_newline = stripped.find("\n")
    if first_newline == -1:
        # Single-line fence with no content
        return stripped[3:].lstrip()
    stripped = stripped[first_newline + 1:]
    # Drop trailing fence
    if stripped.rstrip().endswith("```"):
        stripped = stripped.rstrip()[:-3].rstrip()
    return stripped


def parse_research_json(raw: str) -> ResearchResult:
    """Parse raw text (with optional markdown fences) into a ResearchResult.

    Strips ```json ... ``` fences then delegates to the canonical lenient
    parser (schemas.parse_research_json) which handles extra top-level keys
    from small local models.

    Raises:
        ResearchParseError: if the text cannot be parsed into ResearchResult.
    """
    text = _strip_fences(raw)
    try:
        return _parse_strict(text)
    except (ValidationError, ValueError) as e:
        raise ResearchParseError(str(e)) from e
