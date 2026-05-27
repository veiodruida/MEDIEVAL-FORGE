---
phase: 08
plan: 03a
subsystem: backend-persistence
tags: [branches, orm, fastapi, sqlite, crud, d-10, d-11, d-13, d-15, d-22]
dependency_graph:
  requires: [08-00]
  provides: [branches-api, branch-orm]
  affects: [08-03b, 08-04, 08-09]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy 2.0 Mapped[..] + mapped_column (Branch ORM)
    - FastAPI thin router delegating to service layer
    - BranchNameReservedError subclass for HTTP status disambiguation (400 vs 409)
    - is_valid_uuid guard at every endpoint (T-08-03a-02)
key_files:
  created:
    - backend/medieval_forge/services/branches/__init__.py
    - backend/medieval_forge/services/branches/service.py
    - backend/medieval_forge/api/v3/branches.py
  modified:
    - backend/medieval_forge/models.py
    - backend/medieval_forge/main.py
    - backend/tests/unit/test_models_branches.py
    - backend/tests/integration/test_branches_endpoint.py
decisions:
  - "BranchNameReservedError subclass of BranchNameTakenError: 'main' reserved maps to 400 (bad request), DB duplicate maps to 409 (conflict)"
  - "service.py uses ...models import (3 dots from services/branches/): verified path depth from api/v3/projects.py pattern"
  - "Wave-0 snapshot/edit_event test stubs remain skipped (per-test @pytest.mark.skip) — belong to 08-03b"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-27"
  tasks_completed: 2
  files_changed: 7
---

# Phase 08 Plan 03a: Branch ORM + Service + API Summary

**One-liner:** SQLAlchemy 2.0 `Branch` model with `original_idx_high_water` + 5 FastAPI CRUD endpoints with lazy `main` creation (D-10) and delete-protection (D-15).

## What Was Built

### Branch ORM model (`models.py`)

`Branch` class added with:
- `project_id` FK to `projects.id`, indexed
- `is_main` boolean (delete-protected per D-15)
- `original_idx_high_water` integer default 0 (D-22 per-branch idx tracking)
- `edits_since_snapshot` integer default 0 (D-10 auto-snapshot cadence counter)
- `UniqueConstraint("project_id", "name")` — uq_branch_project_name
- `created_at` / `updated_at` with `_utcnow` helper

Table created automatically via existing `Base.metadata.create_all` in `main.py` lifespan (no migration needed).

### Service layer (`services/branches/service.py`)

Five functions:
- `ensure_main_branch(db, project_id)` — D-10 lazy-create, idempotent
- `create_branch(db, project_id, name, parent_branch_id)` — D-11 + D-22 inheritance
- `list_branches(db, project_id)` — sorted by `updated_at desc`
- `rename_branch(db, branch_id, new_name)` — D-15 rename allowed on main
- `delete_branch(db, branch_id)` — D-15 raises `BranchProtectedError` for main

Two exception types: `BranchProtectedError`, `BranchNameTakenError` (+ subclass `BranchNameReservedError`).

### Router (`api/v3/branches.py`)

5 endpoints under `/v3/projects/{project_id}/branches` (main.py adds `/api` prefix):

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/v3/projects/{pid}/branches` | 200 | List + lazy-create main |
| POST | `/api/v3/projects/{pid}/branches` | 201 | Create branch |
| PATCH | `/api/v3/projects/{pid}/branches/{bid}` | 200 | Rename (main allowed) |
| DELETE | `/api/v3/projects/{pid}/branches/{bid}` | 204/409 | Delete (main → 409) |

Security: `is_valid_uuid` guard on all endpoints (T-08-03a-02), Pydantic `pattern=r"^[a-zA-Z0-9_-]+$"` on name fields (T-08-03a-01).

## Test Results

- **Unit tests:** 7 passed, 2 skipped (08-03b stubs)
- **Integration tests:** 10 passed
- **Parity suite:** 17 passed, 2 skipped, 6 xfailed, 4 xpassed — no regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong relative import path in service.py**
- **Found during:** Task 1 GREEN — import verification
- **Issue:** Plan template used `from ..models import Branch` (resolves to `services.models` which doesn't exist); correct depth is 3 dots (`...models`) from `services/branches/service.py`
- **Fix:** Changed to `from ...models import Branch`
- **Files modified:** `backend/medieval_forge/services/branches/service.py`
- **Commit:** 33e0823

**2. [Rule 1 - Bug] HTTP status ambiguity: reserved name vs DB duplicate both returning 400**
- **Found during:** Task 2 GREEN — `test_POST_branches_duplicate_name_returns_409` failed (400 instead of 409)
- **Issue:** `BranchNameTakenError` was raised for both "main" reserved (caller error → 400) and DB duplicate (conflict → 409); endpoint mapped both to 400
- **Fix:** Added `BranchNameReservedError(BranchNameTakenError)` subclass; endpoint catches `BranchNameReservedError` → 400 first, then `BranchNameTakenError` → 409
- **Files modified:** `service.py`, `api/v3/branches.py`
- **Commit:** 68dc99b

**3. [Rule 2 - Deviation from plan import path] `from ..deps import get_db` in plan snippet is wrong**
- **Found during:** Reading plan vs actual codebase; `api/v3/projects.py` confirmed correct path
- **Fix:** Used `from ...database import get_db` (3 dots, matching all other v3 routers)
- **Files modified:** `api/v3/branches.py`

### Wave-0 Stub Handling

Wave-0 stubs for Snapshot and EditEvent models + cascade tests belong to plan 08-03b. Converted from file-level `pytestmark = pytest.mark.skip` to per-test `@pytest.mark.skip(reason="...")` decorators so the Branch tests in the same file can run.

## Known Stubs

None — all Branch CRUD is fully wired. Snapshot/EditEvent models are 08-03b scope (marked skipped with explicit reasons).

## Threat Surface Scan

New endpoints at `/api/v3/projects/{project_id}/branches` introduce HTTP surface. Threat model in plan 08-03a covers T-08-03a-01 through T-08-03a-04 — all mitigations applied:
- T-08-03a-01: Pydantic pattern rejects injection chars — applied
- T-08-03a-02: `is_valid_uuid` guard — applied at all 4 endpoints
- T-08-03a-03: XSS via branch name — accepted (React auto-escapes; documented)
- T-08-03a-04: DoS unbounded branches — accepted (no hard cap in Phase 8)

## Self-Check: PASSED

| Item | Status |
|------|--------|
| backend/medieval_forge/models.py | FOUND |
| backend/medieval_forge/services/branches/__init__.py | FOUND |
| backend/medieval_forge/services/branches/service.py | FOUND |
| backend/medieval_forge/api/v3/branches.py | FOUND |
| backend/tests/unit/test_models_branches.py | FOUND |
| backend/tests/integration/test_branches_endpoint.py | FOUND |
| commit 15d90fe (RED unit tests) | FOUND |
| commit 33e0823 (GREEN model+service) | FOUND |
| commit e840ed7 (RED integration tests) | FOUND |
| commit 68dc99b (GREEN router+main) | FOUND |
