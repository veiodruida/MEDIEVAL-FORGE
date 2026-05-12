---
phase: "05"
plan: "01"
subsystem: "backend/pipeline"
tags: [region-loader, yaml, pydantic, security, tdd, autogen]
dependency_graph:
  requires: []
  provides:
    - "load_region API (key→RegionConfig)"
    - "RegionConfigSchema (pydantic, extra=forbid)"
    - "clear_region_cache"
    - "Wave-0 test scaffold (12 files)"
    - "PyYAML>=6.0,<7.0 dependency"
  affects:
    - "backend/medieval_forge/services/pipeline/region_loader.py"
    - "pyproject.toml"
    - "backend/tests/conftest.py"
tech_stack:
  added:
    - "PyYAML>=6.0,<7.0 — YAML parsing via yaml.safe_load"
    - "pydantic v2 RegionConfigSchema — schema mirror of RegionConfig dataclass"
  patterns:
    - "TDD (RED→GREEN): test file committed before implementation"
    - "Explicit-only cache: _REGION_CACHE keyed by (key, str(regions_dir)); no mtime"
    - "Security guard order: key regex → safe_load → pydantic → path traversal"
key_files:
  created:
    - "backend/medieval_forge/services/pipeline/region_loader.py"
    - "backend/tests/unit/test_region_loader.py"
    - "backend/tests/unit/test_migrate_iberia_to_yaml.py"
    - "backend/tests/unit/test_gen_toy_france.py"
    - "backend/tests/unit/test_england_1216_missing_inputs.py"
    - "backend/tests/parity/test_iberia_868_yaml.py"
    - "backend/tests/integration/test_generate_render_load_region.py"
    - "backend/tests/api/test_regions_endpoint.py"
    - "backend/tests/e2e/test_france_1066_export_contract.py"
    - "backend/tests/e2e/__init__.py"
    - "frontend/src/components/projects/__tests__/NewProjectModal.test.tsx"
    - "frontend/tests/uat/playwright/france_1066_create_project.spec.ts"
  modified:
    - "pyproject.toml (PyYAML added)"
    - "backend/tests/conftest.py (clear_region_cache_between_tests fixture)"
decisions:
  - "PyYAML in root pyproject.toml, not backend/pyproject.toml (backend/ has no pyproject.toml)"
  - "Cache keyed by (key, str(regions_dir)) for test isolation across tmp_path fixtures"
  - "kingdoms/duchies/condados remain list[dict] in schema (pipeline tuple format is Plan 05-04's concern)"
  - "RESEARCH recommendation adopted: explicit-only cache (mtime skipped on Windows NTFS)"
  - "Autogen condados stored as list[dict] with original_idx; voronoi.py tuple conversion is Plan 05-04"
metrics:
  duration: "~65 minutes"
  completed: "2026-05-12"
  tasks_completed: 2
  tasks_total: 2
  files_created: 13
  files_modified: 2
  tests_added: 26
---

# Phase 05 Plan 01: Region Loader Foundation Summary

**One-liner:** YAML-backed `load_region` API with pydantic schema, explicit cache, autogen-from-centroids, and 5 security guards (key regex, safe_load, traversal, sigma range, extra-field rejection).

## What Was Built

### Task 1: PyYAML dependency + Wave-0 test scaffold (b29bfb2)

- Added `PyYAML>=6.0,<7.0` to root `pyproject.toml` (RESEARCH gap closed)
- Created 8 backend scaffold test files (unit/parity/integration/api/e2e), each with 1 `pytest.skip` placeholder — all collected cleanly by pytest with zero ERROR lines
- Created `backend/tests/e2e/__init__.py` (new directory needed)
- Created vitest scaffold `NewProjectModal.test.tsx` (Plan 05-08 target)
- Created Playwright scaffold `france_1066_create_project.spec.ts` (Plan 05-10 target)
- Added `clear_region_cache_between_tests` autouse fixture to `conftest.py` with importorskip-guarded try/except

### Task 2: Implement region_loader.py (TDD) (ee63cab → b957183)

**RED commit (ee63cab):** 26 unit tests written first, all failing with `ModuleNotFoundError`

**GREEN commit (b957183):** `region_loader.py` implemented (369 lines):

- `RegionConfigSchema`: pydantic v2 BaseModel, `extra='forbid'`, mirrors ALL YAML-serialisable fields of `RegionConfig`. Excludes `lon_scale` (derived), `on_stage` (Callable), `stop_event` (threading.Event).
- `DatasetSchema`: all 4 fields `str | None = None` (R-03: template-only regions pass pydantic cleanly)
- `load_region(key, regions_dir)`: key regex guard → YAML exists check → `yaml.safe_load` → `RegionConfigSchema.model_validate` → path resolution → dataset build → autogen → `RegionConfig(**kwargs)` → cache store
- `clear_region_cache()`: empties `_REGION_CACHE`
- `_autogen_territories`: reads pt_geojson + es_input GeoJSON features, extracts representative points, produces `Condado_001..N` dicts each with unique `original_idx` (CLAUDE.md rule 4)
- list→tuple conversions for all RGB fields + `pt_duchies` list→set

## Verification

```
pytest backend/tests/unit/test_region_loader.py -q
→ 26 passed

pytest backend/tests/parity/test_iberia_868.py -q
→ 11 passed (parity unchanged)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] pyproject.toml path correction**
- **Found during:** Task 1 (advisor call)
- **Issue:** Plan references `backend/pyproject.toml` but that file does not exist; the project's single `pyproject.toml` is at repo root
- **Fix:** Added `PyYAML>=6.0,<7.0` to root `pyproject.toml` between `Pillow` and `rasterio` (alphabetical)
- **Acceptance grep adjusted:** `grep -E '^\s*"?PyYAML' pyproject.toml` (root path)
- **Commit:** b29bfb2

**2. [Rule 2 - Missing critical] `backend/tests/e2e/` directory + `__init__.py`**
- **Found during:** Task 1
- **Issue:** `backend/tests/e2e/` did not exist; pytest collection would fail without `__init__.py`
- **Fix:** Created directory + `__init__.py` before scaffold file
- **Commit:** b29bfb2

**3. [Design note] kingdoms/duchies/condados schema uses list[dict] while voronoi.py expects tuple format**
- **Scope:** Not fixed in 05-01 — Plan 05-04 owns the pipeline adapter
- **Reason:** 05-01 loader never runs against the live pipeline; parity test still uses `iberia_config()` from `regions.py`; schema shape is Plan 05-04's concern
- **Documented:** Deferred to Plan 05-04

**4. [Cache key] Keyed by (key, str(regions_dir)) instead of key-only**
- **Reason:** Tests use multiple `tmp_path` fixtures; key-only cache would collide across tests even after `clear_region_cache()` is called between test runs. (key, dir) provides per-test isolation without touching test teardown.
- **Impact:** Transparent to production code (single regions_dir in prod); only matters in tests.

## Known Stubs

None — plan goal (loader API + scaffold files) is fully achieved. The autogen `condados` list produces dicts (not tuples); tuple conversion for voronoi.py is Plan 05-04's responsibility.

## Threat Surface

All three threat model mitigations confirmed implemented:
- T-05-01-01: `_REGION_KEY_RE = re.compile(r"^[a-z0-9_]+$")` — line 39, unit tested (6 key tests)
- T-05-01-02: `yaml.safe_load` only — 1 call at line 191; `yaml.load` grep returns 0 matches; malicious tag test passes
- T-05-01-03: `resolved.relative_to(region_root)` guard — line 255; traversal test with `../../../etc/passwd` passes

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| region_loader.py exists (≥150 lines) | FOUND (369 lines) |
| test_region_loader.py exists | FOUND |
| conftest.py contains clear_region_cache | FOUND |
| PyYAML in pyproject.toml | FOUND |
| Commit b29bfb2 (Task 1) | FOUND |
| Commit ee63cab (TDD RED) | FOUND |
| Commit b957183 (TDD GREEN) | FOUND |
| 26 tests passing | PASSED |
| Parity 11/11 green | PASSED |
