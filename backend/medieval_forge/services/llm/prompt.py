"""Prompt builder for LLM historical research requests.

D-06/D-07: LLM receives existing condados with id/name/lon/lat and must return
explicit assignments referencing condado ids from the provided list.
"""
from __future__ import annotations

import json

SYSTEM_INSTRUCTIONS = (
    "You output ONLY valid JSON matching the EXACT schema provided. "
    "You do NOT invent new top-level keys. You do NOT add prose, markdown, or explanations. "
    "You assign modern OSM condados to medieval kingdoms/duchies/baronies."
)

# Concrete minimal example — small local models copy structure from examples far
# more reliably than they follow abstract schema descriptions.
EXAMPLE_OUTPUT = """{
  "kingdoms": {
    "K_PORT": "Reino de Portugal",
    "K_LEON": "Reino de Leon"
  },
  "duchies": {
    "D_MINHO": { "kingdom_id": "K_PORT", "name": "Minho" },
    "D_LEON":  { "kingdom_id": "K_LEON", "name": "Leon" }
  },
  "condados_assignment": [
    { "condado_id": "12345", "kingdom_id": "K_PORT", "duchy_id": "D_MINHO" },
    { "condado_id": "67890", "kingdom_id": "K_LEON", "duchy_id": "D_LEON" }
  ],
  "baronies": {
    "12345": [ { "name": "Baronia de Braga", "lon": -8.43, "lat": 41.55 } ],
    "67890": [ { "name": "Baronia de Leon", "lon": -5.57, "lat": 42.60 } ]
  }
}"""

RULES = """CRITICAL RULES — any violation fails validation:
1. TOP-LEVEL KEYS ALLOWED: exactly "kingdoms", "duchies", "condados_assignment", "baronies". NOTHING ELSE.
   DO NOT emit keys like "regions", "historical_names", "cities", "provinces", "description".
2. kingdoms: object mapping <kingdom_id> to the kingdom's display name (a string).
3. duchies: object mapping <duchy_id> to an object with exactly two keys: "kingdom_id" and "name".
4. condados_assignment: array of objects, each with exactly "condado_id", "kingdom_id", "duchy_id".
5. baronies: object mapping <condado_id> to an array of {name, lon, lat}.
6. kingdom_id / duchy_id: short slugs you invent (e.g. "K_PORT", "D_MINHO").
7. condado_id: MUST be one of the ids from the provided list. Do NOT invent condado ids.
8. Output a SINGLE JSON object. No prose before or after. No ```json fences."""


def build_research_prompt(
    country_name: str,
    period_start: int,
    period_end: int,
    condados: list[dict],  # [{"id": "...", "name": "...", "lon": float, "lat": float}, ...]
) -> str:
    """Build the full research prompt string for LLM submission.

    Structure (order matters for small local models):
      1. System role instruction
      2. Example output (concrete, copy-paste shape)
      3. Hard rules with negative examples
      4. Task parameters (country + period)
      5. Condados list
      6. Final "go" instruction
    """
    condados_json = json.dumps(condados, ensure_ascii=False)
    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"EXAMPLE OUTPUT (follow this EXACT shape):\n{EXAMPLE_OUTPUT}\n\n"
        f"{RULES}\n\n"
        f"TASK:\n"
        f"Country: {country_name}\n"
        f"Period: {period_start} AD to {period_end} AD\n\n"
        f"Condados available (use ONLY these exact ids in condados_assignment and baronies):\n"
        f"{condados_json}\n\n"
        f"Now output the JSON object following the example shape. "
        f"Do not include any other top-level keys."
    )
