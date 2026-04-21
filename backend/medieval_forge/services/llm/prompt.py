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

OUTPUT_FORMAT_SPEC = """Return ONLY a JSON object with this exact shape (no prose, no markdown fences):
{
  "kingdoms": { "<kingdom_id>": "<kingdom_name>", ... },
  "duchies":  { "<duchy_id>": { "kingdom_id": "<kingdom_id>", "name": "<duchy_name>" }, ... },
  "condados_assignment": [
    { "condado_id": "<one of the ids provided below>", "kingdom_id": "<a kingdom_id>", "duchy_id": "<a duchy_id>" },
    ...
  ],
  "baronies": {
    "<condado_id>": [ { "name": "<barony_name>", "lon": <float>, "lat": <float> }, ... ],
    ...
  }
}

Rules:
- kingdom_id / duchy_id: short slugs you invent (e.g. "K_PORT", "D_MINHO").
- condado_id: MUST be one of the ids from the list provided below — do not invent new condado ids.
- Every condado from the list should appear once in condados_assignment.
- baronies keys must be condado_ids from the list; each barony has name and centroid coordinates.
- No extra fields. Valid JSON only."""


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
        f"Condados available (use these exact ids):\n{condados_json}\n\n"
        f"{OUTPUT_FORMAT_SPEC}"
    )
