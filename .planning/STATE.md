---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: + bootstrap v3 infrastructure
status: executing
stopped_at: Completed 04.1-03-PLAN.md
last_updated: "2026-05-11T12:56:28.826Z"
last_activity: 2026-05-11
progress:
  total_phases: 10
  completed_phases: 4
  total_plans: 27
  completed_plans: 26
  percent: 96
---

# Project State (v3)

## Project Reference

See: .planning/PROJECT.md

**Core value:** A Game Designer goes from "country + historical period" to a validated, Unity-ready map package — driven by geometry, with LLM as opt-in metadata.
**Current focus:** Phase 04.1 — parameter-studio-polish-cancel-race-hardening

## Current Position

Phase: 04.1 (parameter-studio-polish-cancel-race-hardening) — EXECUTING
Plan: 4 of 5 (out-of-order: 01 + 02 + 04 complete; 03 + 05 still pending)
Status: Ready to execute
Last activity: 2026-05-11

Progress: [█████████░] 93% (25 of 27 plans complete)

**RESUME:** Plan 04.1-03 (D-01 stable projection key + D-02 preview gesture, frontend-only, no dependency on backend or plan 04) is the natural next step. Plan 04.1-05 (Playwright regression sweep) gates phase closure — it consumes the data-testids codified by plan 04.1-04 (`barony-source-coord`, `barony-source-file`, `barony-method-explainer`) for the SC-3 E2E click-through.

## Accumulated Context

### Decisions

See `.planning/PROJECT.md` Key Decisions table (D-V3-01 through D-V3-07).

- [Phase 01-pipeline-parity-port-harness-together]: PREFLIGHT.md Q8: original_idx ABSENT in deployed territory_metadata.json (0/92 condados). Port reproduces inicio verbatim per D-09 (deployed wins).
- [Phase 01-pipeline-parity-port-harness-together]: PREFLIGHT.md Q10: draw_names = False (deployed visual_condado.png has no labels).
- [Phase 01-pipeline-parity-port-harness-together]: RegionConfig is @dataclass (not pydantic) per RESEARCH §2.b — drift from inicio is the hard cost.
- [Phase 01-pipeline-parity-port-harness-together]: border_polygon length is 40 (verbatim from inicio:132-143) — plan/CLAUDE.md mis-counted as 38; documented as Rule 1 deviation.
- [Phase 01-pipeline-parity-port-harness-together]: ES TopoJSON sourced via npm pack es-atlas@0.6.0 (shasum 4c926d9cba); PT GeoJSON via Git LFS.
- [Phase 01]: Plan 02 verbatim port: all 8 inicio sections ported 1:1 across 9 submodules; CLI smoke produces 10 contract files with byte-deterministic SHA-256 across runs; Image.NEAREST + cfg.rng_seed + per-country KD-trees + 9999/-1 sentinels + 2x independent masks all preserved
- [Phase 01]: Windows portability fix (Rule 3 deviation): added encoding='utf-8' to ES TopoJSON open in landmask.py; inicio's POSIX-default open errors on cp1252; fix matches inicio's PT path which already uses utf-8
- [Phase 02]: Plan 02-01: ProjectDataset migration completed atomically (D-01, D-03, D-04, D-06, D-08); 5 callsites migrated; Phase 01 parity stays 10/10; 9 new unit tests
- [Phase 02]: Plan 02-02: services/pipeline/adapters/ subpackage built (4-file flat split: __init__/base/osm/terrain). build_dataset_from_osm wraps fetch_municipalities (D-05); _split_by_iso uses representative_point (Pitfall A3); build_terrain returns vendored mountain_river_data.json (D-13 stub); D-15+D-16 honored by absence. 11 unit tests + Phase 01 parity 10/10 unchanged; combined wave 21/21 green.
- [Phase 02]: Plan 02-04: D-14 implemented (GET /api/v3/projects/{id}/ingest SSE endpoint). Mirrors v1 _sse_generator pattern; wraps build_dataset_from_osm; terminal None sentinel; per-(project_id, step) stop_event; status: ingested on success, error_ingesting on cancel/exception. Legacy v1 /api/projects/{id}/ingest stays mounted (D-14 coexistence). D-13/D-15/D-16 honored by absence. 6 unit tests pass; Phase 01 parity unchanged 10/10.
- [Phase 02]: Plan 02-03 closed with Option C (defer + xfail). ROADMAP-02#1 deferred to Phase 02.1 ('Resolve live-ingestion parity contract') — vendored (es-atlas/IGE) and live (raw OSM) are different upstream sources, structural divergence cannot converge under any waiver-loop iteration. test_iberia_868_live.py xfail(strict=False); 6 xfailed + 4 xpassed, suite exit 0; Phase 01 parity 10/10 green. See D-09-LIVE-WAIVER.md.
- [Phase 03]: Plan 03-01: canvas sidecars emitted from new services/canvas_sidecars.py (NOT v1 territories_geojson.py); cfg.on_stage hook wired with 22 emit points across 11 canonical stages; _write_geojson_atomic lifted to paths.py with re-export stub. Parity 11/11 green.
- [Phase 03]: Plan 03-02: 3 v3 endpoints (POST /generate + GET /generate/stream + GET /status + GET /artifacts) wired in main.py; ARTIFACT_FILES single-source frozenset (14 files) in artifacts.py; cfg.on_stage threadsafe bridge via loop.call_soon_threadsafe; updated_at bumped explicitly on success (D-19). 24 unit tests green; parity 11/11 stays green.
- [Phase 03]: Plan 03-03: useRunStore (5-state machine + 11-stage PIPELINE_STAGES + LOG_CAP=500) created; uiStore evolved with selectedTerritoryIds[] + selectIds + selectSelectedTerritoryId selector (mirror selectedTerritoryId kept for backward-compat); useCanvasArtifacts switched to /api/v3/projects/{id}/artifacts/* (5 URLs); orphaned __tests__/uiStore.test.ts deleted; CanvasViewer.tsx hydrate-fetch URL updated in lock-step; 238/238 vitest green; 4 commits (561f999, fcb2ebf, f7a0576, f9e8a55).
- [Phase 03]: Plan 03-05: CanvasViewer stripped 697->361 LOC (zero v1-deleted-module imports); InteractionLayer multi-id rendering via uiStore.selectedTerritoryIds; TerritoryLayer read-only click (plain=selectIds([id]); shift=toggle); HoverTooltip DOM overlay via Stage.getPointerPosition (D-15); MultiSelectInspector aggregate view (D-17); InspectorSidebar 3-mode dispatcher with English COPY locked + PT-BR placeholder; LayerTogglePanel 5 layers (terrain row removed); pixelsToKm2 extracted to src/lib/. 8 deviations all advisor-confirmed (orphan deletions, contract rebaselines). 2 commits (e146b23, 730648d); full suite 268/268 green.
- [Phase 03]: Plan 03-06: Combined D-10+D-11+D-13 frontend purge in one atomic commit (63 files, -8764 LOC). InspectorSidebar.tsx stripped of useResearchStore + useValidationStore (Plan 05's Wave 3 handoff). api/client.ts trimmed to 8 hooks. Pre-existing RunLogPanel Card 'p' prop fix to unblock typecheck gate. Pitfall-1 grep clean; tsc + vitest 154/154 + vite build all green.
- [Phase 03]: Plan 03-07: D-12 + D-13 backend purge in 2 atomic commits. api/edit.py added (plan-permitted; orphan via 4 LLM imports). services/territories_geojson.py kept (not in plan list; voronoi lazy-imports it). models.py + main.py shrunk; smoke import 25 routes; parity 11/11.
- [Phase 04]: Register pytest.mark.unit in pyproject.toml; expand Playwright testDir to ./tests to discover both uat/ and e2e/ directories
- [Phase 04]: Monolith cleanup_and_smooth removed; 4 split functions (apply_median/remove_fragments/smooth_per_territory/merge_small_blobs) deliver byte-equal D-17 parity
- [Phase 04]: stop_event uses threading.Event directly in RegionConfig (not string forward-ref) — import threading added at module scope in contracts.py
- [Phase 04]: PIPELINE_STAGES expanded 11->12: 'cleanup' replaced by 'median' + 'fragment'; DAG_ORDER canonical 12-stage tuple in dag.py is single source of truth
- [Phase 04]: Completed-stages closure list in _render_producer (not return value) — StageCancelled prevents return; advisor item 2
- [Phase 04]: _VORONOI_CACHE side-table for non-array voronoi intermediates; _STAGE_CACHE holds numpy arrays only
- [Phase 04]: run_pipeline gains optional project_id=None param for cache population; preserves Phase 01 CLI parity
- [Phase 04]: Completed-stages tracked via closure list in _render_producer (not return value) — return unavailable in except StageCancelled block
- [Phase 04]: _VORONOI_CACHE moved to cache.py and cleared by cache_clear_project — stale voronoi after fresh generate prevented
- [Phase 04]: useParameterStudioDispatch extracted to hooks/ to isolate projectId; showCancel=rendering only (not generating) per UI-SPEC; useRenderStore absorbed into useRunStore in Task 4 for Wave 3 parallel safety; FakeEventSource shim pattern for jsdom
- [Phase 04]: getLayers() used instead of findAll('Layer') — findAll not in Konva TypeScript types; getLayers() is the typed Stage method returning Layer[] (Rule 1 deviation from plan implementation detail, same behavior)
- [Phase 04]: useCanvasArtifacts 6-tuple backward-compatible at indices [0]..[4]; index [5] is new stageRasterUrl string; stageView in all 5 queryKeys; effectiveCacheVersion = priorTokens.render ?? cacheVersion (D-13 cancel revert)
- [Phase 04]: Vertex-average centroid (not area-weighted) sufficient for D-12 — baronies roughly convex, 1-2px off-center invisible at 10px font
- [Phase 04]: Approximate text width (char × 6px) avoids post-mount Konva ref complexity for a 10px decorative label
- [Phase 04]: Option A selective writes: _write_outputs_to_disk gated on affected stages (6.8s → 1.3s warm render)
- [Phase 04]: SC-3 Playwright budget relaxed to 30s (D-19); strict 500ms target deferred to Phase 05 pipeline optimization
- [Phase 04]: UAT 12/12 passed; 3 polish gaps (zoom reset, before/after preview, barony data discoverability) deferred to Phase 04.1
- [Phase 04.1]: Plan 04.1-01: WR-02 closed — both producers' finally evict _RUN_QUEUES/_RUN_TASKS after sentinel; 6 new pytest cases (3 per producer); 2 pre-existing cancel tests reshaped to subscribe-before-release via threading.Event gate (Rule 1 deviation, advisor-confirmed). 26/26 backend tests + 11/11 parity green.
- [Phase 04.1]: Plan 04.1-02: WR-01 + WR-03 closed in one wave. useParameterStudioDispatch carries D-04 bounded RENDER_BUSY retry (3 retries / 1.5s window, per-(project_id) useRef<Map> counter, surfaces finish('error', 'RENDER_BUSY') on 4th attempt). ParameterSidebar consumes the canonical hook via onRenderStarted callback — inlined latest-wins copy removed. 5 new vitest cases + 195/195 frontend tests green.
- [Phase 04.1]: Plan 04.1-04: D-03 closed at unit-test level. BaronyFeature/BaronyRender carry optional centroid?: [number, number] (backend already emitted it via canvas_sidecars.py line 233; frontend type was dropping it on the floor). InspectorSidebar barony branch extended with Coordenada de origem (lat/lon 3-decimal precision, fallback '—'), Origem dos dados (literal 'inicio/territory_data_v3.py' monospaced non-clickable label), and collapsible 'Sobre o método' PT-BR explainer of the Voronoi-from-centroids mechanic. CanvasViewer plumbs baronies={baroniesQ.data}. 5 new vitest cases + 200/200 frontend tests + parity 22/22 (12 pass + 6 xfail + 4 xpass) green. SC-3 satisfied at unit level; E2E click-through is plan 04.1-05's responsibility.
- [Phase 04.1]: Plan 04.1-03: D-01 + D-02 closed at unit-test level. CanvasViewer.tsx: (a) replaced !projection guard with metaBoundsKey memo + bounds-keyed setProjection effect; (b) added projectionBoundsKey memo + prevBoundsKeyRef gating fitToView on real bounds change only; (c) split auto-fit into two effects (bounds-key + viewport-key) so slider re-renders with identical bounds preserve zoom (UAT gap #1); (d) added previousCacheVersion state + lastCacheVersionRef + window keydown/keyup/blur listeners + 3-way effectiveCacheVersion precedence (gesture > D-13 cancel revert > cacheVersion) + 'Anterior' PT-BR badge for hold-spacebar before/after preview (UAT gap #2). 10 new vitest cases in 2 split test files; 210/210 frontend tests + tsc clean. D-13 fallback preserved (Test 7 regression guard).

### Blockers/Concerns

- v1 archive holds the lessons that v3 must NOT relearn. Before Phase 01 planning, re-read `.planning/v1-archive/STATE.md` for the 30+ pitfalls discovered during v1.0.
- 6 stale worktrees were removed in Phase 00 — verify `git worktree list` returns 1 line before any future agent work.
- Plan 02-03 paused at decision checkpoint: live OSM admin_level=8 ES (8179 features) is structurally larger than vendored es-atlas (~3000). Waiver-loop strategy locked in plan <approach> cannot converge. Live parity 4/10 pass, 6/10 fail (visual_condado SSIM=0.9630, visual_barony SSIM=0.9439, lookup PNGs byte-mismatch, territory_metadata.json mismatch). Phase 01 parity 10/10 green — isolation confirmed. See .planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md for evidence + 4 options.

### Pending Todos

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260507-g1v | Phase 00 v3 archive milestone reset | 2026-05-07 | a437f5e | [260507-g1v-phase-00-v3-archive-milestone-reset](./quick/260507-g1v-phase-00-v3-archive-milestone-reset/) |

## Session Continuity

Last session: 2026-05-11T12:56:28.824Z
Stopped at: Completed 04.1-03-PLAN.md
Resume file: None
