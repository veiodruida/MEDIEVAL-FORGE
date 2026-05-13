---
phase: 06-export-contract-validation-gate
verified: 2026-05-13T16:00:00Z
status: passed
score: 4/4 success criteria verified
overrides_applied: 0
---

# Phase 06: Export Contract + Validation Gate — Verification Report

**Phase Goal:** Strict 12-file Unity export with manifest, schema validation, and a gate on minimum pixels per territory + color-collision check.
**Verified:** 2026-05-13T16:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth (Success Criterion) | Status | Evidence |
|---|----------------------------|--------|----------|
| SC-1 | All JSON outputs schema-validated via pydantic | VERIFIED | `services/export/schemas.py` ships 6 top-level pydantic v2 schemas (`LookupBaronyColorsSchema`, `LookupCondadoColorsSchema`, `TerrainTypesSchema`, `TerritoryMetadataSchema`, `MountainRiverDataSchema`, `ManifestSchema`); `_SCHEMA_MAP` in `validator.py:95-101` registers all 5 contract JSONs; `_run_schema_validation` orchestrates accept/reject; 15 SCHEMA_INVALID unit tests pass in `tests/unit/test_export_schemas.py` |
| SC-2 | Export blocked on: territory <200px, lookup color collision, ocean leak, missing `original_idx`, `pixel_center` Y-axis check failure | VERIFIED | `validator.py` ships 5 fully-implemented `_check_*` functions (lines 206-486); each maps to a D-08 code: COLOR_COLLISION, OCEAN_LEAK, TERRITORY_TOO_SMALL, MISSING_ORIGINAL_IDX, PIXEL_CENTER_OUT_OF_RANGE; no NotImplementedError raises remain (only a stale doc-comment at line 200); 32 unit tests across 5 files cover each code in isolation; `build_unity_zip` raises `ValidationFailedError` BEFORE writing zip artifact (`zip.py:119-121`) |
| SC-3 | Manifest matches Reconquista structure | VERIFIED | `zip.py:155-168` writes MANIFEST.json with `schema_version=2`, `region_key`, `project_id`, `generated_at_utc`, `exported_at_utc`, `spec_version=1`, `phase=6`, embedded `validation_report`, and per-file array with `name/source/size_bytes/sha256` (64-hex enforced by `ManifestFileEntry.sha256` Field pattern); MANIFEST_SCHEMA_VERSION constant exported and equals 2; D-16 parity assertion in `tests/parity/test_iberia_868_yaml.py:152+` (`test_iberia_passes_export_gate`) |
| SC-4 | Iberia + France + a deliberately-broken project all pass through `/api/v3/export`; broken is blocked with structured error list | VERIFIED | 3 e2e test files exist: `test_export_gate_iberia.py` (1 test, asserts gate pass), `test_export_gate_france.py` (1 test, asserts toy region passes), `test_export_gate_broken.py` (8 tests covering 6 D-08 codes + aggregate); broken test file references all 6 codes (35 matches); endpoint `POST /api/v3/projects/{id}/export` returns 422 with D-08 envelope `{detail: {summary, errors, warnings}}` on gate failure (`api/v3/export.py:99-109`) |

**Score:** 4/4 success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/medieval_forge/services/export/__init__.py` | Package re-exports | VERIFIED | Re-exports `build_unity_zip`, `validate_export`, `ValidationFailedError`, 6 schemas, `MANIFEST_SCHEMA_VERSION` |
| `backend/medieval_forge/services/export/schemas.py` | 6 pydantic schemas + MANIFEST_SCHEMA_VERSION=2 | VERIFIED | Line 15: `MANIFEST_SCHEMA_VERSION: int = 2`; all 6 schemas with `ConfigDict(extra="forbid")` (except `MountainRiverDataSchema` deliberate `extra="allow"`); RootModel for dict-shape JSONs |
| `backend/medieval_forge/services/export/validator.py` | `validate_export` + 5 implemented `_check_*` + `ValidationFailedError` | VERIFIED | All 5 checks have full bodies (no `NotImplementedError` raises); orchestrator implements SCHEMA_INVALID short-circuit (D-18 exception); `_CONDITIONAL_FILES` covers toy France mountains/rivers absence |
| `backend/medieval_forge/services/export/zip.py` | `build_unity_zip(project_id, cfg, region_key)` with validator gate | VERIFIED | Validator called at line 119 BEFORE zip assembly; raises `ValidationFailedError(report)` on `passed=False`; MANIFEST embeds full report + per-file sha256 |
| `backend/medieval_forge/api/v3/export.py` | POST endpoint with dry_run + D-08 envelope | VERIFIED | Routes registered: `/api/v3/projects/{project_id}/export` and `/api/v3/projects/{project_id}/export/download`; 422 envelope on `ValidationFailedError`, 200/422 on dry_run, 409 on FileNotFoundError, 400 on bad UUID, 404 on missing project, 409 on wrong status |
| `backend/medieval_forge/api/export.py` (v1) | DELETED (D-04 atomic) | VERIFIED | File absent (`ls` confirms) |
| `backend/tests/test_export.py` (v1) | DELETED (D-04 atomic) | VERIFIED | File absent |
| `backend/tests/e2e/test_export_gate_iberia.py` | Iberia e2e | VERIFIED | 1 test |
| `backend/tests/e2e/test_export_gate_france.py` | France e2e | VERIFIED | 1 test |
| `backend/tests/e2e/test_export_gate_broken.py` | Broken aggregate e2e | VERIFIED | 8 tests covering all 6 D-08 codes |
| `backend/tests/parity/test_iberia_868_yaml.py` | D-16 extension | VERIFIED | `test_iberia_passes_export_gate` asserts `manifest.validation_report.passed == true` |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `api/v3/export.py::trigger_v3_export` | `services/export/zip.py::build_unity_zip` | function call wrapped in try/except `ValidationFailedError` | WIRED (zip.py:97) |
| `services/export/zip.py::build_unity_zip` | `services/export/validator.py::validate_export` | called before zip assembly; raises on failure | WIRED (zip.py:119-121) |
| `api/v3/__init__` | `main.py` | `v3_export_router` imported + `app.include_router` with `/api` prefix | WIRED (main.py:49,61) |
| `validator.py::_check_ocean_leak` | `pipeline/terrain.py::OCEAN_RGB` | lazy import + numpy comparison | WIRED |
| `validator.py::_check_territory_size` | `RegionConfig.blob_merge_px` | attribute read (`cfg.blob_merge_px`) | WIRED |
| `validator.py::_check_pixel_center` | `RegionConfig.map_w`/`map_h` | attribute read | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Public imports resolve | `python -c "from medieval_forge.services.export import build_unity_zip, validate_export, ValidationFailedError, ManifestSchema, MANIFEST_SCHEMA_VERSION"` | `imports OK; MANIFEST_SCHEMA_VERSION= 2` | PASS |
| v3 export routes registered | `python -c "from medieval_forge.main import app; ..."` | `['/api/v3/projects/{project_id}/export', '/api/v3/projects/{project_id}/export/download']` | PASS |
| No validator stubs remain | `grep "raise NotImplementedError" backend/medieval_forge/services/export/` | No matches (only stale comment) | PASS |
| Full backend suite | (reported in task prompt) | 329 passed, 6 xfailed (pre-existing), 4 xpassed | PASS |
| v1 surface deleted (D-04) | `ls backend/medieval_forge/api/export.py backend/tests/test_export.py` | both absent | PASS |

### Requirements Coverage

Note: `.planning/REQUIREMENTS.md` does not exist (only `v1-archive/REQUIREMENTS.md`). v3 milestone uses ROADMAP Success Criteria as the requirement source; PLAN frontmatter `requirements:` entries map to those SC ids.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SC-1 | 06-01 | All JSON outputs schema-validated via pydantic | SATISFIED | `services/export/schemas.py` + `_run_schema_validation` |
| SC-2 | 06-02 | Export blocked on 5 failure modes | SATISFIED | 5 implemented `_check_*` bodies + 32 unit tests |
| SC-3 | 06-03 | Manifest matches Reconquista structure | SATISFIED | `MANIFEST_SCHEMA_VERSION=2` + Reconquista-shaped manifest body |
| SC-4 | 06-03 | Iberia + France + broken e2e | SATISFIED | 3 e2e files, 10 tests, all D-08 codes covered |

No orphaned requirements detected. All SC ids declared in plans map to ROADMAP.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `services/export/validator.py` | 200 | Stale comment `# Plan 06-02 fills these bodies. Stubs raise NotImplementedError...` | Info | Misleading doc comment now that bodies are implemented; cosmetic only — no `raise NotImplementedError` statement remains |
| `services/export/zip.py` | 16 | Frontend Export button TEMPORARILY broken (D-19 deferral) | Info | Documented + explicitly scheduled to Phase 06.1/07; acceptable per CONTEXT.md tools-first delivery |

No blocker or warning-severity anti-patterns detected. The frontend deferral is an explicit, documented, governed deviation — not a stub.

### Human Verification Required

None required. Phase 06 is backend-only (tools-first per CONTEXT.md); no UI surface is under the success criteria. The deferred frontend Export button swap is scoped to Phase 06.1/07 and is not a Phase 06 deliverable.

### Gaps Summary

No gaps. All 4 ROADMAP success criteria are met with concrete, wired evidence:

- Schema layer: 6 pydantic schemas with `extra="forbid"` enforced; 15 SCHEMA_INVALID unit tests.
- Validator layer: 5 semantic checks implemented; 32 unit tests; orchestrator preserves D-18 collect-all-errors semantics with SCHEMA_INVALID short-circuit.
- Zip layer: validator gates BEFORE any zip artifact is written (no `.tmp` leak); MANIFEST v2 with `validation_report` + per-file `sha256`.
- HTTP layer: `POST /api/v3/projects/{id}/export` with `?dry_run=<bool>`; D-08 structured 422 envelope on failure; v1 surface atomically removed (D-04).
- Test coverage: per-code matrix is GREEN at both unit (32 tests) and e2e (10 tests) layers; Iberia parity carries the D-16 gate assertion; broken-fixture aggregate proves D-18 collect-all behavior end-to-end.

The full backend suite reports 329 passed + 6 xfailed (pre-existing, unrelated live-OSM tests deferred to Phase 02.1) + 4 xpassed. Phase 06 is complete and ready for the orchestrator to mark closed.

---

_Verified: 2026-05-13T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
