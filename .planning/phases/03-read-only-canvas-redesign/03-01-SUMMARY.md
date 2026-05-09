---
phase: 03-read-only-canvas-redesign
plan: 01
subsystem: api
tags: [pipeline, geojson, sse, canvas, sidecars, fastapi]

# Dependency graph
requires:
  - phase: 01-pipeline-parity-port-harness-together
    provides: run_pipeline(cfg) + RegionConfig + 10-file Unity contract
  - phase: 02-ingestion-adapter
    provides: ProjectDataset + v3 SSE pattern (template for cfg.on_stage consumer)
provides:
  - "_write_geojson_atomic in services/paths.py (Pitfall 2 lift; gates Plan 07 ingest_runner deletion)"
  - "cfg.on_stage callback slot on RegionConfig + 22 fire-and-forget emit points across 11 canonical pipeline stages"
  - "4 canvas-sidecar files emitted from run_pipeline (territories.geojson, baronies.geojson, condado_colors.json, barony_colors.json) — closes Pitfall 10 BLOCKER"
affects: [03-02 (SSE producer consumes cfg.on_stage), 03-03 (useCanvasArtifacts URL swap consumes the four sidecars), 03-07 (ingest_runner deletion now safe)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fire-and-forget cfg.on_stage callback as the canonical pipeline-progress hook"
    - "Sidecar emitters as pure-geometry helpers next to the pipeline (no v1 module reuse)"
    - "Re-export-from-paths pattern for helpers leaving deletion-target modules"

key-files:
  created:
    - backend/medieval_forge/services/canvas_sidecars.py
    - backend/tests/unit/test_paths_write_geojson_atomic.py
    - backend/tests/unit/test_run_pipeline_on_stage.py
  modified:
    - backend/medieval_forge/services/paths.py
    - backend/medieval_forge/services/ingest_runner.py
    - backend/medieval_forge/services/pipeline/contracts.py
    - backend/medieval_forge/services/pipeline/__init__.py
    - backend/medieval_forge/services/pipeline/adapters/base.py
    - backend/medieval_forge/services/ingest_terrain/runner.py
    - backend/tests/parity/test_iberia_868.py

key-decisions:
  - "Adopted advisor's recommendation: write a NEW services/canvas_sidecars.py rather than refactor v1 territories_geojson.py / baronies_builder.py — those modules are Wave 3 deletion targets and don't fit the in-memory pipeline call shape"
  - "Sidecar geometry derives from the same pc/result rasters used by metadata + lookup steps — guarantees the canvas sees the same boundaries the lookup PNG hit-tests against (D-09 deployed-wins)"
  - "Captured cmaps inside the lookup-step loop and passed them to the sidecar emitters; avoids a re-read of lookup_*_colors.json"
  - "Used cleanup/smooth/merge as three rapid start/done markers around the single cleanup_and_smooth call (per plan instruction); finer-grained timing belongs to Phase 04"
  - "Barony id == name (no separate id field exists in the bars dict per voronoi.py)"

patterns-established:
  - "_write_geojson_atomic now lives in services/paths.py; legacy import path re-exports until Plan 07 deletes the file"
  - "cfg.on_stage(stage, evt) is the canonical pipeline-progress contract — 11 canonical stages × {start,done} = 22 events in fixed order"
  - "Canvas sidecars sit inside the export on_stage span; emit-only and parity-safe"

requirements-completed: [SC-1, SC-4]

# Metrics
duration: 12min
completed: 2026-05-09
---

# Phase 03 Plan 01: Canvas-sidecar emission BLOCKER Summary

**Pipeline now emits four canvas-sidecar files alongside the 10-file Unity contract, exposes a fire-and-forget cfg.on_stage callback wired into 11 canonical stages, and lifts _write_geojson_atomic into services/paths.py — Phase 01 parity stays 10/10 green and the Phase 03 read-only canvas can hydrate without 404s.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-09T20:37:02Z
- **Completed:** 2026-05-09T20:49:17Z
- **Tasks:** 3
- **Files modified:** 7 (+ 3 created)

## Accomplishments

- Closes Pitfall 10 (canvas-sidecar gap). `run_pipeline(cfg)` now emits `territories.geojson`, `baronies.geojson`, `condado_colors.json`, and `barony_colors.json` into `cfg.output_dir` — every visible condado has a hex color, every painted barony has a polygon.
- Closes Pitfall 2 (`_write_geojson_atomic` lift). Helper now lives in `services/paths.py`; `ingest_runner.py` re-exports for legacy callsites; the two production consumers (`pipeline/adapters/base.py` + `ingest_terrain/runner.py`) import from `paths.py`. Plan 07 can now delete `ingest_runner.py` cleanly.
- Adds `cfg.on_stage: Optional[Callable[[str, str], None]]` slot to `RegionConfig` (default `None` preserves Phase 01 parity). 22 emit points fire across 11 canonical stages in fixed order — Plan 02 wires the SSE producer against this slot.
- Phase 01 parity stays **11/11 green** (10 original Unity-contract assertions + 1 new `test_canvas_sidecars_exist`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Lift `_write_geojson_atomic` to `services/paths.py`** — `93b8e45` (refactor)
2. **Task 2: Add `cfg.on_stage` callback + 11 stage emit points** — `dadab5b` (feat)
3. **Task 3: Emit 4 canvas-sidecar files at end of `run_pipeline`** — `1ea4c86` (feat)

_Note: TDD tasks were combined (test + implementation) into a single commit per task — the helper/feature and its tests are inseparable inside the same atomic change._

## Files Created/Modified

- `backend/medieval_forge/services/canvas_sidecars.py` — NEW. Pure-geometry sidecar emitters: `build_territories_geojson_sidecar` + `build_baronies_geojson_sidecar`. No LLM dependency, no v1 module reuse.
- `backend/medieval_forge/services/paths.py` — added `_write_geojson_atomic` helper.
- `backend/medieval_forge/services/ingest_runner.py` — replaced original definition with a `from .paths import _write_geojson_atomic` re-export.
- `backend/medieval_forge/services/pipeline/contracts.py` — added `Callable` typing import + `on_stage: Optional[Callable[[str, str], None]] = None` field on `RegionConfig`.
- `backend/medieval_forge/services/pipeline/__init__.py` — added `_emit(cfg, stage, evt)` helper, sprinkled 22 emit points across 11 canonical stages, captured `cmaps` from the lookup loop, called the two sidecar emitters inside the export span.
- `backend/medieval_forge/services/pipeline/adapters/base.py` — switched `_write_geojson_atomic` import from `ingest_runner` → `paths`.
- `backend/medieval_forge/services/ingest_terrain/runner.py` — same import switch.
- `backend/tests/unit/test_paths_write_geojson_atomic.py` — NEW. 4 tests cover canonical + legacy import paths, atomic-write semantics, and the no-auto-mkdir contract.
- `backend/tests/unit/test_run_pipeline_on_stage.py` — NEW. 3 tests cover default `None`, the 22-event canonical order (full pipeline run), and exception propagation.
- `backend/tests/parity/test_iberia_868.py` — added `test_canvas_sidecars_exist`. 10-file parity assertions stay untouched.

## Decisions Made

- **Canvas sidecar approach (key):** wrote a NEW `services/canvas_sidecars.py` rather than refactoring v1 `territories_geojson.py` / `baronies_builder.py`. Rationale: the v1 modules are Wave 3 deletion targets (D-12) and don't fit the in-memory call shape (`territories_geojson.py` does disk-readback against `lookup_condado.png`; `baronies_builder.py` clusters OSM municipalities). Refactoring them risks the v1 readback flow before Wave 3 deletes it; a pure helper next to the pipeline is the surgical move.
- **Geometry source:** sidecars use `rasterio.features.shapes` on `pc` (condados) and `result` (baronies) — the same arrays the metadata + lookup steps already use. The canvas thus sees the same boundaries the lookup PNGs hit-test against (D-09 deployed-wins).
- **Color sidecar:** captured cmap dicts inside the lookup loop and passed them to the sidecar emitters. Avoided re-reading `lookup_*_colors.json` from disk; cmap key format is `"r,g,b"` (per `lookup.py`), inverted to `#rrggbb` for the frontend.
- **`cleanup`/`smooth`/`merge` granularity:** emitted as three rapid start/done markers around the single `cleanup_and_smooth(...)` call. Per the plan: finer-grained timing is Phase 04 territory.
- **Barony id == name:** the `bars` dict has no separate `id` field (verified `voronoi.py:50`). The lookup path uses `result == bi` indexing; we use `bars[bi]['name']` as the canvas-side identifier, consistent with how `barony_colors.json` keys map to lookup PNG colors.

## Deviations from Plan

**Total deviations:** 1 minor — adapted to ground truth.

### Adapted to Code Reality

**1. [Rule 2 / Rule 3 — Adapted] New helper module instead of reusing v1 territories_geojson.py / baronies_builder.py**
- **Found during:** Task 3 (Emit 4 canvas-sidecar files)
- **Issue:** The plan suggested refactoring `services/territories_geojson.py` and `services/baronies_builder.py` to accept the in-memory `(result, pc, condados, …)` arguments produced by `run_pipeline`. Those modules don't fit that shape — `territories_geojson.py` is a disk-readback pipeline (`emit_territories_from_disk` reads `lookup_condado.png` from `projects/<uuid>/generated/`), and `baronies_builder.py` clusters OSM municipality polygons (totally unrelated to the post-cleanup raster).
- **Fix:** Created a new `services/canvas_sidecars.py` with two pure emitters (`build_territories_geojson_sidecar`, `build_baronies_geojson_sidecar`) that accept the in-memory arrays directly. Verified the plan explicitly anticipated this (`Adjust function names/signatures to match the audited reality — names above are placeholders. Do NOT invent kwargs not present in the existing functions; refactor the existing function to accept these explicit args if it currently reads from globals.`). The new module is also LLM-free (verified — no `research/llm/openai/anthropic` imports).
- **Files modified:** added `services/canvas_sidecars.py`; left v1 modules untouched (Wave 3 will delete them).
- **Verification:** parity 11/11 green; new `test_canvas_sidecars_exist` covers presence + non-emptiness + condado-id color coverage.
- **Committed in:** `1ea4c86`

**Plan parity-test fixture name was wrong** — the plan example used `iberia_output_dir`, but the conftest fixture is `pipeline_output`. Used `pipeline_output`. (Caught by advisor before any test was written.)

---

**Impact on plan:** No scope creep. Adapted shape; same semantics. Deletion graph for Wave 3 is unchanged.

## Issues Encountered

None. Two IDE-side false-positive diagnostics ("Cannot find module `numpy`/`PIL`") are pre-existing project-root inference issues unrelated to this plan; the actual pytest run resolves all imports cleanly.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 03-02 ready.** Backend v3 endpoints can wire `cfg.on_stage` directly to an `asyncio.Queue.put_nowait`-style SSE producer. The 11-stage canonical order is documented in `_emit` calls + `test_run_pipeline_on_stage.py::CANONICAL_STAGES`.
- **Plan 03-03 ready.** `useCanvasArtifacts` can fetch `/api/v3/projects/{id}/artifacts/{territories,baronies}.geojson` + `{condado,barony}_colors.json`; cardinality is guaranteed (every visible condado has a polygon + a color).
- **Plan 03-07 unblocked.** `_write_geojson_atomic` no longer lives in `ingest_runner.py`; the file's only remaining responsibility is `run_ingest` + `_backfill_bbox` (which are also Wave 3 deletion targets).

## Self-Check: PASSED

- FOUND: backend/medieval_forge/services/canvas_sidecars.py
- FOUND: backend/medieval_forge/services/paths.py (`_write_geojson_atomic`)
- FOUND: backend/medieval_forge/services/pipeline/contracts.py (`on_stage`)
- FOUND: backend/medieval_forge/services/pipeline/__init__.py (22 `_emit(cfg,` calls)
- FOUND: backend/tests/unit/test_paths_write_geojson_atomic.py (4 tests passing)
- FOUND: backend/tests/unit/test_run_pipeline_on_stage.py (3 tests passing)
- FOUND: backend/tests/parity/test_iberia_868.py (`test_canvas_sidecars_exist`, 11/11 parity)
- FOUND commit: 93b8e45 (Task 1 — refactor)
- FOUND commit: dadab5b (Task 2 — feat on_stage)
- FOUND commit: 1ea4c86 (Task 3 — feat sidecars)

---
*Phase: 03-read-only-canvas-redesign*
*Completed: 2026-05-09*
