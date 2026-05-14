"""Defensive prompt-injection sanitizer (REVIEWS soft Qwen3 2026-05-14).

Called by CALLERS of build_map_research_prompt (Plan 07b runner) before passing
condado names into the prompt template. The literal-port prompt.py is NOT modified
(D-02 D-V3-04 locks the port to commit 87f8aab~1).

Threat model: condado names in v3 come from curated YAML (Iberia 868 in
inicio/territory_data_v3.py) — trusted. This guard is defense-in-depth for:
- Future user-edited regions (`.planning/phases/.../05-region-generalization`)
- Toy Voronoi auto-generated regions where condado names may come from OSM tags

Strategy: strip the most common LLM-prompt-injection sigils:
- `</` (closing HTML/XML tags that some models treat as system-prompt delimiters)
- `{{` and `}}` (Jinja/Handlebars-style template delimiters)

T-07-04-10 mitigation: see 07-04-PLAN.md threat register.
"""
from __future__ import annotations


def escape_condado_name(name: str) -> str:
    """Strip prompt-injection sigils from a condado name.

    Pure function. Idempotent. Never raises. None -> empty string.
    Behavior on `</`: strips the literal two-char sigil (so `"Foo</bar>"` becomes
    `"Foobar>"`, not `""`); enough to break LLM-side delimiter heuristics while
    preserving the readable portion of the name.
    """
    if name is None:
        return ""
    cleaned = name.replace("</", "").replace("{{", "").replace("}}", "")
    return cleaned.strip()
