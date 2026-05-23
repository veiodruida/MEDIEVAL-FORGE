# Literal port from commit 87f8aab~1; see D-02 in 07-CONTEXT.md.
# DO NOT MODIFY behaviorally. Allowed edits: import-line adjustments only.
"""Prompt builder for LLM historical research requests.

The LLM generates the full territorial hierarchy from scratch at the START of
the historical period. It invents historically-attested condados (counties) with
coordinates — no pre-supplied OSM list is provided.

Etapa 6 (hazy-hatching-abelson): Added build_map_research_prompt — a new sibling
that receives a pre-built barony list (from Etapa 2 baronies_builder) and asks
the LLM to assign those baronies to condados via barony_assignments.
The legacy build_research_prompt is kept untouched for backwards compatibility.
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
    pipeline_condado_ids: list[str] | None = None,
) -> str:
    """Build the full research prompt string for LLM submission.

    Args:
        country_name: Human-readable region/country name from the project.
        period_start: Start year of the historical period (AD).
        period_end: End year of the historical period (AD).
        bbox: Optional (lon_min, lat_min, lon_max, lat_max) bounding box for
              geographic context. Passed when available to anchor coordinates.
        pipeline_condado_ids: Optional authoritative list of condado ids the
              pipeline has already assigned (e.g. ["Condado_001", "Condado_002",
              ...]). When provided, the LLM is INSTRUCTED to reuse these exact
              ids in its `condados[].id` field — otherwise the runner's
              defense-in-depth matcher drops everything as unknown. Without
              this parameter the LLM keeps inventing `C_BRAGA`-style slugs
              (legacy behavior preserved for stub-provider tests).

    Structure (order matters for small local models):
      1. System role instruction
      2. Example output (concrete, copy-paste shape)
      3. Hard rules with negative examples
      4. Task parameters (country + period + optional bbox + optional id list)
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

    id_hint = ""
    if pipeline_condado_ids:
        # UAT 2026-05-23 — without this section the LLM invents `C_BRAGA`
        # style ids, the runner's matcher allowlist drops them all, and
        # the user sees "0 condados" applied. Pin the LLM to the exact
        # ids the pipeline already minted; the LLM only fills in
        # historical name + coords + hierarchy.
        joined = ", ".join(f'"{cid}"' for cid in pipeline_condado_ids)
        id_hint = (
            "MANDATORY CONDADO IDS:\n"
            "Use EXACTLY these ids in the `condados` array — one entry per id, "
            "in any order. Do NOT invent new ids, do NOT skip any:\n"
            f"  [{joined}]\n"
            "The `id` field of every condado MUST be one of the strings above, "
            "verbatim. Override any `C_*` slug you would otherwise have invented.\n\n"
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
        f"{id_hint}"
        f"\nGenerate the complete territorial hierarchy as it existed at {period_start} AD. "
        f"Output the JSON object following the example shape. "
        f"Do not include any other top-level keys."
    )


# ---------------------------------------------------------------------------
# Etapa 6: baronies-aware prompt — LLM assigns, does not invent geography
# ---------------------------------------------------------------------------

# Example output for MapResearchResult shape (no coords on condados, barony_assignments dict)
EXAMPLE_OUTPUT_MAP = """{
  "kingdoms": {
    "K_PORT": "Reino de Portugal",
    "K_LEON": "Reino de Leon"
  },
  "duchies": {
    "D_MINHO": { "kingdom_id": "K_PORT", "name": "Minho" },
    "D_LEON":  { "kingdom_id": "K_LEON", "name": "Leon" }
  },
  "condados": [
    { "id": "C_BRAGA", "name": "Condado de Braga", "kingdom_id": "K_PORT", "duchy_id": "D_MINHO" },
    { "id": "C_PORTO", "name": "Condado do Porto",  "kingdom_id": "K_PORT", "duchy_id": "D_MINHO" },
    { "id": "C_LEON",  "name": "Condado de Leon",   "kingdom_id": "K_LEON", "duchy_id": "D_LEON"  }
  ],
  "barony_assignments": {
    "B_001": "C_BRAGA",
    "B_002": "C_PORTO",
    "B_003": "C_LEON"
  }
}"""

RULES_MAP = """CRITICAL RULES — any violation fails validation:
1. TOP-LEVEL KEYS ALLOWED: exactly "kingdoms", "duchies", "condados", "barony_assignments". NOTHING ELSE.
   DO NOT emit keys like "baronies", "regions", "historical_names", "cities", "provinces", "description".
2. kingdoms: object mapping <kingdom_id> to the kingdom's display name (a string).
3. duchies: object mapping <duchy_id> to an object with exactly two keys: "kingdom_id" and "name".
4. condados: array of objects, each with exactly "id", "name", "kingdom_id", "duchy_id". NO lon/lat.
   - id: a slug you INVENT using prefix C_, e.g. "C_BRAGA", "C_TOLEDO", "C_PORTO". Must be unique.
   - name: historical name in period vernacular (never in English).
   - kingdom_id / duchy_id: MUST reference an id defined in "kingdoms" / "duchies".
5. barony_assignments: object mapping <barony_id> → <condado_id>.
   - Every KEY MUST be one of the barony_ids listed above — do NOT invent new ids.
   - Every VALUE MUST be one of the condado ids from your "condados" array.
   - EVERY input barony MUST appear exactly once as a key — do NOT leave any unassigned.
6. kingdom_id / duchy_id slugs: short uppercase slugs you invent (e.g. "K_PORT", "D_MINHO").
7. Output a SINGLE JSON object. No prose before or after. No ```json fences.
8. COVERAGE: Generate ALL historically-attested condados/counties for the region and period.
   Include every county mentioned in chronicles, charters, diplomas, fueros, tumbos, or cartularies.
9. LANGUAGE: Use historical names in the regional vernacular of the period — never in English."""


def build_map_research_prompt(
    country_name: str,
    period_start: int,
    baronies: list[dict],
    *,
    period_end: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> str:
    """Build a research prompt that passes pre-built baronies to the LLM for assignment.

    Etapa 6 inversion: baronies are the permanent organic unit (from OSM via
    baronies_builder). The LLM only assigns them to condados — it does NOT invent
    barony coordinates. Returns barony_assignments: {barony_id -> condado_id}.

    Args:
        country_name: Human-readable region/country name from the project.
        period_start: Start year of the historical period (AD).
        baronies: List of barony dicts from baronies_builder. Each has:
                  {"id": str, "name": str, "lon": float, "lat": float}.
        period_end: Optional end year of the historical period (AD).
        bbox: Optional (lon_min, lat_min, lon_max, lat_max) bounding box.

    Structure (order matters for small local models):
      1. System role instruction
      2. Example output (MapResearchResult shape — no coords on condados)
      3. Hard rules (barony_assignments constraint is the critical addition)
      4. BARONIES section (the concrete list the LLM must assign from)
      5. Task parameters (country + period + optional bbox)
      6. Final "go" instruction
    """
    # Build the barony list section — 2 decimals so "-8.43" matches test assertions
    barony_lines = "".join(
        f"- {b['id']}: {b['name']} (lon={b['lon']:.2f}, lat={b['lat']:.2f})\n"
        for b in baronies
    )

    geo_hint = ""
    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        geo_hint = (
            f"Geographic bounding box: lon {lon_min:.2f}..{lon_max:.2f}, "
            f"lat {lat_min:.2f}..{lat_max:.2f}. "
            "All condado coordinate references MUST fall within or near this box.\n"
        )

    period_line = f"Historical period: {period_start} AD (focus on this START year for territory layout)\n"
    if period_end is not None:
        period_line += f"Period end reference: {period_end} AD\n"

    barony_ids_inline = ", ".join(b["id"] for b in baronies)

    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"EXAMPLE OUTPUT (follow this EXACT shape):\n{EXAMPLE_OUTPUT_MAP}\n\n"
        f"{RULES_MAP}\n\n"
        f"BARONIES (pre-built from OSM — you MUST assign ALL of these):\n"
        f"Total: {len(baronies)} baronies\n"
        f"barony_assignments keys MUST be one of the barony_ids listed above — "
        f"do NOT invent new ids. Valid ids: {barony_ids_inline}\n\n"
        f"{barony_lines}\n"
        f"TASK:\n"
        f"Region/Country: {country_name}\n"
        f"{period_line}"
        f"{geo_hint}"
        f"\nGenerate the complete territorial hierarchy as it existed at {period_start} AD. "
        f"Assign every barony listed above to a condado using barony_assignments. "
        f"Output the JSON object following the example shape. "
        f"Do not include any other top-level keys."
    )


# ---------------------------------------------------------------------------
# Etapa 9: Codex prompt — 12-category medieval narrative
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTIONS_CODEX = (
    "You output ONLY valid JSON matching the EXACT CodexResult schema provided. "
    "You do NOT invent new top-level keys beyond the 12 listed. "
    "You DO write rich markdown prose inside each entry's `description` field — "
    "**bold**, _italics_, lists, and short historical narrative are welcome. "
    "Generate historically-grounded medieval lore: dynasties, currencies, traits, "
    "religions, cultural traditions, military doctrines, key events."
)

# Concrete minimal example for the 12 Codex categories. Small local models
# anchor on the example shape; keep one sample entry per category.
EXAMPLE_OUTPUT_CODEX = """{
  "currency": {
    "summary": "Mostly silver dirham + Christian solidi.",
    "entries": [
      { "id": "CUR_DIRHAM", "name": "Dirham de prata",
        "description": "**Cunhada** em Córdoba; padrão monetário do al-Andalus." }
    ]
  },
  "attributes": {
    "summary": "Atributos típicos das casas reais.",
    "entries": [
      { "id": "ATTR_PIETY", "name": "Piedade",
        "description": "_Virtude_ central nos reinos cristãos." }
    ]
  },
  "health": {
    "summary": "Pestes recorrentes na Reconquista.",
    "entries": [
      { "id": "HLT_PLAGUE", "name": "Peste",
        "description": "Surtos esporádicos em **cidades portuárias**." }
    ]
  },
  "traits": {
    "summary": "Traços marcantes dos nobres.",
    "entries": [
      { "id": "TRT_BRAVE", "name": "Bravo",
        "description": "Líder destemido em batalha." }
    ]
  },
  "feudal": {
    "summary": "Vassalagem hereditária consolidada.",
    "entries": [
      { "id": "FEU_HOMAGE", "name": "Homenagem",
        "description": "Cerimônia _ritual_ de juramento ao senhor." }
    ]
  },
  "politics": {
    "summary": "Disputas dinásticas pelo trono leonês.",
    "entries": [
      { "id": "POL_CORTES", "name": "Cortes de Leão",
        "description": "**Assembleia** de nobres e clero." }
    ]
  },
  "dynasty": {
    "summary": "Casa de Leão dominante.",
    "entries": [
      { "id": "DYN_LEON", "name": "Casa de Leão",
        "description": "**Fundada** por Garcia I em 910." }
    ]
  },
  "religion": {
    "summary": "Cristianismo + islã + judaísmo coexistem.",
    "entries": [
      { "id": "REL_CATH", "name": "Catolicismo Romano",
        "description": "_Fé_ dominante nos reinos do norte." }
    ]
  },
  "culture": {
    "summary": "Mosaico ibérico medieval.",
    "entries": [
      { "id": "CUL_MOZARAB", "name": "Cultura moçárabe",
        "description": "**Sincretismo** cristão-andalusi." }
    ]
  },
  "economy": {
    "summary": "Economia agrária + rotas de seda.",
    "entries": [
      { "id": "ECO_WOOL", "name": "Lã",
        "description": "Comércio de _lã_ castelhana." }
    ]
  },
  "military": {
    "summary": "Cavalaria pesada + mesnadas.",
    "entries": [
      { "id": "MIL_MESNADA", "name": "Mesnada",
        "description": "**Hoste** privada do nobre." }
    ]
  },
  "events": {
    "summary": "Eventos pontuais do período.",
    "entries": [
      { "id": "EVT_910", "name": "Coroação de Garcia I",
        "description": "Início da dinastia leonesa em **910 AD**." }
    ]
  }
}"""

_CODEX_CATEGORIES = (
    "currency", "attributes", "health", "traits",
    "feudal", "politics", "dynasty", "religion",
    "culture", "economy", "military", "events",
)

RULES_CODEX = """CRITICAL RULES — any violation fails validation:
1. TOP-LEVEL KEYS ALLOWED: exactly these 12 — currency, attributes, health,
   traits, feudal, politics, dynasty, religion, culture, economy, military,
   events. NOTHING ELSE. DO NOT add keys like "weather", "geography", "notes".
2. Each category MUST be an object with EXACTLY two keys: "summary" (string)
   and "entries" (array). No other keys are allowed.
3. Each entry in "entries" MUST be an object with EXACTLY three keys: "id"
   (uppercase slug, e.g. "DYN_LEON"), "name" (display name in period
   vernacular), "description" (free markdown prose).
4. Use historical names in the regional vernacular of the period
   (português, castelhano, galego, leonês, árabe andalusí, …) — never English.
5. Inside `description`, free markdown is welcome: **bold**, _italics_, lists.
   Do NOT embed raw HTML or ```json fences.
6. Output a SINGLE JSON object. No prose before or after."""


def build_codex_prompt(
    country_name: str,
    period_start: int,
    period_end: int,
    map_summary: str,
    focus_sections: list[str] | None = None,
) -> str:
    """Build the full Codex prompt string for LLM submission.

    Args:
        country_name: Human-readable region/country name.
        period_start: Start year of the historical period (AD).
        period_end: End year of the historical period (AD).
        map_summary: Short string describing the generated map (e.g. how many
                     kingdoms / condados / baronies). Anchors the LLM to the
                     scale of the world it is annotating.
        focus_sections: Optional subset of the 12 category names. When given,
                        the prompt adds a `FOCUS:` line listing them so the LLM
                        prioritises depth in those categories — but the JSON
                        output STILL contains all 12 keys.

    Structure (order matters for small local models):
      1. System role instruction
      2. Example output (concrete CodexResult shape)
      3. Hard rules
      4. Optional FOCUS line
      5. Task parameters (country + period + map summary)
      6. Final "go" instruction
    """
    focus_line = ""
    if focus_sections:
        # List ONLY the requested sections on the FOCUS line.
        focus_line = f"FOCUS: prioritize depth in: {', '.join(focus_sections)}\n"

    # Always render the explicit list of all 12 categories so the schema
    # contract is unambiguous regardless of focus_sections.
    full_schema_line = "FULL SCHEMA (always emit all 12 keys): " + \
        ", ".join(_CODEX_CATEGORIES) + "\n"

    return (
        f"{SYSTEM_INSTRUCTIONS_CODEX}\n\n"
        f"EXAMPLE OUTPUT (follow this EXACT shape):\n{EXAMPLE_OUTPUT_CODEX}\n\n"
        f"{RULES_CODEX}\n\n"
        f"{full_schema_line}"
        f"{focus_line}"
        f"\nTASK:\n"
        f"Region/Country: {country_name}\n"
        f"Historical period: {period_start} AD to {period_end} AD\n"
        f"Map summary: {map_summary}\n"
        f"\nGenerate the complete medieval Codex for {country_name} in the "
        f"{period_start}–{period_end} AD period. Emit ALL 12 categories. "
        f"Output the JSON object following the example shape. "
        f"Do not include any other top-level keys."
    )


# ---------------------------------------------------------------------------
# PROMPT_TEMPLATE — cacheable-shape digest source (Plan 07-07a)
# ---------------------------------------------------------------------------
#
# services/research/cache.py reads this at import time to compute PROMPT_DIGEST
# (REVIEWS soft Codex):
#
#     PROMPT_DIGEST = sha256(PROMPT_TEMPLATE)[:8]
#
# Any edit to ANY of the static prompt components below auto-invalidates the
# cache because PROMPT_DIGEST flows into cache_key.
#
# Coverage rationale: Plan 07b's runner is expected to call build_map_research_prompt
# (Etapa 6 baronies-aware flow) — the legacy build_research_prompt may also be
# invoked, and Plan 09a/09b may invoke build_codex_prompt. To make the digest
# correctly reflect ANY semantic shift in ANY of the three prompt builders, we
# concatenate every static text block that flows into a builder's output. Order
# is irrelevant for digest stability; it just needs to be deterministic across
# imports (which it is — module-level concatenation is fixed at import time).
#
# Plan 07-07a Rule 3 deviation: literal-port file gains a derived constant only.
# No behavioral change to build_research_prompt / build_map_research_prompt /
# build_codex_prompt.
PROMPT_TEMPLATE: str = (
    SYSTEM_INSTRUCTIONS
    + EXAMPLE_OUTPUT
    + RULES
    + EXAMPLE_OUTPUT_MAP
    + RULES_MAP
    + SYSTEM_INSTRUCTIONS_CODEX
    + EXAMPLE_OUTPUT_CODEX
    + RULES_CODEX
)
