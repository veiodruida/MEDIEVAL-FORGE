"""Prompt builder for LLM historical research requests.

D-06/D-07: LLM receives existing condados with id/name/lon/lat and must return
explicit assignments referencing condado ids from the provided list.
"""
from __future__ import annotations

import json

SYSTEM_INSTRUCTIONS = (
    "You are a historical-research assistant. Assign the following modern OSM condados "
    "to medieval historical counties. Each entry: {id, name, lon, lat}. "
    "Your response must reference condados by their id."
)


def build_research_prompt(
    country_name: str,
    period_start: int,
    period_end: int,
    condados: list[dict],  # [{"id": "...", "name": "...", "lon": float, "lat": float}, ...]
) -> str:
    """Build the full research prompt string for LLM submission.

    The returned string includes SYSTEM_INSTRUCTIONS, country/period context,
    and an inline JSON list of all condados with id/name/lon/lat (D-07).
    """
    condados_json = json.dumps(condados, ensure_ascii=False)
    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"Country: {country_name}\n"
        f"Period: {period_start} AD to {period_end} AD\n\n"
        f"Condados (assign every kingdom/duchy/condado_id you reference):\n{condados_json}\n\n"
        "Return the JSON object now."
    )
