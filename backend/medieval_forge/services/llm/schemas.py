"""Pydantic ResearchResult schema mirroring the territory_data_v3.py hierarchy.

D-27: extra='forbid' on all models rejects unknown fields from LLM output.
Shape: kingdoms / duchies / condados_assignment / baronies — four-tier hierarchy.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


# Top-level keys that ResearchResult accepts. Used to sanitize LLM output that
# adds extra keys (small local models often add "regions", "historical_names",
# "cities", "description" etc. that break strict validation).
_RESEARCH_RESULT_KEYS = frozenset({"kingdoms", "duchies", "condados_assignment", "baronies"})


def parse_research_json(text: str) -> "ResearchResult":
    """Parse raw LLM JSON into ResearchResult with lenient fallback.

    1. Try strict validation (extra='forbid' as declared).
    2. If that fails, strip any top-level keys not in _RESEARCH_RESULT_KEYS
       and retry. This lets small local models (qwen2.5:7b, llama3.2:3b) that
       insist on adding metadata keys still succeed if their core structure is right.
    3. If still invalid, raise the ORIGINAL strict error (more informative than
       the second-pass error).
    """
    try:
        return ResearchResult.model_validate_json(text)
    except ValidationError as strict_err:
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError:
            raise strict_err
        if not isinstance(data, dict):
            raise strict_err
        stripped = {k: v for k, v in data.items() if k in _RESEARCH_RESULT_KEYS}
        try:
            return ResearchResult.model_validate(stripped)
        except ValidationError:
            # Surface the strict error — it tells the LLM exactly which key is wrong.
            raise strict_err


class Barony(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    lon: float
    lat: float


class Duchy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdom_id: str
    name: str


class CondadoAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condado_id: str           # OSM id; validated post-parse against provided list (D-09)
    kingdom_id: str
    duchy_id: str


class ResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdoms: dict[str, str]                       # id -> display_name
    duchies: dict[str, Duchy]                      # id -> Duchy(kingdom_id, name)
    condados_assignment: list[CondadoAssignment]
    baronies: dict[str, list[Barony]]              # condado_id -> baronies
