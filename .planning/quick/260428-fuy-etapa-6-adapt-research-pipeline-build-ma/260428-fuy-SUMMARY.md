---
phase: quick-260428-fuy
plan: 01
subsystem: backend/llm
tags: [llm, prompt, validation, barony-assignments, tdd]
dependency_graph:
  requires: [260428-elq (baronies_builder), 260428-ewx (MapResearchResult schema)]
  provides: [build_map_research_prompt, validate_barony_assignments]
  affects: [research_runner.py (Etapa 7 wiring), run_with_retry retry loop]
tech_stack:
  added: []
  patterns: [module-level validator function, prompt builder sibling pattern]
key_files:
  created:
    - backend/tests/unit/test_map_research_prompt.py
    - backend/tests/unit/test_barony_assignments_validation.py
  modified:
    - backend/medieval_forge/services/llm/prompt.py
    - backend/medieval_forge/services/llm/schemas.py
decisions:
  - "build_map_research_prompt added as a sibling function alongside build_research_prompt (not replacing it) for backwards compat"
  - "validate_barony_assignments is a plain module-level function (not method) so Etapa 7 can wrap it in a _ValidatingWrapper adapter"
  - "RULES_MAP uses :.2f formatting for bbox values so test substrings (-9.50, 43.80) match verbatim"
  - "Test assertion for absent baronies key uses list comprehension on ALLOWED line rather than raw string search to avoid false positives from DO NOT mention"
metrics:
  duration: ~20 minutes
  completed: 2026-04-28
  tasks_completed: 2
  files_changed: 4
---

# Phase quick-260428-fuy Plan 01: Etapa 6 — adapt research pipeline (build_map_research_prompt + validate_barony_assignments) Summary

**One-liner:** New baronies-aware prompt builder + strict self-consistency validator so the LLM assigns pre-built OSM baronies to condados instead of inventing geography.

## What Was Built

### `build_map_research_prompt` (prompt.py)

Signature:
```python
def build_map_research_prompt(
    country_name: str,
    period_start: int,
    baronies: list[dict],
    *,
    period_end: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> str
```

Structure of the emitted prompt:
1. `SYSTEM_INSTRUCTIONS` (shared with legacy builder)
2. `EXAMPLE_OUTPUT_MAP` — new example showing the 4-key MapResearchResult shape (no coords on condados, `barony_assignments` dict)
3. `RULES_MAP` — critical rule: every assignment key MUST be one of the barony_ids listed, "baronies" is explicitly forbidden as a top-level key
4. BARONIES section — bulleted list of all input baronies formatted as `- {id}: {name} (lon={lon:.2f}, lat={lat:.2f})`
5. TASK section — country, period_start, optional period_end, optional bbox

The legacy `build_research_prompt` function is **untouched**.

### `validate_barony_assignments` (schemas.py)

Signature:
```python
def validate_barony_assignments(
    result: MapResearchResult,
    input_baronies: list[dict],
) -> None
```

Two strict checks (raises `ValueError` for both — triggering `run_with_retry` re-prompt):
- **Unknown keys**: assignment key not in input barony list → names offending id(s)
- **Unassigned baronies**: input barony not covered by assignments → names missing id(s)

The existing `MapResearchResult._validate_barony_assignments_reference_existing_condados` model validator (checks assignment VALUES point to real condados) is **untouched**.

## Test Count Delta

| State | Tests |
|-------|-------|
| Before (Etapa 5 baseline) | 224 |
| After (Etapa 6) | 230 |
| New tests added | 6 |
| Failures | 0 |

## Commit Hashes

| Phase | Commit | Description |
|-------|--------|-------------|
| RED | `6d1571f` | `test(quick-260428-fuy-01)`: 6 failing tests — ImportError confirmed |
| GREEN | `07733a2` | `feat(quick-260428-fuy-01)`: implementation — 230 tests passing |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertion for absent "baronies" key was too broad**
- **Found during:** Task 2 (GREEN) first run
- **Issue:** Test checked `'"baronies"' not in prompt` but RULES_MAP correctly includes `"baronies"` in the "DO NOT emit" example list, causing a false positive failure
- **Fix:** Replaced raw string check with a list comprehension that parses only the ALLOWED keys line from the rules section — checks that "baronies" is not in the comma-separated allowed keys list after `TOP-LEVEL KEYS ALLOWED:`
- **Files modified:** `backend/tests/unit/test_map_research_prompt.py`
- **Commit:** `07733a2` (test fix included in GREEN commit)

## Deferred to Etapa 7

- Wiring `build_map_research_prompt` into `research_runner.py`
- Wrapping `validate_barony_assignments` in a `_ValidatingWrapper`-style adapter inside research_runner
- Rebuilding `territory_builder.py` to aggregate baronies into condado polygons

## Known Stubs

None — both symbols are fully implemented pure functions with no placeholder data.

## Self-Check

- [x] `backend/medieval_forge/services/llm/prompt.py` — `build_map_research_prompt` importable
- [x] `backend/medieval_forge/services/llm/schemas.py` — `validate_barony_assignments` importable
- [x] `backend/tests/unit/test_map_research_prompt.py` — 3 tests, all pass
- [x] `backend/tests/unit/test_barony_assignments_validation.py` — 3 tests, all pass
- [x] RED commit `6d1571f` exists on main
- [x] GREEN commit `07733a2` exists on main
- [x] Full suite: 230 passed, 0 failed, 4 deselected (slow + requires_llamacpp)
