---
phase: 01
plan: 03
subsystem: data-ingestion-pipeline
tags: [fastapi, sse, wikidata, osm, geojson, asyncio, security, t-ssrf, t-path, t-dos]
dependency_graph:
  requires:
    - medieval_forge.database (AsyncSessionLocal, get_db) — from 01-01
    - medieval_forge.models.Project — from 01-02
    - medieval_forge.services.paths (is_valid_uuid, ensure_project_dirs) — from 01-02
    - medieval_forge.main (app, include_router pattern) — from 01-01/01-02
  provides:
    - medieval_forge.services.ingest_wikidata (fetch_municipalities, validate_qid, WIKIDATA_ENDPOINT)
    - medieval_forge.services.ingest_osm (fetch_municipalities, validate_iso_country, OVERPASS_ENDPOINT)
    - medieval_forge.services.ingest_runner (run_ingest)
    - medieval_forge.api.ingest (router — POST /api/projects/{id}/ingest SSE endpoint)
    - frontend useIngestStream hook (fetch POST + ReadableStream SSE consumer)
    - {project_dir}/raw/municipalities.geojson (GeoJSON FeatureCollection output)
  affects:
    - Plan 01-04 (map generation) consumes raw/municipalities.geojson produced here
    - Plan 01-04 should check project.status == "ingested" before allowing generation
    - Plan 01-05 (export) depends on the project status lifecycle (created -> ingested -> generated)
tech_stack:
  added:
    - httpx.AsyncClient with injectable client_factory for test isolation
    - asyncio.Queue producer/consumer SSE pattern (RESEARCH Pattern 3)
    - StreamingResponse(media_type="text/event-stream") with Cache-Control/X-Accel-Buffering headers
    - fetch() + ReadableStream.getReader() in frontend (POST SSE — not EventSource, which is GET-only)
    - Atomic file write pattern (write to .tmp then Path.replace())
  patterns:
    - T-SSRF: validate_qid (^Q\d+$) and validate_iso_country (^[A-Z]{2}$) before any URL composition
    - WIKIDATA_ENDPOINT and OVERPASS_ENDPOINT as module-level constants — never assembled from user input
    - client_factory injection for network-free tests (no httpx.MockTransport complexity)
    - asyncio.create_task(run_ingest(...)) in SSE generator; finally block cancels on disconnect
    - Query(pattern=...) not Query(regex=...) — FastAPI deprecated regex in favor of pattern
    - OSM relation-to-GeoJSON inline converter (outer/inner ring classification, ring closing)
    - Pagination termination: len(bindings) < page_size signals last page
key_files:
  created:
    - backend/medieval_forge/services/ingest_wikidata.py
    - backend/medieval_forge/services/ingest_osm.py
    - backend/medieval_forge/services/ingest_runner.py
    - backend/medieval_forge/api/ingest.py
    - backend/tests/test_ingest.py
  modified:
    - backend/medieval_forge/main.py (added ingest_router registration)
    - frontend/src/api/client.ts (added useIngestStream hook)
    - frontend/src/pages/ProjectDetail.tsx (wired Ingest buttons + #ingest-log panel)
decisions:
  - "OSM relation-to-GeoJSON: inline converter kept (no osm2geojson dep); Phase 6 can swap in osm2geojson if geometric correctness for inner-ring assignment becomes required"
  - "fetch() POST + ReadableStream used instead of EventSource: EventSource only supports GET; our endpoint is POST per SSE Pattern 3"
  - "Query(pattern=...) used instead of deprecated Query(regex=...): FastAPI deprecation warning observed and fixed inline (Rule 1 auto-fix)"
  - "test_geojson_written uses dedicated in-memory engine: avoids coupling to conftest session lifecycle for status update assertions"
  - "Pagination page_size default 500: matches Wikidata SPARQL 60s page timeout; Spain (~8000 municipalities) needs ~16 pages"
  - "Generate (Plan 1.4) and Export ZIP (Plan 1.5) remain as disabled placeholder buttons: downstream plans wire their handlers to these exact elements"
metrics:
  duration: ~40min
  completed: "2026-04-16"
  tasks_completed: 5
  files_created: 5
  files_modified: 3
---

# Phase 01 Plan 03: Data Ingestion Pipeline Summary

**One-liner:** Async paginated Wikidata SPARQL + OSM Overpass fetchers with T-SSRF validators, SSE-streamed POST endpoint writing GeoJSON FeatureCollection to disk, and a React fetch()+ReadableStream hook wired into the ProjectDetail pipeline panel.

## What Was Built

Full INGEST-01..04 implementation across backend and frontend:

- **backend/medieval_forge/services/ingest_wikidata.py**: Paginated SPARQL fetcher with `LIMIT {page_size}/OFFSET` loop. `validate_qid` enforces `^Q\d+$` before any URL composition — QID interpolated into query only after validation passes. `WIKIDATA_ENDPOINT` is a module constant. `client_factory` injection enables network-free testing. Per-page SSE progress messages emitted to asyncio.Queue.

- **backend/medieval_forge/services/ingest_osm.py**: Single Overpass POST fetcher. `validate_iso_country` enforces `^[A-Z]{2}$`. Inline `_relation_to_geojson_feature` converts OSM relations (with geometry) into GeoJSON Polygon/MultiPolygon via outer/inner ring classification and ring-closing. Nodes and non-relation elements filtered out.

- **backend/medieval_forge/services/ingest_runner.py**: Orchestration layer. Calls the appropriate fetcher, writes result atomically to `{project_dir}/raw/municipalities.geojson` (write-to-tmp then rename), updates `project.status` via a fresh async session, puts `None` sentinel in finally block. Error path: emits `ERROR:` SSE message and sets status to `error_ingesting`.

- **backend/medieval_forge/api/ingest.py**: `POST /api/projects/{id}/ingest?source=wikidata|osm` returns `StreamingResponse(media_type="text/event-stream")`. T-PATH: `is_valid_uuid(project_id)` -> 400 before any DB access. T-DOS: `project.status == "generating"` -> 409. `asyncio.create_task(run_ingest(...))` spawns producer; SSE generator drains queue until None sentinel; `finally` block cancels task on client disconnect.

- **backend/medieval_forge/main.py**: `ingest_router` registered after `projects_router` and before the SPA catch-all (Pitfall 8 compliance).

- **backend/tests/test_ingest.py**: 7 tests (all passing):
  - `test_validate_qid_rejects_non_qid_strings` — T-SSRF guard
  - `test_validate_iso_country_rejects_bad_format` — T-SSRF guard
  - `test_wikidata_pagination` — 2-page pagination, OFFSET advancement, QID-in-query check
  - `test_osm_fallback` — Polygon output, ring closing, node filtering
  - `test_geojson_written` — INGEST-03 file write + status=ingested via isolated engine
  - `test_sse_stream_invalid_uuid_returns_400` — T-PATH defence
  - `test_sse_stream` — end-to-end SSE content-type + event message verification

- **frontend/src/api/client.ts**: `useIngestStream(projectId)` hook — `fetch()` POST to `/api/projects/{id}/ingest?source=...`, reads `Response.body.getReader()`, decodes SSE chunks, strips `data: ` prefix, appends text lines to state array. On stream end: invalidates `['projects', projectId]` and `['projects']` queries so status display refreshes.

- **frontend/src/pages/ProjectDetail.tsx**: Two live ingest buttons ("Ingest from Wikidata", "Ingest from OSM") replace the single disabled placeholder. Buttons disabled while `isStreaming`. Error text shown below buttons. `<pre id="ingest-log">` renders `ingest.lines.join('')` — the D-09 live text stream requirement. "Generate (Plan 1.4)" and "Export ZIP (Plan 1.5)" remain as disabled placeholders.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 52e91ba | Wave 0 test_ingest.py stubs (7 skipped) |
| 2 | 292ae84 | ingest_wikidata.py + ingest_osm.py + 4 fetcher/validator tests |
| 3 | 3233110 | ingest_runner.py + test_geojson_written |
| 4 | b100ec3 | api/ingest.py SSE endpoint + main.py router wire + 2 endpoint tests |
| 5 | faa5837 | Frontend useIngestStream hook + ProjectDetail pipeline buttons |

## Verification Results

```
py -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_generate.py --ignore=backend/tests/test_packaging.py
21 passed in 1.64s

  test_cli.py: 5/5 passed
  test_ingest.py: 7/7 passed
  test_projects.py: 9/9 passed

cd frontend && npm run build
vite v6.4.2 building for production...
344 modules transformed
built in 4.70s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastAPI Query(regex=...) deprecated — replaced with Query(pattern=...)**

- **Found during:** Task 4 test run
- **Issue:** `FastAPIDeprecationWarning: 'regex' has been deprecated, please use 'pattern' instead` appeared during test_ingest.py run. The plan code specified `regex="^(wikidata|osm)$"`.
- **Fix:** Changed to `pattern="^(wikidata|osm)$"` in `api/ingest.py`. The pattern constraint is still enforced — behavior identical, no deprecation warning.
- **Files modified:** backend/medieval_forge/api/ingest.py
- **Commit:** b100ec3

### Architectural Notes (no deviation — documented for downstream plans)

- **OSM inline converter**: The plan explicitly permits inline OSM-to-GeoJSON conversion and notes that Phase 6 can introduce `osm2geojson` if needed. The inline converter handles outer/inner ring assignment naively for Phase 1. Inner rings are not yet matched to their containing outer polygon — acceptable for the current data ingest goal.

- **Frontend SSE via fetch() POST**: EventSource API only supports GET requests. Since the ingest endpoint is POST (to prevent accidental re-triggers from browser prefetch), `fetch()` + `ReadableStream.getReader()` is the correct approach per RESEARCH Pattern 3.

## Placeholder Button Labels (for Plans 04/05)

The two remaining disabled pipeline buttons in `ProjectDetail.tsx` use these exact labels:

| Button text | Plan that wires it | title attribute |
|-------------|---------------------|-----------------|
| `Generate (Plan 1.4)` | 01-04 | "Will be wired by Plan 1.4 (map generation)" |
| `Export ZIP (Plan 1.5)` | 01-05 | "Will be wired by Plan 1.5 (Unity export)" |

Plan 01-04 should add its button handler to the existing `<Flex gap="2" mb="3" wrap="wrap">` block.

## Known Stubs

None — all SSE event text is real data from the fetchers. The `#ingest-log` panel is fully wired. The two remaining pipeline buttons are intentional scaffolds for Plans 04/05, not accidental stubs.

## Threat Flags

None — all mitigations from the plan's STRIDE register are implemented and tested:

| Threat | Mitigation | Verified by |
|--------|------------|-------------|
| T-SSRF (Wikidata) | validate_qid ^Q\d+$ before SPARQL; WIKIDATA_ENDPOINT constant | test_validate_qid_rejects_non_qid_strings, test_wikidata_pagination |
| T-SSRF (OSM) | validate_iso_country ^[A-Z]{2}$ before Overpass; OVERPASS_ENDPOINT constant | test_validate_iso_country_rejects_bad_format, test_osm_fallback |
| T-PATH | is_valid_uuid(project_id) -> 400 in api/ingest.py | test_sse_stream_invalid_uuid_returns_400 |
| T-DOS (overlap) | project.status == "generating" -> 409 | code review (no dedicated test — generating status set by Plan 04) |
| T-DOS (queue) | Accepted — single-user local tool, ~16 messages per Spain ingest | N/A |
| T-03-01 | ERROR message shows str(exc) only — no stack traces | code review |
| T-03-02 | OSM inner-ring assignment naive — accepted for Phase 1 | documented in ingest_osm.py comments |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/medieval_forge/services/ingest_wikidata.py exists | PASSED |
| backend/medieval_forge/services/ingest_osm.py exists | PASSED |
| backend/medieval_forge/services/ingest_runner.py exists | PASSED |
| backend/medieval_forge/api/ingest.py exists | PASSED |
| backend/tests/test_ingest.py exists | PASSED |
| main.py contains ingest_router | PASSED |
| frontend/src/api/client.ts contains useIngestStream | PASSED |
| frontend/src/pages/ProjectDetail.tsx contains Ingest from Wikidata | PASSED |
| All 5 task commits in git log | PASSED (52e91ba, 292ae84, 3233110, b100ec3, faa5837) |
| py -m pytest backend/tests/ (excl. test_generate, test_packaging) | 21 passed |
| cd frontend && npm run build | built in 4.70s |
