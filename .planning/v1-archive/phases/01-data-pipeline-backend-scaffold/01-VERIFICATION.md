---
phase: 01-data-pipeline-backend-scaffold
verified: 2026-04-16T14:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Install from clean virtualenv and open browser"
    expected: "pip install medieval-forge succeeds; medieval-forge start opens browser to React SPA served by FastAPI at http://localhost:8765"
    why_human: "Cannot start a server process or open a browser in automated verification"
  - test: "Trigger Wikidata SPARQL ingestion for Spain (Q29) and observe real-time progress"
    expected: "Progress messages stream into #ingest-log panel; raw/municipalities.geojson written with >0 features; project.status flips to 'ingested'"
    why_human: "Requires live network connection to Wikidata endpoint; SSE streaming not testable headlessly"
  - test: "Trigger map generation and view PNG previews in browser"
    expected: "Status transitions created->generating->generated (polled every 2s); three preview img tags render territories.png, borders.png, terrain.png without downloading"
    why_human: "Visual rendering of <img> tags requires a running browser; GEN-04 <60s assertion only tested with minimal fixture (slow test), not real data"
  - test: "Download Unity ZIP and verify contents"
    expected: "Export ZIP button triggers download; archive contains 12 spec files + MANIFEST.json; MANIFEST.json marks terrain_lookup.png/terrain_types.json/mountain_river_data.json as placeholder"
    why_human: "Browser download flow (hidden anchor click) cannot be triggered headlessly; real ZIP inspection requires a browser session"
---

# Phase 1: Data Pipeline + Backend Scaffold Verification Report

**Phase Goal:** User can install Medieval Forge, start the server, create a project, ingest real geographic data, trigger headless map generation, and receive a Unity-ready ZIP — all without touching the canvas.
**Verified:** 2026-04-16T14:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | pip install + medieval-forge start opens browser to React SPA | ? HUMAN | CLI code verified; PKG-01..05 implemented and tests pass; browser open requires human |
| 2 | User can create, list, open, update, delete a project via UI | ✓ VERIFIED | 9 CRUD tests pass; 5 routes in api/projects.py; 3 React pages built and served from static/index.html |
| 3 | Wikidata ingestion streams real-time progress; raw GeoJSON written | ? HUMAN | SSE endpoint + ingest services verified via 7 tests; real network behavior requires human |
| 4 | Trigger generation + view 3 PNG previews in browser | ? HUMAN | generate.py + slow tests pass (0.11s); visual preview in browser requires human |
| 5 | Download Unity ZIP containing all 12 standardized files | ? HUMAN | 6 export tests pass; browser download trigger requires human |

**Score:** 5/5 must-haves implemented (automated checks all pass; 4 require human browser validation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | package metadata, deps, scripts, package-data | ✓ VERIFIED | Contains entry point, aiosqlite pin, static/**/* glob, asyncio_mode=auto |
| `backend/medieval_forge/cli.py` | Click group with start/stop | ✓ VERIFIED | @click.group, psutil.Process(pid).terminate, PID_FILE, uvicorn.run, webbrowser.open |
| `backend/medieval_forge/main.py` | FastAPI app with lifespan, SPA catch-all | ✓ VERIFIED | lifespan=lifespan, all 4 routers registered before catch-all, FileResponse(INDEX_HTML) |
| `backend/medieval_forge/database.py` | async engine + AsyncSessionLocal + get_db | ✓ VERIFIED | sqlite+aiosqlite:///, expire_on_commit=False, DATA_DIR.mkdir |
| `backend/medieval_forge/models.py` | Project model (13 columns) | ✓ VERIFIED | class Project(Base), all required columns including country_qid, generator_config |
| `backend/medieval_forge/schemas.py` | ProjectCreate, ProjectUpdate, ProjectResponse | ✓ VERIFIED | Q\d+ validator, from_attributes=True, all Pydantic v2 schemas |
| `backend/medieval_forge/services/paths.py` | T-PATH boundary enforcement | ✓ VERIFIED | is_valid_uuid, is_relative_to PROJECTS_ROOT, ensure_project_dirs |
| `backend/medieval_forge/api/projects.py` | 5 CRUD routes | ✓ VERIFIED | POST/GET/GET/PATCH/DELETE routes, is_valid_uuid guard, shutil.rmtree, ensure_project_dirs |
| `backend/medieval_forge/services/ingest_wikidata.py` | paginated SPARQL fetcher | ✓ VERIFIED | WIKIDATA_ENDPOINT constant, QID_RE, validate_qid, page_size=500, client_factory |
| `backend/medieval_forge/services/ingest_osm.py` | Overpass fetcher | ✓ VERIFIED | OVERPASS_ENDPOINT constant, ISO_RE, validate_iso_country |
| `backend/medieval_forge/services/ingest_runner.py` | orchestration + atomic GeoJSON write | ✓ VERIFIED | ensure_project_dirs, atomic write via .tmp+replace, status update, None sentinel |
| `backend/medieval_forge/api/ingest.py` | SSE POST endpoint | ✓ VERIFIED | text/event-stream, asyncio.create_task, is_valid_uuid, pattern=^(wikidata|osm)$ |
| `backend/medieval_forge/lib/map_generator.py` | verbatim copy of inicio/map_generator.py | ✓ VERIFIED | Content-identical after line-ending normalization (40892 bytes normalized); if __name__ == "__main__" guard present |
| `backend/medieval_forge/services/generator.py` | sys.modules injector + asyncio.to_thread wrapper | ✓ VERIFIED | GENERATED_FILE_WHITELIST, _inject_territory_module, sys.modules[name]=mod, asyncio.to_thread, RegionConfig.__dataclass_fields__ |
| `backend/medieval_forge/api/generate.py` | POST /generate + GET /preview/{filename} | ✓ VERIFIED | background_tasks.add_task, is_valid_uuid, filename not in GENERATED_FILE_WHITELIST, FileResponse, T-DOS 409 guard |
| `backend/medieval_forge/services/export.py` | build_unity_zip with 12-file spec | ✓ VERIFIED | UNITY_ZIP_SPEC (12 entries), PLACEHOLDER_FILES, zipfile.ZipFile, MANIFEST.json, atomic write |
| `backend/medieval_forge/api/export.py` | POST /export + GET /export/download | ✓ VERIFIED | build_unity_zip, is_valid_uuid, _ALLOWED_PRE_EXPORT_STATUSES, media_type=application/zip, Content-Disposition |
| `alembic/env.py` | async migration runner | ✓ VERIFIED | asyncio.run, run_sync, from medieval_forge.models import Base, target_metadata = Base.metadata |
| `alembic/versions/0001_create_projects.py` | initial migration | ✓ VERIFIED | op.create_table('projects', 13 columns |
| `frontend/vite.config.ts` | Vite 6 config with base './' | ✓ VERIFIED | base: './', outDir: '../backend/medieval_forge/static', tailwindcss() plugin |
| `frontend/src/index.css` | Radix CSS before Tailwind | ✓ VERIFIED | @import "@radix-ui/themes/styles.css" before @import "tailwindcss" |
| `frontend/src/api/client.ts` | TanStack Query hooks | ✓ VERIFIED | useProjects, useProject (with refetchInterval), useCreateProject, useUpdateProject, useDeleteProject, useIngestStream, useGenerate, useExport |
| `frontend/src/pages/ProjectList.tsx` | list view | ✓ VERIFIED | useProjects, window.confirm, Link to="/projects/new" |
| `frontend/src/pages/ProjectNew.tsx` | create form | ✓ VERIFIED | useCreateProject, country_qid field |
| `frontend/src/pages/ProjectDetail.tsx` | detail + pipeline actions | ✓ VERIFIED | useProject, useUpdateProject, useIngestStream, useGenerate, useExport, id="ingest-log", preview img tags |
| `backend/medieval_forge/static/index.html` | built SPA | ✓ VERIFIED | Exists; script src="./assets/index-DBPV9LeM.js" (relative, confirms base './') |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| pyproject.toml [project.scripts] | medieval_forge.cli:cli | entry point | ✓ WIRED | Pattern: medieval-forge = "medieval_forge.cli:cli" |
| main.py | api/projects.py | include_router | ✓ WIRED | app.include_router(projects_router, prefix="/api") before catch-all |
| main.py | api/ingest.py | include_router | ✓ WIRED | app.include_router(ingest_router, prefix="/api") before catch-all |
| main.py | api/generate.py | include_router | ✓ WIRED | app.include_router(generate_router, prefix="/api") before catch-all |
| main.py | api/export.py | include_router | ✓ WIRED | app.include_router(export_router, prefix="/api") before catch-all |
| api/projects.py | services/paths.py | is_valid_uuid + project_dir | ✓ WIRED | _validate_project_id used on all single-resource routes |
| api/ingest.py | services/ingest_runner.py | asyncio.create_task | ✓ WIRED | asyncio.create_task(run_ingest(...)) |
| api/generate.py | services/generator.py | background_tasks.add_task | ✓ WIRED | background_tasks.add_task(_run_and_update_status, ...) |
| api/export.py | services/export.py | build_unity_zip call | ✓ WIRED | zip_path = build_unity_zip(project_id) |
| services/generator.py | lib/map_generator.py | asyncio.to_thread + RegionConfig | ✓ WIRED | asyncio.to_thread(_run_pipeline_sync, ...), map_generator.generate_maps |
| services/generator.py | sys.modules | synthetic module injection | ✓ WIRED | sys.modules[name] = mod before generate_maps call |
| frontend/src/api/client.ts | /api/projects | TanStack Query fetch | ✓ WIRED | fetch('/api/projects'), jsonFetch<Project[]>('/api/projects') |
| frontend/ProjectDetail.tsx | /api/projects/{id}/ingest | fetch POST + ReadableStream | ✓ WIRED | fetch(`/api/projects/${projectId}/ingest?source=${source}`, {method:'POST'}) |
| frontend/ProjectDetail.tsx | /api/projects/{id}/preview/ | img src | ✓ WIRED | src={`/api/projects/${project.id}/preview/${fname}`} |
| frontend/ProjectDetail.tsx | /api/projects/{id}/export/download | hidden anchor download | ✓ WIRED | a.href = data.download_url in useExport onSuccess |
| alembic/env.py | models.py | Base.metadata import | ✓ WIRED | from medieval_forge.models import Base; target_metadata = Base.metadata |
| vite.config.ts | backend/medieval_forge/static/ | Vite build outDir | ✓ WIRED | outDir: '../backend/medieval_forge/static'; index.html present with ./assets/ paths |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All fast tests pass | py -m pytest backend/tests/ -q -m "not slow" | 33 passed, 3 deselected in 1.75s | ✓ PASS |
| map_generator.py verbatim copy | byte-for-byte compare normalized | Content identical (40892 bytes normalized) | ✓ PASS |
| Frontend built with relative assets | grep ./assets/ in index.html | src="./assets/index-DBPV9LeM.js" | ✓ PASS |
| All required service files exist | ls backend/medieval_forge/{api,services,lib}/ | All 4+7+2 files present | ✓ PASS |
| All frontend page files exist | ls frontend/src/pages/ | ProjectList.tsx, ProjectNew.tsx, ProjectDetail.tsx | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| PKG-01 | 01-01 | pip install medieval-forge | ✓ SATISFIED | pyproject.toml, SUMMARY confirms pip install -e .[dev] succeeds |
| PKG-02 | 01-01 | medieval-forge start opens browser | ✓ SATISFIED | cli.py: threading.Timer(1.5, webbrowser.open); SUMMARY confirms CLI registered |
| PKG-03 | 01-01 | medieval-forge start --no-browser | ✓ SATISFIED | cli.py: --no-browser is_flag; test_start_no_browser passes |
| PKG-04 | 01-01 | medieval-forge stop via PID file | ✓ SATISFIED | cli.py: psutil.Process(pid).terminate(); 2 stop tests pass |
| PKG-05 | 01-01 | Frontend bundled in wheel | ✓ SATISFIED | static/**/* in package-data; test_static_in_wheel passes (slow) |
| PROJ-01 | 01-02 | Create project (name, country, period, bbox, config) | ✓ SATISFIED | POST /api/projects; test_create_project passes |
| PROJ-02 | 01-02 | List projects | ✓ SATISFIED | GET /api/projects; test_list_projects passes |
| PROJ-03 | 01-02 | Open existing project | ✓ SATISFIED | GET /api/projects/{id}; ProjectDetail page; test_get_project passes |
| PROJ-04 | 01-02 | Delete project with confirmation | ✓ SATISFIED | DELETE /api/projects/{id}; window.confirm in ProjectList; test_delete_project passes |
| PROJ-05 | 01-02 | Update project settings | ✓ SATISFIED | PATCH /api/projects/{id}; edit form in ProjectDetail; test_update_project passes |
| INGEST-01 | 01-03 | Wikidata SPARQL paginated ingestion | ✓ SATISFIED | ingest_wikidata.py; validate_qid; pagination loop; test_wikidata_pagination passes |
| INGEST-02 | 01-03 | OSM Overpass fallback | ✓ SATISFIED | ingest_osm.py; validate_iso_country; test_osm_fallback passes |
| INGEST-03 | 01-03 | Store raw GeoJSON to raw/municipalities.geojson | ✓ SATISFIED | ingest_runner.py atomic write; test_geojson_written passes |
| INGEST-04 | 01-03 | Real-time progress feedback | ✓ SATISFIED | SSE endpoint + asyncio.Queue; test_sse_stream passes; frontend useIngestStream wired |
| GEN-01 | 01-04 | Trigger full map generation pipeline | ✓ SATISFIED | POST /generate; run_generation wraps map_generator; test_trigger_generation passes |
| GEN-02 | 01-04 | Generate PNG previews: terrain, territories, borders | ✓ SATISFIED | _PREVIEW_ALIASES copies; test_png_outputs (slow) passes; aliases in GENERATED_FILE_WHITELIST |
| GEN-03 | 01-04 | View PNG previews in browser without downloading | ✓ SATISFIED | GET /preview/{filename} FileResponse; 3 img tags in ProjectDetail |
| GEN-04 | 01-04 | Generation <60s | ✓ SATISFIED | test_generation_time (slow) passes: 0.11s for minimal fixture; human verification needed for real data |
| EXPORT-01 | 01-05 | Export Unity-ready ZIP with 12 files | ✓ SATISFIED | build_unity_zip; POST /export; test_zip_download passes |
| EXPORT-02 | 01-05 | ZIP contains exact 12-file spec | ✓ SATISFIED | UNITY_ZIP_SPEC tuple (12 entries, exact filenames); test_zip_contents passes |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| backend/medieval_forge/services/generator.py | Duplicate `_cleanup_territory_module` function definition (lines 68-69 and 103-104) | ⚠️ Warning | Second definition shadows first at module level; functionally harmless because the first definition is only used as a `finally` guard before the second replaces it. No behavioral impact. |

No blocker anti-patterns found. No TODO/FIXME/placeholder comments in production code paths. No hardcoded empty returns on user-visible flows.

### Human Verification Required

#### 1. Full install and browser launch

**Test:** From a clean virtualenv, run `pip install -e .` then `medieval-forge start`. Wait 3 seconds for browser to open.
**Expected:** Browser opens to http://localhost:8765 showing the React SPA — a "Projects" page with a "New project" button.
**Why human:** Cannot start a long-running server process or open a browser window in automated verification.

#### 2. Real Wikidata ingestion end-to-end

**Test:** Create a project with country_qid=Q45 (Portugal — small country). On the project detail page, click "Ingest from Wikidata". Watch the #ingest-log panel.
**Expected:** Log panel shows "Fetching Wikidata page offset=0..." messages updating in real time, eventually "DONE". After completion, project status badge shows "ingested". On disk: `~/.medieval-forge/projects/{uuid}/raw/municipalities.geojson` exists with a GeoJSON FeatureCollection.
**Why human:** Requires live network connection to query.wikidata.org; SSE streaming behavior can only be visually confirmed in a real browser.

#### 3. Map generation and PNG preview rendering

**Test:** From an ingested project detail page, paste the minimal territory JSON in the textarea and click "Generate". Watch the status badge.
**Expected:** Status transitions "created" → "generating" (polling every 2s) → "generated". Three preview images (territories.png, borders.png, terrain.png) appear below. Images render correctly without downloading.
**Why human:** The visual rendering of img elements loading from /preview/ endpoint requires a running browser with network access to localhost.

#### 4. Unity ZIP download

**Test:** From a project in "generated" status, click "Export ZIP".
**Expected:** Browser download dialog opens with filename `medieval-forge-{uuid}-{timestamp}.zip`. Downloaded ZIP contains 12 spec files + MANIFEST.json. MANIFEST shows terrain_lookup.png, terrain_types.json, mountain_river_data.json as `"source": "placeholder"`.
**Why human:** Browser download flow requires a running browser; the hidden anchor download trigger (createElement + click + removeChild) cannot be automated headlessly.

### Gaps Summary

No gaps found. All must-haves are implemented and verified at artifact, wiring, and (for key behaviors) behavioral spot-check levels.

The only warning-level issue is the duplicate `_cleanup_territory_module` function in `backend/medieval_forge/services/generator.py` — this is a copy-paste artifact where the function was defined at line 68 before the `_patch_reload_for_synthetic` context manager, then defined again at line 103. The second definition overwrites the first in the module's namespace; both are identical. This does not cause any functional issue.

---

_Verified: 2026-04-16T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
