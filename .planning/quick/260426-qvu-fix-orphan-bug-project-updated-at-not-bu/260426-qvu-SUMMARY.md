---
phase: quick-260426-qvu
plan: 01
subsystem: backend/api/edit
tags: [orphan-bug, edit-endpoints, sqlalchemy, regression-test]
requires: [models.Project, services.territories_geojson]
provides: [services.project_meta.touch_project]
affects:
  - backend/medieval_forge/api/edit.py
key-files:
  created:
    - backend/medieval_forge/services/project_meta.py
  modified:
    - backend/medieval_forge/api/edit.py
    - backend/tests/api/test_edit_api.py
decisions:
  - Helper does NOT commit; caller owns transaction so the bump is batched with the disk write
  - Helper is no-op when project_id has no DB row (preserves backwards compat with synthetic-UUID test fixtures)
  - Bump runs AFTER save_territories (disk is authoritative for territory geometry; metadata bump is non-critical)
metrics:
  duration: ~5min
  completed: "2026-04-26"
  tasks: 2
  files: 3
---

# Quick Task 260426-qvu: Fix Orphan Bug — Project.updated_at Not Bumped on Edit Endpoints Summary

Wired a shared `touch_project(session, project_id)` helper into all 5 Phase 4 edit endpoints so `Project.updated_at` advances on every successful mutation, restoring it as a reliable staleness signal. Closes orphan bug #5 from `04-HUMAN-UAT.md` (line 179).

## What Changed

### Task 1 — Helper + endpoint wiring (commit `45288bc`)

- **New:** `backend/medieval_forge/services/project_meta.py`
  - `async touch_project(session, project_id) -> bool` — issues `UPDATE projects SET updated_at = now(UTC) WHERE id = :pid`.
  - Returns `True` if a row was updated, `False` otherwise (no-op for synthetic-UUID test fixtures).
  - Does NOT commit; caller owns the transaction.
- **Modified:** `backend/medieval_forge/api/edit.py`
  - Imported `touch_project` once.
  - Inside the `if persist:` branch of `move_capital`, `merge_territories_endpoint`, `split_territory_endpoint`, `reshape_geometry`: appended `await touch_project(session, project_id); await session.commit()` AFTER `save_territories(...)`.
  - In `save_geometry_snapshot` (always persists): appended the same two lines after `save_territories(...)`.
  - Pattern: 5 call sites, single source of truth for the bump SQL.

### Task 2 — Regression tests (commit `30aee4d`)

- **Modified:** `backend/tests/api/test_edit_api.py`
  - Added `_seed_project(db_session)` helper inserting a `Project(id=PROJECT_ID, ..., updated_at=2020-01-01 UTC)` row.
  - Added `_read_updated_at(db_session)` helper using `db_session.expire_all()` + fresh `select(Project)` to bypass ORM identity cache.
  - Added `_aware(dt)` helper to normalize naive datetimes returned by `aiosqlite`.
  - 5 new tests (one per endpoint), each asserting `after > before` after a successful endpoint call.

## Verification

```bash
cd backend && python -m pytest tests/api/test_edit_api.py -x -q
# 13 passed in 0.21s  (8 original + 5 new)
```

Verification grep checks (from PLAN):

- `grep "touch_project" api/edit.py` → 5 call sites + 1 import (matches plan).
- `grep "update(Project)" api/edit.py` → 0 matches (logic isolated to helper).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `backend/medieval_forge/services/project_meta.py` — FOUND
- `backend/medieval_forge/api/edit.py` — modified, FOUND
- `backend/tests/api/test_edit_api.py` — modified, FOUND
- Commit `45288bc` — FOUND
- Commit `30aee4d` — FOUND
- All 13 tests pass.
