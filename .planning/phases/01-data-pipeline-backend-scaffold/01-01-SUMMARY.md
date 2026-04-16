---
phase: 01
plan: 01
subsystem: backend-scaffold
tags: [packaging, fastapi, sqlalchemy, alembic, cli, pytest]
dependency_graph:
  requires: []
  provides:
    - medieval_forge.database (engine, AsyncSessionLocal, get_db, DATA_DIR)
    - medieval_forge.models (Base)
    - medieval_forge.main (app, lifespan, spa_catch_all)
    - medieval_forge.cli (cli, start, stop)
    - pyproject.toml entry point medieval-forge
    - alembic async env.py
  affects:
    - All subsequent plans in Phase 1 (02-05) depend on this scaffold
tech_stack:
  added:
    - FastAPI 0.135.x with lifespan context manager
    - SQLAlchemy 2.0 async engine + async_sessionmaker
    - aiosqlite 0.21.0 (pinned <0.22 per thread-hanging regression fix)
    - Alembic 1.18.x with -t async template
    - Click 8.x CLI group with start/stop commands
    - psutil 6.x for cross-platform process termination
    - uvicorn[standard] 0.44.x
    - pytest 8.x + pytest-asyncio 0.26.x with asyncio_mode=auto
    - httpx 0.28.x (in main deps, used by tests and services)
  patterns:
    - FastAPI lifespan context manager (replaces deprecated on_event)
    - SQLAlchemy async engine with expire_on_commit=False
    - Alembic asyncio.run + run_sync pattern (avoids empty migrations)
    - SPA catch-all route registered LAST (after API routers)
    - Conditional ASSETS_DIR mount (graceful when frontend not built)
    - psutil.Process.terminate() for Windows-safe process termination
    - PID file in DATA_DIR for stop command
key_files:
  created:
    - pyproject.toml
    - .gitignore
    - backend/medieval_forge/__init__.py
    - backend/medieval_forge/database.py
    - backend/medieval_forge/models.py
    - backend/medieval_forge/cli.py
    - backend/medieval_forge/main.py
    - backend/medieval_forge/static/.gitkeep
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - backend/tests/test_cli.py
    - backend/tests/test_packaging.py
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/versions/.gitkeep
  modified: []
decisions:
  - "aiosqlite pinned >=0.20,<0.22: confirmed thread-hanging regression in 0.22.0 (SQLAlchemy issue #13039)"
  - "psutil.Process.terminate() instead of os.kill(SIGTERM): Windows SIGTERM unreliable (RESEARCH.md Assumption A5)"
  - "Alembic initialized with -t async flag: sync env.py produces empty migrations (Pitfall 1)"
  - "SPA catch-all returns 503 JSON when index.html missing: graceful degradation during dev before frontend build"
  - "ASSETS_DIR mount is conditional: prevents startup error when frontend not yet built"
  - "conftest.py uses ASGITransport(app=app): correct httpx pattern for FastAPI testing without network"
metrics:
  duration: ~25min
  completed: "2026-04-16"
  tasks_completed: 6
  files_created: 16
---

# Phase 01 Plan 01: Project Scaffold + Packaging Summary

**One-liner:** pip-installable Python package scaffold with async FastAPI shell, Alembic async migrations, Click CLI start/stop via psutil PID file, and SPA catch-all — ready for downstream plans.

## What Was Built

A complete backend scaffold for Medieval Forge covering all PKG-01..05 requirements:

- **pyproject.toml**: single source of truth for package metadata, deps (aiosqlite pinned `>=0.20,<0.22`), `medieval-forge` entry point, `static/**/*` package-data glob, and pytest config with `asyncio_mode = auto`.
- **backend/medieval_forge/**: Python package with `database.py` (async engine + `get_db`), `models.py` (empty `Base`), `main.py` (FastAPI with lifespan + SPA catch-all), `cli.py` (Click `start`/`stop` commands), and `static/.gitkeep`.
- **alembic/**: async env.py overrides URL from `DATA_DIR`/medieval_forge.db, imports `Base.metadata` for autogenerate.
- **backend/tests/**: conftest with `db_session` + `client` async fixtures, 5 CLI tests, 2 packaging tests.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | d984167 | Wave 0 pytest scaffold and test stubs |
| 2 | 803e0bf | pyproject.toml and .gitignore |
| 3 | 73e2ed0 | Async SQLAlchemy engine, session factory, empty Base |
| 4 | f00c663 | Alembic async scaffold with env.py wired to Base |
| 5 | d1c16e9 | Click CLI start/stop with psutil PID termination |
| 6 | dbea3fe | FastAPI app shell, static/.gitkeep, packaging tests |

## Verification Results

```
py -m pytest backend/tests/ -v --tb=short
7 passed in 25.72s
  - test_help_lists_start_and_stop PASSED
  - test_start_no_browser PASSED
  - test_pid_file PASSED
  - test_stop_command_no_pid_file PASSED
  - test_stop_command_terminates_process PASSED
  - test_pyproject_declares_static_glob PASSED
  - test_static_in_wheel PASSED (slow — builds actual wheel)

py -m alembic upgrade head → Context impl SQLiteImpl (clean)
~/.medieval-forge/ → exists with medieval_forge.db
FastAPI import → SPA catch-all route registered
medieval-forge --help → lists start and stop (via Scripts/medieval-forge.exe)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Created package stub modules during Task 2 before Tasks 3/5/6**

- **Found during:** Task 2 (pip install + pytest verification)
- **Issue:** conftest.py imports `medieval_forge.main`, `medieval_forge.database`, and `medieval_forge.models` at collection time. These modules did not yet exist when Task 2 ran pytest.
- **Fix:** Created `__init__.py`, `database.py`, `models.py`, `main.py`, and `cli.py` alongside `pyproject.toml` in Task 2 so pytest could collect and skip the stubs. Tasks 3, 5, and 6 then committed these files with their final content.
- **Files modified:** backend/medieval_forge/{__init__.py, database.py, models.py, main.py, cli.py}
- **Commit:** 73e2ed0 (database/models), d1c16e9 (cli), dbea3fe (main)

**2. [Rule 3 - Blocking issue] medieval-forge script not on bash PATH**

- **Found during:** Task 5 verification
- **Issue:** pip installs scripts to `C:\Users\veio_\AppData\Roaming\Python\Python312\Scripts` which is not on bash PATH in this environment.
- **Fix:** Verified via direct path `Scripts/medieval-forge.exe --help` and via `py -m medieval_forge.cli --help`. The entry point is correctly registered; PATH is a user environment config issue, not a packaging bug.
- **Acceptance criteria met:** Entry point resolves and prints correct usage.

## Known Stubs

None — all stubs from Task 1 were replaced by Tasks 5 and 6 with real implementations. No placeholder text or hardcoded empty values remain in code paths that flow to functionality.

## Threat Flags

None — all threat model mitigations from the plan's STRIDE register are implemented:
- T-01-01: `full_path` argument ignored in spa_catch_all (returns constant `INDEX_HTML` path)
- T-01-02: PID validated as integer before psutil.Process; NoSuchProcess caught
- T-01-04: No `debug=True` on FastAPI constructor
- T-01-05: static/ in .gitignore with !.gitkeep exception

## Self-Check: PASSED

All 16 files exist on disk. All 6 task commits found in git log.

| Check | Result |
|-------|--------|
| All created files exist | PASSED (16/16) |
| All task commits exist | PASSED (6/6) |
| py -m pytest backend/tests/ -v | 7 passed |
| py -m alembic upgrade head | Clean (no errors) |
| FastAPI app importable | PASSED |
| medieval-forge entry point | PASSED (Scripts/medieval-forge.exe) |
