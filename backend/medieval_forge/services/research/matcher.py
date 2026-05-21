"""Matcher — bridge LLM MapResearchResult to overlay shape.

Per RESEARCH §Pattern 7: pure functions that translate an LLM research payload
(hierarchical kingdoms -> duchies -> condados) into the flat
`{condado_id: {name, kingdom_owner, historical_notes}}` shape consumed by
`services/research/overlay.merge_overlay`.

Per RESEARCH §Pitfall 3 (Iberia vs autogen): we MUST NOT regex on condado ids
(`Condado_NNN` vs Iberia slugs); ids are opaque strings. Defense-in-depth
filtering happens against the authoritative pipeline_condado_ids set.

Per checker NIT 3: when a kingdom has no `name` key OR `name == ""`, the
resulting `kingdom_owner` is `None` (NOT empty string). The
`kingdom.get("name") or None` idiom collapses both cases to `None`.

Threat model (07-06):
    T-07-06-01: LLM-injected unknown condado id -> filtered against
                pipeline_condado_ids (allowed set).
    T-07-06-02: LLM-injected unexpected hierarchy fields -> tolerated via
                `.get()` everywhere; missing -> None.
"""
from __future__ import annotations

from typing import Iterable


def build_pipeline_condado_list(metadata: dict) -> list[dict]:
    """Project the pipeline's territory_metadata.json down to `[{id, lon, lat}]`.

    Used by the research runner (Plan 07) to send the AUTHORITATIVE condado
    list to the LLM prompt so the LLM cannot invent new ids that the pipeline
    has never heard of (RESEARCH §Pattern 7).

    Args:
        metadata: territory_metadata.json shape — must contain `condados: list[dict]`
                  where each entry has `id: str`, `lon: float`, `lat: float`.

    Returns:
        A list of `{id, lon, lat}` dicts in the same order as metadata['condados'].
    """
    return [
        {"id": c["id"], "lon": c["lon"], "lat": c["lat"]}
        for c in metadata["condados"]
    ]


def llm_output_to_overlay(
    llm_result: dict,
    pipeline_condado_ids: Iterable[str],
) -> dict:
    """Collapse a hierarchical LLM result into the flat overlay shape.

    Walks `llm_result['kingdoms'][].duchies[].condados[]` and emits, for each
    condado whose `id` is in `pipeline_condado_ids`, an entry
    `{name, kingdom_owner, historical_notes}` keyed by the condado id.

    Args:
        llm_result: LLM research payload — hierarchical
            `{kingdoms: [{name, duchies: [{name, condados: [{id, name,
            historical_notes}]}]}]}`. All fields read defensively via `.get()`.
        pipeline_condado_ids: Authoritative set of condado ids from the
            pipeline's territory_metadata.json. Any LLM-output condado id
            NOT in this set is DROPPED (T-07-06-01 defense-in-depth).

    Returns:
        `{condado_id: {name, kingdom_owner, historical_notes}}` consumable by
        `services/research/overlay.merge_overlay`. Missing kingdom name (NIT 3)
        -> `kingdom_owner is None`. Missing condado fields -> `None`.
    """
    allowed = set(pipeline_condado_ids)
    overlay: dict = {}
    # Small local models (qwen2.5:1.5b, gemma3:1b, ...) often ignore the
    # nested-schema instruction and return arrays of strings, mixed shapes,
    # or single dicts where lists were asked for. Defend each level so a
    # malformed branch is dropped rather than crashing the whole run.
    for kingdom in llm_result.get("kingdoms", []) or []:
        if not isinstance(kingdom, dict):
            continue
        # NIT 3: empty string OR missing key -> None (NOT "").
        # `dict.get("name")` returns None when key absent; `or None` collapses
        # the empty-string case (and any other falsy value) to None.
        kingdom_owner = kingdom.get("name") or None
        for duchy in kingdom.get("duchies", []) or []:
            if not isinstance(duchy, dict):
                continue
            for condado in duchy.get("condados", []) or []:
                if not isinstance(condado, dict):
                    continue
                cid = condado.get("id")
                if cid not in allowed:
                    # T-07-06-01: drop unknown ids (defense-in-depth).
                    continue
                overlay[cid] = {
                    "name": condado.get("name"),
                    "kingdom_owner": kingdom_owner,
                    "historical_notes": condado.get("historical_notes"),
                }
    return overlay


__all__ = [
    "build_pipeline_condado_list",
    "llm_output_to_overlay",
]
