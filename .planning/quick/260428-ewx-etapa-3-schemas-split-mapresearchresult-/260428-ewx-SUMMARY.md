---
phase: quick-260428-ewx
plan: 01
subsystem: backend/llm/schemas
tags: [schema, pydantic, llm, etapa-3, hazy-hatching-abelson]
requires:
  - pydantic v2 (model_validator, ConfigDict)
provides:
  - MapResearchResult (CK3-style schema split: condados without coords + barony_assignments)
  - MapCondado (no-coords variant of Condado)
affects:
  - backend/medieval_forge/services/llm/schemas.py
  - backend/tests/unit/test_llm_schemas.py
tech-stack:
  added: []
  patterns:
    - "@model_validator(mode='after') for cross-reference invariant enforcement"
key-files:
  created: []
  modified:
    - backend/medieval_forge/services/llm/schemas.py
    - backend/tests/unit/test_llm_schemas.py
decisions:
  - "MapResearchResult is purely additive — legacy ResearchResult/Condado/Barony untouched until Etapa 4 migrates callers"
  - "Cross-reference validator runs in mode='after' so condado ids exist before lookup; error names the unknown condado_id(s) for LLM retry feedback"
metrics:
  duration: ~5min
  completed: 2026-04-28
  tasks: 1
  files: 2
  tests_added: 7
  tests_total: 216
---

# Quick Task 260428-ewx: Etapa 3 — Schemas Split (MapResearchResult) Summary

CK3-style schema split: added `MapResearchResult` Pydantic model where condados carry no coordinates and baronies are referenced via a flat `barony_assignments: dict[barony_id, condado_id]` map, with a model_validator enforcing referential integrity. Legacy `ResearchResult` preserved.

## What Was Done

### Task 1: Add MapResearchResult + MapCondado schemas with cross-ref validator

- Imported `model_validator` from pydantic.
- Added `MapCondado` (`id`, `name`, `kingdom_id`, `duchy_id`; `extra='forbid'`; no lon/lat).
- Added `MapResearchResult` (`kingdoms`, `duchies`, `condados: list[MapCondado]`, `barony_assignments: dict[str, str]`; `extra='forbid'`).
- Added `@model_validator(mode='after')` `_validate_barony_assignments_reference_existing_condados` that raises `ValueError` listing unknown condado_id(s) when assignments reference condados not in `condados[]`.
- Updated module docstring to note Etapa 3 additivity.
- Did NOT modify `Barony`, `Duchy`, `Condado`, `ResearchResult`, `parse_research_json`, `_RESEARCH_RESULT_KEYS`.

### Tests added (7, all passing)

1. `test_map_research_result_accepts_minimal_valid_payload_with_two_baronies_assigned_to_condado_braga`
2. `test_map_condado_rejects_lon_lat_fields_because_coords_are_no_longer_part_of_the_new_schema`
3. `test_map_condado_requires_id_name_kingdom_id_and_duchy_id`
4. `test_map_research_result_barony_assignments_accepts_empty_dict_when_no_baronies_yet`
5. `test_map_research_result_cross_reference_validator_raises_when_barony_assigned_to_unknown_condado_id`
6. `test_map_research_result_cross_reference_validator_passes_when_all_assignments_point_to_known_condados`
7. `test_legacy_research_result_still_works_after_schema_split` (regression guard)

Module-level fixtures `_MAP_MINIMAL_VALID` and `_MAP_TWO_CONDADOS` use explicit numeric/string literals per project convention.

## Verification

- `python -m pytest backend/tests/unit/test_llm_schemas.py -v` → 12 passed (5 legacy + 7 new), 0 failed.
- `python -m pytest backend/tests -q -m "not slow"` → **216 passed**, 4 deselected, 0 failed (209 baseline + 7 new).
- `python -c "from medieval_forge.services.llm.schemas import MapResearchResult, MapCondado, ResearchResult, Condado; print('ok')"` → `ok`.

## Deviations from Plan

None — plan executed exactly as written.

## Commits

- `3c914b8` feat(quick-260428-ewx-01): add MapResearchResult schema with barony_assignments + cross-ref validator (Etapa 3)

## Self-Check: PASSED

- FOUND: backend/medieval_forge/services/llm/schemas.py (modified, contains `class MapResearchResult` and `class MapCondado`)
- FOUND: backend/tests/unit/test_llm_schemas.py (modified, contains 7 new tests)
- FOUND commit: 3c914b8
- All 7 new tests passing; 209 baseline tests still passing (216 total).
