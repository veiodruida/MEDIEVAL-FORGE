---
phase: 05-region-generalization
plan: 07
subsystem: api
tags: [fastapi, yaml, regions, endpoint, has_dataset, discovery]

# Dependency graph
requires:
  - phase: 05-01
    provides: region_loader.py, data/regions/*.yaml structure
  - phase: 05-06
    provides: france_1066.yaml + toy inputs (france_1066 has_dataset=True)

provides:
  - GET /api/v3/regions FastAPI endpoint (api/v3/regions.py)
  - Alphabetical region list with key, display_name, nested bounds, has_dataset flag
  - has_dataset logic: True iff pt_geojson + es_input + mountain_river_json all exist on disk
  - parents[4] path-depth anchor comment (R-04) preventing backend/-root regression
  - 5 endpoint tests in backend/tests/api/test_regions_endpoint.py

affects:
  - 05-08 (frontend NewProjectModal populates dropdown from this endpoint)
  - 05-09 (integration tests hit this endpoint)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Router prefix /v3/regions (not /api/v3/regions) — main.py adds prefix=/api at registration"
    - "parents[4] anchor for api/v3/*.py files to reach repo root"
    - "yaml.safe_load + relative_to guard for traversal protection"
    - "monkeypatch _REGIONS_DIR for test isolation without real disk paths"

key-files:
  created:
    - backend/medieval_forge/api/v3/regions.py
    - backend/tests/api/test_regions_endpoint.py (replaced Wave 0 placeholder)
  modified:
    - backend/medieval_forge/main.py (v3_regions.router registered)

key-decisions:
  - "Router prefix must be /v3/regions (not /api/v3/regions) — main.py adds prefix=/api, same as all other v3 routers"
  - "projects.py does not exist yet (Plans 05-04/05-05 pending) — combined R-04 grep criterion deferred to 05-04"
  - "display_name fallback chain: doc.get('display_name') or doc.get('name') or key (R-06)"

patterns-established:
  - "v3 router prefix pattern: /v3/<resource> + registered with prefix=/api in main.py"

requirements-completed: [SC-2]

# Metrics
duration: 10min
completed: 2026-05-12
---

# Phase 05 Plan 07: GET /api/v3/regions Endpoint Summary

**FastAPI endpoint `GET /api/v3/regions` with YAML discovery, `has_dataset` disk-check, alphabetical sort, and path-traversal guard — backing the Plan 05-08 frontend region modal.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-12T14:30:00Z
- **Completed:** 2026-05-12T14:40:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- `backend/medieval_forge/api/v3/regions.py` created (64 lines) with router prefix `/v3/regions`
- R-04 permanent anchor comment: `DO NOT change to parents[3]` guards the `parents[4]` path depth
- R-06: `display_name` preferred over machine key via `doc.get("display_name") or doc.get("name") or key`
- Three threat mitigations (T-05-07-01/02/03): glob restriction, `yaml.safe_load` only, `relative_to` traversal guard
- Router registered in `main.py` as `app.include_router(v3_regions.router, prefix="/api")`
- 5 tests all green; parity gate 23 passed + 6 xfailed + 4 xpassed (unchanged)

## Task Commits

1. **Task 1: api/v3/regions.py + router registration + endpoint tests** - `d342558` (feat)

## Files Created/Modified

- `backend/medieval_forge/api/v3/regions.py` — GET /api/v3/regions router, 64 lines
- `backend/medieval_forge/main.py` — Added `from .api.v3 import regions as v3_regions` + `app.include_router(v3_regions.router, prefix="/api")`
- `backend/tests/api/test_regions_endpoint.py` — 5 tests replacing Wave 0 placeholder

## Decisions Made

- Router prefix is `/v3/regions` (not `/api/v3/regions`): all v3 routers use this convention — `main.py` adds `prefix="/api"` at registration time. Using full `/api/v3/regions` would double-prefix to `/api/api/v3/regions`.
- The combined R-04 grep acceptance criterion (`grep ... projects.py regions.py` ≥2 matches) cannot fully pass until Plan 05-04 creates `projects.py`. Documented as a deferred acceptance criterion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected router prefix from `/api/v3/regions` to `/v3/regions`**
- **Found during:** Task 1 (pre-write analysis)
- **Issue:** Plan's code snippet uses `prefix="/api/v3/regions"`. All existing v3 routers (`ingest`, `generate`, `status`, `artifacts`, `render`) declare `prefix="/v3/..."` and are mounted with `prefix="/api"` in `main.py`. Using the plan's prefix literally would result in `/api/api/v3/regions` (double-prefix).
- **Fix:** Used `prefix="/v3/regions"` to match the established pattern; effective URL is `/api/v3/regions` as required.
- **Files modified:** `backend/medieval_forge/api/v3/regions.py`
- **Verification:** `test_returns_iberia_and_france` hits `/api/v3/regions` and passes (5/5 tests green)
- **Committed in:** `d342558`

---

**Total deviations:** 1 auto-fixed (Rule 1 — wrong router prefix in plan code snippet)
**Impact on plan:** Fix necessary for endpoint to be reachable. No scope creep.

## Issues Encountered

- `backend/medieval_forge/api/v3/projects.py` does not yet exist (Plans 05-04/05-05 pending execution). The combined R-04 grep acceptance criterion (`grep ... projects.py regions.py` ≥2 matches) can only produce 1 match currently. This is expected — Plan 05-04 will add the anchor comment to `projects.py` when it creates that file.

## Known Stubs

None — all plan deliverables fully implemented. `has_dataset` reflects real disk state (no mock/hardcoded return).

## Threat Surface

All three threat model mitigations confirmed implemented:
- T-05-07-01: `_REGIONS_DIR.glob("*.yaml")` — no traversal possible; `relative_to(region_root)` guard on dataset paths (line 48-53)
- T-05-07-02: `try/except` around `yaml.safe_load` — malformed YAML skips silently, endpoint stays 200 (line 31-33)
- T-05-07-03: `yaml.safe_load` only — no `yaml.load` call anywhere in module

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/medieval_forge/api/v3/regions.py` exists | FOUND |
| `grep parents[4]` matches ≥1 | FOUND (line 21) |
| `grep display_name` matches ≥1 | FOUND (line 37) |
| `grep "DO NOT change to parents\[3\]"` matches ≥1 | FOUND (line 16) |
| `grep v3_regions` in main.py matches ≥1 | FOUND (lines 47, 57) |
| 5 tests passing | PASSED |
| Parity gate green | PASSED (23 passed, 6 xfailed, 4 xpassed) |
| Commit d342558 | FOUND |

## Next Phase Readiness

- `GET /api/v3/regions` live and tested — Plan 05-08 frontend modal can now populate region dropdown
- `iberia_868` and `france_1066` both return `has_dataset: true`
- England 1216 (YAML-only, no inputs) will return `has_dataset: false` once its YAML is added by Plan 05-09

---
*Phase: 05-region-generalization*
*Completed: 2026-05-12*
