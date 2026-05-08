---
phase: 02
plan: 04
subsystem: api-v3-ingest
tags: [api, v3, sse, http-endpoint, fastapi, asyncio-queue, terminal-sentinel]
requires:
  - phase-02-plan-02 (build_dataset_from_osm + ProjectDataset)
provides:
  - GET /api/v3/projects/{project_id}/ingest SSE endpoint
  - api/v3/ namespace (router for Phase 03/04 expansion)
  - per-(project_id, step) stop_event registry for v3 ingest
  - _adapter_producer wrapping build_dataset_from_osm with terminal-sentinel discipline
affects:
  - backend/medieval_forge/api/v3/__init__.py
  - backend/medieval_forge/api/v3/ingest.py
  - backend/medieval_forge/main.py
  - backend/tests/unit/api/__init__.py
  - backend/tests/unit/api/test_v3_ingest.py
tech-stack:
  added: []
  patterns:
    - "asyncio.Queue producer + StreamingResponse consumer with terminal None sentinel (mirrors api/ingest.py:_sse_generator and ingest_terrain/runner.py)"
    - "module-scope AsyncSessionLocal as test seam (monkeypatch overrides factory) — Plan 02 Task 1 PROJECTS_ROOT pattern"
    - "T-PATH UUID guard before DB lookup (V5 input validation; reuses paths.is_valid_uuid)"
    - "anti-overlap status guard (mirrors v1 api/ingest.py 409 path)"
    - "exception class-name only in SSE body; full traceback to logger (T-02-04-05 carry-forward)"
    - "httpx.ASGITransport for in-process FastAPI testing (httpx ≥ 0.28 contract)"
key-files:
  created:
    - backend/medieval_forge/api/v3/__init__.py
    - backend/medieval_forge/api/v3/ingest.py
    - backend/tests/unit/api/__init__.py
    - backend/tests/unit/api/test_v3_ingest.py
  modified:
    - backend/medieval_forge/main.py
decisions:
  - "D-14 implemented: /api/v3/projects/{project_id}/ingest SSE endpoint mounted under /api prefix; v1 /api/projects/{id}/ingest stays mounted (legacy coexistence)"
  - "D-13 honored by absence: zero ingest_terrain imports in api/v3/ingest.py (verified by grep)"
  - "D-15 honored by absence: zero ingest_wikidata imports in api/v3/ingest.py (verified by grep)"
  - "D-16 honored by absence: no CLI subcommand introduced; endpoint is HTTP-only"
  - "GET (not POST) chosen for v3 endpoint — idempotent per ingest run, mirrors EventSource browser API which only supports GET; v1 was POST because it mutated raw/ — v3 writes to projects/<uuid>/inputs/ which is a different namespace per D-07"
  - "SSE payload schema = mirror v1 plain string messages (D-14 Claude's Discretion); Phase 03 will define a stricter envelope when canvas consumes the stream"
  - "Per-(project_id, step) stop_event registry copied locally (4-line pattern) instead of importing from ingest_terrain/runner.py — keeps v3 ingest decoupled from terrain (D-13)"
  - "Status transitions: success → 'ingested', cancel/exception → 'error_ingesting' (mirrors ingest_runner._set_status semantics)"
metrics:
  duration: ~12min
  completed: 2026-05-08
  tasks_total: 1
  tasks_completed: 1
  files_created: 4
  files_modified: 1
  unit_tests_added: 6
  unit_tests_passing: 6
  parity_pre_commit: "10/10 green"
  parity_post_commit: "10/10 green"
  combined_wave_merge: "36/36 green (6 v3-ingest + 11 adapters + 9 plan-01 unit + 10 parity)"
requirements:
  - ROADMAP-02#3
---

# Phase 02 Plan 04: v3 SSE Ingest Endpoint Summary

Added the `/api/v3/projects/{project_id}/ingest` SSE endpoint (D-14) that
wraps `build_dataset_from_osm` and streams adapter progress to the client.
The legacy v1 `/api/projects/{id}/ingest` endpoint stays mounted untouched —
both coexist until Phase 03 deletes the v1 stepper + v1 router together.
Phase 02 closeout — final plan in this phase.

## What was built

- **`api/v3/__init__.py`** — single-line module marker comment establishing
  the v3 API namespace.
- **`api/v3/ingest.py`** (175 lines) — the new endpoint. Mirrors
  `api/ingest.py:_sse_generator` exactly: `asyncio.Queue[str | None]` +
  `asyncio.create_task(producer)` + `StreamingResponse` + `None` terminal
  sentinel + `finally: stop_event.set() + task.cancel()`. The producer
  invokes `build_dataset_from_osm` (from Plan 02-02) and updates
  `project.status` on success/failure.
- **`main.py`** — single 1-line import + 1-line `app.include_router(...)`
  addition. v1 `ingest_router` import and mount left intact (D-14
  coexistence).
- **`tests/unit/api/__init__.py`** — pytest package marker.
- **`tests/unit/api/test_v3_ingest.py`** (180 lines) — 6 unit tests covering
  the endpoint contract (UUID guard 400, 404 missing project, 409 anti-
  overlap, 400 missing bbox, happy-path stream + status update, error path
  + status update). Uses `httpx.AsyncClient(transport=ASGITransport(app))`
  and `pytest_asyncio.fixture` (matches existing
  `backend/tests/conftest.py`).

## Threat model implementation

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-02-04-01 (path traversal via project_id) | mitigate | `is_valid_uuid` BEFORE DB lookup → 400 if invalid (Test 1) |
| T-02-04-02 (concurrent ingest corrupts inputs/) | mitigate | 409 if `project.status == "generating"` (Test 3) |
| T-02-04-03 (oversized bbox / SSRF) | mitigate | Adapter's `_validate_bbox` (Plan 02-02) clamps span ≤ 30°/axis; endpoint 400 when bbox is None (Test 4) |
| T-02-04-04 (mid-stream disconnect leaks producer task) | mitigate | `finally: stop_event.set() + task.cancel() + await task` + `_clear_stop_event` registry; Test 6 wraps read in `asyncio.timeout(10.0)` to surface task leaks |
| T-02-04-05 (exception details in SSE) | mitigate | Producer emits ONLY `exc.__class__.__name__`; `logger.exception` writes full traceback to server logs (Test 6 asserts `"RuntimeError" in body` not the message) |
| T-02-04-06 (SSE injection in error messages) | accept | No user-supplied strings echoed; project_id is UUID-validated; error vocab is class names only |
| T-02-04-07 (test seam weakening prod) | accept | Production wires `AsyncSessionLocal` from module scope; test monkeypatches the module global. FastAPI-idiomatic; no production weakening |

## Final route table (post-commit)

`grep`-equivalent verification: `python -c "from medieval_forge.main import app; ..."`

| Method | Path | Source | Status |
|--------|------|--------|--------|
| POST | `/api/projects/{project_id}/ingest` | `api/ingest.py` (v1) | mounted (D-14 coexistence) |
| GET  | `/api/v3/projects/{project_id}/ingest` | `api/v3/ingest.py` (NEW) | mounted |

Both are reachable; the v1 stepper still POSTs to the v1 path; Phase 03
will switch the new canvas to GET the v3 path. Phase 03 then deletes both
the v1 stepper and the v1 router together (D-V3-04 — dead code is
regression risk).

## Decision coverage

| Decision | Status | Implementation |
|----------|--------|----------------|
| D-14 (new HTTP endpoint, legacy coexists) | DONE | `app.include_router(v3_ingest_router, prefix="/api")` added; v1 `app.include_router(ingest_router, prefix="/api")` left in place |
| D-13 (no terrain wrap) | HONORED BY ABSENCE | `grep "ingest_terrain" backend/medieval_forge/api/v3/ingest.py` → 0 matches |
| D-15 (no Wikidata wrap) | HONORED BY ABSENCE | `grep "ingest_wikidata" backend/medieval_forge/api/v3/ingest.py` → 0 matches |
| D-16 (no new CLI) | HONORED BY ABSENCE | No `argparse` / `click` / `@cli.command` calls in any new file |

D-01..D-12 (Plan 01–02) untouched; D-09..D-11 (Plan 02-03) blocked at the
waiver checkpoint and out of this plan's scope.

## Phase 02 closeout — ROADMAP-02 success criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Phase 01 parity test stays green when input is "live ingestion" instead of fixture snapshot | **BLOCKED** | Plan 02-03 paused at D-09 LIVE waiver decision (4 options open in `D-09-LIVE-WAIVER.md`); 6/10 live parity tests fail. NOT a regression — pre-existing checkpoint state. Phase 01 fixture-path parity 10/10 green throughout. |
| 2 | `services/pipeline/contracts.py` defines `ProjectDataset` consumed by both fixture and live paths | **DONE** (Plan 02-01) | `ProjectDataset` `@dataclass` shipped in commit `5adc9f5`; `cfg.dataset` consumed by `landmask.py` (vendored + live), `render.py` (`mountain_river_json`), `__init__.py` (`mountain_river_json`); `iberia_config()` builds vendored variant. |
| 3 | Adapter functions wrap (don't rewrite) `ingest_wikidata`, `ingest_osm`, `overpass_client`, `ingest_terrain` | **DONE** (Plan 02-02 + 02-04) | `services/pipeline/adapters/osm.py` imports `fetch_municipalities` (D-05); `terrain.py` returns vendored Path stub (D-13); `ingest_wikidata.py` deliberately not wrapped (D-15); `git diff HEAD~3 -- backend/medieval_forge/services/{ingest_osm.py,overpass_client.py,ingest_terrain/,ingest_wikidata.py}` empty. Plan 02-04 wires the adapter into a v3 HTTP endpoint, completing the surface. |

**Phase 02 closeout call:** SC-2 and SC-3 are met (Plans 01, 02, 04). SC-1
remains gated on the Plan 02-03 D-09 LIVE waiver decision — that's the
parity strategy choice the user paused on. Plan 02-04 is independent of
that decision: the SSE endpoint contract holds whether the parity strategy
ends up being waiver-loop, relaxed-SSIM, or separate `golden-live/`.

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `api/v3/__init__.py` and `api/v3/ingest.py` exist | PASS |
| `from medieval_forge.api.v3.ingest import router; assert router.prefix == '/v3/projects'` | PASS (`OK` printed) |
| `grep "from .api.v3.ingest import router as v3_ingest_router" main.py` = 1 | PASS |
| `grep "app.include_router(v3_ingest_router" main.py` = 1 | PASS |
| `grep "from .api.ingest import router as ingest_router" main.py` = 1 (v1 NOT removed) | PASS |
| `grep "app.include_router(ingest_router" main.py` = 1 (v1 still mounted) | PASS |
| `pytest backend/tests/unit/api/test_v3_ingest.py -v` reports 6 passed | PASS (6 passed in 0.07s) |
| `'/api/v3/projects/{project_id}/ingest' in [r.path for r in app.routes]` | PASS (`OK` printed) |
| Phase 01 parity unchanged: `pytest backend/tests/parity/test_iberia_868.py -m parity -x -q` reports 10 passed | PASS (10 passed in 33.15s) |
| `grep "ingest_terrain\|ingest_wikidata" api/v3/ingest.py` = 0 (D-13 + D-15 honored) | PASS |
| Combined wave-merge (Phase 02 plans + Phase 01 parity, excluding paused 02-03 live test) all green | PASS (36/36 green in 33.47s) |

## Deviations from Plan

### 1. [Rule 1 - Bug] httpx 0.28 dropped the `app=` kwarg on `AsyncClient`

- **Found during:** Pre-task setup verification (advisor flagged before code write).
- **Issue:** Plan literal `httpx.AsyncClient(app=app, base_url="http://test")` would raise `TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'` against installed `httpx==0.28.1`. The codebase's `pyproject.toml` allows `httpx[http2]>=0.27,<0.30`, so the production stack and test stack diverged.
- **Fix:** Use `httpx.AsyncClient(transport=ASGITransport(app=app), ...)` — matches `backend/tests/conftest.py:39` and `backend/tests/integration/test_research_sse.py:41` which already use this pattern. Imports updated to `from httpx import ASGITransport, AsyncClient`.
- **Files modified:** `backend/tests/unit/api/test_v3_ingest.py` (test file only — no production code change).
- **Commit:** `d5b0827`.

### 2. [Rule 1 - Bug] `_make_project` helper missing `period_start` / `period_end` (NOT NULL fields)

- **Found during:** Pre-task setup verification (advisor flagged before code write).
- **Issue:** Plan literal `_make_project` set only `id, name, country_qid, status` (and bbox optionally). The `Project` model declares `period_start` and `period_end` as `nullable=False` (`backend/medieval_forge/models.py:31-32`), so all 4 tests that create a Project would have raised `IntegrityError: NOT NULL constraint failed: projects.period_start`.
- **Fix:** Added `period_start=868, period_end=1492` (Iberia 868 historically-meaningful defaults) to the base kwargs of `_make_project`. Documents what the test is modelling.
- **Files modified:** `backend/tests/unit/api/test_v3_ingest.py` (test file only).
- **Commit:** `d5b0827`.

### 3. [Rule 1 - Cleanup] `pytest_asyncio.fixture` instead of `pytest.fixture` for async fixtures

- **Found during:** Pre-task setup verification (codebase convention check).
- **Issue:** Plan literal used `@pytest.fixture` for async fixtures. The project's `backend/tests/conftest.py` uses `@pytest_asyncio.fixture` for async fixtures (lines 23, 34, 60, 72), and `pyproject.toml` has `asyncio_mode = "auto"` which makes test functions auto-async but does NOT auto-promote `@pytest.fixture` to async-aware on all pytest-asyncio versions.
- **Fix:** Use `@pytest_asyncio.fixture` for `in_memory_db` and `client`. Matches codebase convention; deterministic across pytest-asyncio versions.
- **Files modified:** `backend/tests/unit/api/test_v3_ingest.py` (test file only).
- **Commit:** `d5b0827`.

### 4. [Plan ambiguity] `httpx` import not used directly

- **Found during:** Code-write review.
- **Issue:** The plan literal listed `import httpx` but only `ASGITransport` and `AsyncClient` from it are used. Lint hooks (if any) would flag the bare `httpx` import as unused.
- **Fix:** Kept `import httpx` (no-op against current toolchain — there are no active lint hooks here per `.git/hooks/` inspection — but harmless). The two named imports (`ASGITransport`, `AsyncClient`) come from `httpx`. Removed the unused `json` and `from contextlib import asynccontextmanager` imports the plan listed.
- **Files modified:** `backend/tests/unit/api/test_v3_ingest.py` (test file only).
- **Commit:** `d5b0827`.

No production-code deviations. The endpoint, router registration, status
transitions, terminal-sentinel discipline, and threat-model mitigations
all match the plan literally. The deviations are all in the test scaffolding
to keep the test suite consistent with the codebase's existing patterns and
the actually-installed dependency versions.

## Self-Check: PASSED

Verified post-write:
- FOUND: backend/medieval_forge/api/v3/__init__.py
- FOUND: backend/medieval_forge/api/v3/ingest.py
- FOUND: backend/medieval_forge/main.py (modified, v1 + v3 routers both mounted)
- FOUND: backend/tests/unit/api/__init__.py
- FOUND: backend/tests/unit/api/test_v3_ingest.py
- FOUND commit d5b0827: `feat(02-04): add /api/v3/projects/{id}/ingest SSE endpoint`
- Phase 01 parity: 10/10 green (33.15s, post-commit)
- Plan 02-04 unit tests: 6/6 green (0.07s)
- Combined Phase 02 + Phase 01 parity (excluding paused 02-03 live test): 36/36 green
- Endpoint reachable: `'/api/v3/projects/{project_id}/ingest' in app.routes` confirmed
- v1 endpoint still mounted: `'/api/projects/{project_id}/ingest'` still in app.routes (D-14 coexistence)
