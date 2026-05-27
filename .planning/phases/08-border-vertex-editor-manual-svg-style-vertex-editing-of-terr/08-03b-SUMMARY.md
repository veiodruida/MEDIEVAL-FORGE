---
phase: 08
plan: 03b
subsystem: backend-persistence
tags: [snapshots, edit-events, orm, gzip, fastapi, sqlite, crud, d-12, d-35, d-37, persist-01, persist-02]
dependency_graph:
  requires: [08-03a]
  provides: [snapshots-api, edit-events-api, snapshot-serializer]
  affects: [08-04, 08-09, 08-10]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy 2.0 Mapped[..] + LargeBinary for blob column (Snapshot ORM)
    - stdlib gzip + json for snapshot blob serialization (no new deps)
    - FastAPI thin router with service-layer delegation (same pattern as 08-03a)
    - SnapshotTooLargeError -> 413, EditLogFullError -> 409 EDIT_LOG_FULL
    - seq-monotonic snapshot numbering via ORDER BY seq DESC LIMIT 1
key_files:
  created:
    - backend/medieval_forge/services/branches/snapshot.py
  modified:
    - backend/medieval_forge/models.py
    - backend/medieval_forge/services/branches/service.py
    - backend/medieval_forge/api/v3/branches.py
    - backend/tests/integration/test_snapshot_persistence.py
decisions:
  - "serialize() enforces MAX_DECOMPRESSED_BYTES=10MB pre-compress (not just at deserialize) to match endpoint 413 contract"
  - "T-08-03b-02 (edit-log cap 10k) treated as Rule 2 correctness requirement per threat register mitigate disposition"
  - "append_edit_event returns EditEvent directly (not tuple); edits_since_snapshot re-queried fresh in endpoint after commit"
  - "auto-snapshot in edit-event endpoint only fires when both counter>=25 AND snapshot_payload_if_due provided by frontend"
metrics:
  duration_minutes: 30
  completed_date: "2026-05-27"
  tasks_completed: 2
  files_changed: 5
---

# Phase 08 Plan 03b: Snapshot + EditEvent Persistence Summary

**One-liner:** `Snapshot` + `EditEvent` ORM tables with gzip blob serializer, 4 CRUD endpoints (create/list/restore snapshot + edit-event log), and D-37 auto-snapshot every 25 edits with T-08-03b-01/02 threat mitigations.

## What Was Built

### ORM Models (`models.py`)

Two new SQLAlchemy 2.0 classes added with `LargeBinary` import:

**`Snapshot`** — stores gzip-compressed JSON blobs per branch:
- `id` UUID PK, `branch_id` FK to branches, `seq` 1-based monotonic integer
- `blob` LargeBinary (gzip(json(geojson + region_config + edit_log)))
- `trigger` String(16): "auto" | "manual" | "pre_slider_change" (D-19)
- `created_at` DateTime
- `UniqueConstraint("branch_id", "seq", name="uq_snapshot_branch_seq")`

**`EditEvent`** — append-only edit operation log per branch:
- `id` Integer autoincrement PK, `branch_id` FK to branches
- `op_type` String(32): "vertex_move", "vertex_add", "split", "merge", etc.
- `payload` JSON column
- `created_at` DateTime

Both tables created via existing `Base.metadata.create_all` in `main.py` lifespan.

### Snapshot Serializer (`services/branches/snapshot.py`)

New module with `serialize()` + `deserialize()` using stdlib `gzip` + `json`:
- `MAX_DECOMPRESSED_BYTES = 10 * 1024 * 1024` (10 MB cap, RESEARCH §V12)
- `serialize()` checks raw JSON size before compressing (pre-compress guard)
- `deserialize()` checks decompressed size after expanding (post-decompress guard)
- Both raise `SnapshotTooLargeError` — defense in depth per T-08-03b-01
- `SnapshotPayload` TypedDict: `{geojson, region_config, edit_log}`

### Service Layer (`services/branches/service.py`)

Five new functions + two constants:
- `AUTO_SNAPSHOT_EVERY_N_EDITS = 25` (D-37)
- `MAX_EDIT_EVENTS_PER_BRANCH = 10_000` (T-08-03b-02)
- `create_snapshot(db, branch_id, payload, trigger)` — seq-monotonic, resets counter
- `list_snapshots(db, branch_id)` — reverse-chronological (ORDER BY seq DESC)
- `restore_snapshot(db, snapshot_id)` — returns decoded SnapshotPayload
- `append_edit_event(db, branch_id, op_type, payload)` — increments counter; raises `EditLogFullError` at 10k cap
- `EditLogFullError` exception class

### Router (`api/v3/branches.py`)

4 new endpoints added under `/v3/projects/{project_id}/branches`:

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| POST | `/{bid}/snapshots` | 201/413 | Create snapshot; 413 on >10 MB |
| GET | `/{bid}/snapshots` | 200 | List reverse-chronological |
| POST | `/{bid}/snapshots/{sid}/restore` | 200 | Restore → SnapshotPayload |
| POST | `/{bid}/edit-events` | 201/409 | Log op; auto-snapshot at 25 edits |

Two new Pydantic body models: `SnapshotCreateBody` + `EditEventBody`.

## Test Results

- **Integration tests (08-03b):** 9/9 passed
  - Snapshot CRUD: create seq=1, monotonic seq=2, reverse-chrono list, restore identity
  - 11 MB payload → 413 (T-08-03b-01)
  - Edit-event counter increment (0→1)
  - 25th edit triggers auto-snapshot, counter resets to 0 (D-37)
  - Serializer round-trip (gzip magic + identity)
  - 10001st edit → 409 EDIT_LOG_FULL (T-08-03b-02)
- **Parity suite:** 17 passed, 2 skipped, 6 xfailed, 4 xpassed — no regressions
- **Pre-existing failures (out of scope):** 3 tests unrelated to 08-03b:
  - `test_llm_registry_has_exactly_three_providers` (Phase 07.2 added 3 more providers after this test was written)
  - `test_llm_registry_list_providers_returns_sorted_ids` (same)
  - `test_run_pipeline_emits_22_events_in_canonical_order` (manual_edit stage added in Phase 08 increased count from 24 to 26)
  - None of these files were touched in 08-03b. Deferred to appropriate plans.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's `serialize()` had no size guard**
- **Found during:** advisor review before coding
- **Issue:** Plan draft only guarded `deserialize()` with MAX_DECOMPRESSED_BYTES. The 413 endpoint test (`test_POST_snapshots_with_11mb_payload_returns_413`) requires the error to propagate from `create_snapshot()` via `SnapshotTooLargeError`, which only fires if `serialize()` checks size pre-compress.
- **Fix:** Added pre-compress size check in `serialize()`: `if len(raw) > MAX_DECOMPRESSED_BYTES: raise SnapshotTooLargeError(...)`
- **Files modified:** `backend/medieval_forge/services/branches/snapshot.py`
- **Commit:** ca4f373

**2. [Rule 2 - Missing critical functionality] T-08-03b-02 edit-log cap not in plan tasks**
- **Found during:** advisor review — threat register has `mitigate` disposition
- **Issue:** The threat register mandates capping edit_events at 10,000 per branch and returning 409 EDIT_LOG_FULL. Neither Task 1 nor Task 2 in the plan implemented this.
- **Fix:** Added `MAX_EDIT_EVENTS_PER_BRANCH = 10_000`, `EditLogFullError` exception, `COUNT(*)` guard in `append_edit_event()`, and 409 mapping in the endpoint. Added Test 9 in the test file.
- **Files modified:** `service.py`, `api/v3/branches.py`, `test_snapshot_persistence.py`
- **Commit:** 2e11b7c

## Known Stubs

None — all 4 endpoints are fully wired with real DB persistence. Snapshot blob stores real gzip+json data; restore returns the original payload. No mock data flows to any API response.

## Threat Surface Scan

No new endpoints beyond what is documented in the plan's threat model (T-08-03b-01 through T-08-03b-04). All four mitigations with `mitigate` disposition applied:
- T-08-03b-01: MAX_DECOMPRESSED_BYTES=10MB in serialize + deserialize → 413
- T-08-03b-02: MAX_EDIT_EVENTS_PER_BRANCH=10_000 → 409 EDIT_LOG_FULL
- T-08-03b-03: op_type max_length=32 at Pydantic Field level (accepted)
- T-08-03b-04: blob stored in ~/.medieval-forge/medieval_forge.db (accepted)

## Self-Check: PASSED

| Item | Status |
|------|--------|
| backend/medieval_forge/models.py | FOUND — Snapshot + EditEvent classes present (grep count=2) |
| backend/medieval_forge/services/branches/snapshot.py | FOUND — serialize/deserialize/SnapshotTooLargeError/MAX_DECOMPRESSED_BYTES |
| backend/medieval_forge/services/branches/service.py | FOUND — create_snapshot/list_snapshots/restore_snapshot/append_edit_event/EditLogFullError |
| backend/medieval_forge/api/v3/branches.py | FOUND — 4 new endpoints registered |
| backend/tests/integration/test_snapshot_persistence.py | FOUND — 9 tests, 0 skipped |
| commit c11b360 (RED tests) | FOUND |
| commit ca4f373 (GREEN models + serializer) | FOUND |
| commit 2e11b7c (GREEN endpoints + service) | FOUND |
| Serializer round-trip | VERIFIED — python -c import check passed |
| AUTO_SNAPSHOT_EVERY_N_EDITS = 25 | VERIFIED — grep count=1 |
| MAX_DECOMPRESSED_BYTES occurrences | VERIFIED — 9 occurrences in snapshot.py |
| 9/9 integration tests pass | VERIFIED — pytest output confirmed |
| Parity suite: no regressions | VERIFIED — 17 passed, same xfail/xpass as before |
