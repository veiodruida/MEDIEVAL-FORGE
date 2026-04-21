"""Pydantic ResearchResult schema mirroring the territory_data_v3.py hierarchy.

D-27: extra='forbid' on all models rejects unknown fields from LLM output.
Shape: kingdoms / duchies / condados_assignment / baronies — four-tier hierarchy.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Barony(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    lon: float
    lat: float


class CondadoAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condado_id: str           # OSM id; validated post-parse against provided list (D-09)
    kingdom_id: str
    duchy_id: str


class ResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdoms: dict[str, str]                       # id -> display_name
    duchies: dict[str, tuple[str, str]]            # id -> (kingdom_id, display_name)
    condados_assignment: list[CondadoAssignment]
    baronies: dict[str, list[Barony]]              # condado_id -> baronies
