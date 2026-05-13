---
phase: 06-export-contract-validation-gate
plan: 03
subsystem: backend/services/export + backend/api/v3
tags: [validator-wiring, v3-endpoint, d-04-atomic, e2e-coverage]
dependency-graph:
  requires:
    - backend/medieval_forge/services/export/__init__.py (06-01 re-exports)
    - backend/medieval_forge/services/export/validator.py (06-02 _check_* bodies)
    - backend/medieval_forge/services/export/schemas.py (MANIFEST_SCHEMA_VERSION=2)
    - backend/medieval_forge/services/pipeline/region_loader.py (load_region)
  provides:
    - build_unity_zip(project_id, cfg, region_key) -- validator-gated zip builder
    - POST /api/v3/projects/{id}/export with ?dry_run=true (D-03)
    - GET /api/v3/projects/{id}/export/download
    - D-08 structured error envelope on gate failure
    - MANIFEST v2 (schema_version, region_key, generated_at_utc, validation_report, per-file sha256)
    - 10 e2e tests across 3 files (SC-3, SC-4-Iberia, SC-4-France, SC-4-Broken)
    - 5 HTTP wiring unit tests
  affects:
    - frontend Export button TEMPORARILY broken until Phase 06.1/07 (D-19; documented)
    - any caller of services.export.build_unity_zip must pass (cfg, region_key)
tech-stack:
  added: []  # all deps pre-existing
  patterns:
    - "Validator-gated zip builder: raise ValidationFailedError BEFORE writing .tmp (no leak)"
    - "Atomic D-04: 5 file changes + 1 new test in a single commit (a95ffce)"
    - "Cross-layer COLOR_COLLISION fixture via PLAINS_RGB swap (avoids dict-key-collapse)"
    - "Pipeline-output dir resolution: prefer project_dir/output (v3); fallback project_dir/generated (v1)"
key-files:
  created:
    - backend/medieval_forge/api/v3/export.py
    - backend/tests/unit/api/test_v3_export_endpoint.py
    - backend/tests/e2e/test_export_gate_iberia.py
    - backend/tests/e2e/test_export_gate_france.py
    - backend/tests/e2e/test_export_gate_broken.py
  modified:
    - backend/medieval_forge/services/export/zip.py
    - backend/medieval_forge/api/v3/__init__.py
    - backend/medieval_forge/main.py
    - backend/tests/parity/test_iberia_868_yaml.py
  deleted:
    - backend/medieval_forge/api/export.py
    - backend/tests/test_export.py
decisions:
  - "Atomic D-04: v1 delete + v3 add in commit a95ffce -- no between-commit window where parity could break"
  - "build_unity_zip signature change is intentional. Old single-arg form was v1-only; deleted in same commit as the v1 endpoint"
  - "_resolve_generated_dir prefers project_dir/output (v3 generate.py:140 target). The /generated fallback covers any in-flight v1 project; can be removed once v1 pipeline fully retired"
  - "generated_at_utc uses validator-call time (v3 pipeline emits no per-run timestamp). Documented as stand-in in zip.py docstring"
  - "Cross-layer COLOR_COLLISION fixture (PLAINS_RGB swap) is the right e2e induction for D-13 -- JSON dict-key-collapse made within-file untestable at unit layer (06-02 carry-over)"
  - "Hard precondition `assert 'original_idx' in meta['condados'][0]` added in drop_original_idx broken test (advisor item #6) -- prevents silent no-op if autogen ever regresses"
  - "Iberia e2e gets its own module-scope fixture (cannot share parity session-scope fixture across test modules without coupling test ordering)"
metrics:
  duration: "~12 min"
  completed: 2026-05-13T15:35:00Z
  tasks_completed: 3
  files_created: 5
  files_modified: 4
  files_deleted: 2
  commits: 3
  e2e_tests_added: 10
  unit_tests_added: 5
---

# Phase 06 Plan 03: Wire validator into build_unity_zip + v3 endpoint + e2e gate Summary

One-liner: Wired `validate_export()` into `build_unity_zip` (raises `ValidationFailedError` before any zip artifact is written), shipped `POST /api/v3/projects/{id}/export?dry_run=<bool>` with the D-08 structured error envelope, atomically deleted v1 `api/export.py` + `tests/test_export.py`, and landed 10 e2e tests across 3 files that prove every D-08 code is exercised end-to-end.

## What Was Built

Three atomic commits, three tasks. The Phase 06 export gate is now wired end-to-end: pipeline output -> validator -> v3 endpoint -> 422 on fail / 201 on pass / 200 on dry-run.

### Three atomic commits

| Commit  | Task | Subject                                                                                     |
| ------- | ---- | ------------------------------------------------------------------------------------------- |
| 5401962 | 1    | feat(06-03): refactor build_unity_zip + expand MANIFEST + extend Iberia parity (D-07, D-16) |
| a95ffce | 2    | feat(06-03): add v3 export endpoint with validation gate; remove v1 (D-04)                  |
| 96b6a9e | 3    | test(06-03): land 3 e2e gate test files -- Iberia + France + broken aggregate (D-14/17/18)  |

### Final endpoint surface

```
POST /api/v3/projects/{project_id}/export?dry_run=<bool>
GET  /api/v3/projects/{project_id}/export/download
```

Verified live via `python -c "from medieval_forge.main import app; ..."`:

```
/api/v3/projects/{project_id}/export
/api/v3/projects/{project_id}/export/download
```

Both registered. The 5 wiring unit tests in `backend/tests/unit/api/test_v3_export_endpoint.py` confirm this stays true on every CI run.

### Pipeline-output dir resolution

The endpoint and the zip builder both prefer `project_dir/output` (v3 generate.py:140 target) and fall back to `project_dir/generated` only if the v3 path is missing/empty. In test runs the parity fixture uses `tmp_path_factory.mktemp` directly (no PROJECTS_ROOT involvement) so the fallback never triggered in the e2e suite. The fallback is genuinely v1-transition compat -- safe to remove once the v1 pipeline path is fully retired.

### MANIFEST shape (D-07 verified)

The new MANIFEST.json embeds the validation report directly. A real example shape produced inside an Iberia run zip:

```json
{
  "schema_version": 2,
  "region_key": "iberia_868",
  "project_id": "<uuid>",
  "generated_at_utc": "2026-05-13T15:32:01.234567+00:00",
  "exported_at_utc": "20260513-153201",
  "spec_version": 1,
  "phase": 6,
  "validation_report": {
    "passed": true,
    "errors": [],
    "warnings": []
  },
  "files": [
    {
      "name": "lookup_barony.png",
      "source": "generated",
      "size_bytes": 24813,
      "sha256": "a1b2c3d4...<64 hex>"
    },
    ...
  ]
}
```

Per-file `sha256` is a 64-char lowercase hex string. The validator computes it once at file-read time and passes the `sha256_by_file` dict back through to `build_unity_zip` (no second I/O pass). For placeholder bytes (not seen by the validator), the zip builder hashes inline at write time.

## Test Results

### Per-code coverage matrix (D-08)

Every D-08 code has unit + e2e coverage now:

| Code                      | Unit                                        | E2E broken fixture                                    | Iberia parity (sanity 0 occurrences) |
| ------------------------- | ------------------------------------------- | ----------------------------------------------------- | ------------------------------------ |
| SCHEMA_INVALID            | test_export_schemas.py (15)                 | test_broken_corrupt_json_*                            | 0                                    |
| COLOR_COLLISION           | test_validator_color_collision.py (6)       | test_broken_duplicate_lookup_color_*                  | 0                                    |
| OCEAN_LEAK                | test_validator_ocean_leak.py (5)            | test_broken_paint_ocean_leak_*                        | 0                                    |
| MISSING_ORIGINAL_IDX      | test_validator_original_idx.py (6)          | test_broken_drop_original_idx_*                       | 0                                    |
| TERRITORY_TOO_SMALL       | test_validator_territory_size.py (7)        | test_broken_shrink_territory_*                        | 0                                    |
| PIXEL_CENTER_OUT_OF_RANGE | test_validator_pixel_center.py (8)          | test_broken_pixel_center_out_of_range_*               | 0                                    |
| (aggregate, D-18)         | --                                          | test_aggregate_five_failures_records_all_five_codes_* | --                                   |

### Full suite numbers

| Suite                                         | Count        | Notes                                                                          |
| --------------------------------------------- | ------------ | ------------------------------------------------------------------------------ |
| backend/tests/unit (187 tests)                | 187 pass     | Includes 5 new test_v3_export_endpoint.py + 47 export/validator tests          |
| backend/tests/parity (Iberia + render + live) | 13 pass + 6 xfail + 4 xpass | xfail/xpass are pre-existing Plan 02-03 live-OSM (deferred to Phase 02.1)      |
| backend/tests/e2e (4 files)                   | 18 pass      | 10 new gate tests + 8 pre-existing France contract tests                       |
| **Total**                                     | **218 pass** | + 6 xfail + 4 xpass; wall-clock 207s (Iberia is the cost driver)               |

Wall-clock breakdown:
- Iberia parity fixture: ~30s (session-scoped, runs once for whole suite)
- Iberia e2e gate fixture: ~27s (module-scoped, separate Iberia run; could share with parity later)
- France clean run + France broken-source run + per-test mutations: ~10s combined
- Everything else: ~140s (other parity tests, unit suite churn)

## Decisions Made

### Atomic D-04

All 5 file changes (create api/v3/export.py, update api/v3/__init__.py, update main.py, delete api/export.py, delete tests/test_export.py) plus the new `tests/unit/api/test_v3_export_endpoint.py` landed in commit `a95ffce` as a single `git add` set. No transitional shim, no parity break window. Phase 05 precedent (commit 6a388a2) repeated.

### Signature change isolated to one commit window

Task 1 broke `tests/test_export.py` by design (single-arg `build_unity_zip(project_id)` no longer exists). Task 1 verify excluded that path; Task 2 immediately deleted the broken test file. Between Task 1 (5401962) and Task 2 (a95ffce) commits the build was intentionally inconsistent -- documented in Task 1 commit message body.

### Hard precondition in drop_original_idx test

Per advisor item #6: if France's autogen path ever stops emitting `original_idx` on condados, the silent `if "original_idx" in meta["condados"][0]: del ...` would leave the test asserting `count == 1` against a count of 0. The plan-literal guarded `if` was replaced with an explicit `assert "original_idx" in ...` so a regression in `_autogen_territories` surfaces as a clear failure in the broken-fixture test rather than a confusing one-off in some downstream consumer.

## Deviations from Plan

None substantive. Two minor judgment calls:

1. **Test names dropped the "_only" suffix on broken tests where the assertion was deliberately loose** (e.g., `test_broken_duplicate_lookup_color_triggers_color_collision` vs the plan's `_color_collision_only`). The "only" name implied an exact-codes count; the body asserts presence (`len >= 1`) per advisor item #5. Names now match behavior.

2. **`tests/unit/api/test_v3_export_endpoint.py` is in the plan but not in the frontmatter `files_modified` array.** Plan Step F creates it explicitly. Caught via advisor item #2.

## Frontend Export Button Status (D-19)

The React Export button (Phase 03/04 UI) still calls v1 `POST /api/projects/{id}/export`. Since v1 is now deleted, the button is **temporarily broken** until Phase 06.1 / 07 swaps it to v3 + renders the D-08 structured error envelope. Documented in:

- `backend/medieval_forge/api/v3/export.py` module docstring (lines 7-11)
- This summary

Acceptable per CONTEXT.md (tools-first delivery; UI is not under SC in v3 PROJECT.md).

## Skipped tests

None observed. France toy region had ample ocean pixels (>= 5 in the OCEAN_LEAK test and >= 1 in the aggregate) so neither pytest.skip branch triggered in this run.

## Threat Surface Scan

No new external network endpoints, auth paths, or schema changes at trust boundaries. T-06-03-01..07 dispositions all implemented or accepted:

- T-06-03-01 (UUID gate): `is_valid_uuid(project_id)` at endpoint entry -- inherited from v1 pattern
- T-06-03-02 (project_dir traversal): `services/paths.py:36-52` `is_relative_to(root)` check
- T-06-03-03 (dry_run coercion): FastAPI bool coercion; `?dry_run=banana` returns 422 (test_post_v3_export_dry_run_with_invalid_value_rejected_by_fastapi)
- T-06-03-04 (concurrent validator DoS): single-user local; accepted
- T-06-03-05 (error context disclosure): single-user local; accepted (this IS the debug surface)
- T-06-03-06 (validator on missing dir): explicit 409 pre-check on dry_run path; FileNotFoundError -> 409 on real-run path
- T-06-03-07 (status flip on fail): only flips on 201; 422/409 preserve existing status

No threat flags raised.

## Known Stubs

None remaining in Phase 06. The 5 `_check_*` bodies from 06-02 are wired and live in production code paths now. No `NotImplementedError("06-0X")` string survives anywhere in `services/export/`.

## Phase 06 Status

All 4 success criteria met:

- **SC-1** (all JSON outputs schema-validated): pydantic schemas in `services/export/schemas.py` + validator orchestrator; unit + e2e + parity all green.
- **SC-2** (export blocked on 5 failures): 5 isolated broken fixtures + 1 aggregate; per-code coverage matrix E2E column GREEN.
- **SC-3** (MANIFEST matches Reconquista structure): MANIFEST grew per D-07 (schema_version=2, region_key, per-file sha256, validation_report); file set canonical via EXPORT_FILE_CONTRACT.
- **SC-4** (Iberia + France pass; broken blocked): All 3 e2e files green; Iberia parity gained the D-16 gate assertion.

Phase 06 is **complete**.

## Self-Check: PASSED

- + `backend/medieval_forge/api/v3/export.py` exists (FOUND)
- + `backend/tests/unit/api/test_v3_export_endpoint.py` exists (FOUND)
- + `backend/tests/e2e/test_export_gate_iberia.py` exists (FOUND)
- + `backend/tests/e2e/test_export_gate_france.py` exists (FOUND)
- + `backend/tests/e2e/test_export_gate_broken.py` exists (FOUND)
- + `backend/medieval_forge/api/export.py` deleted (CONFIRMED absent)
- + `backend/tests/test_export.py` deleted (CONFIRMED absent)
- + Commit 5401962 (Task 1) exists (FOUND)
- + Commit a95ffce (Task 2) exists (FOUND)
- + Commit 96b6a9e (Task 3) exists (FOUND)
- + `pytest backend/tests/unit -x` exits 0 (187/187 passed)
- + `pytest backend/tests/parity/test_iberia_868_yaml.py -x` exits 0 (12/12 passed, D-16 included)
- + `pytest backend/tests/e2e -x` exits 0 (18/18 passed including all 10 new gate tests)
- + Combined run: 218 passed + 6 xfailed (pre-existing live-OSM) + 4 xpassed
- + No `NotImplementedError("06-0X"` strings in validator.py
- + Route `/api/v3/projects/{project_id}/export` registered
- + `from .api.export import` NOT present in main.py
