"""Prompt builder for LLM historical research requests.

The LLM generates the full territorial hierarchy from scratch at the START of
the historical period. It invents historically-attested condados (counties) with
coordinates — no pre-supplied OSM list is provided.
"""
from __future__ import annotations

SYSTEM_INSTRUCTIONS = (
    "You output ONLY valid JSON matching the EXACT schema provided. "
    "You do NOT invent new top-level keys. You do NOT add prose, markdown, or explanations. "
    "You generate historically-attested medieval kingdoms, duchies, counties, and baronies."
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
  "condados": [
    { "id": "C_BRAGA",  "name": "Condado de Braga",  "lon": -8.43, "lat": 41.55, "kingdom_id": "K_PORT", "duchy_id": "D_MINHO" },
    { "id": "C_VIANA",  "name": "Condado de Viana",  "lon": -8.83, "lat": 41.69, "kingdom_id": "K_PORT", "duchy_id": "D_MINHO" },
    { "id": "C_LEON",   "name": "Condado de Leon",   "lon": -5.57, "lat": 42.60, "kingdom_id": "K_LEON",  "duchy_id": "D_LEON"  }
  ],
  "baronies": {
    "C_BRAGA": [
      { "name": "Baronia de Braga",     "lon": -8.43, "lat": 41.55 },
      { "name": "Baronia de Guimaraes", "lon": -8.30, "lat": 41.44 }
    ],
    "C_VIANA": [ { "name": "Baronia de Viana do Castelo", "lon": -8.83, "lat": 41.69 } ],
    "C_LEON":  [ { "name": "Baronia de Leon",             "lon": -5.57, "lat": 42.60 } ]
  }
}"""

RULES = """CRITICAL RULES — any violation fails validation:
1. TOP-LEVEL KEYS ALLOWED: exactly "kingdoms", "duchies", "condados", "baronies". NOTHING ELSE.
   DO NOT emit keys like "regions", "historical_names", "cities", "provinces", "description".
2. kingdoms: object mapping <kingdom_id> to the kingdom's display name (a string).
3. duchies: object mapping <duchy_id> to an object with exactly two keys: "kingdom_id" and "name".
4. condados: array of objects, each with exactly "id", "name", "lon", "lat", "kingdom_id", "duchy_id".
   - id: a slug you INVENT using prefix C_, e.g. "C_BRAGA", "C_TOLEDO", "C_PORTO". Must be unique.
   - name: historical name in period vernacular (never in English).
   - lon/lat: realistic geographic centroid — NEVER 0.0, 0.0.
   - kingdom_id / duchy_id: MUST reference an id defined in "kingdoms" / "duchies".
5. baronies: object mapping <condado_id> to an array of {name, lon, lat}.
   - Keys MUST be condado ids from the "condados" array above.
   - Every condado MUST have at least 1 barony. No upper limit.
6. kingdom_id / duchy_id slugs: short uppercase slugs you invent (e.g. "K_PORT", "D_MINHO").
7. Output a SINGLE JSON object. No prose before or after. No ```json fences.
8. COVERAGE: Generate ALL historically-attested condados/counties that existed at the START
   of the period in the given region. Do NOT limit to a small number — a typical medieval
   Iberian project should produce 60-120 condados. Include every county mentioned in
   chronicles, charters, diplomas, fueros, tumbos, or cartularies of the era.
9. BARONY COVERAGE: For each condado, generate all historically-documented baronies
   (castles, villas, senhoreios, fortalezas, señoríos). Prefer entities with clear
   documentary evidence. DO NOT use generic names like "Baronia de <condado>".
10. COORDINATE ACCURACY: Use realistic coordinates within the correct geographic region.
    Each condado centroid should reflect its actual historic location.
11. LANGUAGE: Use historical names in the regional vernacular of the period
    (português, castelhano, galego, catalão, leonês, asturiano, árabe andalusí, etc.)
    — never in English or Modern Latin.
    Examples: "Santiago de Compostela" (not "Saint James"), "Qurtuba" for Córdoba in
    Arabic, "Llión" in Leonese, "Batalha" in Portuguese."""


def build_research_prompt(
    country_name: str,
    period_start: int,
    period_end: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> str:
    """Build the full research prompt string for LLM submission.

    Args:
        country_name: Human-readable region/country name from the project.
        period_start: Start year of the historical period (AD).
        period_end: End year of the historical period (AD).
        bbox: Optional (lon_min, lat_min, lon_max, lat_max) bounding box for
              geographic context. Passed when available to anchor coordinates.

    Structure (order matters for small local models):
      1. System role instruction
      2. Example output (concrete, copy-paste shape)
      3. Hard rules with negative examples
      4. Task parameters (country + period + optional bbox)
      5. Final "go" instruction
    """
    geo_hint = ""
    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        geo_hint = (
            f"Geographic bounding box: lon {lon_min:.2f}..{lon_max:.2f}, "
            f"lat {lat_min:.2f}..{lat_max:.2f}. "
            "All condado/barony coordinates MUST fall within or near this box.\n"
        )

    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"EXAMPLE OUTPUT (follow this EXACT shape):\n{EXAMPLE_OUTPUT}\n\n"
        f"{RULES}\n\n"
        f"TASK:\n"
        f"Region/Country: {country_name}\n"
        f"Historical period: {period_start} AD (focus on this START year for territory layout)\n"
        f"Period end reference: {period_end} AD\n"
        f"{geo_hint}"
        f"\nGenerate the complete territorial hierarchy as it existed at {period_start} AD. "
        f"Output the JSON object following the example shape. "
        f"Do not include any other top-level keys."
    )
