---
phase: "05"
plan: "04"
subsystem: "backend/api+db"
tags: [region-key, alembic, migration, sqlite-batch, v3-endpoint, load-region, singleton-guard]
dependency_graph:
  requires:
    - phase: "05-01"
      provides: "load_region API, clear_region_cache"
    - phase: "05-02"
      provides: "data/regions/iberia_868.yaml"
    - phase: "05-03"
      provides: "YAML parity gate"
  provides:
    - "Alembic migration 0004: region_key VARCHAR(64) NOT NULL DEFAULT 'iberia_868'"
    - "Alembic migration 0005: v1 legacy fields nullable for v3 projects"
    - "Project.region_key ORM field"
    - "POST /api/v3/projects with region_key enum validation"
    - "generate.py + render.py use replace(load_region(project.region_key), ...)"
    - "Singleton-non-mutation regression test (RESEARCH Pitfall 9 / T-05-04-04)"
  affects:
    - "alembic/versions/0004_add_region_key_to_projects.py"
    - "alembic/versions/0005_make_v1_legacy_fields_nullable_for_v3.py"
    - "backend/medieval_forge/models.py"
    - "backend/medieval_forge/api/v3/projects.py"
    - "backend/medieval_forge/api/v3/__init__.py"
    - "backend/medieval_forge/main.py"
    - "backend/medieval_forge/api/v3/generate.py"
    - "backend/medieval_forge/api/v3/render.py"
    - "backend/tests/integration/test_generate_render_load_region.py"
tech_stack:
  added: []
  patterns:
    - "SQLite batch_alter_table for NOT NULL + server_default in migration"
    - "dataclasses.replace() for immutable per-call config copy from cached singleton"
    - "region_key threaded from endpoint to producer (no DB in worker thread)"
    - "Pydantic Field(pattern=r'^[a-z0-9_]+$') + set membership for region enum validation"
    - "parents[4] anchor for _REGIONS_DIR in v3/projects.py (permanent anchor comment)"
key_files:
  created:
    - "alembic/versions/0004_add_region_key_to_projects.py"
    - "alembic/versions/0005_make_v1_legacy_fields_nullable_for_v3.py"
    - "backend/medieval_forge/api/v3/projects.py"
  modified:
    - "backend/medieval_forge/models.py (region_key field + v1 fields nullable)"
    - "backend/medieval_forge/api/v3/__init__.py (projects_router export)"
    - "backend/medieval_forge/main.py (v3_projects router registered)"
    - "backend/medieval_forge/api/v3/generate.py (iberia_config → load_region)"
    - "backend/medieval_forge/api/v3/render.py (iberia_config → load_region)"
    - "backend/tests/integration/test_generate_render_load_region.py (6 tests)"
decisions:
  - "Router prefix /v3/projects (not /api/v3/projects) — plan snippet had wrong prefix; main.py adds /api at mount time (STATE.md lesson from 05-07)"
  - "AsyncSession for POST /api/v3/projects — codebase uses async engine; plan snippet used sync Session (would fail at runtime)"
  - "Migration 0005 added to make v1 legacy fields nullable — v3 projects need only name+region_key; country_qid/period_start/period_end are v1-only"
  - "region_key fetched at endpoint, passed as str to producer — no DB access in worker thread"
  - "dataclasses.replace() at every callsite — load_region() returns cached singleton; replace() builds a fresh per-call copy (RESEARCH Pitfall 9 guard)"
metrics:
  duration: "~35 minutes"
  completed: "2026-05-12"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 6
  tests_added: 6
requirements-completed: [SC-1, SC-2]
---

# Phase 05 Plan 04: region_key End-to-End Wiring Summary

**One-liner:** `region_key` wired end-to-end: Alembic 0004 migration (SQLite batch mode), new `POST /api/v3/projects` with YAML-backed enum validation, and `generate.py` + `render.py` swapped to `replace(load_region(project.region_key), ...)` with singleton-non-mutation guard.

## What Was Built

### Task 1: Alembic migration 0004 + Project.region_key field (1c6acbf)

- `alembic/versions/0004_add_region_key_to_projects.py`: `batch_alter_table` adds `region_key VARCHAR(64) NOT NULL DEFAULT 'iberia_868'` with defensive backfill
- `models.py`: `region_key: Mapped[str] = mapped_column(String(64), nullable=False, default="iberia_868")`
- `alembic upgrade head` exits 0; both parity gates 22/22 green

### Task 2: POST /api/v3/projects + migration 0005 (087312d)

- `api/v3/projects.py`: `APIRouter(prefix="/v3/projects")` (NOT `/api/v3/projects` — main.py adds `/api`)
- `V3ProjectCreate`: `name` + `region_key` with `pattern=r"^[a-z0-9_]+$"` + server-side set membership against `data/regions/*.yaml`
- Returns 201 + `{id, name, region_key}`; 400 on unknown region; 422 on path-injection input
- `_REGIONS_DIR = Path(__file__).resolve().parents[4] / "data" / "regions"` (permanent anchor comment: DO NOT change to `parents[3]`)
- `alembic/versions/0005_make_v1_legacy_fields_nullable_for_v3.py`: makes `country_qid`, `period_start`, `period_end` nullable (v1-only fields)
- `main.py` + `__init__.py` updated to register the new router

### Task 3: iberia_config() swap + integration tests (d726774)

- `generate.py`: `from ...services.pipeline.region_loader import load_region` + `from dataclasses import replace`; producer receives `region_key: str` from endpoint; `cfg = replace(load_region(region_key), output_dir=..., on_stage=...)`
- `render.py`: same swap; `_render_producer` receives `region_key: str`; `cfg = replace(load_region(region_key), output_dir=..., stop_event=...)`
- 6 integration tests: POST creates project, generate/render spy assertions, singleton-non-mutation guard (Pitfall 9 regression)
- 28/28 tests green (6 integration + 11+11 parity)

## Verification

```
pytest tests/integration/test_generate_render_load_region.py -q
→ 6 passed

pytest tests/parity/test_iberia_868_yaml.py tests/parity/test_iberia_868.py -q
→ 22 passed

pytest tests/unit/ -q
→ 130 passed, 1 skipped
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Router prefix was /api/v3/projects in plan snippet**
- **Found during:** Task 2 (pre-coding check; STATE.md lesson from 05-07)
- **Issue:** Plan's `router = APIRouter(prefix="/api/v3/projects")` would double-prefix to `/api/api/v3/projects` since `main.py` adds `prefix="/api"` at mount time
- **Fix:** Used `prefix="/v3/projects"` matching all other v3 routers
- **Files modified:** `backend/medieval_forge/api/v3/projects.py`
- **Commit:** 087312d

**2. [Rule 3 - Blocker] Plan used sync Session; codebase is fully async**
- **Found during:** Task 2 (database.py confirms AsyncSession + aiosqlite)
- **Issue:** Plan's snippet imported `from sqlalchemy.orm import Session` and used `db: Session = Depends(get_db)` — `get_db` yields `AsyncSession`; sync session would fail at runtime against the async engine
- **Fix:** `async def create_v3_project(... db: AsyncSession = Depends(get_db))` with `await db.commit()` / `await db.refresh(project)`
- **Files modified:** `backend/medieval_forge/api/v3/projects.py`
- **Commit:** 087312d

**3. [Rule 2 - Missing critical] Migration 0005 needed for v3 create to work**
- **Found during:** Task 2 (runtime IntegrityError on `NOT NULL constraint failed: projects.country_qid`)
- **Issue:** v1 columns `country_qid`, `period_start`, `period_end` were `NOT NULL` at DB level; v3 endpoint creates projects with only `name + region_key`
- **Fix:** Added migration 0005 (`batch_alter_table` for SQLite) making the three v1-only fields nullable; updated `models.py` types to `Mapped[X | None]`
- **Files modified:** `alembic/versions/0005_make_v1_legacy_fields_nullable_for_v3.py`, `backend/medieval_forge/models.py`
- **Commit:** 087312d

## Known Stubs

None — all three tasks fully implemented and verified.

## Threat Surface

All T-05-04-01 through T-05-04-04 mitigations confirmed implemented:
- T-05-04-01: `Field(pattern=r"^[a-z0-9_]+$", max_length=64)` + set membership check — 422 + 400 tests pass
- T-05-04-02: `VARCHAR(64) NOT NULL DEFAULT 'iberia_868'` in migration 0004
- T-05-04-03: 400 detail reveals only region key names (no filesystem paths)
- T-05-04-04: `dataclasses.replace()` at both callsites; singleton-non-mutation test guards regression

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| alembic/versions/0004_*.py exists with batch_alter_table | FOUND |
| alembic/versions/0005_*.py exists | FOUND |
| grep region_key models.py → inside Project class | FOUND |
| grep batch_alter_table 0004_*.py → ≥1 match | FOUND |
| grep "parents\[4\]" api/v3/projects.py → ≥1 match | FOUND |
| grep "DO NOT change to parents\[3\]" api/v3/projects.py → ≥1 match | FOUND |
| grep "v3_projects" main.py → ≥1 match | FOUND |
| grep "iberia_config" generate.py → 0 matches | CONFIRMED |
| grep "iberia_config" render.py → 0 matches | CONFIRMED |
| grep "from dataclasses import replace" generate.py | FOUND |
| grep "from dataclasses import replace" render.py | FOUND |
| 6 integration tests passing | PASSED |
| 22 parity tests green | PASSED |
| 130 unit tests green | PASSED |
| Commit 1c6acbf (Task 1) | FOUND |
| Commit 087312d (Task 2) | FOUND |
| Commit d726774 (Task 3) | FOUND |
