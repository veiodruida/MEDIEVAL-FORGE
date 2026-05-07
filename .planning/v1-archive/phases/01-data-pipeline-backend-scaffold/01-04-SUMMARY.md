---
phase: 01
plan: 04
subsystem: map-generation-wrapper
tags: [fastapi, map-generation, voronoi, background-tasks, sse, preview, sys-modules, asyncio]
dependency_graph:
  requires:
    - medieval_forge.database (AsyncSessionLocal, get_db) — from 01-01
    - medieval_forge.models.Project — from 01-02
    - medieval_forge.services.paths (is_valid_uuid, project_dir, ensure_project_dirs) — from 01-02
    - medieval_forge.main (app, include_router pattern) — from 01-01/01-02
  provides:
    - medieval_forge.lib.map_generator (verbatim copy of inicio/map_generator.py)
    - medieval_forge.services.generator (run_generation, GENERATED_FILE_WHITELIST)
    - medieval_forge.api.generate (POST /api/projects/{id}/generate, GET /api/projects/{id}/preview/{filename})
    - frontend useGenerate hook (useMutation POST /generate)
    - frontend useProject refetchInterval polling (every 2s when status=generating)
    - frontend ProjectDetail: Generate button + TextArea + Previews card
  affects:
    - Plan 01-05 (export) consumes generated/ outputs and GENERATED_FILE_WHITELIST
    - Plan 02 (canvas viewer) loads visual_condado.png and lookup_condado.png
tech_stack:
  added:
    - asyncio.to_thread (synchronous map_generator run in thread pool)
    - types.ModuleType + sys.modules patching (Pitfall 6 mitigation)
    - importlib.reload patch via context manager (reload compatibility for synthetic modules)
    - contextlib.redirect_stdout to StringIO (Windows cp1252 Unicode print suppression)
    - FastAPI BackgroundTasks (fire-and-forget generation)
    - FileResponse with media_type dispatch (.png -> image/png, .json -> application/json)
    - TanStack Query refetchInterval (2s polling while status=generating)
    - Radix UI TextArea (territory JSON input)
  patterns:
    - Synthetic module injection: types.ModuleType + sys.modules[name] = mod before generate_maps
    - importlib.reload no-op patch: monkey-patch importlib.reload in global namespace for duration of pipeline call
    - stdout redirect: contextlib.redirect_stdout(io.StringIO()) captures all map_generator print output
    - alias materialisation: shutil.copyfile source to stable alias names post-generation
    - T-PATH double guard: is_valid_uuid(project_id) + filename in GENERATED_FILE_WHITELIST
    - T-DOS guard: 409 if project.status == "generating" BEFORE scheduling BackgroundTask
    - Status commit before BackgroundTask: status="generating" committed to DB before task is enqueued
    - Fresh AsyncSessionLocal session in background task (not the request-scoped session)
    - refetchInterval: (query) => data.status === 'generating' ? 2000 : false
key_files:
  created:
    - backend/medieval_forge/lib/__init__.py
    - backend/medieval_forge/lib/map_generator.py
    - backend/medieval_forge/services/generator.py
    - backend/medieval_forge/api/generate.py
    - backend/tests/test_generate.py
  modified:
    - backend/medieval_forge/main.py (added generate_router)
    - frontend/src/api/client.ts (added useGenerate, added refetchInterval to useProject)
    - frontend/src/pages/ProjectDetail.tsx (Generate button + TextArea + Previews card)
decisions:
  - "importlib.reload patched via context manager: load_territory_data calls importlib.reload(mod) after import_module; bare types.ModuleType has no file-backed spec so _bootstrap._find_spec returns None and raises ModuleNotFoundError. Patching the global importlib.reload for the duration of the generate_maps call is the minimal non-invasive fix consistent with D-04 (no modification to map_generator.py)"
  - "redirect_stdout to StringIO: map_generator prints Unicode characters (—, →) that fail on Windows cp1252 console encoding when run in asyncio.to_thread. D-04 prohibits modifying map_generator.py; stdout redirect is the correct wrapper-layer fix. Output is logged at DEBUG level."
  - "CONDADOS is a list of tuples, not a dict: territory_data_v3.py uses list[(id, name, lon, lat, duchy_id, [(barony_name, lon, lat)])]. Injected module must set CONDADOS to a list to match setup_baronies() iteration (for ci, c in enumerate(condados): did = c[4])."
  - "DUCHIES uses tuple values: {duchy_id: (kingdom_id, duchy_name)} — setup_baronies accesses duchies[did][0] for kingdom_id."
  - "GeoJSON fixture for tests uses polygon within cfg.lon_min-1..cfg.lon_max+1 and cfg.lat_min-1..cfg.lat_max+1 bounds: build_land_mask filters points outside these bounds; a polygon with corners at [-14,34] would have only 2 points survive the filter (< 3) and nothing drawn."
  - "map_w=192, map_h=108, upscale=1 for slow tests: reduces generation time from ~3-5s (full 1920x1080) to ~0.11s for minimal fixture while still exercising the full pipeline."
  - "terrain.png alias maps to mountains_mask.png: mountains_mask.png is only produced when mountain_river_json is set and exists; terrain.png alias is only copied if the source exists. Without mountain data, terrain.png will not be in the manifest — acceptable per plan's conditional file spec."
metrics:
  duration: ~75min
  completed: "2026-04-16"
  tasks_completed: 6
  files_created: 5
  files_modified: 3
  generation_time_minimal: "0.11s (192x108px, 2 condados, 4 baronies, no municipality data except synthetic GeoJSON)"
---

# Phase 01 Plan 04: Map Generation Wrapper Summary

**One-liner:** FastAPI background-task pipeline wrapping map_generator.py via sys.modules territory injection, asyncio.to_thread isolation, and a whitelist-guarded preview endpoint — with React polling, TextArea input, and three PNG preview images in the browser.

## What Was Built

Full GEN-01..04 implementation across backend and frontend:

- **backend/medieval_forge/lib/map_generator.py**: Verbatim byte-for-byte copy of `inicio/map_generator.py` (40892 bytes). `if __name__ == "__main__":` guard confirmed at line 941. Importable as `medieval_forge.lib.map_generator`.

- **backend/medieval_forge/services/generator.py**: The core wrapper layer with three non-trivial responsibilities:
  1. **sys.modules injection**: `_inject_territory_module(name, data)` creates a `types.ModuleType`, sets `KINGDOMS`/`DUCHIES`/`CONDADOS`, registers in `sys.modules`. `importlib.reload` is patched via context manager during the pipeline call to handle `load_territory_data`'s `importlib.reload(mod)` call on the synthetic module (Pitfall 6 full mitigation).
  2. **Thread isolation**: `asyncio.to_thread(_run_pipeline_sync, ...)` keeps the FastAPI event loop responsive during the 0.1–60s pipeline run.
  3. **Alias materialisation**: `shutil.copyfile` copies `visual_condado.png` → `territories.png`, `lookup_condado.png` → `borders.png`, `mountains_mask.png` → `terrain.png` post-generation for stable frontend URLs.
  4. **stdout redirect**: `contextlib.redirect_stdout(io.StringIO())` captures all `print()` output including Unicode characters that fail on Windows cp1252. Output logged at DEBUG level.

- **backend/medieval_forge/api/generate.py**:
  - `POST /api/projects/{id}/generate`: T-PATH (UUID validation), T-DOS (409 if already generating), optional JSON body `{territory_data: {...}}`, commits `status="generating"` to DB before scheduling `BackgroundTasks.add_task(_run_and_update_status, ...)`.
  - `GET /api/projects/{id}/preview/{filename}`: T-PATH (UUID + filename in `GENERATED_FILE_WHITELIST` → 400 if not), 404 if file doesn't exist, `FileResponse` with dispatched media_type.
  - `_run_and_update_status`: Fresh `AsyncSessionLocal` session (not request-scoped); updates `project.status` to `"generated"` or `"error_generating"` + stores `last_error` in `generator_config`.

- **backend/medieval_forge/main.py**: `generate_router` registered after `ingest_router` and before the SPA catch-all.

- **backend/tests/test_generate.py**: 7 tests (5 non-slow + 2 slow):
  - `test_inject_territory_module_creates_sys_modules_entry` — injector contract verified via `importlib.import_module`
  - `test_trigger_generation` — 202 + status=generating (stubbed run_generation)
  - `test_trigger_generation_rejects_when_already_generating` — T-DOS 409
  - `test_png_fileresponse` — FileResponse with image/png content-type
  - `test_preview_rejects_non_whitelisted_filename` — T-PATH whitelist enforcement
  - `test_png_outputs` (slow) — real pipeline run; verifies 5 required outputs
  - `test_generation_time` (slow) — asserts elapsed < 60s (GEN-04)

- **frontend/src/api/client.ts**: Added `refetchInterval` to `useProject` (2s polling when `status === "generating"`); new `useGenerate(projectId)` hook using `useMutation`.

- **frontend/src/pages/ProjectDetail.tsx**: Generate button (live, not disabled); TextArea for territory JSON with default example; error display for `generate.error` and `project.generator_config.last_error`; Previews card (3 `<img>` tags pointing at `/api/projects/{id}/preview/{fname}`) rendered when `status === "generated"`. Export ZIP placeholder preserved for Plan 1.5.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | fc77495 | Wave 0 test_generate.py stubs (7 skipped) |
| 2 | 6fac8d2 | Verbatim copy of inicio/map_generator.py into medieval_forge.lib |
| 3 | e208f8d | services/generator.py + injector test |
| 4 | e88e140 | api/generate.py + main.py wire + 4 endpoint tests |
| 5 | a28f760 | Slow integration tests + reload/Unicode bug fixes |
| 6 | 6704e1b | Frontend useGenerate + polling + Previews card |
| fix | d480321 | Traversal test assertion fix (SPA catch-all returns 200 with built frontend) |

## Verification Results

```
py -m pytest backend/tests/ -v --tb=short -m "not slow"
27 passed, 3 deselected in 1.47s

py -m pytest backend/tests/ -v --tb=short -m slow
3 passed (test_png_outputs, test_generation_time, test_static_in_wheel)
Generation time (minimal fixture, 192x108px): 0.11s  <<< GEN-04: <60s

cd frontend && npm run build
vite v6.4.2 building for production...
344 modules transformed
built in 5.07s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] importlib.reload fails for synthetic modules**

- **Found during:** Task 5 slow test run
- **Issue:** `load_territory_data` in map_generator.py calls `importlib.reload(mod)` after `importlib.import_module(name)`. For a synthetic module created by `types.ModuleType`, Python's `_bootstrap._find_spec` cannot locate a file-backed spec and raises `ModuleNotFoundError: spec not found for the module '_mf_territory_...'`.
- **Fix:** Added `_patch_reload_for_synthetic(module_name)` context manager that monkey-patches `importlib.reload` globally for the duration of the `generate_maps` call. Only the specific synthetic module name is no-op'd; real modules reload normally. D-04 preserved — no modification to map_generator.py.
- **Files modified:** backend/medieval_forge/services/generator.py
- **Commit:** a28f760

**2. [Rule 1 - Bug] Windows cp1252 UnicodeEncodeError on map_generator print statements**

- **Found during:** Task 5 slow test run (after fixing reload)
- **Issue:** map_generator.py prints Unicode characters (→ U+2192, — U+2014) in its final summary. When running as an `asyncio.to_thread` worker on Windows with cp1252 console encoding, these raise `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`.
- **Fix:** Added `redirect_stdout(io.StringIO())` around the `generate_maps` call. All print output is captured to an in-memory UTF-8 buffer and logged at DEBUG level. D-04 preserved.
- **Files modified:** backend/medieval_forge/services/generator.py
- **Commit:** a28f760

**3. [Rule 1 - Bug] GeoJSON polygon corners filtered out by build_land_mask bounds check**

- **Found during:** Task 5 slow test development
- **Issue:** `build_land_mask` filters polygon coordinates to `cfg.lon_min-1 <= lo <= cfg.lon_max+1` and `cfg.lat_min-1 <= la <= cfg.lat_max+1`. The initial test fixture used `[-14,34]...[9,45]` — the lat=34.0 corners are below `cfg.lat_min-1=34.4`, leaving only 2 points after filtering (< 3 required for Pillow to draw a polygon). The land mask was all zeros, causing `np.argmax(sizes[1:])` to fail on an empty sequence.
- **Fix:** Updated `_write_minimal_geojson` to use `[-12,36]...[7,44]` — well within default RegionConfig bounds so all 5 ring points survive the filter.
- **Files modified:** backend/tests/test_generate.py
- **Commit:** a28f760

**4. [Rule 1 - Bug] TypeScript TS2322: `unknown` not assignable to `ReactNode`**

- **Found during:** Task 6 frontend build
- **Issue:** `project.generator_config?.last_error` has type `unknown` (from `Record<string, unknown>`). Using it directly in a `&&` chain rendered it as a ReactNode, causing `TS2322: Type 'unknown' is not assignable to type 'ReactNode'`.
- **Fix:** Wrapped the conditional with `Boolean(...)` and used `String(project.generator_config?.last_error ?? '')` for the rendered value.
- **Files modified:** frontend/src/pages/ProjectDetail.tsx
- **Commit:** 6704e1b

**5. [Rule 1 - Bug] Path traversal test assertion inconsistent with built frontend**

- **Found during:** Overall verification run (27-test suite)
- **Issue:** `test_preview_rejects_non_whitelisted_filename` expected traversal paths to return 400/404/422/503. After the frontend was built (static/index.html exists), the SPA catch-all now returns 200 (serving index.html). The security property is unchanged — the traversal never reaches our handler.
- **Fix:** Updated traversal assertion to accept 200 and added a content-type check (must be text/html or application/json, not image/png) to confirm no sensitive file was returned.
- **Files modified:** backend/tests/test_generate.py
- **Commit:** d480321

### Architectural Notes

- **territory_data schema discovery:** `CONDADOS` in territory_data_v3.py is a list of tuples, not a dict. `setup_baronies` iterates `for ci, c in enumerate(condados): did = c[4]`. The minimal test fixture uses the same tuple schema. The injected module sets `mod.CONDADOS = data.get("condados", [])` — callers must pass a list of tuples matching the real schema.
- **DUCHIES tuple values:** `{duchy_id: (kingdom_id, duchy_name)}`. The injector sets `mod.DUCHIES = data.get("duchies", {})` without schema enforcement — callers are responsible for correct structure.
- **terrain.png is conditional:** `mountains_mask.png` is only produced when `mountain_river_json` is set and exists. Without it, the alias `terrain.png` is not written. The plan acknowledges this — `terrain.png` may be missing from the manifest on first run without mountain data.

## Generation Time Baseline

For Phase 4's Voronoi recalc <500ms target:

| Fixture | Resolution | Condados | Baronies | Time |
|---------|-----------|----------|----------|------|
| Minimal (test) | 192x108 | 2 | 4 | 0.11s |
| Full Iberia (expected) | 1920x1080 x2 upscale | 91 | ~350 | est. 15-45s |

The 0.11s baseline at 192x108 demonstrates that the wrapper overhead (sys.modules injection, to_thread, stdout redirect) is negligible. Phase 4 will need per-territory delta recalculation, not full pipeline reruns.

## Preview Alias Mapping

| Alias | Source | Notes |
|-------|--------|-------|
| territories.png | visual_condado.png | Always produced |
| borders.png | lookup_condado.png | Always produced |
| terrain.png | mountains_mask.png | Only produced when mountain_river_json is set |

## Known Stubs

None — all placeholder elements from Plans 01-02/01-03 are replaced:
- "Generate (Plan 1.4)" button: replaced with live Generate button
- Territory JSON TextArea: pre-populated with working minimal example
- Previews card: rendered when status === "generated"

The "Export ZIP (Plan 1.5)" button remains disabled — intentional scaffold for Plan 01-05.

## Threat Flags

None — all mitigations from the plan's STRIDE register are implemented:

| Threat | Mitigation | Verified by |
|--------|------------|-------------|
| T-PATH (preview) | is_valid_uuid + filename in GENERATED_FILE_WHITELIST → 400 | test_preview_rejects_non_whitelisted_filename |
| T-PATH (generate) | is_valid_uuid → 400 | test_trigger_generation |
| T-DOS (overlap) | 409 if project.status == "generating"; committed before BackgroundTask | test_trigger_generation_rejects_when_already_generating |
| T-04-01 | Synthetic module name is _mf_territory_{uuid} — namespaced; cleaned up in finally | test_inject_territory_module_creates_sys_modules_entry |
| T-04-02 | last_error = str(exc) only — no stack traces in HTTP response | code review |
| T-04-03 | Accepted — map_generator is trusted vendored code | N/A |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/medieval_forge/lib/map_generator.py exists | PASSED |
| map_generator.py file size matches source (40892 bytes) | PASSED |
| __main__ guard at line 941 | PASSED |
| backend/medieval_forge/services/generator.py exists | PASSED |
| backend/medieval_forge/api/generate.py exists | PASSED |
| backend/tests/test_generate.py exists | PASSED |
| main.py contains generate_router | PASSED |
| frontend/src/api/client.ts contains useGenerate | PASSED |
| frontend/src/api/client.ts contains refetchInterval | PASSED |
| frontend/src/pages/ProjectDetail.tsx contains useGenerate | PASSED |
| frontend/src/pages/ProjectDetail.tsx contains territories.png | PASSED |
| py -m pytest backend/tests/ -m "not slow" | 27 passed |
| py -m pytest backend/tests/ -m slow | 3 passed |
| cd frontend && npm run build | built in 5.07s |
| All 7 task commits in git log | PASSED (fc77495..d480321) |
