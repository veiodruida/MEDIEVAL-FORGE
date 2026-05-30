---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 08.3-01-PLAN.md
last_updated: "2026-05-30T18:27:04.880Z"
last_activity: 2026-05-30
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 19
  completed_plans: 14
  percent: 74
---

# Project State (v3)

## Project Reference

See: .planning/PROJECT.md

**Core value:** A Game Designer goes from "country + historical period" to a validated, Unity-ready map package — driven by geometry, with LLM as opt-in metadata.
**Current focus:** Phase 08.3 — pen-tool-barony-contour-authoring

## Current Position

Phase: 08.3 (pen-tool-barony-contour-authoring) — EXECUTING
Plan: 2 of 6
Status: Ready to execute
Last activity: 2026-05-30

Progress: [█████████░] 93% (25 of 27 plans complete)

**RESUME:** Plan 04.1-03 (D-01 stable projection key + D-02 preview gesture, frontend-only, no dependency on backend or plan 04) is the natural next step. Plan 04.1-05 (Playwright regression sweep) gates phase closure — it consumes the data-testids codified by plan 04.1-04 (`barony-source-coord`, `barony-source-file`, `barony-method-explainer`) for the SC-3 E2E click-through.

## Accumulated Context

### Roadmap Evolution

- Phase 07.1 inserted after Phase 07: Period numeric inputs + Llama.cpp re-add with auto-launch and local model list (URGENT)
- Phase 07.2 added: cloud LLM providers (OpenRouter / OpenAI / Gemini) + .env auto-discover + live token streaming + CredentialsManager dialog
- Phase 08 added: border-vertex-editor — manual SVG-style vertex editing of territory polygons with project branching
- Phase 08.1 inserted after Phase 08: Bezier-assisted barony contour editing — UI-layer Bezier control points over the existing polygon model, parity-safe (store stays polygon, curve-fit derived for display, only edited segments flatten back) (URGENT — raw vertex handles unusable: hundreds of dots per barony)
- Phase 08.2 inserted after Phase 08.1: Bézier edit-to-map convergence — backend vertex move/add/delete replay in manual_edit + render cascade so contour edits reach the colored map and export (URGENT — closes G8: 08.1 saves edits to branch but render pipeline drops op:'move', so colored boundary never changes; user-confirmed in browser 2026-05-29). Completed 2026-05-30, verified 5/5 (incl. 08.2-05 gap: MultiPolygon→largest-component reduction so second Apply keeps original_idx).
- Phase 08.3 inserted after Phase 08.2: Pen tool — Photoshop-style barony contour authoring, create new baronies + extend existing (URGENT — 08.2 UAT feedback 2026-05-30: Bézier handle editor too hard to fill the empty space left by editing a neighbor; could not draw clean S-curves. Need click=straight anchor / click-drag=curve handle. Not planned yet — discuss before planning.)

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
- [Phase 04.1]: Plan 04.1-05: SC-1 E2E gate caught two production bugs in Plan 04.1-03 — viewport-key effect clobbering user zoom on every workspace layout micro-oscillation, and useCanvasArtifacts queries dropping CanvasViewer into the loading branch on every cacheVersion refetch. Both fixed inline as Rule 1 deviations via (a) Math.abs(currentScale - minScale) < 1e-6 guard in viewport-key effect, (b) placeholderData: keepPreviousData on all 5 useQueries. Unit tests passed because they mocked rather than reproduced real ResizeObserver oscillation + real refetch loading branch. 5/5 Playwright specs green (3 new + 2 Phase 04); 210/210 frontend vitest; 38 backend pytest green; xfail/xpass unchanged.
- [Phase 04.1]: Plan 04.1-05: Dev-only window escape hatches (__forgeStageScale + __forgeSelectBarony) added to CanvasViewer + BaronyLayer; gated on import.meta.env.DEV per T-04.1-05-01 disposition. Pattern reusable for any future E2E spec needing deterministic access to runtime state.
- [Phase 05]: pyproject.toml is at repo root (not backend/); PyYAML added there
- [Phase 05]: region_loader cache keyed by (key, regions_dir) for test isolation
- [Phase 05]: Plan 05-01: explicit-only cache (no mtime) per RESEARCH D-15 recommendation
- [Phase 05]: KINGDOMS/DUCHIES/CONDADOS converted from native dict/tuple formats to list[dict] matching RegionConfigSchema (plan literal dict(raw_condado) crashed on tuple input)
- [Phase 05]: kingdom_colors int keys emitted as str keys — pydantic v2 rejects int keys in dict[str, list[int]]
- [Phase 05]: parents[3] is correct repo root anchor for test files in backend/tests/unit/ (not parents[4])
- [Phase 05]: _convert_territory_data added to region_loader.py: load_region must produce voronoi-compatible shapes before any parity test can pass
- [Phase 05]: kingdom_colors keys converted int(k): render.py indexes with integer ki; YAML emits str keys by pydantic contract
- [Phase 05]: Router prefix is /v3/regions (not /api/v3/regions) — main.py adds prefix=/api, same as all other v3 routers; plan code snippet had wrong prefix that would double-prefix to /api/api/v3/regions
- [Phase 05]: Router prefix /v3/projects (not /api/v3/projects) — plan snippet had wrong prefix; main.py adds /api at mount time
- [Phase 05]: Migration 0005 added: v1 legacy fields (country_qid/period_start/period_end) made nullable for v3 project creation
- [Phase 05]: region_key threaded from endpoint to producer as plain str — no DB access in worker thread (generate.py + render.py)
- [Phase 05]: england_1216.yaml YAML-only template (no inputs dir): loader raises FileNotFoundError with actionable message; GET /api/v3/regions reports has_dataset=false
- [Phase 05]: All 5 planned migrations + 3 extras (audit found __main__.py + 2 unit tests) done in commit 6a388a2; 3 retirements in same commit; D-13+D-17 step 5 locked by c0be89e
- [Phase 05]: Dialog.Trigger without asChild: @radix-ui/themes DialogTriggerProps doesn't include asChild; data-testid placed on inner Button instead
- [Phase 05]: 10-file EXPORT_FILE_CONTRACT (not 12): terrain_lookup.png + terrain_types.json deferred to Phase 06 (P-2); E2E test asserts 10-file contract per EXPORT_FILE_CONTRACT constant
- [Phase 05]: original_idx emitted conditionally in export.py: len(c)>6 gate lets Iberia parity stay green while autogen regions gain CLAUDE.md rule 4 compliance
- [Phase 05]: autogen baronies: 1 barony per condado at centroid — voronoi KD-trees require non-empty baronies list; autogen path previously left bars=[] → blank map
- [Phase 06]: Plan 06-01: services/export/ subpackage carved out (zip.py + schemas.py + validator.py + __init__.py); 6 pydantic v2 schemas (RootModel for dict-shape JSONs) + MANIFEST_SCHEMA_VERSION=2; validator orchestrator + 5 stub _check_* fns (bodies in 06-02); ValidationFailedError defined but raised only by build_unity_zip (06-03); 15 SCHEMA_INVALID unit tests; 150 unit + 11 parity + 6 existing export tests all green
- [Phase 06]: Plan 06-02: 5 _check_* bodies implemented + 32 unit tests across 5 D-08-code modules; lazy numpy/PIL imports inside _check_ocean_leak; within-file COLOR_COLLISION scope deferred to e2e (06-03) due to JSON dict-key-collapse; validator runs end-to-end on Iberia output with passed=True; parity 11/11 stays green (validator unwired until 06-03)
- [Phase 06]: Plan 06-03: validator wired into build_unity_zip (raises ValidationFailedError); POST /api/v3/projects/{id}/export with ?dry_run=true (D-03); D-04 atomic v1 delete (api/export.py + tests/test_export.py); MANIFEST v2 with schema_version/region_key/validation_report/per-file sha256; 10 e2e tests across 3 files cover all 6 D-08 codes; 218/218 tests pass
- [Phase 07.1]: Wave 0 test scaffolds: 9 skip-marked files created (59 tests) closing VALIDATION.md Wave 0 gaps; no production imports; per-task commit protocol used (2 commits instead of 1 atomic)
- [Phase 07.1]: D-09 additive-only: available_models field added to HealthStatus with default None; healthy stays canonical (no rename to ok forces touch of Claude+Ollama)
- [Phase 07.1]: shutdown() is the single sync entry point (review-fix #4); no shutdown_sync symbol exported
- [Phase 07.1]: _set_process_for_tests() seam used for Test 13 shutdown real subprocess without importlib.reload
- [Phase 07.1]: parse_research_json imported at module top level in llamacpp.py (not inline) — required for test monkeypatching
- [Phase 07.1]: Registry count tests updated 2->3 (Rule 3): adding LlamaCppProvider at import directly breaks len==2 assertions
- [Phase 07.1]: D-04c atomic swap: all 6 runner.py callsites + cache.py + StartResearchBody changed in ONE commit — no transitional period_label shim
- [Phase 07.1]: review-fix #5: _QID_DISPLAY_NAMES dict + _resolve_country_display_name() in runner.py prevents local LLM hallucination on raw Wikidata Q-codes
- [Phase 07.1]: 7 tests implemented (not 5): plan objective was stale; must_haves.artifacts listed 7 — review-fix #4 added GET-running-false + GET-running-true
- [Phase 07.1]: import logging + logger added to main.py (Rule 3 fix): lifespan snippet used logger without prior definition
- [Phase 07.1]: GET /api/projects/{id} (v1 legacy) used for useProject hook — v3 only has POST; queryKey ['v3','research','providers'] corrected from plan's ['providers'] to match useProviders.ts actual registration
- [Phase 07.1]: useResearchStream.ts not modified: period_label was in ResearchDialog.tsx handleSubmit only; plan incorrectly identified the hook as the file target
- [Phase 07.1]: 11 vitest cases implemented (plan objective said '8'; must_haves.artifacts + acceptance_criteria canonical at 11 — review-fixes #1+#10 add Tests 9/10/11; objective was stale draft)
- [Phase 07.1]: hasPointerCapture shims added to test-setup.ts (Rule 3: Radix Select pointerDown throws in jsdom without them)
- [Phase 07.1]: Harness fallback (review-fix #6): test-only /test-routes/research-dialog route created since Phase 07 entry affordance not reachable via stable selector; V2/V4 not testable without real llama-server binary per D-08b
- [Phase 07.1]: Pre-existing Playwright failures (Phase 04/05) excluded from 07.1 gate: git log confirms none modified during 07.1; timing/environment issues unrelated to 07.1 changes
- [Phase 07.1]: grep gate: production code clean (0 period_label hits in medieval_forge/*.py and frontend/src); test-file hits are all negative assertions
- [Phase 08.1]: Plan 08.1-01: bezierFit.ts + bezierFlatten.ts pure store-free geometry libs. BEZ_FIT_ERROR=30 calibrated (Iberia fixture -> 4 cubics, inside 4..30 band). No deps.inline needed for fit-curve under Vite 6 + vitest 3. BEZ-FLATTEN-02 tolerance relaxed 1e-4->0.01deg (fit error ~0.004deg by design, not float drift). buildPolyIndexMap closes Split-Index Gap via O(N) post-fit scan. 482/482 vitest green; 4 TDD commits.
- [Phase 08.1]: Plan 08.1-02: BezierEditLayer.tsx render+activate Konva Layer (z=5) created. Fits selected barony polygon to 4 cubics on entry (IBERIA_BARONY_RING -> 4 anchors, far below ~100 raw verts). All Bezier display state component-local (zero useEditorStore fields, zero partialize change); activeAnchorIdx never in store. projection passed as PROP (not useProjection). BEZ-IDENTITY-01 GREEN by construction (zero setVerticesAndLog). DEV-only window.__forgeBezierState escape hatch. temporal API fix in test: useEditorStore.temporal.getState().pause() (Rule 3). 488/488 vitest green.
- [Phase 08.1]: Plan 08.1-03: BezierEditLayer drag-commit landed. Anchor drag marks segments i-1+i dirty, control-handle drag marks one (cp1->i-1, cp2->i); only dirty segments flatten via flattenSegment, non-dirty ranges copied verbatim from store (identity mechanism). Anchor drag rigidly translates both handles by the same delta (no cusp); snap (snapToNeighbour) on anchors only, never handles; getCoupledVertices coupling before commit. Single setVerticesAndLog(op:'move'). Rule-1 fix: deriveAnchors cp2 corrected from Plan02's c2 to c1 (fit-curve c1 near p0, c2 near next anchor; verified on IBERIA_BARONY_RING |p0->c1|~9-13px vs |p0->c2|~65-92px). BEZ-IDENTITY-01 stays green; 494/494 vitest, tsc clean.
- [Phase 08.1]: Plan 08.1-04: BezierEditLayer wired into CanvasViewer z=5 via bezierActive ternary (exactly one of VertexEditLayer/BezierEditLayer mounted — T-08.1-04-01). EditToolPalette gains disabledTools prop (A/D Radix-disabled with locked PT copy); stays Bézier-unaware, WorkspaceToolbar derives bezierMode set. BEZ-UAT-01 green (barony Grado → anchorCount 4..40 → DEV-hook __forgeBezierTriggerDrag commits op:move); BEZ-UAT-02 green (lookup_barony.png SHA d557e8e6... byte-identical after zero-drag round trip). Real page.mouse drag non-deterministic vs ~3px anchor at fit scale → plan-sanctioned DEV hook (Rule 3). Zero backend commits; vitest 499/499; tsc clean.
- [Phase 08.1-05]: Ring model: last-anchor-wrap chosen; closing segment runs anchor[N-1]->anchor[0] via last cubic
- [Phase 08.1-05]: RESEARCH Pattern1/WR-01 REVERSED: closing segment now editable; cp1 anchor-0 commits via op:move (G2 fix)
- [Phase 08.1-05]: G4 palette: CURVE_STROKE #22c55e (green), HANDLE_FILL #e879f9 (magenta) — 5 distinct hexes, no collision
- [Phase 08.1]: G3 insert-anchor: identity-safe NO-OP (setAnchors only), first commit on drag via op:move; dedicated hit-Path keeps visible outline listening=false
- [Phase 08.1]: [Rule 1] findNearestSegmentAndVertex closing-segment fix: loop s<N-1 -> s<N with wrap — all N segments reachable (G1+G2 mandate from plan 05)
- [Phase 08.1-07]: getRelativePointerPosition() in onDblClick: map-space vs screen-space coordinate bug fixed (G7 production fix)
- [Phase 08.1-07]: MAX_SCALE_MULTIPLIER raised 4→16; screen-space sizing BASE/currentScale for anchors/handles/hit-path
- [Phase 08.1]: G6 fix (option a): live amber-dashed overlay reads store.vertices read-only — phase boundary preserved (backend never sees Bezier), BEZ-IDENTITY-01 safe by construction
- [Phase 08.1]: op:move has NO Phase-08 precedent on the colored map — only split/merge/translate POST /editor/apply; colored barony converges only via /render; G6 contract is a new live-overlay, not a phantom pattern
- [Phase 08.1]: editedRingPtsRef: ref synced every render for stale-closure-safe DEV hook access; editedRingSnapshot (not count) is the Playwright geometry-change discriminator
- [Phase 08.2]: A1 coordinate contract: lon/lat->rasterio_y requires round()+H-flip (NOT int()). Plan 02 replay_vertex_ring must use round(); geo_to_pixel is parity-frozen.
- [Phase 08.2]: RESEARCH Open Q#2 confirmed: vertices key survives gzip+json round-trip; test locks contract before Wave 1 wires loader.
- [Phase 08.2]: replay_vertex_ring uses round()+H-flip NOT geo_to_pixel — parity-frozen int() causes 34px drift; buffer(0) heals non-convex rings from add/delete ops; _geometry_modified short-circuit ensures byte-identical on landmask-only path
- [Phase 08.2]: bezierApplyMode excluded from zundo partialize: UI preference (not edit op), undo must never change mode toggle state
- [Phase 08.2]: useBezierApply calls postRender directly — NOT via dispatch/diffOverrides (Pitfall 3: diffOverrides({}, lastRendered) is empty on Apply path → silent no-op)
- [Phase 08.2]: BezierApplyControls extracted from WorkspaceToolbar (228 LOC + ~50 = exceeds 250 LOC planner limit); subcomponent hosts the data-testid anchors
- [Phase 08.2]: BEZ-CONV-05 UAT approved: real-mouse Bezier edit on coastline barony -> colored boundary moves, overlay clears, survives reload (G8 closed end-to-end)
- [Phase 08.2]: Known defect deferred: replay_vertex_ring degrades edited barony on second Apply (MultiPolygon from buffer(0) not extracted by sidecar writer) — single Apply intact, G8 closed for first edit
- [Phase 08.2]: BEZ-CONV-05: buffer(0) MultiPolygon guard — largest-area component over unary_union; second Apply no longer drops barony from baronies.geojson (CLAUDE.md rule #4)
- [Phase 08.3-01]: Raster overpaint (not KD-tree mutation) is the CREATE mechanism — D-11 re-described
- [Phase 08.3-01]: compute() tuple return (ndarray, list) — all 4 early returns updated; ocean_mask scoped to (input==-1)&(out==-1)
- [Phase 08.3-01]: bars list-copied before extension in run_pipeline_incremental to avoid polluting _VORONOI_CACHE reference

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

Last session: 2026-05-30T18:27:04.876Z
Stopped at: Completed 08.3-01-PLAN.md
Resume file: None
