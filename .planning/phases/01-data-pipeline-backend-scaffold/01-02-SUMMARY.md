---
phase: 01
plan: 02
subsystem: project-crud-frontend
tags: [fastapi, sqlalchemy, alembic, pydantic, react, vite, tailwind, radix-ui, tanstack-query, crud]
dependency_graph:
  requires:
    - medieval_forge.database (engine, AsyncSessionLocal, get_db, DATA_DIR) — from 01-01
    - medieval_forge.models (Base) — from 01-01
    - medieval_forge.main (app, lifespan) — from 01-01
    - alembic async env.py — from 01-01
  provides:
    - medieval_forge.models.Project (full 13-column ORM model)
    - medieval_forge.schemas (ProjectCreate, ProjectUpdate, ProjectResponse)
    - medieval_forge.api.projects (5 CRUD routes at /api/projects)
    - medieval_forge.services.paths (is_valid_uuid, project_dir, ensure_project_dirs)
    - alembic/versions/0001_create_projects.py (projects table migration)
    - frontend/ (Vite 6 + React 19 SPA with 3 pages)
    - frontend/src/api/client.ts (useProjects, useProject, useCreateProject, useUpdateProject, useDeleteProject)
  affects:
    - Plans 03/04/05 consume project_id and per-project folder structure from this plan
    - Plans 03/04/05 wire the placeholder buttons in ProjectDetail
tech_stack:
  added:
    - Pydantic v2 field_validator for country_qid (^Q\d+$ pattern)
    - SQLAlchemy JSON column for generator_config
    - shutil.rmtree for project folder cleanup on DELETE
    - React 19.2 + react-router-dom 7.14
    - TanStack Query 5.99 (staleTime 30s, invalidateQueries on mutations)
    - Radix UI Themes 3.3 (Theme wrapper, Card, Box, Flex, Heading, Text, Button, TextField.Root)
    - Tailwind CSS v4 via @tailwindcss/vite plugin
    - zundo 2.3.0 (declared in deps, not yet wired — future phases)
    - zustand 5.0.12 (declared in deps, not yet wired — future phases)
  patterns:
    - T-PATH guard: _validate_project_id raises 400 before any DB/fs access on single-resource routes
    - project_dir() double-checks resolved path is_relative_to PROJECTS_ROOT
    - ensure_project_dirs() called inside POST handler after DB commit (D-07)
    - shutil.rmtree(ignore_errors=True) on DELETE for idempotent folder cleanup
    - monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root) isolates fs tests
    - TanStack Query hooks in client.ts; relative /api/paths for dev+prod compatibility
    - Radix CSS imported BEFORE @import "tailwindcss" in index.css (Pitfall 7)
    - Vite base: './' ensures ./assets/ relative paths in built index.html (Pitfall 4)
key_files:
  created:
    - backend/medieval_forge/models.py (expanded with Project model)
    - backend/medieval_forge/schemas.py
    - backend/medieval_forge/services/__init__.py
    - backend/medieval_forge/services/paths.py
    - backend/medieval_forge/api/__init__.py
    - backend/medieval_forge/api/projects.py
    - alembic/versions/0001_create_projects.py
    - backend/tests/test_projects.py
    - frontend/package.json
    - frontend/vite.config.ts
    - frontend/tsconfig.json
    - frontend/tsconfig.node.json
    - frontend/index.html
    - frontend/src/index.css
    - frontend/src/main.tsx
    - frontend/src/App.tsx
    - frontend/src/api/client.ts
    - frontend/src/pages/ProjectList.tsx
    - frontend/src/pages/ProjectNew.tsx
    - frontend/src/pages/ProjectDetail.tsx
  modified:
    - backend/medieval_forge/main.py (added include_router for projects)
decisions:
  - "Radix UI Card component used for project list rows and detail sections (not Box+border) — cleaner semantic grouping"
  - "TanStack Query staleTime set to 30s (1000*30) — balances freshness vs unnecessary refetches for local tool"
  - "Placeholder buttons labeled 'Ingest (Plan 1.3)', 'Generate (Plan 1.4)', 'Export ZIP (Plan 1.5)' — exact labels Plans 03/04/05 must match to wire their handlers"
  - "from .api.projects import router placed inline after app=FastAPI() to avoid circular import at module level"
  - "noqa: E402 comment on inline import — intentional ordering to preserve SPA catch-all last constraint"
  - "pip install -e . required in worktree before alembic upgrade head (editable install was pointing to different worktree)"
metrics:
  duration: ~45min
  completed: "2026-04-16"
  tasks_completed: 6
  files_created: 20
  files_modified: 1
---

# Phase 01 Plan 02: SQLite Schema + Project CRUD Summary

**One-liner:** Project domain end-to-end — SQLAlchemy model + Alembic migration + Pydantic schemas + 5 CRUD FastAPI routes + T-PATH filesystem guard + React 19 SPA with 3 pages backed by TanStack Query.

## What Was Built

Full PROJ-01..05 implementation covering both backend and frontend layers:

- **backend/medieval_forge/models.py**: Expanded with `Project` model — 13 columns (UUID PK, name, country_qid, period_start/end, 4 bbox floats, generator_config JSON, status, created_at, updated_at). `_new_uuid()` and `_utcnow()` callables used as column defaults (not lambda — SQLAlchemy ORM requirement).

- **backend/medieval_forge/schemas.py**: Pydantic v2 `ProjectCreate`, `ProjectUpdate`, `ProjectResponse`. `country_qid` validated against `^Q\d+$` via `field_validator`. `ProjectResponse` uses `ConfigDict(from_attributes=True)` for ORM serialization.

- **backend/medieval_forge/services/paths.py**: T-PATH boundary enforcement. `is_valid_uuid()` validates format via regex + `uuid.UUID()`. `project_dir()` resolves the candidate path and asserts `is_relative_to(PROJECTS_ROOT)` to block traversal. `ensure_project_dirs()` creates `raw/`, `generated/`, `exports/` subdirectories.

- **backend/medieval_forge/api/projects.py**: 5 CRUD routes under prefix `/projects` (mounted at `/api` by main.py). Every single-resource route calls `_validate_project_id()` before DB access. POST calls `ensure_project_dirs` after commit. DELETE uses `shutil.rmtree(ignore_errors=True)` for idempotent folder removal.

- **alembic/versions/0001_create_projects.py**: Hand-written (not autogenerated) migration for deterministic column ordering. Applied to `~/.medieval-forge/medieval_forge.db`.

- **backend/tests/test_projects.py**: 9 real async tests using `client` fixture. `_isolated_projects_root` autouse fixture monkeypatches `PROJECTS_ROOT` to `tmp_path/projects` so no test pollutes `~/.medieval-forge/`.

- **frontend/**: Vite 6.4 + React 19.2 + TypeScript 5.8 SPA. `vite.config.ts` sets `base: './'` and `outDir: '../backend/medieval_forge/static'`. `index.css` imports Radix Themes CSS before Tailwind. Three pages: ProjectList (list+delete), ProjectNew (create form), ProjectDetail (info + edit + placeholder pipeline buttons).

- **frontend/src/api/client.ts**: Typed `Project` interface + 5 TanStack Query hooks using relative `/api/projects` paths (works in both dev proxy and production same-origin).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | c0b7d9d | Wave 0 test_projects.py stubs (9 skipped) |
| 2 | 500c3b3 | Project model, schemas, paths.py T-PATH, Alembic 0001 migration |
| 3 | d016170 | 5 CRUD routes in api/projects.py; wire router into main.py |
| 4 | a012676 | Implement 9 CRUD/security tests (9 passed) |
| 5 | 1e09c45 | Bootstrap Vite 6 + React 19 SPA scaffold |
| 6 | a0a4fe9 | TanStack Query client + 3 project pages |

## Verification Results

```
py -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_generate.py
16 passed in 16.60s
  - test_help_lists_start_and_stop PASSED
  - test_start_no_browser PASSED
  - test_pid_file PASSED
  - test_stop_command_no_pid_file PASSED
  - test_stop_command_terminates_process PASSED
  - test_pyproject_declares_static_glob PASSED
  - test_static_in_wheel PASSED
  - test_create_project PASSED
  - test_list_projects PASSED
  - test_get_project PASSED
  - test_get_project_invalid_uuid_returns_400 PASSED
  - test_get_project_not_found_returns_404 PASSED
  - test_update_project PASSED
  - test_delete_project PASSED
  - test_create_project_creates_folders PASSED
  - test_country_qid_validation_rejects_bad_format PASSED

cd frontend && npm run build
✓ built in 8.32s
backend/medieval_forge/static/index.html: script src="./assets/index-Dgxfov5Y.js" (relative path confirmed)

py -m alembic upgrade head → projects table confirmed in ~/.medieval-forge/medieval_forge.db
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Editable install pointing to wrong worktree**

- **Found during:** Task 2 (alembic upgrade head)
- **Issue:** `medieval_forge` module not importable — the editable install (`pip show medieval-forge`) showed `Editable project location: D:\...\agent-a6aac284` (a different agent worktree), not this worktree.
- **Fix:** Ran `pip install -e .` from this worktree root to redirect the editable install. Command completed without errors and `py -c "import medieval_forge"` confirmed the correct path.
- **Files modified:** None (install state only)
- **Commit:** N/A (infrastructure fix, not a code change)

**2. [Rule 2 - Missing functionality] noqa comment on inline import in main.py**

- **Found during:** Task 3
- **Issue:** The plan specified adding `from .api.projects import router as projects_router` after `app = FastAPI(...)`. This placement is technically a non-top-level import (E402) but is intentional to preserve the constraint that API routes must be registered before the SPA catch-all which is module-level code.
- **Fix:** Added `# noqa: E402` comment to suppress linter warning while keeping the ordering constraint intact.
- **Files modified:** backend/medieval_forge/main.py

## UI Component Decisions

Per the plan's output spec requesting documentation of component choices:

- **Card vs Box+border**: Used Radix UI `Card` for project list rows and all detail panels. Card provides built-in padding, border-radius, and box-shadow appropriate for a local desktop tool without custom CSS.
- **Styling**: Used Radix UI `Box`, `Flex`, `Heading`, `Text`, `Button`, `TextField.Root` throughout — no raw Tailwind utility classes on structural layout (Tailwind used for global resets in index.css only).
- **TanStack Query staleTime**: Set to `1000 * 30` (30 seconds). For a local tool where the backend is on localhost, 30s is conservative enough to avoid stale data without unnecessary refetches.

## Placeholder Button Labels (for Plans 03/04/05)

The three disabled buttons in `ProjectDetail.tsx` use these exact labels — downstream plans must match them to wire handlers:

| Button text | Plan that wires it | title attribute |
|------------|---------------------|-----------------|
| `Ingest (Plan 1.3)` | 01-03 | "Will be wired by Plan 1.3 (data ingestion)" |
| `Generate (Plan 1.4)` | 01-04 | "Will be wired by Plan 1.4 (map generation)" |
| `Export ZIP (Plan 1.5)` | 01-05 | "Will be wired by Plan 1.5 (Unity export)" |

The `<pre id="ingest-log">` element is also present in ProjectDetail for Plan 1.3's SSE event appending (D-09).

## Known Stubs

None — all placeholder page stubs from Task 5 were replaced in Task 6 with full implementations. The three pipeline buttons in ProjectDetail are intentional scaffolds documented above, not accidental stubs.

## Threat Flags

None — all T-PATH mitigations from the plan's STRIDE register are implemented:
- T-PATH: `_validate_project_id` raises 400 + `project_dir()` asserts `is_relative_to(PROJECTS_ROOT)`
- T-02-01: `shutil.rmtree(ignore_errors=True)` on DELETE after path validation
- T-02-02: `^Q\d+$` validator on `country_qid` in both ProjectCreate and ProjectUpdate
- T-02-03: FastAPI default 422 (accepted — local tool, no PII)
- T-02-04: Unbounded list accepted — single-user local tool
- T-02-05: TypeScript Project interface enforces shape at compile time

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| All 20 created files exist | PASSED |
| main.py modified correctly | PASSED |
| All 6 task commits in git log | PASSED |
| py -m pytest backend/tests/ (excl. test_generate) | 16 passed |
| cd frontend && npm run build | ✓ built in 8.32s |
| index.html script src starts with ./assets/ | PASSED |
| projects table in ~/.medieval-forge/medieval_forge.db | PASSED |
