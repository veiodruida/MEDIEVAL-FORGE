# Roadmap: Medieval Forge v3

## Overview

Eight phases reset Medieval Forge to its roots. Phase 00 archives v1.0 and bootstraps v3 infrastructure (CI, planning docs, skill move). Phase 01 ports `inicio/map_generator.py` as a parametrized library and proves byte-equivalence with the Reconquista exports. Phase 02 wires the existing v1 ingestion into the new pipeline contract. Phase 03 replaces the v1 stepper UI with a single-canvas read-only workspace. Phase 04 turns that canvas into a parameter studio with live re-render. Phase 05 generalizes Iberia from hard-coded to config-driven. Phase 06 adds export validation gates. Phase 07 reintroduces LLM as opt-in metadata.

## Phases

### Phase 00: Archive v1.0 + bootstrap v3 infrastructure
**Goal:** v3 starts from a clean base without breaking the working v1 server.
**Depends on:** Nothing
**Status:** in-progress
**Success criteria:**
1. `git tag --list` contains `v1.0-archive`
2. `.planning/v1-archive/` contains 5 archived planning docs + `STACK_RESEARCH.md`
3. CLAUDE.md reflects v3 (Pipeline Contract + Architecture + Conventions + What v3 is NOT)
4. `.claude/skills/karpathy/SKILL.md` exists and is auto-discoverable
5. `.github/workflows/ci.yml` exists with 4 jobs; pytest markers + frontend e2e script in place
6. `medieval-forge start` still boots and serves 200 OK on `/`

### Phase 01: Pipeline parity (port + harness together)
**Goal:** Port `inicio/map_generator.py` as a deterministic, parametrized library and prove byte-equivalence with the Reconquista exports for Iberia 868.
**Depends on:** Phase 00
**Status:** planned
**Success criteria:**
1. `pytest tests/parity/test_iberia_868.py` passes (pixel-perfect for lookup PNGs; SSIM ≥ 0.98 for visual PNGs; deep-equal for JSONs)
2. Pipeline runs standalone (`python -m medieval_forge.services.pipeline --region iberia_868 --out /tmp/out`) without FastAPI
3. CI blocks merges on parity break (non-skippable from this phase forward)
**Plans:** 3/3 plans complete
Plans:
- [x] 01-01-PLAN.md — Wave 0 preflight + scaffold (verify P-1/Q10, source ES TopoJSON, commit fixtures + inputs, move territory data, scaffold pipeline package + RegionConfig)
- [x] 01-02-PLAN.md — Verbatim port of inicio/map_generator.py into 9 submodules (contracts/landmask/border/voronoi/cleanup/render/lookup/export + run_pipeline wiring)
- [x] 01-03-PLAN.md — Delete v1 generator stack + parity harness + CI flip to non-skippable

### Phase 02: Ingestion adapter
**Goal:** The existing v1 ingestion (Wikidata/OSM/Overpass/DEM/HydroSHEDS) produces inputs that the v3 pipeline accepts unchanged.
**Depends on:** Phase 01
**Status:** planned
**Success criteria:**
1. Phase 01 parity test stays green when input is "live ingestion" instead of fixture snapshot
2. `services/pipeline/contracts.py` defines `ProjectDataset` consumed by both fixture and live paths
3. Adapter functions wrap (don't rewrite) `ingest_wikidata`, `ingest_osm`, `overpass_client`, `ingest_terrain`
**Plans:** 4/4 plans complete
Plans:
- [x] 02-01-PLAN.md — Define ProjectDataset and atomically migrate all RegionConfig path-field callsites + GeoJSON branch + fail-fast assert (D-01..D-08)
- [x] 02-02-PLAN.md — services/pipeline/adapters/ subpackage: build_dataset_from_osm + split-by-ISO + terrain stub (D-05, D-07, D-13, D-15, D-16)
- [x] 02-03-PLAN.md — Live-ingestion parity test + snapshot + manual refresh script (D-09..D-12, ROADMAP-02#1, waiver-loop strategy)
- [x] 02-04-PLAN.md — /api/v3/projects/{id}/ingest SSE endpoint + v3 router registration (D-14)

### Phase 02.1: Resolve live-ingestion parity contract (was ROADMAP-02#1)
**Goal:** Replace the dead waiver-loop premise of Plan 02-03 with a coherent live-parity contract. Plan 02-03 assumed any divergence between live OSM and vendored fixture was transient drift; empirical evidence (`.planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md`) showed they are different upstream sources entirely (es-atlas@0.6.0 + IGE concelhos vs raw OSM admin_level=6/8), so live cardinality structurally exceeds vendored at every admin tier. ROADMAP-02#1 ("Phase 01 parity test stays green when input is live ingestion") is unreachable as written; this phase picks one of the rejected options (split golden, curate snapshot, in-pipeline cardinality match, or other) once the v3 vision on "what live should match" is sharper.
**Depends on:** Phase 02 (closes with SC-1 deferred), and ideally Phase 04 (parameter studio may inform whether a curate-to-vendored pass belongs in the pipeline)
**Status:** backlog
**Success criteria:**
1. Pick and document a live-parity contract option (re-open RESEARCH Open Q1 with current evidence)
2. `backend/tests/parity/test_iberia_868_live.py` xfail markers removed; suite reports `passed` (not `xpassed`/`xfailed`) under the new contract
3. ROADMAP-02#1 is either marked complete (success path) or formally retired with a follow-up requirement that supersedes it
**Plans:** TBD when phase opens

### Phase 03: Read-only canvas redesign
**Goal:** Single-canvas Figma/Mapbox workspace replaces the v1 stepper (697 lines), but read-only.
**Depends on:** Phase 02
**Status:** complete
**Success criteria:**
1. v3 user opens project generated by Phase 01 and pans/zooms/clicks territories
2. Inspector populates on click; layer toggles work
3. Old stepper invisible; no console errors
4. Runs against Phase 01 artifacts directly
**Plans:** 8/8 plans executed
Plans:
- [x] 03-01-PLAN.md — Wave 0 BLOCKER: pipeline canvas-sidecar emitter + _write_geojson_atomic lift + cfg.on_stage callback (closes RESEARCH Pitfalls 2 + 10)
- [x] 03-02-PLAN.md — Wave 1: backend v3 endpoints (POST /generate + GET /generate/stream + /status manifest + /artifacts FileResponse with allowlist)
- [x] 03-03-PLAN.md — Wave 1: frontend useRunStore + uiStore selectedTerritoryIds[] + useCanvasArtifacts URL swap
- [x] 03-04-PLAN.md — Wave 2: ProjectDetail rewrite + 6 workspace chrome components + SSE wiring
- [x] 03-05-PLAN.md — Wave 2: canvas surface (CanvasViewer strip + InteractionLayer multi-select + TerritoryLayer shift+click + HoverTooltip + MultiSelectInspector)
- [x] 03-06-PLAN.md — Wave 3: v1 frontend purge (D-10 + D-11 + D-13 frontend) + dangling-import grep gate
- [x] 03-07-PLAN.md — Wave 3: v1 backend purge (D-12 + D-13 backend incl. auth.py + credential_store.py + 3 ORM models) + main.py lifespan shrink
- [x] 03-08-PLAN.md — Wave 4: Playwright UAT for SC-1..SC-4 + final cross-surface grep + visual sign-off

### Phase 04: Parameter studio (live re-render)
**Goal:** The same canvas drives the pipeline. Sliders for σ, median passes, fragment threshold, blob-merge threshold; toggles for per-stage outputs; incremental re-render.
**Depends on:** Phase 03
**Status:** planned
**Success criteria:**
1. Explicit DAG with `version_token` per stage drawn BEFORE first slider (Karpathy: avoid v1's compound-undo gap)
2. Backend incremental endpoint per stage; in-memory cache of intermediate arrays
3. Move σ from 3.0 → 4.5 reformats territories visibly in <500ms without full re-run
4. Cancel restores prior state; Konva `clearCache()` after every geometric mutation
**Plans:** 7/7 plans complete
Plans:
- [x] 04-00-PLAN.md — Wave 0 stub bootstrap (14 test stub files; pytest/vitest/Playwright suite stays green)
- [x] 04-01-PLAN.md — Wave 1: cleanup.py split into 4 cacheable functions + cache.py + dag.py + 12-stage PIPELINE_STAGES sync (D-01/D-02/D-03/D-17/D-18)
- [x] 04-02-PLAN.md — Wave 2: api/v3/_run_state.py extract + render.py POST/GET/cancel + run_pipeline_incremental + stage raster endpoint + parity (D-04/D-13/D-14/D-17/D-18)
- [x] 04-03-PLAN.md — Wave 3: ParameterSidebar + 4 SliderCards + StageViewToggle + usePipelineParams + useRenderStream + WorkspaceToolbar Cancel (D-05..D-08, D-10/D-11, D-16)
- [x] 04-04-PLAN.md — Wave 3: useRunStore rendering state + useCanvasArtifacts re-key + CanvasViewer Konva.clearCache discipline + prior_token swap (D-13, CLAUDE.md rule)
- [x] 04-05-PLAN.md — Wave 3: BaronyLayer Konva Text labels (D-12 polish)
- [x] 04-06-PLAN.md — Wave 4: ProjectDetail integration + Playwright SC-3 + SC-4 + cross-surface gate + visual sign-off

### Phase 04.1: Parameter studio polish + cancel-race hardening
**Goal:** Close the six items deferred from Phase 04 verification (3 UAT polish gaps + 3 code-review warnings recorded in `.planning/phases/04-parameter-studio-live-re-render/04-VERIFICATION.md` and `04-REVIEW.md`). Make the parameter studio production-ready before Phase 05 reuses the canvas for multi-region generalization.
**Depends on:** Phase 04
**Status:** planned
**Success criteria:**
1. Canvas preserves zoom/pan across slider re-render — `CanvasViewer.tsx:206-208` no longer calls `fitToView()` when the projection reference changes mid-render (UAT gap #1, severity major)
2. Before/after preview affordance lets the user compare slider impact without re-running (UAT gap #2, severity minor)
3. In-app discoverability panel surfaces source-of-truth references for the historical 868 AD barony dataset (UAT gap #3, severity minor)
4. Cancel→POST 409 race (WR-01) treated as non-fatal — debounce re-queue replaces the `useRunStore.finish('error', 'RENDER_BUSY')` transition in `useParameterStudioDispatch.ts` and `ParameterSidebar.tsx`
5. `_RUN_QUEUES` and `_RUN_TASKS` evicted in `_render_producer` and `_generate_producer` `finally` blocks (WR-02) — late `GET /render/stream` subscribers no longer hang on a drained queue
6. Single canonical dispatch path (WR-03) — `ParameterSidebar.tsx` consumes `useParameterStudioDispatch` instead of inlining the latest-wins sequence; no duplicate logic
**Plans:** 5/5 plans complete
Plans:
- [x] 04.1-01-PLAN.md — Wave 1: Backend producer eviction (D-05 / WR-02) — _RUN_QUEUES + _RUN_TASKS evicted in render.py + generate.py finally blocks + pytest coverage
- [x] 04.1-02-PLAN.md — Wave 2: Frontend dispatch consolidation + bounded RENDER_BUSY retry (D-06 + D-04 / WR-03 + WR-01) — ParameterSidebar consumes useParameterStudioDispatch; 3-retry/1.5s window
- [x] 04.1-03-PLAN.md — Wave 3: CanvasViewer stable projection-bounds key + preview gesture (D-01 + D-02) — fitToView gated, hold-spacebar shows prior raster + Anterior badge
- [x] 04.1-04-PLAN.md — Wave 2: InspectorSidebar barony historical panel (D-03) — extends BaronyRender with centroid; adds source-coord, source-file label, PT-BR explainer
- [x] 04.1-05-PLAN.md — Wave 4: Regression + E2E gate — 3 new Playwright specs (SC-1/SC-2/SC-3) + parity + Phase 04 specs stay green

### Phase 05: Region generalization
**Goal:** Iberia is a config, not a hard-coded path. Other regions/periods supported.
**Depends on:** Phase 04
**Status:** planned
**Success criteria:**
1. `data/regions/iberia_868.yaml` externalizes the config currently in code
2. `france_1066.yaml` + `england_1216.yaml` ship as templates (geometry only — historical research deferred to v3.1)
3. France 1066 with toy synthetic dataset → ingest → generate → export produces 12 well-formed files (parity to Reconquista NOT required; file contract IS)
**Plans:** 15/15 plans complete
Plans:
- [x] 05-01-PLAN.md — Wave 1: region_loader.py (schema + load_region + autogen + cache + security guards) + PyYAML dep + 12 Wave-0 test scaffolds
- [x] 05-02-PLAN.md — Wave 2: scripts/migrate_iberia_to_yaml.py emits data/regions/iberia_868.yaml (idempotent) + loader roundtrip test
- [x] 05-03-PLAN.md — Wave 3: tests/parity/test_iberia_868_yaml.py — hard parity gate (D-14) proving YAML cfg byte-equal to legacy
- [x] 05-04-PLAN.md — Wave 4: Alembic region_key column + Project.region_key field + POST /api/v3/projects + generate.py/render.py swap to load_region
- [x] 05-05-PLAN.md — Wave 5: delete regions.py + territory_data.py + retire legacy test_iberia_868.py (D-13)
- [x] 05-06-PLAN.md — Wave 2: scripts/gen_toy_france.py + data/regions/france_1066.yaml + toy inputs + autogen loader test
- [x] 05-07-PLAN.md — Wave 3: GET /api/v3/regions endpoint + alphabetical order + has_dataset flag
- [x] 05-08-PLAN.md — Wave 5: NewProjectModal.tsx + useRegions hook + useCreateV3Project + ProjectList trigger swap (per 05-UI-SPEC)
- [x] 05-09-PLAN.md — Wave 2: data/regions/england_1216.yaml (YAML-only) + loader FileNotFoundError contract test
- [x] 05-10-PLAN.md — Wave 5: SC-3 backend E2E (10-file contract — terrain pair deferred) + Playwright UAT (France create+generate flow — code review only)
- [x] 05-11-PLAN.md — Wave 6 (gap closure): terrain.py module + terrain_lookup.png + terrain_types.json wired into _write_outputs_to_disk; EXPORT_FILE_CONTRACT 10→12; Iberia parity preserved
- [x] 05-12-PLAN.md — Wave 7 (gap closure): bash + PowerShell UAT runner scripts + checkpoint:human-verify for live France Playwright execution + visual sign-off
- [x] 05-13-PLAN.md — Wave 8 (cross-AI review): _autogen_territories dedupe (WR-01 fix: 80→40 condados) + tightened bound test + determinism regression guard
- [x] 05-14-PLAN.md — Wave 9 (cross-AI review): Iberia parity fixture replace() (WR-02 / Pitfall 9) + NewProjectModal a11y nits (htmlFor + finite Toast duration + drop dead defaultValue)
- [x] 05-15-PLAN.md — Wave 9 (cross-AI review): delete dead helpers (render.py _make_on_stage + test helper) + flatten no-op try/except + england YAML comment + test:uat:ci npm script

### Phase 06: Export contract + validation gate (merged)
**Goal:** Strict 12-file Unity export with manifest, schema validation, and a gate on minimum pixels per territory + color-collision check.
**Depends on:** Phase 05
**Status:** planned
**Success criteria:**
1. All JSON outputs schema-validated via pydantic
2. Export blocked on: territory <200px, lookup color collision, ocean leak, missing `original_idx`, `pixel_center` Y-axis check failure
3. Manifest matches Reconquista structure
4. Iberia + France + a deliberately-broken project all pass through `/api/v3/export`; broken is blocked with structured error list
**Plans:** 1/3 plans executed
Plans:
- [x] 06-01-PLAN.md — Wave 1: services/export/ subpackage + 6 pydantic schemas + validator stubs + schema unit tests (SC-1)
- [ ] 06-02-PLAN.md — Wave 2: 5 validator check function bodies + 5 unit test files (SC-2: COLOR_COLLISION, OCEAN_LEAK, TERRITORY_TOO_SMALL, MISSING_ORIGINAL_IDX, PIXEL_CENTER_OUT_OF_RANGE)
- [ ] 06-03-PLAN.md — Wave 3: api/v3/export.py + build_unity_zip refactor + D-04 atomic v1 delete + parity D-16 extension + 3 e2e gate tests (SC-3, SC-4)

### Phase 07: LLM research as opt-in metadata layer
**Goal:** Optional research dialog populates `name`, `kingdom_owner`, `historical_notes` on geometrically-fixed territories. Never mandatory.
**Depends on:** Phase 06
**Status:** planned
**Success criteria:**
1. Project without API key generates and exports successfully (zero LLM calls)
2. With research run, territories show historical names instead of `Condado_001`
3. `services/research_runner.py`, `services/llm/`, `services/research_cache.py`, `components/research/` are reused (moved into `v3/` namespace)

---

## Requirement coverage (v3)

| Requirement ID | Phase | Notes |
|----------------|-------|-------|
| V3-PHASE-00 | Phase 00 | This phase (covered by quick task 260507-g1v) |
| V3-PIPELINE-PARITY | Phase 01 | Pixel parity vs. Reconquista |
| V3-INGEST-ADAPTER | Phase 02 | v1 ingestion → v3 contract |
| V3-CANVAS-RO | Phase 03 | Read-only single-canvas |
| V3-CANVAS-PARAM | Phase 04 | Live parameter studio |
| V3-REGION-CONFIG | Phase 05 | Iberia → config |
| V3-EXPORT-GATE | Phase 06 | 12-file validation gate |
| V3-LLM-OPT-IN | Phase 07 | Sidecar metadata |

---

## Backlog (v3.1 — deferred, not discarded)

See `.planning/backlog.md`.
