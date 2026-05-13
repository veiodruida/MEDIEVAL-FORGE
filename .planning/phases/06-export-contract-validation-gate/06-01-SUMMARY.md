---
phase: 06-export-contract-validation-gate
plan: 01
subsystem: backend/services/export
tags: [pydantic-v2, schema-validation, export-gate, refactor]
dependency-graph:
  requires:
    - backend/medieval_forge/services/pipeline/contracts.py (EXPORT_FILE_CONTRACT, RegionConfig)
    - backend/medieval_forge/services/pipeline/region_loader.py (RegionConfigSchema idiom)
    - backend/medieval_forge/services/pipeline/export.py (territory_metadata.json writer — schema fidelity source)
  provides:
    - services/export package (zip.py + schemas.py + validator.py + __init__.py)
    - 6 pydantic v2 schemas + MANIFEST_SCHEMA_VERSION = 2
    - validate_export() signature + ValidationReport + ValidationFailedError
    - 15 unit tests for SCHEMA_INVALID code coverage (D-08)
  affects:
    - backend/medieval_forge/api/export.py (caller — unchanged, re-export preserved)
    - backend/tests/test_export.py (still imports build_unity_zip + UNITY_ZIP_SPEC; unchanged)
tech-stack:
  added: []  # pydantic v2.7+, hashlib, pathlib all pre-existing
  patterns:
    - "RootModel[dict[str, T]] for top-level-dict JSON schemas (pydantic v2 idiom)"
    - "ConfigDict(extra='forbid') on every internal BaseModel for drift detection"
    - "Internal mutable _ValidationContext dataclass; public return is pydantic ValidationReport"
    - "Stub functions raise NotImplementedError('06-02: ...') — keeps gate honest until bodies land"
key-files:
  created:
    - backend/medieval_forge/services/export/__init__.py
    - backend/medieval_forge/services/export/zip.py
    - backend/medieval_forge/services/export/schemas.py
    - backend/medieval_forge/services/export/validator.py
    - backend/tests/unit/test_export_schemas.py
  modified: []
  deleted:
    - backend/medieval_forge/services/export.py (content moved verbatim to services/export/zip.py)
decisions:
  - "RootModel over BaseModel-with-root-field for LookupBaronyColorsSchema, LookupCondadoColorsSchema, TerrainTypesSchema (pydantic v2 idiom; cleaner JSON shape; tests pass on first try)"
  - "MANIFEST_SCHEMA_VERSION = 2 at module-top constant (Karpathy simplicity: no __version__ field for a single int)"
  - "Validator-time sha256 (RESEARCH §Per-Discretion #2; one I/O pass)"
  - "ValidationFailedError lives in validator.py + re-exports through __init__; raised by build_unity_zip in Plan 06-03, NOT by validate_export itself (D-01 pure-function discipline)"
  - "_CONDITIONAL_FILES = {mountains_mask.png, rivers_overlay.png} short-circuits SCHEMA_INVALID for toy France region (precedent: tests/e2e/test_france_1066_export_contract.py:44-48)"
metrics:
  duration: "~25 min"
  completed: 2026-05-13T15:10:52Z
  tasks_completed: 3
  files_created: 5
  files_modified: 0
  files_deleted: 1
  commits: 3
  unit_tests_added: 15
---

# Phase 06 Plan 01: Carve out services/export/ subpackage + land pydantic schemas + validator stubs Summary

One-liner: Split monolithic services/export.py file into services/export/ package (zip.py + schemas.py + validator.py + __init__) and land 6 pydantic v2 schemas + 15 SCHEMA_INVALID unit tests + validator orchestrator skeleton — bodies of 5 semantic checks deferred to Plan 06-02.

## What Was Built

Plan 06-01 was a foundational refactor — zero new behavior, but the contract surface that Plans 06-02 (semantic check bodies) and 06-03 (endpoint + zip-builder wiring) consume.

### Three atomic commits, three tasks

| Commit  | Task                                                              | Summary                                                                                                  |
| ------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 1885c27 | Task 1: convert services/export.py file → services/export/ package | Verbatim move of build_unity_zip + UNITY_ZIP_SPEC + PLACEHOLDER_FILES into zip.py; __init__.py re-exports preserve every existing caller |
| 263871b | Task 2: 6 pydantic v2 schemas + 15 unit tests                     | schemas.py with RootModel dict-shape schemas + BaseModel territory-metadata-shape schemas; test_export_schemas.py covers accept/reject of every schema |
| aa535ef | Task 3: validator.py with orchestrator + 5 stub check functions   | validate_export() pure function + ValidationFailedError + Step 1 (read + sha256 + parse) + Step 2 (schema validation) IMPLEMENTED; 5 _check_* stubs raise NotImplementedError until 06-02 |

### Final module layout

```
backend/medieval_forge/services/export/
├── __init__.py        # re-exports: build_unity_zip, schemas, validate_export, ValidationFailedError
├── zip.py             # build_unity_zip (verbatim from old services/export.py)
├── schemas.py         # 6 pydantic v2 schemas + MANIFEST_SCHEMA_VERSION = 2
└── validator.py       # validate_export() orchestrator + 5 stub check fns + ValidationFailedError
```

## Decisions Made

### RootModel vs BaseModel-with-`root`-field (RESEARCH Open Q2)

**Picked: RootModel.** Tests passed on first try with `RootModel[dict[str, int]]` + `@field_validator("root")`. No pydantic v2.7 quirks observed. All three dict-shape schemas (LookupBaronyColorsSchema, LookupCondadoColorsSchema, TerrainTypesSchema) consistently use RootModel. The `.root` attribute is preserved on parsed objects (used in test assertions) but JSON serialization stays plain dict.

### MANIFEST_SCHEMA_VERSION placement

**Module-level constant** at top of schemas.py. Karpathy simplicity: no `__version__` field for a single integer.

### Validator returns report; ValidationFailedError raised by the caller

`validate_export()` is pure (D-01) — it returns `(ValidationReport, sha256_map)` and never raises ValidationFailedError. The exception type is defined in validator.py but is raised by `build_unity_zip` in Plan 06-03 when the report says `passed=False`. Endpoint catches it and maps to HTTP 422.

### Conditional-file handling (toy regions)

`_CONDITIONAL_FILES = frozenset({"mountains_mask.png", "rivers_overlay.png"})` short-circuits the "missing → SCHEMA_INVALID" branch in Step 1 of the orchestrator. Established precedent: `backend/tests/e2e/test_france_1066_export_contract.py:44-48`. Without this gate, toy France would always 422.

## Schema Fields That Surprised vs. RESEARCH

No surprises. The RESEARCH §Pydantic Schema Templates section was field-accurate against the canonical golden territory_metadata.json. The only meaningful detail clarified during implementation:

- **BaronyEntrySchema legitimately omits `original_idx`.** Confirmed by directly inspecting `tests/fixtures/iberia_868/golden/territory_metadata.json:1838+` — baronies in the golden have only `{name, condado_idx, duchy, pixel_count}`. D-11 (condados-only) is therefore enforced by *absence of the field* on the schema, not by an explicit `Optional`. The validator's `_check_original_idx` body (Plan 06-02) will scan only the `condados[]` list.

## Callers Discovered During Verification

Same as the plan's pre-flight grep. No surprise consumers:

- `backend/medieval_forge/api/export.py:12` → `from ..services.export import build_unity_zip` (still resolves through __init__.py)
- `backend/tests/test_export.py:39, 91, 139` → imports `build_unity_zip` and `UNITY_ZIP_SPEC` (still resolves)
- `backend/medieval_forge/main.py:40` (indirect via api.export router import)

All resolved through __init__.py re-exports — zero source changes outside services/export/.

## Pydantic v2 Idiom Notes

- `RootModel[dict[str, int]]` + `@field_validator("root")` worked exactly as RESEARCH documented; no v2.7 quirks.
- `ConfigDict(extra="forbid")` correctly rejects unknown fields (tested via `condados[0].extra_key = "x"` → ValidationError).
- `Field(pattern=r"^[0-9a-f]{64}$")` on `ManifestFileEntry.sha256` correctly rejects short hex strings.
- `Field(ge=1)` on `CondadoEntrySchema.pixel_count` correctly rejects `pixel_count: 0` (matches export.py:52 compaction — empty condados are dropped, never emitted with 0).

## Deviations from Plan

None. Plan executed exactly as written.

The only minor judgment call was the number of unit tests: the plan targeted "13+" tests; the final test file ships **15** tests — added two extras (one for `LookupCondadoColorsSchema` accept/reject parity with barony, one sanity check on `ValidationReport` default state). Both are inside the spirit of the plan's behavior list (Test 4 expansion + Test 11 sanity).

## Test Coverage

- **15 unit tests** in `backend/tests/unit/test_export_schemas.py` — all pass in 0.03s.
- **6 existing tests** in `backend/tests/test_export.py` — all pass (re-export contract preserved).
- **11 parity tests** in `backend/tests/parity/test_iberia_868_yaml.py` — all pass (no behavior change in zip builder).
- **150 total unit tests** across `backend/tests/unit/` — all pass after refactor.

## Threat Surface Scan

No new external network endpoints, auth paths, or schema changes at trust boundaries introduced by Plan 06-01. The pipeline-output → schema boundary noted in the threat register is established but unenforced at the file level until Plan 06-02 fills the `_check_*` bodies. No threat flags raised.

## Known Stubs

5 stub functions in `backend/medieval_forge/services/export/validator.py` (lines 195-237) raise `NotImplementedError("06-02: fill body")`:

- `_check_color_collision`
- `_check_ocean_leak`
- `_check_territory_size`
- `_check_original_idx`
- `_check_pixel_center`

**These are intentional.** Plan 06-02 fills them. They are NOT yet wired into `build_unity_zip` (Plan 06-03's job) — any accidental call surfaces immediately because `validate_export` is not invoked from production code paths today. Phase 06's plan-of-plans sequencing makes the stubs safe.

## Next Steps

- **Plan 06-02:** Fill the 5 `_check_*` bodies + 5 unit-test files (one per check, per D-15).
- **Plan 06-03:** Wire `validate_export()` into `build_unity_zip`; raise `ValidationFailedError`; add `POST /api/v3/projects/{id}/export` endpoint; delete v1 `api/export.py` + `backend/tests/test_export.py`; extend `tests/parity/test_iberia_868_yaml.py` with MANIFEST.validation_report.passed assertion (D-16).

## Self-Check: PASSED

- ✓ `backend/medieval_forge/services/export/__init__.py` exists (FOUND)
- ✓ `backend/medieval_forge/services/export/zip.py` exists (FOUND)
- ✓ `backend/medieval_forge/services/export/schemas.py` exists (FOUND)
- ✓ `backend/medieval_forge/services/export/validator.py` exists (FOUND)
- ✓ `backend/tests/unit/test_export_schemas.py` exists (FOUND)
- ✓ `backend/medieval_forge/services/export.py` deleted (CONFIRMED — `! test -f` passes)
- ✓ Commit 1885c27 exists (FOUND in git log)
- ✓ Commit 263871b exists (FOUND in git log)
- ✓ Commit aa535ef exists (FOUND in git log)
- ✓ `pytest backend/tests/unit/test_export_schemas.py` exits 0 (15/15 passed)
- ✓ `pytest backend/tests/test_export.py` exits 0 (6/6 passed)
- ✓ `pytest backend/tests/parity/test_iberia_868_yaml.py` exits 0 (11/11 passed)
- ✓ `pytest backend/tests/unit` exits 0 (150/150 passed)
