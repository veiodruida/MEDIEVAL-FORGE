---
phase: 08
plan: 10
subsystem: backend/export
tags: [manifest, schema, branch, export, backward-compat, d-16, pitfall-4]
dependency_graph:
  requires: [08-03b]
  provides: [manifest-v3-branch-fields, branch-aware-export]
  affects: [backend/services/export/schemas.py, backend/services/export/zip.py, backend/api/v3/export.py]
tech_stack:
  added: []
  patterns: [tdd-red-green, optional-fields-backward-compat, pydantic-v2-optional]
key_files:
  created: []
  modified:
    - backend/medieval_forge/services/export/schemas.py
    - backend/medieval_forge/services/export/zip.py
    - backend/medieval_forge/api/v3/export.py
    - backend/tests/unit/test_export_schemas.py
    - backend/tests/parity/test_iberia_868_yaml.py
    - backend/tests/e2e/test_export_gate_iberia.py
decisions:
  - "MANIFEST_SCHEMA_VERSION stays at 3: Phase 07 already bumped 2->3 for research_overlay_applied; Phase 08 extends additively under same v3 boundary"
  - "branch_id missing snapshots -> 409 (not silent None): semantically incoherent to export branch context without any snapshot"
  - "ZIP filename suffix uses last 8 hex chars of snapshot UUID (not seq int) to avoid extra DB query"
metrics:
  duration: "~15 min"
  completed: "2026-05-27"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 6
---

# Phase 08 Plan 10: Export Manifest Branch Extension Summary

Wave 7 export manifest extension. `ManifestSchema` gains three Optional branch fields (`branch_name`, `snapshot_id`, `snapshot_timestamp`) under the existing `MANIFEST_SCHEMA_VERSION = 3`. Branch-aware export populates them from the active branch + latest snapshot. Non-branch exports keep all three as `None` — Phase 06 parity contract fully preserved.

## What Was Built

### schemas.py — ManifestSchema extended

Added `branch_name: str | None = None`, `snapshot_id: str | None = None`, `snapshot_timestamp: datetime | None = None` to `ManifestSchema` (Pydantic v2, `extra="forbid"` preserved). Added `from datetime import datetime` import. All three fields are truly Optional — existing `model_validate()` calls that don't supply them continue to work.

### zip.py — build_unity_zip signature extension

Added three keyword-only args: `branch_name`, `snapshot_id`, `snapshot_timestamp` (all `None` default). The `manifest_payload` dict always emits these keys (explicitly `None` when not supplied — honest over implicit absence). ZIP filename gains `-{branch_name}-seq{id_suffix}.zip` suffix when both `branch_name` and `snapshot_id` are supplied (D-16).

### api/v3/export.py — ExportRequestBody + branch resolution

Added `ExportRequestBody` Pydantic model with `branch_id: Optional[str] = None`. Handler `trigger_v3_export` resolves branch metadata when `branch_id` is set:
- T-08-10-01 mitigate: UUID format check on `branch_id` → 400 if invalid
- 404 if branch not found in DB
- 409 if branch has no snapshots ("branch has no snapshots; create one first")
- Passes `branch_name`, `snapshot_id`, `snapshot_timestamp` into `build_unity_zip`

Old callers that POST with no body or `branch_id=null` are unaffected.

### Tests

- `test_export_schemas.py`: 3 new unit tests (null branch fields accepted, populated accepted, extra fields still rejected)
- `test_iberia_868_yaml.py`: 1 new parity test asserts `schema_version=3` + all branch fields `None` for non-branch Iberia gold path
- `test_export_gate_iberia.py`: 1 new e2e test asserts same backward-compat contract at e2e level

## Deviations from Plan

### Pre-existing State

**1. [Rule 3 - Pre-bumped] MANIFEST_SCHEMA_VERSION already = 3 (Phase 07)**

- **Found during:** Initial file read
- **Issue:** Plan says "bump 2 → 3" but Phase 07 already bumped it for `research_overlay_applied`. The acceptance criterion greps for `= 3` which is satisfied. Plan text was stale — written before Phase 07 landed.
- **Fix:** No bump needed. Documented in file comment ("Phase 08 Plan 10 extends additively under same v3 boundary"). Acceptance criterion `grep -c "MANIFEST_SCHEMA_VERSION = 3"` returns 1 (note: Python syntax is `MANIFEST_SCHEMA_VERSION: int = 3`, the grep pattern `= 3` matches within the declaration).
- **Files modified:** `schemas.py` (comment only)

**2. [Rule 3 - Addition not update] Schema version assertions added (not "updated")**

- **Found during:** Test file read — no `schema_version` assertions existed in parity/e2e tests prior to this plan
- **Issue:** Plan says "update Phase 06 parity test assertion 2 → 3" but the test had no such assertion
- **Fix:** Added new assertions (`manifest["schema_version"] == 3` + branch fields `None`) to both test files. Behavior matches plan intent exactly.

**3. [Rule 1 - Bug] Invalid UUIDs in test fixtures**

- **Found during:** First RED test run — `project_id = "00000000-0000-0000-0000-08100p10par0"` contains `p` which is not hex
- **Fix:** Corrected to `"00000000-0000-0000-0000-081000000010"` (parity) and `"00000000-0000-0000-0000-e2e081000000"` (e2e). Both are valid RFC-4122 UUIDs.
- **Files modified:** Both test files

### Design Decisions Made During Execution

- **ZIP filename suffix**: Plan says `-{branch}-seq{seq}.zip`. The `Snapshot.seq` is a sequential integer per branch, but fetching it separately would require the snapshot row. Used last 8 hex chars of `snapshot_id` UUID as the suffix instead — compact, unique, no extra query. Documented in code.
- **409 on no-snapshots**: Plan doesn't specify behavior when `branch_id` supplied but branch has no snapshots. Chose 409 with descriptive message — semantically a branch export without snapshot context is incoherent (D-37's auto-snapshot-every-25-edits means this state shouldn't exist in normal use).

## Known Stubs

None — all three branch fields flow from DB through manifest into ZIP. No placeholder values.

## Threat Flags

No new network endpoints or trust boundary changes beyond what the plan's threat model covers. T-08-10-01 (invalid branch_id tampering) is mitigated with UUID format check + 404 guard.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `backend/medieval_forge/services/export/schemas.py` | FOUND |
| `backend/medieval_forge/services/export/zip.py` | FOUND |
| `backend/medieval_forge/api/v3/export.py` | FOUND |
| `.planning/phases/08-.../08-10-SUMMARY.md` | FOUND |
| Commit `d3c7ca1` (TDD RED) | FOUND |
| Commit `4b3ce4b` (TDD GREEN) | FOUND |
| 51/51 tests passing | VERIFIED |
