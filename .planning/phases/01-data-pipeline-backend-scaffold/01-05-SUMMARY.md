---
phase: 01-data-pipeline-backend-scaffold
plan: 05
subsystem: api
tags: [zipfile, fastapi, fileresponse, unity, export, react, tanstack-query, zustand]

# Dependency graph
requires:
  - phase: 01-04
    provides: map_generator outputs in generated/ directory (9 PNG/JSON files); ensure_project_dirs + project_dir from services/paths.py; is_valid_uuid T-PATH guard

provides:
  - build_unity_zip(project_id) — assembles 12-file Unity ZIP with MANIFEST.json distinguishing real vs placeholder content
  - POST /api/projects/{id}/export — triggers ZIP build, flips status to "exported", returns download URL
  - GET /api/projects/{id}/export/download — serves most-recent ZIP as attachment
  - useExport(projectId) React hook — wires POST export + browser download trigger via hidden anchor
  - MANIFEST.json inside each ZIP clearly flags 3 placeholder files for Phase 6 upgrade

affects: [phase-06-export-polish, EXPORT-03, EXPORT-04, unity-packaging, gsd-verify-work, gsd-uat]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Atomic ZIP write via tmp file + rename (tmp_path.replace(zip_path)) prevents partial ZIPs on crash
    - MANIFEST.json embedded in ZIP with source:"generated"|"placeholder" for Phase 6 handoff
    - Hidden anchor download pattern (createElement a + click + removeChild) avoids SPA route loss
    - Status guard frozenset ({"generated","exported"}) allows re-export without re-generating

key-files:
  created:
    - backend/medieval_forge/services/export.py
    - backend/medieval_forge/api/export.py
    - backend/tests/test_export.py
  modified:
    - backend/medieval_forge/main.py
    - frontend/src/api/client.ts
    - frontend/src/pages/ProjectDetail.tsx

key-decisions:
  - "ZIP retention: keep all ZIPs forever in exports/; GET /download picks most-recent by mtime. Phase 6 may add cleanup."
  - "3 placeholder files (terrain_lookup.png, terrain_types.json, mountain_river_data.json) get stub content (1x1 PNG, {}) because map_generator does not produce them in Phase 1 (RESEARCH Open Q #3)."
  - "MANIFEST.json added to every ZIP to give Phase 6 a clear inventory of real vs placeholder content."
  - "build_unity_zip is called synchronously in the POST handler — ZIP assembly is fast enough (<1s for stub content) that a BackgroundTask is unnecessary."

patterns-established:
  - "Atomic file write: write to .tmp then rename — prevents partial/corrupt artifacts on crash."
  - "Hidden anchor download: createElement + click + removeChild in onSuccess — avoids SPA navigation loss."
  - "Status guard with frozenset: frozenset({...}) for O(1) membership checks on project status conditions."

requirements-completed:
  - EXPORT-01
  - EXPORT-02

# Metrics
duration: 4min
completed: 2026-04-16
---

# Phase 01-05: Unity Export Summary

**12-file Unity ZIP export pipeline: stdlib zipfile assembly with MANIFEST.json placeholder tracking, FastAPI POST+GET endpoints, and React useExport hook with browser download trigger**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-16T13:32:39+01:00
- **Completed:** 2026-04-16T13:36:21+01:00
- **Tasks:** 4
- **Files modified:** 6

## Accomplishments

- `build_unity_zip` assembles all 12 EXPORT-02 spec files (9 real from generated/, 3 stubs) plus `MANIFEST.json` into an atomically-written ZIP under `exports/`
- Two FastAPI endpoints cover the full export lifecycle: POST triggers and returns metadata; GET serves the most-recent ZIP as a file attachment
- Frontend `useExport` hook replaces the last Plan-1.5 placeholder button — Game Designer can now click "Export ZIP" and receive a download automatically after generation

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 — test_export.py stubs** - `38d7aec` (test)
2. **Task 2: services/export.py — build_unity_zip + 12-file spec + 2 unit tests** - `80ace45` (feat)
3. **Task 3: api/export.py + main.py wire + 4 endpoint tests** - `c74e4fd` (feat)
4. **Task 4: Frontend Export ZIP button wired via useExport hook** - `ab24a2d` (feat)

**Plan metadata:** this commit (docs: complete plan summary)

## Files Created/Modified

- `backend/medieval_forge/services/export.py` - UNITY_ZIP_SPEC tuple, PLACEHOLDER_FILES frozenset, _PLACEHOLDER_PNG/JSON bytes, build_unity_zip() with atomic write + MANIFEST.json generation
- `backend/medieval_forge/api/export.py` - POST /projects/{id}/export (status guard, build, commit, 201 response) + GET /projects/{id}/export/download (FileResponse with Content-Disposition)
- `backend/medieval_forge/main.py` - include_router(export_router, prefix="/api") wired before SPA catch-all
- `backend/tests/test_export.py` - 6 tests: 2 service-level unit tests + 4 endpoint integration tests (all passing)
- `frontend/src/api/client.ts` - ExportResponse interface + useExport(projectId) hook using useMutation
- `frontend/src/pages/ProjectDetail.tsx` - Export ZIP button wired (disabled until status is generated/exported); error display added

## Decisions Made

- **ZIP retention:** Keep all ZIPs in `exports/` indefinitely; GET /download picks the most-recent by mtime. No cleanup in Phase 1. Phase 6 may add a retention policy.
- **Sync vs async ZIP build:** `build_unity_zip` is called synchronously in the POST handler. Assembling stub content takes well under 1 second; no BackgroundTask overhead needed.
- **3 placeholder files:** `terrain_lookup.png`, `terrain_types.json`, `mountain_river_data.json` are not produced by `map_generator` in Phase 1. They receive minimal stub content (1x1 transparent PNG, `{}\n`). MANIFEST.json marks them `"source":"placeholder"` so Phase 6 knows exactly what to replace.
- **Download trigger:** Hidden anchor `createElement + click + removeChild` in TanStack Query `onSuccess` — standard SPA-safe browser download pattern; avoids `window.location.href` which would lose SPA route state.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 1 is fully end-to-end exercisable:
- #1 pip install + CLI start (01-01)
- #2 project CRUD (01-02)
- #3 Wikidata ingest + progress (01-03)
- #4 map generation + PNG previews (01-04)
- #5 Unity ZIP download with 12 standardized files (01-05 — this plan)

Ready for `/gsd-verify-work` and `/gsd-uat`.

Phase 6 (EXPORT-03/04) will replace the 3 placeholder files with real content. The MANIFEST.json `"source"` field in every ZIP provides a clean handoff — Phase 6 does not need to guess what was generated vs stubbed.

**Approximate ZIP size for minimal test project (inform Phase 6 EXPORT-04 UI):** ~3–5 KB (stub content only; real PNG outputs from map_generator will push this to ~500 KB–2 MB depending on resolution).

---
*Phase: 01-data-pipeline-backend-scaffold*
*Completed: 2026-04-16*
