---
phase: quick-260428-g5g
plan: 01
subsystem: backend/services/territory_builder
tags: [backend, geometry, baronies, territory-builder, tdd]
dependency_graph:
  requires:
    - backend/medieval_forge/services/baronies_builder.py (Etapa 2 — GeoJSON FeatureCollection)
    - backend/medieval_forge/services/llm/schemas.py (Etapa 3 — MapResearchResult / barony_assignments)
  provides:
    - "assemble_territory_data_from_baronies(map_research_payload, baronies_geojson) -> dict"
  affects:
    - backend/medieval_forge/services/territory_builder.py (additive — module docstring + new function)
tech_stack:
  added: []
  patterns:
    - "Two coexisting aggregation paths: legacy (LLM-invented condado coords) vs Etapa 7 (mean-of-baronies centroid)"
    - "Defensive ValueError on ingestion mismatch (collect-all-then-raise pattern)"
key_files:
  created:
    - backend/tests/services/test_territory_builder_baronies_aggregation.py
  modified:
    - backend/medieval_forge/services/territory_builder.py
decisions:
  - "Centroid = arithmetic mean of member-barony centroids (no weighting by area) — simple, deterministic, matches plan H.7 contract."
  - "Assignments to unknown condado_ids are silently ignored at aggregation level (cross-ref validation is the responsibility of validate_barony_assignments from Etapa 6)."
  - "Empty-condado check raised AS aggregator-level invariant (defensive — guards map_generator from the 'erro 0' IndexError of master plan H.1)."
metrics:
  duration: ~10min
  completed: 2026-04-28
requirements: [HAZY-STEP-7]
---

# Phase quick-260428-g5g Plan 01: Territory builder reconstruído (Etapa 7) Summary

## One-liner

`assemble_territory_data_from_baronies` aggregates OSM-derived baronies into condados via `barony_assignments`, computing each condado's centroid as the arithmetic mean of its member-barony centroids — closing the geometry gap between Etapa 2 (baronies_builder) + Etapa 6 (MapResearchResult) and the existing `services/generator.py` contract.

## What Was Built

- **New function** `assemble_territory_data_from_baronies(map_research_payload, baronies_geojson) -> dict` in `backend/medieval_forge/services/territory_builder.py`.
  - Builds an `O(1)` index of baronies by id, resolves each condado's member-barony list from `barony_assignments` (preserving insertion order), and computes the mean lon/lat centroid.
  - Returns the same 6-tuple shape consumed by `services.generator`: `(id, name, lon, lat, duchy_id, baronies)` where `baronies = list[(name, lon, lat)]`.
  - Two defensive `ValueError` paths: (1) any `barony_id` in assignments not present in the GeoJSON, (2) any condado that ends up with zero baronies (would otherwise crash `map_generator` with the "erro 0" IndexError described in master plan H.1).
- **Module docstring** updated to document the two coexisting aggregation paths (legacy embedded-coords vs Etapa 7 baronies-aggregation).
- **4 new tests** in `backend/tests/services/test_territory_builder_baronies_aggregation.py`, all using explicit numeric fixtures (no random, no hidden math) per project test-style memory.
- **Backwards compat preserved**: `select_latest_cache_row`, `assemble_territory_data`, and `build_territory_data_from_cache` are byte-identical (verified via diff — only additions). 7 existing `test_territory_builder.py` tests still pass.

## Test Count Delta

230 → **234** (+4 new). Full suite: `234 passed, 4 deselected (slow + requires_llamacpp)` in 19.04s. 0 failures.

## Commit Hashes

- RED: `4078fad` — `test(quick-260428-g5g-01): add 4 failing tests for assemble_territory_data_from_baronies (RED)`
- GREEN: `2189315` — `feat(quick-260428-g5g-01): assemble_territory_data_from_baronies — aggregate baronies into condados (GREEN, 4 tests)`

## Deviations from Plan

None — plan executed exactly as written. Tests pass on first GREEN run with no test edits required.

## Deferred to Etapa 7b (per `<out_of_scope>`)

Tracked for the next quick task; explicitly out of scope here:

1. Wire `build_map_research_prompt` into `research_runner.py` (LLM provider call site, `_ValidatingWrapper` adapter, retry loop).
2. Wrap `validate_barony_assignments` in a `_ValidatingWrapper`-style adapter inside `research_runner.py`.
3. Update `api/generate.py` to pass baronies geojson into the territory builder path (needs item 1 + a schema-detection decision: `ResearchResult` vs `MapResearchResult` in cache row).

## Known Stubs

None. The new function is fully implemented and wired to its tests; the only "unwired" surface is intentional (the new function is not yet called by `research_runner` / `api/generate` — that wiring is Etapa 7b, see Deferred section above).

## Self-Check: PASSED

- FOUND: `backend/medieval_forge/services/territory_builder.py` (modified, contains `def assemble_territory_data_from_baronies`)
- FOUND: `backend/tests/services/test_territory_builder_baronies_aggregation.py` (4 test functions)
- FOUND commit: `4078fad` (RED)
- FOUND commit: `2189315` (GREEN)
- VERIFIED: 234 backend tests pass, 0 failures.
- VERIFIED: existing functions `assemble_territory_data` and `build_territory_data_from_cache` are byte-identical to pre-plan state (only additions in `git diff` — module docstring expansion + new function inserted between `assemble_territory_data` and `build_territory_data_from_cache`).
