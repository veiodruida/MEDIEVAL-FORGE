---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 06
subsystem: services/research
tags: [matcher, overlay, llm, metadata, pure-functions]
requires:
  - 07-02  # MapResearchResult schema (literal-ported)
  - 07-05  # services/research/overlay.py + ResearchOverlay schema
provides:
  - build_pipeline_condado_list  # metadata -> [{id, lon, lat}]
  - llm_output_to_overlay        # MapResearchResult-shaped dict -> overlay dict
affects:
  - 07-07  # research runner (will call build_pipeline_condado_list)
  - 07-08  # unity zip emitter (consumes overlay shape)
tech-stack:
  added: []
  patterns:
    - "RESEARCH §Pattern 7 — flat overlay dict keyed by condado id"
    - "RESEARCH §Pitfall 3 — no regex on ids; opaque strings only"
    - "Defense-in-depth — drop ids not in pipeline_condado_ids (T-07-06-01)"
key-files:
  created:
    - backend/medieval_forge/services/research/matcher.py
    - backend/tests/unit/test_matcher.py
  modified:
    - backend/medieval_forge/services/research/__init__.py
decisions:
  - "NIT 3: `kingdom.get('name') or None` idiom collapses missing-key AND empty-string to None"
  - "historical_notes empty-string is preserved (only kingdom_owner has empty-string→None semantics)"
  - "Matcher accepts a raw dict (`llm_result: dict`) rather than `MapResearchResult` — caller validates upstream; matcher stays pydantic-free per pure-function convention"
metrics:
  duration: ~5min
  completed: 2026-05-14
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  tests_added: 6
---

# Phase 07 Plan 06: Matcher (LLM → Overlay Bridge) Summary

Land pure functions `build_pipeline_condado_list` and `llm_output_to_overlay` in
`services/research/matcher.py`, bridging hierarchical LLM research output to the
flat overlay dict consumed by `merge_overlay` (Plan 05). Includes 6-case unit
test suite covering Iberia slugs, autogen `Condado_NNN` placeholders, unknown-id
drop, empty `historical_notes`, and the NIT 3 missing-kingdom-name case.

## What was built

### `services/research/matcher.py` (new, 94 lines)

Two pure functions, no I/O, no state, no pydantic at the boundary (caller
validates upstream):

- **`build_pipeline_condado_list(metadata) -> list[dict]`** — projects
  `territory_metadata.json["condados"]` down to `[{id, lon, lat}, ...]` for use
  as the AUTHORITATIVE condado list shipped to the LLM prompt (RESEARCH §Pattern 7).
  This is what prevents the LLM from inventing ids the pipeline has never heard of.

- **`llm_output_to_overlay(llm_result, pipeline_condado_ids) -> dict`** — walks
  `llm_result["kingdoms"][].duchies[].condados[]` and emits a flat
  `{condado_id: {name, kingdom_owner, historical_notes}}` keyed by condado id.
  Defense-in-depth: any condado id NOT in `pipeline_condado_ids` is silently
  dropped (T-07-06-01).

The NIT 3 fix is the idiom `kingdom_owner = kingdom.get("name") or None`:
`dict.get("name")` returns `None` for missing keys; `or None` collapses any other
falsy value (notably `""`) to `None` as well. The combined effect: BOTH
missing-key AND empty-string cases yield `kingdom_owner=None` (never `""`).

### `services/research/__init__.py` (extended)

Added `build_pipeline_condado_list` and `llm_output_to_overlay` to the package
exports without clobbering the Plan 05 overlay surface
(`merge_overlay`, `load_overlay_if_exists`, `ResearchOverlay`, `CondadoOverlayEntry`,
`_ZIP_BOUND_FIELDS`, `_ALL_OVERLAY_FIELDS`).

### `tests/unit/test_matcher.py` (new, 6 cases)

| # | Test | Covers |
|---|------|--------|
| 1 | `test_build_pipeline_condado_list_extracts_id_lon_lat_per_condado_for_iberia` | Iberia curated slugs (`oviedo`, `leon`, `burgos`) |
| 2 | `test_build_pipeline_condado_list_extracts_id_lon_lat_per_condado_for_autogen_condado_nnn` | Autogen placeholders (`Condado_001`..) — Pitfall 3 |
| 3 | `test_llm_output_to_overlay_collapses_hierarchy_keyed_by_condado_id_with_name_and_kingdom_owner` | Happy path — 2 kingdoms, 3 condados |
| 4 | `test_llm_output_to_overlay_drops_unknown_condado_ids` | T-07-06-01 defense-in-depth |
| 5 | `test_llm_output_to_overlay_handles_empty_historical_notes` | Missing key → `None`, `""` → preserved |
| 6 | `test_llm_output_to_overlay_sets_kingdom_owner_none_when_kingdom_name_missing` | **NIT 3** — empty + missing both → `None` |

All 6 pass: `pytest tests/unit/test_matcher.py -x -q` → `6 passed in 0.02s`.

## Verification

- `python -c "from medieval_forge.services.research import build_pipeline_condado_list, llm_output_to_overlay"` exits 0.
- `grep -nE "re\.match|re\.search|re\.compile.*Condado" matcher.py` → 0 matches (Pitfall 3).
- `grep -n 'kingdom.get("name") or None' matcher.py` → 1 match (NIT 3).
- All 6 unit tests pass.

## Deviations from Plan

None — plan executed exactly as written.

The plan's reference code in `<action>` (lines 96-130) was used essentially
verbatim; only inline docstring expansion was added to call out the threat
references (T-07-06-01) and the NIT 3 rationale.

A subtle point worth flagging: the plan describes the matcher as bridging
`MapResearchResult` (the pydantic model defined in `services/llm/schemas.py`),
but the actual `MapResearchResult` model has a FLAT shape
(`kingdoms: dict[str, str]`, `duchies: dict[str, Duchy]`, `condados: list[MapCondado]`,
`barony_assignments: dict[str, str]`), NOT the hierarchical
`kingdoms[].duchies[].condados[]` shape the plan's code and fixtures assume.

The matcher is written against the hierarchical dict shape exactly as the plan
specifies — this is intentional and consistent with the plan accepting a raw
`dict` (not a `MapResearchResult` instance) at the boundary. Wiring between the
flat pydantic model and the hierarchical dict the matcher consumes is the
responsibility of the research runner (Plan 07-07) and is out of scope here.

## Commits

| Task | Subject | Hash |
|------|---------|------|
| 1 | `feat(07-06): add services/research/matcher.py — build_pipeline_condado_list + llm_output_to_overlay` | `62a7453` |
| 2 | `test(07-06): add test_matcher.py — 6 cases incl NIT 3 missing-kingdom-name` | `84298b9` |

## Self-Check: PASSED

- `backend/medieval_forge/services/research/matcher.py` — FOUND
- `backend/medieval_forge/services/research/__init__.py` (modified) — FOUND
- `backend/tests/unit/test_matcher.py` — FOUND
- Commit `62a7453` — FOUND
- Commit `84298b9` — FOUND
- Test suite — 6/6 passed
