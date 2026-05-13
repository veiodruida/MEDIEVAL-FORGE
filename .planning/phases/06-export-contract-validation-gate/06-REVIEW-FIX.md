---
phase: 06-export-contract-validation-gate
fixed_at: 2026-05-13T00:00:00Z
review_path: .planning/phases/06-export-contract-validation-gate/06-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-05-13
**Source review:** .planning/phases/06-export-contract-validation-gate/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03; Info findings excluded per fix_scope=critical_warning)
- Fixed: 3
- Skipped: 0

> **Reviewer's note (from REVIEW.md Summary):** The reviewer's own summary stated
> "No source modifications recommended for Phase 06 merge; suggest tracking WR-01 and
> WR-02 as Phase 06.1 follow-ups." These are behavioral/API changes rather than
> correctness bugs. All three are fixed here; a human should verify the response
> shape changes do not break any consumers before merging.

## Fixed Issues

### WR-03: Broad `except Exception` in schema validation

**Files modified:** `backend/medieval_forge/services/export/validator.py`
**Commit:** 7206c94
**Applied fix:** Added `from pydantic import ValidationError` import and narrowed the
`except Exception` clause in `_run_schema_validation` to `except ValidationError`.
Changed `context={"errors": str(exc)}` to `context={"errors": exc.errors()}` so the
error context carries a structured list (path/type/msg per field) rather than a raw
string — improves D-08 error context for downstream UI display.

**Status:** fixed: requires human verification (logic change — unexpected exceptions
from field validators now surface instead of being silently swallowed as SCHEMA_INVALID;
verify no pipeline `field_validator` raises unexpected exceptions in practice)

### WR-02: Inconsistent `generated_dir` resolution between dry-run and real export

**Files modified:** `backend/medieval_forge/services/export/zip.py`, `backend/medieval_forge/api/v3/export.py`
**Commit:** 3b14f34
**Applied fix:**
- Renamed `_resolve_generated_dir` to `resolve_generated_dir` in `zip.py` (public API);
  added `_resolve_generated_dir = resolve_generated_dir` alias so the internal `build_unity_zip`
  caller continues to work without change.
- Added clarifying docstring: the `/output` fallback requires both `is_dir()` AND
  `any(iterdir())` — an empty directory falls back to `/generated`.
- In `api/v3/export.py`: replaced the hand-rolled `project_dir/"output"` / `project_dir/"generated"`
  logic with `resolve_generated_dir(project_id)`, then replaced the `if not generated.is_dir()`
  guard with `any((generated / fname).exists() for fname in UNITY_ZIP_SPEC)` — exactly the
  same guard `build_unity_zip` uses at lines 110–114. This ensures dry-run and real export
  see the same directory and apply the same "has output" test.

**Status:** fixed: requires human verification (behavioral change in 409 trigger for empty /output dir)

### WR-01: Dry-run failure shape diverges from real-export D-08 envelope

**Files modified:** `backend/medieval_forge/api/v3/export.py`
**Commit:** 1b64c6b
**Applied fix:** Split the single `JSONResponse(status_code=200 if report.passed else 422, ...)`
into two branches. The `passed=True` branch returns 200 + `{dry_run: true, ...report}` unchanged.
The `passed=False` branch now returns 422 + `{dry_run: true, detail: {summary, errors, warnings}}`
matching the real-export D-08 envelope exactly. Updated the function docstring to document
both 422 shapes. No tests asserted the old dry-run failure body shape so no test updates needed.

**Status:** fixed: requires human verification (API response shape change for dry-run 422 — any
existing UI or Unity consumer parsing `body["errors"]` or `body["passed"]` on a dry-run 422
must be updated to use `body["detail"]["errors"]`)

---

_Fixed: 2026-05-13_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
