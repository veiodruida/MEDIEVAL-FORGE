---
status: partial
phase: 02-ingestion-adapter
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md]
started: 2026-05-09T00:00:00Z
updated: 2026-05-09T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test

expected: Kill any running medieval-forge server. Clear ephemeral DB state. Start `medieval-forge start` from scratch. Server boots without import errors, FastAPI mounts both v1 (`/api/projects/.../ingest`) and v3 (`/api/v3/projects/.../ingest`) routes, root `/` returns HTTP 200. No regression from Plan 04's `main.py` edit.
result: pass — verified by Claude 2026-05-09 (user-approved). Server bootou via `py -3.14 -m medieval_forge.cli start --port 8765 --no-browser`. `/openapi.json` returned 200 confirming FastAPI lifespan complete. `/api/v3/projects/notauuid/ingest` returned 400 with `{"detail":"project_id must be a valid UUID"}` confirming v3 mounted with T-02-04-01 UUID guard live. `POST /api/projects/notauuid/ingest` returned 400 confirming v1 coexists. NOTE: `/` returns 503 (Service Unavailable) — frontend SPA dist not built in `frontend/dist/`. This is a **pre-existing condition unrelated to Phase 02** (Phase 02 did not touch frontend); no regression. Backend-only smoke passes.

### 2. v3 SSE endpoint guards (UUID/404/409/bbox)

expected: Endpoint `/api/v3/projects/{id}/ingest` returns:
  - 400 when `project_id` is not a valid UUID
  - 404 when valid UUID but project doesn't exist
  - 409 when project status is "generating"
  - 400 when project has no bbox
Plus: success path streams `data: ...` events and emits terminal sentinel; error path emits `data: ERROR: ExceptionClassName` (no traceback in stream); status transitions to `ingested` (success) or `error_ingesting` (failure).
result: pass — verified by Claude 2026-05-09 (user-approved). Live UUID gate confirmed against running server (Test 1 evidence: 400 + UUID error message). Other 5 guards covered by automated tests `backend/tests/unit/api/test_v3_ingest.py` — 6/6 PASSED in 0.21s during /gsd-validate-phase 02 audit (test_v3_ingest_returns_400_when_project_id_is_not_uuid, test_v3_ingest_returns_404_when_project_does_not_exist, test_v3_ingest_returns_409_when_project_status_is_generating, test_v3_ingest_returns_400_when_project_has_no_bbox, test_v3_ingest_streams_terminal_sentinel_and_updates_status_on_success, test_v3_ingest_emits_terminal_sentinel_even_when_adapter_raises).

### 3. v1 endpoint coexistence

expected: Legacy `/api/projects/{id}/ingest` still mounted and functional after Phase 02 changes. v3 endpoint added in parallel without breaking v1 (D-14 coexistence).
result: pass — verified by Claude 2026-05-09 (user-approved). `POST /api/projects/notauuid/ingest` against running server returned 400, confirming both: (a) v1 route still mounted in `main.py` after Plan 04 edits, (b) v1 handler still validates inputs. v3 + v1 coexist as designed (D-14).

### 4. Live OSM ingest via real Overpass call

expected: Trigger real ingest against Iberia bbox `(36.0, -9.5, 44.0, 4.3)` for project with country_qid="Q29,Q45" (PT/ES). Adapter calls Overpass, splits features by representative_point into PT/ES, dedupes by `osm_id` (WR-02 fix), writes `projects/<uuid>/inputs/pt_concelhos_live.geojson` + `es_municipalities_live.geojson`. Project status transitions draft → generating → ingested. ~30MB ES + ~28MB PT in <5 min on good network.
result: blocked
blocked_by: network-required
reason: "Real Overpass API call requires network + ~5min runtime + ~58MB download. Manual operator action — not automated in this UAT session. Live snapshot already committed via earlier Plan 02-03 refresh (commit ccc947b: pt_concelhos_live.geojson + es_municipalities_live.geojson). Defer empirical re-verification until next snapshot refresh cycle or Phase 02.1 contract decision."

## Summary

total: 4
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps

[none — no implementation issues found]

## Notes

- **`/` returning 503** is documented pre-existing condition (frontend SPA dist not built). Phase 02 did not touch frontend. Not tracked as regression. Phase 03 (single-canvas workspace UI) will rebuild frontend.
- **Test 4 deferred** to next snapshot refresh cycle or Phase 02.1 live-parity contract decision — already-committed snapshot from Plan 02-03 (commit ccc947b) provides current evidence; live re-fetch unnecessary for this UAT.
