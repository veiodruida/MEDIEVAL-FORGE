# Phase 03: Read-only canvas redesign - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the 697-line v1 stepper UI (`frontend/src/pages/ProjectDetail.tsx` plus
`components/pipeline/*` + `usePipelineStore`) with a single-canvas
Figma/Mapbox-style workspace that consumes the Phase 01 12-file Unity export
directly. Read-only: pan, zoom, click territories, populate inspector, toggle
layers, view legend. Wires a new `/api/v3/projects/{id}/generate` SSE endpoint
that invokes `run_pipeline(cfg)` from Phase 01 and serves the resulting
artifacts via a `StaticFiles` mount. Closes the Phase 02 D-15 deferral by
deleting the legacy v1 ingest endpoint, `ingest_wikidata.py`, and
`ingest_runner.py`.

Out of scope for Phase 03:
- Parameter sliders / live re-render (Phase 04 — DAG with `version_token`)
- Edit territory geometry (paint-brush, vertex drag — explicitly out of v3 per
  PROJECT.md "Out of Scope")
- Compound undo / `useUndoShortcut` (Phase 04 owns param-studio undo)
- LLM research dialog (Phase 07 — opt-in metadata sidecar; rewritten from
  scratch, not migrated)
- Schema validation gate on export (Phase 06)
- Region YAML loader / non-Iberia regions (Phase 05)
- Cancel of in-flight pipeline run (Phase 04 when re-run is frequent)
- Auth / remote hosting (backlog v3.1)
- DEM/HydroSHEDS terrain wire-up (Phase 06 or v3.1)

</domain>

<decisions>
## Implementation Decisions

### Workspace shell

- **D-01 (Shell style):** Mapbox-like full-bleed canvas. Top toolbar (thin
  bar) carries project name + status badge + "Generate Map" button + "Export
  ZIP" button + breadcrumb-back to `/projects`. Inspector docks to the right
  as a collapsible sidebar (~320px) with toggle button. `LayerTogglePanel`
  + `LegendCard` stack in the upper-left as floating overlays. `FitToView`
  + zoom controls float in another corner (planner picks). Maximum canvas
  area; chrome floats over the map.

- **D-02 (Pipeline trigger):** Single "Generate Map" button in the toolbar
  dispatches ingest + generate in sequence. Frontend tracks an internal run
  state machine: `idle → ingesting → generating → generated | error`. User
  doesn't decide ingest vs. generate — pipeline runs end-to-end. After first
  success the button label becomes "Re-generate".

- **D-03 (Progress feedback):** Toolbar status badge streams the SSE event
  text inline ("Ingesting OSM 30%", "Generating: voronoi", "Done"). Clicking
  the badge expands an inline log panel listing the 11 DAG stages
  (landmask → border → voronoi → cleanup → smooth → merge → hierarchy →
  render → lookup → metadata → export); each SSE event paints a checkmark
  next to its stage. No modal — canvas stays interactive (placeholder
  visible).

- **D-04 (Cancel):** No cancel in Phase 03. Iberia 868 pipeline runs in
  ~10s; cancel introduces per-stage `stop_event` plumbing that pays off only
  with frequent re-runs (Phase 04 territory). Karpathy: don't build for
  hypothetical.

### Empty / loading / error states

- **D-05 (Empty state — fresh project):** Canvas placeholder with an icon
  + text "Gerar mapa medieval para [país] [período]" + a centered CTA
  button "Generate Map". User understands the next action without docs.

- **D-06 (Ingesting state):** Canvas shows a grey country silhouette
  placeholder; toolbar status badge streams `/api/v3/.../ingest` SSE events
  (e.g., "Baixando municípios PT/ES…", "Clipping ISO codes", file counts).

- **D-07 (Generating state):** Canvas shows the same placeholder; inline
  expanded log lists the 11 pipeline stages and paints `✓` per SSE event.
  No partial render of intermediate artifacts (Phase 04 may add when
  incremental DAG matters).

- **D-08 (Error state):** Top-of-canvas red callout with the failed stage
  name + last log line + a copyable error message + "Retry" button. Status
  badge turns red. Toolbar back/Export remain functional. Existing
  `useResearchStream` / Phase 02 `_sse_generator` error pattern is the
  template.

### Canvas core reuse

- **D-09 (Reuse 5-layer Konva stack as-is):** `CanvasViewer.tsx` plus the
  five layers (`BackgroundLayer`, `TerritoryLayer`, `BaronyLayer`,
  `DecorationsLayer`, `InteractionLayer`), `ProjectionContext`,
  `lib/projection.ts`, `useZoomPan`, `useKeyboardShortcuts`,
  `useCanvasArtifacts`, `FitToViewButton`, `LayerTogglePanel`, `LegendCard`,
  `InspectorSidebar` are reused **verbatim**. Only their data hydration
  changes — they consume the new `/api/v3/projects/{id}/artifacts/*` URLs
  instead of v1 `/preview/*`. Tests under
  `frontend/src/components/canvas/__tests__/` carry forward unchanged
  (those that still apply to read-only behavior).

- **D-10 (Delete edit-only components + hooks):** Remove
  `EditToolbar`, `SplitTool`, `VertexHandlesLayer`,
  `SelectionFloatingToolbar`, `ValidationBadgesLayer`,
  `useRubberBandSelection`, `useEditKeyboardMap`, `useUndoShortcut`,
  `useBeforeUnloadGuard`, `services/validation.ts`,
  `services/persistence.ts`, `useValidationStore`, `useEditorStore`,
  `pages/TerritoryEditor.tsx` (and its route), `components/research/
  AssignmentEditor.tsx`, plus their tests. ~1500 LOC + tests delete.
  D-V3-04 — dead code is regression risk.

### V1 deletion scope (closes D-V3-04 + Phase 02 D-15)

- **D-11 (V1 stepper UI purge):** Delete `frontend/src/components/pipeline/`
  (Stepper, StepCard, ProviderEffortPicker, TerrainDataSection, plus tests),
  `frontend/src/components/ingest/BaronyGranularitySlider.tsx`,
  `frontend/src/stores/usePipelineStore.ts` (+ tests),
  `frontend/src/api/useTerrainStepStream.ts`, `frontend/src/api/edit.ts`.
  Update `App.tsx` so `/projects/:id` routes to the new `ProjectDetail.tsx`
  rewrite.

- **D-12 (V1 backend purge):** Delete `backend/medieval_forge/api/ingest.py`
  (legacy v1 SSE endpoint at `/api/projects/{id}/ingest`),
  `backend/medieval_forge/services/ingest_runner.py`,
  `backend/medieval_forge/services/ingest_wikidata.py`. Remove the v1 ingest
  router registration from `main.py`. Phase 02 D-14 + D-15 explicitly
  deferred this to Phase 03; ingest_runner had `_write_geojson_atomic` —
  if Phase 02 v3 SSE adapter still imports it, lift the helper into
  `services/paths.py` first (planning task). v1 `/api/generate` already
  deleted in Phase 01.

- **D-13 (V1 LLM purge):** Delete `frontend/src/components/research/`,
  `frontend/src/components/codex/`, `frontend/src/stores/useResearchStore.ts`,
  `frontend/src/hooks/useResearchStream.ts`, `frontend/src/hooks/
  useCodexStream.ts`, `frontend/src/api/research.ts`, `frontend/src/api/
  codex.ts`. Backend: delete `services/research_runner.py`,
  `services/research_cache.py`, `services/llm/`, `api/research.py`,
  `api/codex.py`, `api/llm.py`. Phase 07 rewrites from scratch — ROADMAP
  Phase 07's "moved into v3/" wording is vision, not contract; D-V3-04
  wins. Audit `api/auth.py` + `services/credential_store.py`: they exist
  to hold LLM provider keys; if no surviving consumer remains after the
  purge, delete them too. Open question for the planner.

### Inspector + interaction

- **D-14 (Inspector content):** Inspector renders the full metadata of the
  selected condado from `territory_metadata.json`: id, name, kingdom name
  (resolved via `metadata.kingdoms[id]`), duchy name (via
  `metadata.duchies[id].name`), `capital_name` (optional — when absent
  show "No capital assigned" sentinel per existing
  `InspectorSidebar` D-06.3 behavior), `pixel_count`, lon/lat, baronies
  list (each row: name + `pixel_count`), neighbors list (each row: id +
  resolved name). Single card with implicit sections; everything visible
  without expand/collapse.

- **D-15 (Hover):** Mouse over a condado paints a 1px light-grey outline
  + tooltip showing the condado name. Click promotes the territory to the
  gold `InteractionLayer` outline (existing). Karpathy: minimum useful
  feedback.

- **D-16 (Click on water/ocean):** Clicking outside any territory polygon
  clears the selection. Inspector returns to the placeholder "Clique num
  território para ver detalhes". Figma/Mapbox standard.

- **D-17 (Multi-select via shift+click):** `Shift+click` adds or removes
  a condado from the selection set. The inspector shows an aggregate
  view: count, listed names, summed `pixel_count`, union of duchies +
  kingdoms, no per-territory metadata in the multi-select view (single
  selection still shows full metadata per D-14). Click without shift =
  single selection (replaces). Gold outline applies to all selected
  territories. **Note:** This adds capability vs. the recommended
  "no multi-select" — kept because it's read-only inspection (within
  scope), the existing `InteractionLayer` already supports multi-outline
  rendering, and `useRubberBandSelection` is being deleted (D-10) so
  shift+click is the only multi-select mechanism.

### Artifact serving

- **D-18 (StaticFiles mount):** FastAPI mounts
  `/api/v3/projects/{id}/artifacts/*` pointing at the per-project output
  directory `projects/<uuid>/output/`. Predictable URLs (e.g.,
  `/api/v3/projects/abc/artifacts/territory_metadata.json`,
  `.../lookup_condado.png`). Native HTTP cache, no file-reading code
  per artifact, no schema validation at the serve boundary (Phase 06
  owns export-gate validation).

- **D-19 (Cache-busting):** Frontend appends `?v={project.updated_at}` to
  every artifact URL. Phase 01's `run_pipeline` updates
  `project.updated_at` after writing the 12 files; the existing
  `CanvasViewer.cacheVersion` prop already implements this pattern from v1.

- **D-20 (No auth):** v3 stays local-only. No `Depends(...)` middleware,
  no Bearer/cookie. Reaffirms PROJECT.md "local web tool"; matches
  Phase 01/02 endpoint posture. `api/auth.py`'s purpose is LLM credential
  storage (handled by D-13's audit), not endpoint protection.

- **D-21 (Status manifest):** New `GET /api/v3/projects/{id}/status`
  returns `{ status, has_artifacts: { lookup_barony, lookup_condado,
  territory_metadata, ... }, last_generated_at }`. Frontend reads this
  on mount to decide which UI state to render (empty / generating /
  ready / error). Reuses Phase 06 manifest shape where possible — the
  planner consults `CLAUDE.md` §"v3 Pipeline Contract" for the
  authoritative 12-file list.

### Backend pipeline endpoint

- **D-22 (POST + GET-SSE pair):** `POST /api/v3/projects/{id}/generate`
  starts the run (returns 202 Accepted with a run_id). `GET
  /api/v3/projects/{id}/generate/stream` returns the SSE event stream
  for the active run (one event per pipeline stage entry/exit + error +
  done). Mirrors the Phase 02 D-14 pattern (`asyncio.Queue` producer +
  `StreamingResponse` consumer + terminal `None` sentinel + per-(project,
  step) `stop_event` slot reserved but unused per D-04). Endpoint
  invokes `run_pipeline(cfg)` from `medieval_forge.services.pipeline`;
  on success updates `project.status = generated` and
  `project.updated_at`; on exception updates `project.status =
  error_generating`.

### Routing

- **D-23 (Route layout):** Keep `/projects` (ProjectList) +
  `/projects/:id` (new ProjectDetail workspace). `ProjectList.tsx` (64
  lines) and `ProjectNew.tsx` (254 lines) stay as-is — neither depends on
  the stepper. Toolbar back-button uses `<Link to="/projects">` rather
  than `navigate(-1)`.

### Claude's Discretion

- Tailwind v4 vs Radix Themes split for the workspace shell (toolbar,
  inspector chrome, status badge): both available; planner picks based
  on existing component patterns.
- Tooltip implementation for D-15: Radix `Tooltip` vs custom Konva
  `Text` overlay (Radix can't sit on a Konva `Stage` without portal
  dance). Probably a `<div>` overlay positioned via `Stage.getPointerPosition`.
- Status badge animation/format (pulse, percent bar, text-only).
- SSE event envelope shape — mirror Phase 02 v3 ingest verbatim or
  define a stricter `{stage, event_type, message, progress?}` envelope.
- Where the run state lives (new `useRunStore` Zustand store vs derived
  from TanStack Query polling `/status` + the SSE subscription).
- Empty-state visual: Lucide vs Radix vs custom SVG icon.
- How much of `useCanvasArtifacts` needs to change to swap `/preview/*`
  → `/artifacts/*` (path replacement only vs. broader refactor).
- Whether `api/auth.py` + `services/credential_store.py` survive the
  D-13 purge (depends on who else imports them).
- Run-id generation strategy for D-22 (uuid4 vs project_id+timestamp).

### Folded Todos

None — `gsd-tools todo match-phase 03` returned `todo_count=0`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & success criteria
- `.planning/ROADMAP.md` §"Phase 03: Read-only canvas redesign" — four
  success criteria are the acceptance gate; "no console errors" (SC-3) is
  a hard constraint
- `.planning/PROJECT.md` §"Out of Scope (v3)" — no edit, no compound undo,
  no Kuwahara filter; PT-BR only
- `.planning/PROJECT.md` §"Key Decisions" — D-V3-04 (delete dead v1 code)
  drives the deletion scope; D-V3-05 (RegionConfig is the single mutable
  input) constrains the canvas data path

### Pipeline contract (consumer side)
- `CLAUDE.md` §"v3 Pipeline Contract" — authoritative 12-file output list
  (file 7 `territory_metadata.json` is the inspector's source; files 1–4
  drive `BackgroundLayer` + `TerritoryLayer`); seven non-negotiable rules
  still apply (canvas must NEAREST-upscale lookup PNGs, never BICUBIC)
- `CLAUDE.md` §"What v3 explicitly is NOT" — rejected designs: no
  stepper UI (this is the explicit anti-target), no compound undo
- `CLAUDE.md` §"Architecture" — Phase 03 hydrates from the same DAG
  outputs Phase 04's parameter studio will re-render from
- `backend/medieval_forge/services/pipeline/__init__.py` —
  `run_pipeline(cfg)` is the single entry point the new `/generate`
  endpoint invokes
- `backend/medieval_forge/services/pipeline/contracts.py` — `RegionConfig`
  + `ProjectDataset` shapes; the new endpoint must build `cfg` exactly as
  Phase 01's `iberia_config()` does for parity

### Phase carry-forward
- `.planning/phases/01-pipeline-parity-port-harness-together/01-CONTEXT.md`
  — D-09 (deployed wins → canvas displays whatever the pipeline emits;
  no client-side reinterpretation), D-13/D-14 (territory data on cfg)
- `.planning/phases/02-ingestion-adapter/02-CONTEXT.md` — D-14 (v3 SSE
  pattern is the template for `/generate` SSE), D-15 (Wikidata drop +
  this phase deletes), D-13 (terrain stub stays — canvas reads vendored
  `mountain_river_data.json` as-is)
- `.planning/phases/02-ingestion-adapter/02-VERIFICATION.md` — Phase 02
  acceptance state; Phase 03 must keep parity 10/10 green
- `backend/medieval_forge/api/v3/ingest.py` — concrete Phase 02 SSE
  implementation; `/generate` endpoint copies the
  `_sse_generator` shape

### Frontend reuse
- `frontend/src/components/canvas/CanvasViewer.tsx` — 5-layer Konva
  read-only viewer designed for read-only by v1 phase 2; reused as-is
- `frontend/src/components/canvas/InspectorSidebar.tsx` — existing
  inspector card; D-14 content keeps its shape (with capital_name
  sentinel D-06.3 already implemented)
- `frontend/src/components/canvas/{LayerTogglePanel,LegendCard,
  FitToViewButton,BackgroundLayer,TerritoryLayer,BaronyLayer,
  DecorationsLayer,InteractionLayer}.tsx` — full reuse
- `frontend/src/hooks/useCanvasArtifacts.ts` — adapt to read from
  `/api/v3/projects/{id}/artifacts/*` instead of `/preview/*`; URL
  rewrite is the only behavioral change
- `frontend/src/hooks/useZoomPan.ts` + `useKeyboardShortcuts.ts` —
  read-only-friendly subsets reused
- `frontend/src/lib/projection.ts` — geo→canvas coordinate math; reused
- `frontend/src/context/ProjectionContext.tsx` — projection provider;
  reused

### Frontend deletion (D-10..D-13)
- `frontend/src/pages/ProjectDetail.tsx` (697 lines) — rewritten
- `frontend/src/pages/TerritoryEditor.tsx` (341 lines) — deleted
- `frontend/src/components/canvas/{EditToolbar,SplitTool,
  VertexHandlesLayer,SelectionFloatingToolbar,ValidationBadgesLayer}.tsx`
  — deleted with tests
- `frontend/src/components/pipeline/*` — entire subdir deleted
- `frontend/src/components/{research,codex}/*` — entire subdirs deleted
- `frontend/src/components/ingest/BaronyGranularitySlider.tsx` — deleted
- `frontend/src/stores/{usePipelineStore,useResearchStore,useEditorStore,
  useValidationStore}.ts` — deleted
- `frontend/src/hooks/{useResearchStream,useCodexStream,useUndoShortcut,
  useBeforeUnloadGuard,useEditKeyboardMap,useRubberBandSelection}.ts` —
  deleted
- `frontend/src/api/{research,codex,edit,useTerrainStepStream}.ts` —
  deleted
- `frontend/src/services/{validation,persistence}.ts` — deleted

### Backend deletion (D-12..D-13)
- `backend/medieval_forge/api/{ingest,research,codex,llm}.py` — deleted
- `backend/medieval_forge/services/{ingest_runner,ingest_wikidata,
  research_runner,research_cache}.py` — deleted; LLM subdir
  `services/llm/` deleted
- `backend/medieval_forge/api/auth.py` + `services/credential_store.py`
  — auditar; deletar se sem consumer (D-13 follow-up)

### v1-archive lessons
- `.planning/v1-archive/STATE.md` — read for the 30+ pitfalls; relevant
  to Phase 03: `Konva.clearCache()` after every geometric mutation, never
  upscale-interpolate lookup PNGs at the canvas (read directly via
  `<img>` src + `crisp-edges`), Konva ResizeObserver callback-ref pattern
  (already in `CanvasViewer` GAP-05 fix)
- `.planning/v1-archive/PROJECT.md` — context for why the stepper UI is
  being removed (697-line monolith from v1 phase 5/6 that conflated
  ingestion + research + canvas state)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`CanvasViewer.tsx`** — 5-layer Konva stack designed read-only;
  consumes `useCanvasArtifacts(projectId, cacheVersion)` and passes data
  to layers. Phase 03 adapts the URL prefix and that's it.
- **`useCanvasArtifacts`** — fetches `territory_metadata.json` +
  `territories.geojson` + `baronies.geojson` via `useQueries`. Phase 03
  switches the base path from v1 `/preview/` to `/api/v3/projects/{id}/
  artifacts/`; data shape unchanged (Phase 01 already emits matching
  schemas).
- **`InspectorSidebar`** — already renders condado metadata with
  `capital_name` sentinel + `neighbors` hoist; D-14's "full metadata"
  decision matches its current shape. Multi-select aggregate view (D-17)
  is a NEW mode the planner adds.
- **`LayerTogglePanel` + `LegendCard` + `FitToViewButton`** — three
  free-floating overlays already; positioning in CSS only.
- **`api/v3/ingest.py` SSE pattern** — `_sse_generator` + `asyncio.Queue`
  + `StreamingResponse` + per-(project_id, step) `stop_event` slot;
  template for `/generate` endpoint.
- **`services/pipeline/__init__.run_pipeline`** — single sync invocation
  point; the new `/generate` endpoint wraps it in a thread / asyncio.
  to_thread call so SSE can stream progress while the pipeline runs.
- **`services/paths.py`** (`project_dir`, `ensure_project_dirs`) — used
  by Phase 02 ingest; reused by `/generate` to locate the output dir.
- **`models.Project`** — has `status`, `updated_at` columns; Phase 03
  flips status to `generated` + bumps `updated_at` after `run_pipeline`
  returns. D-19 cache-bust depends on `updated_at` being touched.

### Established Patterns

- Phase 02 atomic SSE: `asyncio.Queue.put(None)` sentinel terminates the
  stream; per-step `stop_event` reserved (Phase 03 D-04 keeps the slot
  for Phase 04 to wire cancel later).
- Per-project filesystem at `projects/<uuid>/{inputs,output}/`; Phase 03
  reads from `output/` via the StaticFiles mount.
- Atomic commits per task: `feat(03-NN): ...`, `chore(03-NN): ...`,
  `test(03-NN): ...`. Deletion commits use `chore(03-NN): delete v1 ...`
- TanStack Query for project + status; Zustand for UI state. Existing
  `uiStore.ts` already exists — Phase 03 may reuse for the run state
  machine (Claude's Discretion).
- pytest markers: `unit` + `parity` + `integration`. Phase 01 parity
  test stays green (Phase 03 SC-4 demands this). Frontend uses Vitest +
  Playwright; new Playwright UAT for the canvas workspace ships in this
  phase per CLAUDE.md "Conventions".
- Frontend test convention: tests sit next to components in `__tests__/`.
  Existing `CanvasViewer.test.tsx`, `CanvasViewer.hydrate.test.tsx`,
  `CanvasViewer.resize.test.tsx`, `InspectorSidebar.test.tsx` carry over
  with URL-prefix updates only.

### Integration Points

- New endpoints (3): POST `/api/v3/projects/{id}/generate`, GET
  `/api/v3/projects/{id}/generate/stream`, GET
  `/api/v3/projects/{id}/status`. Plus StaticFiles mount
  `/api/v3/projects/{id}/artifacts/*`. All registered under the existing
  v3 router added in Phase 02.
- `main.py` registration: add three v3 endpoints + StaticFiles mount;
  remove the v1 ingest router (D-12).
- New `ProjectDetail.tsx` workspace replaces the 697-line stepper.
  Routes through `App.tsx` `<Route path="/projects/:id">` unchanged.
- `useCanvasArtifacts` URL switch is the only frontend hidration change;
  the rest of the canvas component graph receives the same data shapes
  Phase 01 emits.

</code_context>

<specifics>
## Specific Ideas

- **"Single-canvas Figma/Mapbox workspace"** — ROADMAP wording. D-01
  Mapbox-like full-bleed shell is the explicit pick.
- **"Old stepper invisible; no console errors"** — SC-3. Means: nothing
  in the new ProjectDetail references deleted modules. Pre-merge
  checklist: `grep -r "components/pipeline\|usePipelineStore\|
  useResearchStore\|useEditorStore" frontend/src/` returns zero.
- **"Runs against Phase 01 artifacts directly"** — SC-4. Canvas reads
  the same files Phase 01's parity test asserts on (after refresh) — no
  client-side reinterpretation, no re-projection of geometries that the
  pipeline already projected.
- **"Karpathy: don't build for hypothetical use"** — drives D-04 (no
  cancel), D-07 (no partial render), D-10 (delete edit-only), D-13
  (delete v1 LLM). Multi-select aggregate view (D-17) is the documented
  exception: read-only inspection capability that's cheap because
  `InteractionLayer` already supports it and `useRubberBandSelection`
  delete leaves shift+click as the only path.
- **"Deployed wins"** — Phase 01 D-09 carries: canvas displays exactly
  what the pipeline emitted; no smoothing, no re-coloring, no
  server-side normalization at the serving layer (D-18 StaticFiles).

</specifics>

<deferred>
## Deferred Ideas

- **Cancel of in-flight runs** — Phase 04 when re-runs are frequent
  (sliders fire many runs per minute). Per-step `stop_event` slot
  reserved by D-04.
- **Partial render of intermediate stages** — Phase 04 incremental DAG
  re-render after a slider change.
- **Param studio sliders + live re-render** — Phase 04 owns this.
- **Compound undo for slider changes** — Phase 04, with `zundo`
  `temporal` middleware (per CLAUDE.md "What v3 is NOT" — no
  hand-rolled compound undo).
- **DEM/HydroSHEDS terrain wire-up** — Phase 02 D-13 stub stays;
  Phase 06 or v3.1 owns the live terrain pipeline.
- **Region YAML loader** — Phase 05.
- **Schema validation on artifact serve** — Phase 06 export-gate.
- **LLM research dialog rewrite** — Phase 07. Phase 03 deletes v1
  LLM stack outright (D-13).
- **Edit territory geometry / paint-brush mountains** — out of v3 per
  PROJECT.md.
- **Auth + remote hosting** — backlog v3.1 (no roadmap entry yet).
- **Multi-language UI** — out of v3 per PROJECT.md.
- **Manifest dedicated endpoint** — Phase 06 export gate refines
  `/status` into a strict manifest; Phase 03 ships the simpler
  has_artifacts response.
- **Map switcher / multi-project sidebar** — D-23 keeps `/projects`
  + `/projects/:id` separation; "switch project from inside workspace"
  is a v3.1 polish.
- **Visual refresh of `ProjectList` and `ProjectNew`** — D-23 keeps
  them as-is; cohesive theming is a v3.1 polish.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 03` returned zero matches at
gathering time.

</deferred>

---

*Phase: 03-read-only-canvas-redesign*
*Context gathered: 2026-05-09*
