---
phase: 06-export-contract-validation-gate
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - backend/medieval_forge/api/v3/__init__.py
  - backend/medieval_forge/api/v3/export.py
  - backend/medieval_forge/main.py
  - backend/medieval_forge/services/export/__init__.py
  - backend/medieval_forge/services/export/schemas.py
  - backend/medieval_forge/services/export/validator.py
  - backend/medieval_forge/services/export/zip.py
  - backend/tests/e2e/test_export_gate_broken.py
  - backend/tests/e2e/test_export_gate_france.py
  - backend/tests/e2e/test_export_gate_iberia.py
  - backend/tests/parity/test_iberia_868_yaml.py
  - backend/tests/unit/api/test_v3_export_endpoint.py
  - backend/tests/unit/test_export_schemas.py
  - backend/tests/unit/test_validator_color_collision.py
  - backend/tests/unit/test_validator_ocean_leak.py
  - backend/tests/unit/test_validator_original_idx.py
  - backend/tests/unit/test_validator_pixel_center.py
  - backend/tests/unit/test_validator_territory_size.py
findings:
  critical: 0
  warning: 3
  info: 6
  total: 9
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-13
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

The Phase 06 export validation gate is well-structured: a pure `validate_export` function returning `(ValidationReport, sha256_map)` is wired into `build_unity_zip` (which raises `ValidationFailedError` on failure) and the v3 endpoint (which maps to a D-08 422 envelope). Schemas use pydantic v2 with `extra='forbid'`, the five semantic checks (D-09..D-13) implement their decision-log contracts faithfully, and test coverage is layered (unit checks per error code, e2e broken-fixture mutations, parity gate).

The issues found are minor: an inconsistency between the dry-run response shape and the real-export 422 envelope (D-08), divergent `generated_dir` resolution logic between the dry-run endpoint and `zip.build_unity_zip`, an `assert` used for a runtime invariant, an unsafe broad `except` in the schema-validation pass, and several small code-quality items (unused logger, missing auth/status check on `/export/download`, etc.). No critical security or correctness defects found. No source modifications recommended for Phase 06 merge; suggest tracking WR-01 and WR-02 as Phase 06.1 follow-ups.

## Warnings

### WR-01: Dry-run failure shape diverges from real-export D-08 envelope

**File:** `backend/medieval_forge/api/v3/export.py:88-93`
**Issue:** When `dry_run=true` and the gate fails, the endpoint returns status 422 with body `{"dry_run": true, "passed": false, "errors": [...], "warnings": [...]}`. When `dry_run=false` and the gate fails, it returns 422 with body `{"detail": {"summary": "...", "errors": [...], "warnings": [...]}}` (D-08 structured envelope, see lines 100-109). UI / Unity-side consumers parsing the 422 body therefore need two code paths for the same logical failure. The docstring at line 49 advertises only the D-08 shape; the dry-run shape is not documented in the function-level contract.
**Fix:** Wrap the dry-run failure path in the same envelope so both 422 responses are parseable identically:
```python
if dry_run:
    generated = project_dir(project_id) / "output"
    if not generated.is_dir():
        generated = project_dir(project_id) / "generated"
    if not generated.is_dir():
        raise HTTPException(status_code=409, detail=...)
    report, _sha = validate_export(generated, cfg)
    if report.passed:
        return JSONResponse(status_code=200, content={"dry_run": True, **report.model_dump()})
    return JSONResponse(
        status_code=422,
        content={
            "dry_run": True,
            "detail": {
                "summary": f"{len(report.errors)} errors blocked export",
                "errors": [e.model_dump() for e in report.errors],
                "warnings": [w.model_dump() for w in report.warnings],
            },
        },
    )
```

### WR-02: Inconsistent `generated_dir` resolution between dry-run and real export

**File:** `backend/medieval_forge/api/v3/export.py:80-82` vs. `backend/medieval_forge/services/export/zip.py:68-80`
**Issue:** The dry-run branch picks `project_dir/output` whenever the directory exists (`is_dir()` only). `zip._resolve_generated_dir` requires both `is_dir()` AND `any(output.iterdir())` before preferring `/output`, otherwise it falls back to `/generated`. If `/output` exists but is empty (e.g., generate started, crashed, left an empty dir), dry-run will validate against `/output` and report all files as missing (`SCHEMA_INVALID` x12), while a real export against the same project will fall back to `/generated` and may pass. Two different answers for the same project state.
**Fix:** Extract one helper and share it. Move `_resolve_generated_dir` to a module-level helper exported from `services/export` and call it from both code paths:
```python
# services/export/zip.py — already defines this; just export it
def resolve_generated_dir(project_id: str) -> Path: ...  # rename, remove leading underscore

# api/v3/export.py
from ...services.export.zip import resolve_generated_dir
...
if dry_run:
    generated = resolve_generated_dir(project_id)
    if not generated.is_dir():
        raise HTTPException(status_code=409, detail=...)
    report, _sha = validate_export(generated, cfg)
    ...
```

### WR-03: Broad `except Exception` in schema validation can mask non-validation bugs

**File:** `backend/medieval_forge/services/export/validator.py:186-195`
**Issue:** `_run_schema_validation` catches `Exception` to handle "pydantic.ValidationError or json shape mismatch", but a programming bug inside a `field_validator` (e.g., `_validate_rgb_keys` raises `AttributeError` because a key is unexpectedly `None`) would silently be reported as `SCHEMA_INVALID` against user data. This makes diagnosing pipeline-side regressions harder — the error code points at a payload defect, but the real defect is in our code.
**Fix:** Narrow to the expected exception types and let unexpected exceptions surface:
```python
from pydantic import ValidationError

try:
    Schema.model_validate(payloads[fname])
except ValidationError as exc:
    ctx.add_error(
        "SCHEMA_INVALID",
        file=fname,
        context={"errors": exc.errors()},  # structured, not stringified
        message=f"schema validation failed for {fname}",
    )
    all_ok = False
```
Bonus: `exc.errors()` yields a structured list (path/type/msg per error) rather than `str(exc)`, improving the D-08 error context for downstream UI display.

## Info

### IN-01: Module-level `assert` enforces a runtime invariant

**File:** `backend/medieval_forge/services/export/zip.py:40`
**Issue:** `assert len(UNITY_ZIP_SPEC) == 12, "Unity contract: 12 files"` is stripped when Python runs with `-O`. If a future edit to `EXPORT_FILE_CONTRACT` accidentally drops a file and CI ever runs optimized, the invariant disappears silently.
**Fix:** Replace with a runtime check:
```python
if len(UNITY_ZIP_SPEC) != 12:
    raise RuntimeError(
        f"Unity contract violated: EXPORT_FILE_CONTRACT has "
        f"{len(UNITY_ZIP_SPEC)} files, expected 12"
    )
```

### IN-02: `/export/download` endpoint lacks project existence and status checks

**File:** `backend/medieval_forge/api/v3/export.py:127-148`
**Issue:** `download_v3_export` validates the UUID format but does not look up the project, check ownership, or verify status. Any caller who knows a valid UUID can probe arbitrary project directories on disk. The POST endpoint enforces `project in db` and `project.status in {generated, exported}`; the GET does not. For a local single-user tool the impact is low, but the asymmetry is surprising and trivially fixable.
**Fix:** Add the same `db.get(Project, project_id)` + 404-on-miss pattern as the POST endpoint. Optionally check `project.status == "exported"` to surface a 409 instead of 404 when a project exists but never exported.

### IN-03: Unused module-level `logger`

**File:** `backend/medieval_forge/api/v3/export.py:30`
**Issue:** `logger = logging.getLogger(__name__)` is defined but never referenced. The export path silently succeeds or 422s — useful debugging would be a log line on each gate failure with `(project_id, len(errors), codes)`.
**Fix:** Add an info log on validation failure paths, or remove the unused binding:
```python
except ValidationFailedError as exc:
    logger.info(
        "export gate failed: project=%s errors=%d codes=%s",
        project_id, len(exc.report.errors),
        sorted({e.code for e in exc.report.errors}),
    )
    return JSONResponse(...)
```

### IN-04: Dead defensive `except ValueError` after schema-validated RGB keys

**File:** `backend/medieval_forge/services/export/validator.py:258-261`
**Issue:** `tuple(int(c) for c in rgb_key.split(","))` cannot raise `ValueError` here because `_run_schema_validation` ran first (Step 2) and short-circuited on `SCHEMA_INVALID`. By the time `_check_color_collision` runs, every key in `payloads[fname]` has already matched `^\d{1,3},\d{1,3},\d{1,3}$` and `int(c) for c in split(",")` cannot fail. The fallback `continue` is unreachable.
**Fix:** Remove the try/except and add a comment instead, or — if you want belt-and-suspenders — make it `assert` against the invariant. Either is fine; current state is dead code that confuses readers about whether collision Scope 2 can be skipped mid-loop.

### IN-05: PIL `Image.open` without explicit close

**File:** `backend/medieval_forge/services/export/validator.py:312, 320`
**Issue:** `np.array(Image.open(path).convert("RGB"))` opens a file but never closes it. PIL lazy-loads, so this can leave the file handle open longer than necessary. On Windows this matters when the same path is then opened for writing by tests/fixtures (test_export_gate_broken.py:111 writes back to `lookup_condado.png`). Probably fine because numpy forces decode, but explicit context managers are safer.
**Fix:**
```python
with Image.open(terrain_path) as img:
    terrain_arr = np.array(img.convert("RGB"))
```

### IN-06: Endpoint test asserts 422 without disambiguating from gate-failure 422

**File:** `backend/tests/unit/api/test_v3_export_endpoint.py:46-49`
**Issue:** `test_post_v3_export_dry_run_with_invalid_value_rejected_by_fastapi` asserts `resp.status_code == 422`. Both "FastAPI rejected query param" and "gate failed" return 422. The test happens to hit a non-existent project first, so the gate cannot be reached — but if someone later refactors the endpoint to validate `dry_run` after fetching the project, this test would still pass while masking the regression.
**Fix:** Also assert on the response body shape to distinguish FastAPI's validation envelope from the D-08 envelope:
```python
assert resp.status_code == 422
body = resp.json()
assert "detail" in body
# FastAPI's envelope has detail as a list of {loc, msg, type} entries;
# the D-08 envelope has detail as a dict with summary/errors/warnings.
assert isinstance(body["detail"], list)
```

---

_Reviewed: 2026-05-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
