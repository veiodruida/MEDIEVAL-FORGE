---
phase: "05"
plan: "05"
subsystem: "backend/pipeline+tests"
tags: [delete-dead-code, regions-py, territory-data, migration, load-region, parity]
dependency_graph:
  requires:
    - phase: "05-01"
      provides: "load_region API, clear_region_cache"
    - phase: "05-02"
      provides: "data/regions/iberia_868.yaml"
    - phase: "05-03"
      provides: "YAML parity gate (test_iberia_868_yaml.py) as canonical replacement"
    - phase: "05-04"
      provides: "generate.py + render.py swapped to load_region"
  provides:
    - "D-13 + D-17 step 5: regions.py permanently deleted"
    - "territory_data.py permanently deleted"
    - "test_iberia_868.py retired (YAML gate is canonical)"
    - "Repo-wide zero functional import of iberia_config / REGIONS"
  affects:
    - "backend/medieval_forge/services/pipeline/regions.py (deleted)"
    - "backend/medieval_forge/data/regions/iberia_868/territory_data.py (deleted)"
    - "backend/tests/parity/test_iberia_868.py (deleted — R-09)"
    - "backend/medieval_forge/services/pipeline/__main__.py (migrated)"
    - "backend/tests/parity/conftest.py (migrated)"
    - "backend/tests/parity/test_iberia_868_live.py (migrated)"
    - "backend/tests/parity/test_iberia_868_render_default.py (migrated)"
    - "backend/tests/integration/test_render_endpoint.py (migrated)"
    - "backend/tests/fixtures/uat_setup.py (migrated)"
    - "backend/tests/unit/test_dag_tokens.py (extra migration)"
    - "backend/tests/unit/test_run_pipeline_on_stage.py (extra migration)"
    - "backend/tests/unit/test_regions.py (retired)"
    - "backend/tests/unit/test_migrate_iberia_to_yaml.py (retired)"
    - "scripts/migrate_iberia_to_yaml.py (retired — D-V3-04)"
tech_stack:
  added: []
  patterns:
    - "dataclasses.replace(load_region(key), ...) is the universal migration pattern for all callsites"
    - "load_region read-only call (no replace) for D-18 non-mutation assertion baseline"
key_files:
  created: []
  modified:
    - "backend/medieval_forge/services/pipeline/__main__.py (REGIONS → load_region + YAML dir scan)"
    - "backend/tests/parity/conftest.py (REGIONS → load_region)"
    - "backend/tests/parity/test_iberia_868_live.py (iberia_config → replace(load_region(...), ...))"
    - "backend/tests/parity/test_iberia_868_render_default.py (iberia_config → replace(load_region(...), ...))"
    - "backend/tests/integration/test_render_endpoint.py (iberia_config → load_region read-only)"
    - "backend/tests/fixtures/uat_setup.py (REGIONS → replace(load_region(...), ...))"
    - "backend/tests/unit/test_dag_tokens.py (REGIONS → replace(load_region(...), ...))"
    - "backend/tests/unit/test_run_pipeline_on_stage.py (REGIONS → replace(load_region(...), ...))"
decisions:
  - "All 5 planned files + 3 extra files migrated in single commit 6a388a2; __main__.py was a Plan 05-04 escape found during audit"
  - "test_regions.py retired (tested iberia_config/REGIONS directly; YAML loader tests cover it)"
  - "test_migrate_iberia_to_yaml.py retired (referenced iberia_config as baseline; impossible after deletion)"
  - "scripts/migrate_iberia_to_yaml.py retired per D-V3-04 (delete v1 dead code); git history preserves it"
  - "Docstring/comment mentions of iberia_config in tests are OK per Task 2 acceptance criteria"
metrics:
  duration: "~10 minutes (verification + SUMMARY only; code committed in prior session)"
  completed: "2026-05-12"
  tasks_completed: 3
  tasks_total: 3
  files_created: 0
  files_modified: 8
  tests_added: 0
requirements-completed: [SC-1]
---

# Phase 05 Plan 05: Delete regions.py + territory_data.py Summary

**One-liner:** D-13 + D-17 step 5 locked — `regions.py`, `territory_data.py`, and legacy `test_iberia_868.py` deleted; 8 test/fixture files (5 planned + 3 extras found by audit) migrated to `load_region('iberia_868')`; repo-wide grep for `iberia_config` and `REGIONS` returns zero functional code hits.

## What Was Built

### Task 1: Pre-deletion audit (verified by commits 6a388a2, c0be89e)

The audit found:
- Zero production callsites in `backend/medieval_forge/` for the doomed symbols (Plan 05-04 had already swapped `generate.py` and `render.py`)
- **3 extra files beyond the planned 5** still importing doomed symbols: `__main__.py` (production escape from Plan 05-04), `test_dag_tokens.py`, `test_run_pipeline_on_stage.py`
- **3 additional files to retire** (not migrate): `test_regions.py`, `test_migrate_iberia_to_yaml.py`, `scripts/migrate_iberia_to_yaml.py`

### Task 2: Migrate test/fixture files (6a388a2)

11 files changed (8 migrated, 3 retired), -428 LOC net:

**5 planned migrations:**
1. `conftest.py` — `REGIONS["iberia_868"]()` → `load_region("iberia_868")`
2. `test_iberia_868_live.py` — `iberia_config()` → `replace(load_region("iberia_868"), dataset=..., output_dir=...)`
3. `test_iberia_868_render_default.py` — `iberia_config()` → `replace(load_region("iberia_868"), output_dir=...)` (×2)
4. `test_render_endpoint.py` — `iberia_config()` → `load_region("iberia_868")` (read-only, no `replace` needed for D-18 baseline)
5. `uat_setup.py` — `REGIONS["iberia_868"]()` → `replace(load_region("iberia_868"), output_dir=...)`

**3 extra migrations:**
6. `__main__.py` — `REGIONS[args.region]()` → `replace(load_region(args.region), output_dir=...)` + YAML-directory scan for argparse choices
7. `test_dag_tokens.py` — `REGIONS["iberia_868"]()` → `replace(load_region("iberia_868"), ...)`
8. `test_run_pipeline_on_stage.py` — `REGIONS["iberia_868"]()` → `replace(load_region("iberia_868"), ...)`

**3 retirements:**
- `test_regions.py` — tested the deleted function; YAML loader's test_region_loader.py covers equivalent
- `test_migrate_iberia_to_yaml.py` — referenced `iberia_config()` as baseline; semantically impossible after deletion
- `scripts/migrate_iberia_to_yaml.py` — one-shot migration script; D-V3-04 delete v1 dead code; git history preserves it

### Task 3: Delete regions.py + territory_data.py + retire legacy parity test (c0be89e)

- `git rm backend/medieval_forge/services/pipeline/regions.py` (89 lines, D-13 + D-17 step 5)
- `git rm backend/medieval_forge/data/regions/iberia_868/territory_data.py` (307 lines)
- `git rm backend/tests/parity/test_iberia_868.py` (R-09 unconditional retirement; `test_iberia_868_yaml.py` from Plan 05-03 is the canonical replacement)
- `backend/medieval_forge/data/regions/iberia_868/__init__.py` remains as empty module file (OK — the package still exists for the YAML loader)
- 283 tests collect clean; YAML parity gate 11/11 green post-deletion

## Verification

```
pytest --collect-only -q
→ 283 tests collected, 0 errors

pytest tests/parity/test_iberia_868_yaml.py -q
→ 11 passed in 38.48s

pytest tests/parity/test_iberia_868_render_default.py tests/integration/test_render_endpoint.py -q
→ 12 passed in 56.91s

pytest tests/unit/test_region_loader.py tests/integration/test_generate_render_load_region.py -q
→ 32 passed in 58.92s

grep -rn "iberia_config\b" backend/medieval_forge/ --include="*.py"
→ 0 matches (R-12 gate)

grep -rn "from medieval_forge.services.pipeline.regions" backend/ tests/ --include="*.py"
→ 0 matches

grep -rn "iberia_config\b" backend/tests/ --include="*.py" | grep -v docstring
→ only docstring/comment lines (OK per Task 2 acceptance criteria)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing scope] 3 extra files beyond planned 5 needed migration**
- **Found during:** Task 1 audit (commit 6a388a2 message documents this)
- **Issue:** Plan listed 5 files to migrate; full repo audit found `__main__.py` (production — missed by Plan 05-04), `test_dag_tokens.py`, `test_run_pipeline_on_stage.py` also importing `REGIONS`
- **Fix:** Migrated all 8 (5 planned + 3 extras) in commit 6a388a2
- **Files modified:** `__main__.py`, `test_dag_tokens.py`, `test_run_pipeline_on_stage.py`
- **Commit:** 6a388a2

**2. [Rule 2 - Missing scope] 3 additional files retired (not in plan)**
- **Found during:** Task 1 audit (commit 6a388a2 message documents this)
- **Issue:** `test_regions.py` (tests deleted function), `test_migrate_iberia_to_yaml.py` (references `iberia_config` as baseline — impossible after deletion), `scripts/migrate_iberia_to_yaml.py` (imports both doomed symbols)
- **Fix:** Retired all 3 in commit 6a388a2 per D-V3-04 (delete v1 dead code)
- **Commit:** 6a388a2

### Execution Note

All code work was already committed in a prior session (commits `6a388a2` and `c0be89e`). This execution ratified the plan closure by running the full verification gate and creating the SUMMARY.md.

## Known Stubs

None — 3 files deleted, 8 files migrated, all verification gates green.

## Threat Surface

T-05-05-01: accept — deletion only; no new attack surface. Pre-deletion audit confirmed zero missed callsites before deletion. Repo-wide grep clean.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| regions.py deleted | OK_DELETED |
| territory_data.py deleted | OK_DELETED |
| test_iberia_868.py deleted (R-09) | OK_DELETED |
| grep iberia_config backend/medieval_forge/ → 0 (R-12) | CONFIRMED |
| grep regions import backend/tests/ → 0 | CONFIRMED |
| REGIONS symbol backend/tests/ → 0 code lines | CONFIRMED |
| 283 tests collect, 0 errors | PASSED |
| YAML parity gate 11/11 | PASSED |
| D-17 + D-18 invariant tests green (12 passed) | PASSED |
| region_loader + integration tests 32 passed | PASSED |
| Commit 6a388a2 (migration) | FOUND |
| Commit c0be89e (deletion) | FOUND |
