---
phase: quick-260428-h0p
plan: 01
subsystem: backend/services
tags: [llm, research-runner, territory-builder, map-research, tdd, etapa-7b]
dependency_graph:
  requires:
    - 260428-fuy (build_map_research_prompt + validate_barony_assignments)
    - 260428-g5g (assemble_territory_data_from_baronies)
  provides:
    - research_runner map-path branching
    - territory_builder cache dispatch
  affects:
    - api/generate.py (now exercises the new aggregator path through build_territory_data_from_cache)
tech_stack:
  added: []
  patterns:
    - schema-dispatch wrapper (isinstance branch in _ValidatingWrapper)
    - file-presence feature flag (raw/baronies.geojson)
key_files:
  created:
    - backend/tests/services/test_research_runner_map_path.py
    - backend/tests/services/test_territory_builder_cache_dispatch.py
  modified:
    - backend/medieval_forge/services/research_runner.py
    - backend/medieval_forge/services/territory_builder.py
decisions:
  - "Detection signal is filesystem (raw/baronies.geojson), not a DB column — matches existing file-driven patterns and avoids a migration"
  - "_ValidatingWrapper dispatches via isinstance(result, MapResearchResult) so a single class supports both schemas without two parallel wrappers"
  - "build_territory_data_from_cache dispatches by payload key (\"barony_assignments\" present) — the cache row alone is enough; no schema discriminator column added"
  - "MapResearchResult cache row + missing baronies.geojson raises FileNotFoundError naming project_id (defensive — the prior pipeline must have produced the geojson)"
  - "schema_cls (type[BaseModel]) is captured per-branch and passed to run_with_retry; the wrapper's research method accepts the schema parameter generically"
metrics:
  duration: ~30 minutes
  completed: 2026-04-28
  tasks_completed: 2
  files_changed: 4
---

# Phase quick-260428-h0p Plan 01: Etapa 7b — wire map research runner + cache dispatch

**One-liner:** Plumb the new MapResearchResult/barony_assignments path end-to-end so research with pre-built baronies generates a usable cache row that flows through Etapa 7's aggregator into map generation.

## What Was Built

### `research_runner.run_research` — map-path branching

After loading the project, `run_research` now checks for `raw/baronies.geojson` under the project's directory. When present, it:

1. Loads the FeatureCollection and projects each feature into the
   `{id, name, lon, lat}` shape that `build_map_research_prompt` expects
   (using `properties.centroid`).
2. Calls `build_map_research_prompt(country_name, period_start, baronies, period_end=..., bbox=...)`.
3. Selects `MapResearchResult` as the schema for `run_with_retry`.
4. The local `_ValidatingWrapper` dispatches by result type:
   - `MapResearchResult` → `validate_barony_assignments(result, input_baronies)`
   - `ResearchResult` → `validate_condados_self_consistency(result)` (legacy)
5. The cached payload is `result.model_dump()` for the matching schema, so a
   MapResearchResult cache row carries `barony_assignments` instead of legacy `baronies`.

When `raw/baronies.geojson` is absent, the function is byte-equivalent to the previous behavior — the legacy 234-test baseline keeps passing without change.

### `territory_builder.build_territory_data_from_cache` — payload-shape dispatch

After fetching the latest `ResearchCache` row, the function inspects `row.payload`:

- `"barony_assignments" in payload` → reads `project_path/raw/baronies.geojson`
  and calls `assemble_territory_data_from_baronies(payload, geojson)` (Etapa 7).
  Raises `FileNotFoundError` naming the project_id when the geojson is missing
  (defensive guard — prior pipeline should have produced it).
- otherwise → `assemble_territory_data(payload)` (legacy path, unchanged).

The `project_path` parameter (previously kept "for API compat; no longer used") is now load-bearing for the map-path. `api/generate.py` already passes `project_dir(project_id)`, so no caller change is required.

## Test Count Delta

| State | Tests |
|-------|-------|
| Before (Etapa 7 baseline) | 234 |
| After (Etapa 7b) | 240 |
| New tests added | 6 |
| Failures | 0 |

### New tests

`backend/tests/services/test_research_runner_map_path.py` (4):
- `test_run_research_uses_map_prompt_and_schema_when_baronies_geojson_exists`
- `test_run_research_falls_back_to_legacy_when_no_baronies_geojson`
- `test_run_research_map_path_validates_assignments_and_retries_on_mismatch`
- `test_run_research_map_path_caches_payload_with_barony_assignments_key`

`backend/tests/services/test_territory_builder_cache_dispatch.py` (2):
- `test_build_territory_data_from_cache_uses_baronies_aggregator_when_payload_has_assignments`
- `test_build_territory_data_from_cache_uses_legacy_assembler_when_payload_lacks_assignments`

## Commit Hashes

| Phase | Commit | Description |
|-------|--------|-------------|
| PLAN  | `d8d86b5` | `docs(quick-260428-h0p)`: PLAN.md for Etapa 7b |
| RED   | `fda974c` | `test(quick-260428-h0p-01)`: 6 failing tests |
| GREEN | `153fca8` | `feat(quick-260428-h0p-01)`: wire map-path + cache dispatch |

## Deviations from Plan

None — TDD cycle executed as designed. RED phase showed exactly the expected failures (3 in runner, 1 in cache dispatch); the 2 regression-guard tests passed on existing code, which is the correct RED state for "behavior must be preserved" tests.

## Deferred to Future Etapas

Per master plan H ordering, the following are explicitly NOT part of 7b:
- **H.8 — Edit assignments endpoint** (PATCH + AssignmentEditor frontend).
- **H.9/H.10 — Codex schema/runner/viewer.**
- **H.11 — Pipeline UI Stepper / StepCards.**

## Known Stubs

None.

## Self-Check

- [x] `research_runner.run_research` branches on `raw/baronies.geojson` presence.
- [x] `_ValidatingWrapper` dispatches by `isinstance(result, MapResearchResult)`.
- [x] `build_territory_data_from_cache` dispatches by payload `"barony_assignments"` key.
- [x] PLAN commit `d8d86b5`, RED `fda974c`, GREEN `153fca8` on main.
- [x] Full backend suite: 240 passed, 0 failed, 4 deselected (slow + requires_llamacpp).
