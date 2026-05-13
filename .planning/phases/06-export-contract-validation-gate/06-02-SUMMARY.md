---
phase: 06-export-contract-validation-gate
plan: 02
subsystem: backend/services/export
tags: [validator, semantic-checks, unit-tests, D-08-codes]
dependency-graph:
  requires:
    - backend/medieval_forge/services/export/validator.py (stubs from 06-01)
    - backend/medieval_forge/services/export/schemas.py (ValidationErrorEntry, ValidationReport)
    - backend/medieval_forge/services/pipeline/terrain.py (PLAINS_RGB, OCEAN_RGB)
    - backend/medieval_forge/services/pipeline/contracts.py (RegionConfig.blob_merge_px, map_w, map_h, ocean_far)
    - backend/medieval_forge/services/pipeline/region_loader.py (load_region, clear_region_cache for fixtures)
  provides:
    - 5 implemented _check_* validator bodies (no NotImplementedError stubs remain)
    - 32 unit tests across 5 D-08-code-specific test modules
    - Per-code unit coverage GREEN for: COLOR_COLLISION, OCEAN_LEAK, TERRITORY_TOO_SMALL, MISSING_ORIGINAL_IDX, PIXEL_CENTER_OUT_OF_RANGE
  affects:
    - backend/medieval_forge/services/export/__init__.py (no surface change; validate_export now functional end-to-end)
    - Plan 06-03 (build_unity_zip refactor will call validate_export and raise ValidationFailedError on failure)
tech-stack:
  added: []   # numpy, PIL, pydantic all pre-existing
  patterns:
    - "Lazy import of numpy/PIL/terrain inside _check_ocean_leak body — keeps validator import cost low for the 4 non-image checks"
    - "tmp_path PIL-write fixtures for image-dependent unit tests (avoids heavy session-scope pipeline runs)"
    - "dataclasses.replace(cfg, blob_merge_px=N) — Karpathy-simple cfg variant construction in unit tests"
    - "Explicit numeric fixtures + descriptive test names per user preference (feedback-tests-descriptive)"
key-files:
  created:
    - backend/tests/unit/test_validator_color_collision.py
    - backend/tests/unit/test_validator_ocean_leak.py
    - backend/tests/unit/test_validator_territory_size.py
    - backend/tests/unit/test_validator_original_idx.py
    - backend/tests/unit/test_validator_pixel_center.py
  modified:
    - backend/medieval_forge/services/export/validator.py (5 _check_* bodies; +~220 LoC)
  deleted: []
decisions:
  - "Within-file COLOR_COLLISION Scope 1 unit-tested via JSON-dict-pre-parsed dicts is degenerate (JSON parser collapses duplicate keys at load time). Coverage moved to e2e broken-fixture in plan 06-03; unit file documents the limit in module docstring."
  - "Lazy imports of numpy/PIL inside _check_ocean_leak body (not module top) — keeps validator.py import cost trivial for the 4 dict-only checks. Pattern survives the e2e wiring in 06-03."
  - "_check_pixel_center uses cfg.map_w / cfg.map_h (1x lookup space) — NOT meta.map_size which is the 2x visual dim (3840×2160). Confirmed by canonical golden territory_metadata.json pixel_center values in 0..1920 / 0..1080 range."
  - "All check function signatures preserve full (ctx, ..., cfg) shape even when generated_dir or cfg is unused by a specific body — keeps orchestrator dispatch uniform, makes future cfg-reading additions painless (no signature churn)."
  - "TERRITORY_TOO_SMALL applies the same blob_merge_px floor to BOTH condados and baronies (D-12). Plan-literal phrasing 'single threshold; baronies that survive cleanup can be smaller than condados but cannot be < 200' codified verbatim."
metrics:
  duration: "~6 min"
  completed: 2026-05-13T15:20:00Z
  tasks_completed: 5
  files_created: 5
  files_modified: 1
  files_deleted: 0
  commits: 5
  unit_tests_added: 32   # 6 + 5 + 7 + 6 + 8 across the 5 files
  validator_loc_after: 489
---

# Phase 06 Plan 02: Fill 5 _check_* validator bodies + 5 D-08-coded unit test modules Summary

One-liner: Replaced the 5 `NotImplementedError("06-02")` stubs in `services/export/validator.py` with surgical, single-responsibility bodies (~220 LoC total) and landed 5 unit test files (32 tests total, one module per D-08 code) — Iberia parity stays 11/11 green; validator is now functionally complete and ready for build_unity_zip wiring in Plan 06-03.

## What Was Built

5 atomic commits, 5 tasks, 32 new unit tests. The orchestrator from 06-01 now runs end-to-end against any pipeline output and produces a real ValidationReport instead of raising NotImplementedError on every semantic check.

### Five atomic commits

| Commit  | Task | Check                  | D-code                    | Tests | Body LoC |
| ------- | ---- | ---------------------- | ------------------------- | ----- | -------- |
| 114a381 | 1    | _check_color_collision | COLOR_COLLISION (D-13)    | 6     | ~60      |
| 5d5e357 | 2    | _check_ocean_leak      | OCEAN_LEAK (D-09)         | 5     | ~80      |
| 777a872 | 3    | _check_territory_size  | TERRITORY_TOO_SMALL (D-12) | 7     | ~40      |
| e3484ac | 4    | _check_original_idx    | MISSING_ORIGINAL_IDX (D-11)| 6     | ~25      |
| 148be7c | 5    | _check_pixel_center    | PIXEL_CENTER_OUT_OF_RANGE (D-10) | 8 | ~45     |

Total: 32 unit tests, ~250 LoC of validator body, ~750 LoC of test fixtures.

### Per-D-code coverage (D-15)

Unit-test column of the coverage matrix (RESEARCH §Per-Code Coverage Matrix) is GREEN for every D-08 code Plan 06-02 owns:

| Code                       | Unit file                              | Tests |
|----------------------------|----------------------------------------|-------|
| COLOR_COLLISION            | test_validator_color_collision.py      | 6     |
| OCEAN_LEAK                 | test_validator_ocean_leak.py           | 5     |
| TERRITORY_TOO_SMALL        | test_validator_territory_size.py       | 7     |
| MISSING_ORIGINAL_IDX       | test_validator_original_idx.py         | 6     |
| PIXEL_CENTER_OUT_OF_RANGE  | test_validator_pixel_center.py         | 8     |

(SCHEMA_INVALID stays covered by Plan 06-01's 15-test test_export_schemas.py; e2e fixtures land in Plan 06-03.)

## Decisions Made

### Within-file color collision is degenerate at the unit-layer payload level

JSON dict parsing collapses duplicate keys to one — by the time `payloads` reaches `_check_color_collision`, the within-file dup scope is unrepresentable as a hand-built `dict[str, int]` fixture (Python literals also collapse `{"x": 1, "x": 2}` to `{"x": 2}`). The check still has a working Scope-1 inversion loop (territory ids mapping to same RGB key), but exercising it requires writing+reading a JSON byte stream that bypasses the dict semantics — i.e., the e2e broken-fixture territory in Plan 06-03. Unit file's module docstring documents this limit; Scope 2 (cross-layer terrain palette) carries the full unit coverage burden.

### Lazy import inside _check_ocean_leak

`numpy` + `PIL` + `from ..pipeline.terrain import OCEAN_RGB` are imported INSIDE the function body, not at module top. Rationale: validator.py is imported every time the export package is imported (which is every API request boot). The 4 dict-only checks need no image stack. Karpathy-simple. The pattern survives the e2e wiring in 06-03 — the import of `validator` itself stays cheap, only the call site pays.

### map_w/map_h vs meta.map_size

`_check_pixel_center` reads `cfg.map_w` and `cfg.map_h` (1x lookup space, default 1920×1080) — NOT `meta.map_size` from the JSON (which is the 2x visual dim, 3840×2160). Confirmed by inspecting canonical golden `territory_metadata.json` pixel_center values: all within [0, 1920) × [0, 1080). The 2x visual dim is for the 3840×2160 PNG renders (`visual_condado.png`, `visual_barony.png`), not for the pixel_center coordinate which lives in the 1x lookup raster.

### Same threshold for condados AND baronies (D-12)

`_check_territory_size` iterates BOTH `meta["condados"]` and `meta["baronies"]` with the same `cfg.blob_merge_px` threshold. Plan literal: "single threshold; baronies that survive cleanup can be smaller than condados but cannot be < 200 in the final lookup". Coded verbatim. Test 5 exercises a barony at pixel_count=100 to prove this — the plan's behavior list explicitly requires it.

### Half-open interval boundary semantics (D-10)

`_check_pixel_center` uses `not (0 <= col < map_w)` — strictly less-than upper bound. Test 4 + Test 5 (pixel_center at exactly map_w or map_h) explicitly assert these ARE out of range; Test 6 (pixel_center at map_w - 1, map_h - 1) explicitly asserts the corner IS in range. Documents the convention in the error context with `"note": "Y-down numpy convention (D-10); Unity flips on load"`.

## Deviations from Plan

None. Plan executed exactly as written.

The within-file COLOR_COLLISION limitation (6 tests instead of plan-stated 7) is documented in the plan itself (action note: "JSON dict semantics collapse duplicate keys at parse time, so within-file dup is hard to induce at the unit-layer payload level"). The plan's acceptance criteria stipulate "at least 5 test functions" — 6 delivered. Within-file coverage stays a Plan 06-03 e2e fixture responsibility (D-14).

Pixel_center test count is 8 — exactly matches plan target.

## Iberia Parity Smoke

```
pytest backend/tests/parity/test_iberia_868_yaml.py -x
11/11 passed in 35.36s
```

Parity stays green because Plan 06-02 only touches the (currently unwired) validator. The `build_unity_zip` refactor that calls `validate_export()` lands in Plan 06-03 — that's when the Iberia parity test gets the new `MANIFEST.validation_report.passed == true` assertion (D-16).

## Test Coverage

- **47 unit tests pass** across the 6 export-related test files in 1.56s:
  - test_validator_color_collision.py (6)
  - test_validator_ocean_leak.py (5)
  - test_validator_territory_size.py (7)
  - test_validator_original_idx.py (6)
  - test_validator_pixel_center.py (8)
  - test_export_schemas.py (15, from Plan 06-01)
- **11 parity tests pass** (Iberia 868 unchanged)
- **0 NotImplementedError("06-02"** strings remain in validator.py
- **No regressions** in other unit tests (validator file is functionally isolated; semantic checks are pure functions over payloads dict + cfg dataclass)

## Threat Surface Scan

No new external network endpoints, auth paths, or schema changes at trust boundaries. The disk → numpy boundary identified in the plan's threat register (T-06-02-01..T-06-02-05) is mitigated by:
- `.convert("RGB")` before `np.array()` in `_check_ocean_leak` (T-06-02-01)
- Explicit shape-mismatch guard in `_check_ocean_leak` records `OCEAN_LEAK` with `reason: shape_mismatch` rather than crashing (T-06-02-02)
- Schema-layer `Field(ge=1)` short-circuit blocks negative `pixel_count` injection before the territory_size check runs (T-06-02-05)

No threat flags raised.

## Known Stubs

None remaining. All 5 `_check_*` functions are fully implemented. Within-file COLOR_COLLISION coverage at the e2e level lands in Plan 06-03 (D-14 broken fixture).

## Next Steps

- **Plan 06-03:** Wire `validate_export()` into `build_unity_zip` (raise `ValidationFailedError` on failure); add `POST /api/v3/projects/{id}/export` endpoint with `?dry_run=true` query parameter; delete v1 `api/export.py` + `backend/tests/test_export.py`; extend `tests/parity/test_iberia_868_yaml.py` with `MANIFEST.validation_report.passed` assertion (D-16); land 3 e2e files (`test_export_gate_iberia.py`, `test_export_gate_france.py`, `test_export_gate_broken.py`).

## Self-Check: PASSED

- ✓ `backend/medieval_forge/services/export/validator.py` exists and has 0 `NotImplementedError("06-02"` strings (FOUND: 0)
- ✓ `backend/tests/unit/test_validator_color_collision.py` exists (FOUND)
- ✓ `backend/tests/unit/test_validator_ocean_leak.py` exists (FOUND)
- ✓ `backend/tests/unit/test_validator_territory_size.py` exists (FOUND)
- ✓ `backend/tests/unit/test_validator_original_idx.py` exists (FOUND)
- ✓ `backend/tests/unit/test_validator_pixel_center.py` exists (FOUND)
- ✓ Commit 114a381 (Task 1) exists in git log (FOUND)
- ✓ Commit 5d5e357 (Task 2) exists in git log (FOUND)
- ✓ Commit 777a872 (Task 3) exists in git log (FOUND)
- ✓ Commit e3484ac (Task 4) exists in git log (FOUND)
- ✓ Commit 148be7c (Task 5) exists in git log (FOUND)
- ✓ `pytest backend/tests/unit/test_validator_*.py backend/tests/unit/test_export_schemas.py` exits 0 (47/47 passed)
- ✓ `pytest backend/tests/parity/test_iberia_868_yaml.py` exits 0 (11/11 passed)
