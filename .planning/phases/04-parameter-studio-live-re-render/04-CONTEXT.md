# Phase 04: Parameter studio (live re-render) - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn the Phase 03 read-only canvas into a parameter studio. User drags
sliders for the four cleanup/smoothing knobs documented in `RegionConfig`
(`smooth_sigma`, `median_passes`, `fragment_min_px`, `blob_merge_px`); the
pipeline re-renders incrementally via an explicit DAG with `version_token`
per stage and an in-memory cache of intermediate arrays; the canvas swaps
to the new render in <500 ms for a σ change without full re-run; cancel
mid-render snaps the canvas back to the prior cached state and re-syncs
the slider value.

Deliverables:
- Backend: split `cleanup_and_smooth` into 4 cacheable stages (median /
  fragment / smooth / merge); each pipeline stage declares its `cfg`
  field reads + receives upstream `version_token`s and returns a token of
  its own; an in-memory dict keyed by `(project_id, stage_name, token)`
  holds latest + prior arrays per stage per project; new
  `POST /api/v3/projects/{id}/render` endpoint accepts cfg overrides,
  diffs against the project's current cfg, identifies stages whose token
  changes, recomputes only those stages, streams progress via the same
  `_RUN_QUEUES` + SSE pair pattern Phase 03 D-22 established.
- Frontend: new collapsible left sidebar (`~320 px`, mirrors
  `InspectorSidebar`) holds 4 sliders + 5 stage-view radio toggles + a
  per-slider reset button. Slider drag debounces 250 ms, latest-wins
  fires `POST /render`; in-flight stream is closed before the new POST.
  `WorkspaceToolbar` status badge becomes a clickable "Cancel" button
  while `state ∈ { ingesting, generating }`. `Konva.clearCache()` runs
  on every layer after each canvas hydration that swaps a different
  `version_token`.
- Stage-view radios let the user inspect intermediate canvas state
  (landmask / voronoi-raw / cleanup / smooth / render-final) — pipeline
  always runs full; the toggle only re-points the canvas hydrator at a
  different cached array. No bypass of stages.

Out of scope for Phase 04:
- Compound cross-stage undo via `zundo` `temporal` (deferred per
  `PROJECT.md` "Out of Scope" — CLAUDE.md fixes zundo as the contract
  *if* compound undo lands; Phase 04 does not introduce undo history).
- Region YAML loader (Phase 05)
- Schema validation gate on incremental renders (Phase 06)
- Disk-backed cache survival across server restarts (revisit Phase 06+
  if needed)
- Sliders for `island_min_px`, `mountain_threshold`, `mountain_noise`,
  `coast_inner_width`, etc. — only the four ROADMAP-named sliders ship
- LLM-driven parameter recommendations (Phase 07)
- Persistence of per-project slider values across sessions
  (Claude's Discretion — open below)
- Kuwahara filter alternative (out per `PROJECT.md`)

</domain>

<decisions>
## Implementation Decisions

### DAG + cache topology

- **D-01 (cleanup split — 4 stages):** Refactor
  `services/pipeline/cleanup.py:cleanup_and_smooth` into 4 separately
  cacheable functions matching the markers `__init__.py` already emits:
  `apply_median(raw, cfg) → med`, `remove_fragments(med, cfg) → frag`,
  `smooth_per_territory(frag, cfg) → sm`, `merge_small_blobs(sm, cfg) → final`.
  Each takes `(input_array, cfg)` and returns `np.ndarray`. The 11-stage
  list expands to 14 cacheable units (landmask, border, voronoi,
  median, fragment, smooth, merge, hierarchy, render, lookup, metadata,
  export, plus mountains + rivers if they need re-render — planner
  decides). Phase 01 D-02 explicitly deferred Stage abstraction here;
  this is the moment.

- **D-02 (version_token derivation):** Each stage declares
  `reads: frozenset[str]` of `cfg` field names it consumes.
  `version_token = sha256(stage_name + sorted((field, cfg[field]) for
  field in reads) + sorted(upstream_tokens))[:16]`. Hashing only the
  declared reads guarantees that a slider on `smooth_sigma` does not
  invalidate `median`'s token (median doesn't read `smooth_sigma`). The
  upstream tokens fold transitively so any earlier-stage change cascades.
  Stage `reads` declarations live next to the stage function (single
  source of truth).

- **D-03 (cache structure + lifetime):** `_STAGE_CACHE: dict[str, dict[str,
  StageEntry]]` where outer key is `project_id` and inner key is
  `stage_name`. `StageEntry` carries `{token: str, array: np.ndarray,
  prior_token: str | None, prior_array: np.ndarray | None}`. Two
  versions per stage per project, no more. Cleared on a fresh
  `POST /generate` (full run); kept across `POST /render` calls. RAM
  budget: ~80 MB per project for arrays at 1920×1080 int16 + their
  priors (numbers in CONTEXT for visibility — planner tunes if measured
  pressure differs). No disk persistence in Phase 04. No LRU policy in
  Phase 04 (single-user local tool — process death clears everything).

- **D-04 (incremental endpoint):** New `POST /api/v3/projects/{id}/render`
  + `GET /api/v3/projects/{id}/render/stream` SSE pair. Body:
  `{ cfg_overrides: { smooth_sigma?: float, median_passes?: int,
  fragment_min_px?: int, blob_merge_px?: int, stage_view?: str } }`.
  Server: builds the same `iberia_config()` cfg, applies overrides,
  walks the DAG computing each stage's new token, executes only stages
  whose token differs from the current cached token, streams
  `stage_start` / `stage_done` events for the affected stages only via
  the existing `_make_on_stage` bridge. Reuses `_RUN_QUEUES` /
  `_RUN_TASKS` from Phase 03's `api/v3/generate.py`. Single-flight per
  project: 409 if a `/render` or `/generate` is already alive.

### Slider UX

- **D-05 (slider set):** Exactly the four ROADMAP-named knobs.
  Bounds + types (planner confirms via inicio/JORNADA notes):
  - `smooth_sigma`: float, `[3.0, 4.5]` clamped (CLAUDE.md rule #2),
    step 0.1, default `3.0`
  - `median_passes`: int, `[1, 12]`, step 1, default `8`
  - `fragment_min_px`: int, `[0, 2000]`, step 50, default `600`
  - `blob_merge_px`: int, `[0, 500]`, step 25, default `200`
  Other `RegionConfig` cleanup fields (`island_min_px`,
  `mountain_threshold`, `mountain_noise`, `coast_inner_width`) stay
  cfg-only — not exposed as sliders. Karpathy: don't build for
  hypothetical use; add later when a Game Designer asks.

- **D-06 (panel slot):** New collapsible left sidebar `~320 px`,
  mirroring the existing right-side `InspectorSidebar`. Toggle button
  in the `WorkspaceToolbar`. Reuses the Tailwind v4 + Radix Themes
  patterns from Phase 03 D-01. Sliders stack vertically (4 cards),
  each card: title + range bar + numeric input + "↻ reset" button +
  default-tick mark. Stage-view radio group (D-10) sits at the top of
  the same panel.

- **D-07 (re-render trigger):** Slider drag fires onChange events
  rate-limited by a 250 ms `useDebouncedCallback`. On debounce expiry,
  if any slider value differs from the last-rendered cfg, the frontend
  closes the active SSE EventSource (if any) and POSTs `/render` with
  the diff. Latest-wins: a new debounce while a render is in flight
  cancels the in-flight render (D-13) and starts a new one. Target SC-3
  budget: ≤250 ms debounce + ≤200 ms compute (σ-only path) = ≤450 ms,
  comfortably under 500 ms.

- **D-08 (slider component):** Each slider card carries a Radix
  `Slider.Root` + adjacent numeric input (HTML `type="number"`) +
  default-tick mark + reset button. Numeric input commits on blur or
  Enter; out-of-bounds values clamp + flash red briefly. Reset button
  reverts that single slider to its `RegionConfig` default and
  immediately fires the standard re-render path.

### Stage-view toggles

- **D-09 (semantic — visualization only):** Stage view toggles do NOT
  bypass any pipeline stage. The pipeline always runs to completion; the
  toggle only changes which cached array the canvas hydrators read. A
  bypass would risk producing arrays that violate downstream contracts
  (e.g., hierarchy assumes cleanup ran). Visualization-only is
  debug-friendly and never breaks the contract.

- **D-10 (toggle set — 5 views):** Radio group: `landmask` (boolean
  raster from `landmask.py`), `voronoi-raw` (pre-cleanup `result` from
  `rasterize_baronies`), `cleanup` (post-`merge_small_blobs` final
  cleanup result), `smooth` (post-`smooth_per_territory`,
  pre-`merge_small_blobs`), `render-final` (the painted
  `visual_condado.png` / `visual_barony.png` — default). The remaining
  cacheable units (border / hierarchy / lookup / metadata / export) do
  not produce a meaningful canvas overlay diff; planner can revisit if
  evidence emerges.

- **D-11 (toggle slot):** Top of the left slider sidebar (D-06). Radio
  group with 5 options. A planner-side spike confirms whether
  `useCanvasArtifacts` can re-key the queries on `(stage_view, token)`
  to re-fetch the appropriate sidecar/array, or whether a new endpoint
  is needed for intermediate-stage rasters (likely needed: lookup PNGs
  only exist for the final `render` — earlier stages need a serializer).
  Open Q for the planner.

- **D-12 (Phase 04 polish — barony name labels):** When the
  `LayerTogglePanel`'s "Baronies" toggle is on, render the barony name
  centered on each barony via a Konva `Text` node (or DOM overlay,
  planner picks). Reuses `BaronyLayer` + `DecorationsLayer`; positions
  via barony centroid from `cfg.condados[i].baronies[j]`. Small task,
  one plan, lives inside Phase 04 because the parameter studio
  re-renders barony tiers when `smooth` / `merge` change, so labels
  update naturally on each re-hydrate. **Side note from user during
  discussion** — captured here so it isn't lost.

### Cancel + undo

- **D-13 (cancel = O(1) cache swap):** "Restore prior state" means: on
  cancel, the backend re-points the canvas at each affected stage's
  `prior_array` (D-03) and emits a `stage_cancel` SSE event carrying
  the reverted prior token per stage. Frontend snaps `useCanvasArtifacts`
  to the prior token, runs `Konva.clearCache()` per layer, and resets
  each affected slider to the cfg value that produced the prior token
  (server includes the prior cfg fragment in the cancel event). No
  re-run. Latency target: <50 ms end-to-end (no compute).

- **D-14 (cancel mechanic):** Cooperative `cfg.stop_event:
  threading.Event | None`. Each cleanup-stage function checks
  `if cfg.stop_event and cfg.stop_event.is_set(): raise StageCancelled`
  at its top. `_make_on_stage` already holds the `(project, step)` slot
  Phase 03 D-04 reserved; a new `POST /render/cancel` endpoint (or
  `DELETE /render`) sets the stop_event for the active task. Worst-case
  cancel latency = duration of the currently-running stage (~50–300 ms
  typical, ~2 s for full `render`). Hard `asyncio.Task.cancel()` on the
  CPU-bound thread is meaningless — the thread cannot be interrupted
  mid-numpy/scipy call.

- **D-15 (undo composto deferido):** `zundo` `temporal` middleware does
  NOT land in Phase 04. PROJECT.md Out of Scope explicitly defers
  compound cross-stage undo from v1 Phase 4. CLAUDE.md fixes zundo as
  the contract *if* undo is added — that contract holds for whichever
  later phase introduces it. Phase 04 ships only:
  (a) cancel via D-13/D-14, (b) per-slider "↻ reset" button in
  D-08 reverts a single slider to its default + dispatches a re-render.
  No history, no Cmd+Z, no cross-slider undo.

- **D-16 (cancel UI):** During `useRunStore.state ∈ { generating,
  rendering }` the WorkspaceToolbar status badge re-purposes itself
  into a clickable "Cancel" button (red). On click it `POST`s
  `/render/cancel` (or `DELETE /render`, planner picks). When state
  flips back to `idle | generated` the badge restores to status text.
  Reuses Phase 03 D-03 status-badge shell; no new chrome component.

### Determinism + parity

- **D-17 (parity stays green at default cfg):** When all 4 sliders sit
  at their `RegionConfig` defaults, `tests/parity/test_iberia_868.py`
  must still produce byte-equal lookup PNGs / SSIM ≥ 0.98 visuals. The
  DAG split (D-01) is a refactor, not an algorithmic change — each
  split function performs the same numpy operations the merged
  `cleanup_and_smooth` performs today. CI parity job remains
  non-skippable. A dedicated regression test in `tests/parity/` reruns
  the pipeline with sliders explicitly defaulted via the new endpoint
  to prove the incremental path matches the full path bit-for-bit.

- **D-18 (slider mutates a per-render copy of cfg):** `POST /render`
  builds `cfg = iberia_config(); cfg.dataset = ...; cfg.<override>`
  for each call — the project's persisted cfg is not mutated until a
  full `POST /generate` runs (or until D-19 is decided). This keeps
  `cfg` the single mutable input (D-V3-05) without the persisted
  project state drifting on every slider drag.

### Folded Todos

None — `gsd-tools todo match-phase 04` returned `todo_count=0`.

### Claude's Discretion

- **Slider value persistence across sessions.** Per-project DB column
  vs. localStorage vs. ephemeral (lost on refresh). Phase 04 default
  inclination: ephemeral — refresh resets sliders to `RegionConfig`
  defaults. Planner decides if Game Designer feedback during Phase 04
  UAT pushes back.
- **Cache eviction policy beyond 2 versions.** D-03 fixes latest+prior;
  if memory measurement shows pressure (e.g., concurrent project tabs),
  planner may add an LRU layer or evict on idle.
- **Stage-view → endpoint shape for non-final rasters.** `landmask`,
  `voronoi-raw`, `cleanup`, `smooth` arrays are int16 / bool — they
  need a serializer (PNG colormap? raw npy?) to reach the canvas. New
  endpoint `GET /v3/projects/{id}/stage/{name}.png` or expand
  `/artifacts/*` semantics. Planner picks.
- **`POST /render/cancel` vs `DELETE /render`.** Both fit; pick the one
  that reads cleanly with the `_RUN_TASKS` map.
- **Stage-view ↔ LayerTogglePanel interaction.** When stage_view ≠
  `render-final`, do BaronyLayer / DecorationsLayer / RiversOverlay
  still paint? Probably hidden (intermediate views are pre-render).
  Planner specifies.
- **Failure mode mid-`/render`.** If `merge_small_blobs` raises, do we
  emit `stage_error`, swap canvas to the pre-render state (the prior
  token of `render` stage), and surface the error in the toolbar?
  Likely yes — mirrors D-13's swap mechanism.
- **`Konva.clearCache()` invocation site.** Per-layer hook on
  `cacheVersion` change vs. centralized in `CanvasViewer`. Planner
  picks; CLAUDE.md only requires it happens after every geometric
  mutation.
- **Run state machine extension.** Existing `useRunStore` has
  `state: idle | ingesting | generating | generated | error`. Phase 04
  adds an incremental-render concept; naming options:
  add `rendering` state, or treat render as a flavor of `generating`
  with an `incremental` flag. Planner picks.
- **`stage_view` cfg field placement.** Add to `RegionConfig` (mutable
  alongside sliders) vs. keep client-only and pass as a query/body
  param to `/render`. Likely keep off cfg (it's a UI selector, not a
  pipeline parameter).
- **Barony name label rendering** (D-12): Konva `Text` node vs DOM
  overlay positioned via projection. Planner picks based on existing
  `HoverTooltip` precedent (DOM overlay).
- **Border / hierarchy stage cacheability.** Their tokens probably
  never change in Phase 04 (no slider reads `border_polygon` or
  `pt_duchies`); planner can mark them as "compute once per project,
  pin in cache".

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & success criteria
- `.planning/ROADMAP.md` §"Phase 04: Parameter studio (live re-render)"
  — four success criteria are the acceptance gate; SC-1 (DAG drawn
  before first slider) is a hard sequencing constraint
- `.planning/PROJECT.md` §"Out of Scope (v3)" — compound cross-stage
  undo deferred (drives D-15); Kuwahara filter forbidden
- `.planning/PROJECT.md` §"Key Decisions" — D-V3-05 (`RegionConfig` is
  the only mutable input — drives D-18) and D-V3-04 (delete v1 dead
  code — confirms `useRunStore` extension over a parallel store)

### Pipeline contract (algorithm + data shapes)
- `CLAUDE.md` §"v3 Pipeline Contract" — 12-file output table; the
  seven non-negotiable rules still apply (rule #2 σ ∈ [3.0, 4.5] drives
  D-05's clamp; rule #6 2× mask independence means mountains/rivers
  re-render is a downstream effect of `render`)
- `CLAUDE.md` §"What v3 explicitly is NOT" — no hand-rolled compound
  undo (drives D-15); no `sys.modules` patching (DAG cache stays in a
  module-level dict, never re-imports); no global Voronoi (cache keys
  on `project_id`)
- `CLAUDE.md` §"Architecture" — 11-stage DAG ordering; Phase 04 splits
  cleanup into 4 cacheable units inside the same flow
- `CLAUDE.md` §"Conventions" — `services/pipeline/` submodule layout +
  "atomic commits per task" rule applies to the cleanup split
- `inicio/map_generator.py` — gold-standard reference for cleanup
  semantics; the 4-way split (D-01) preserves bit-equivalent output at
  default cfg (D-17)
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` — 25-iteration history of why
  σ ∈ [3.0, 4.5] and why median pass sizes are `[11,11,9,9,7,7,5,5]`
  (drives slider bounds rationale in D-05)

### Pipeline implementation (refactor targets)
- `backend/medieval_forge/services/pipeline/__init__.py` —
  `run_pipeline(cfg)`; D-01 split lives here (orchestrator stays the
  same shape, the called function names expand)
- `backend/medieval_forge/services/pipeline/cleanup.py` —
  `cleanup_and_smooth` is the function being split (D-01) into 4
- `backend/medieval_forge/services/pipeline/contracts.py` —
  `RegionConfig` already carries the four slider fields
  (`smooth_sigma`, `median_passes`, `fragment_min_px`, `blob_merge_px`);
  Phase 04 adds `stop_event: threading.Event | None = None` (D-14) and
  optionally `stage_view` (Claude's Discretion)
- `backend/medieval_forge/services/pipeline/regions.py` —
  `iberia_config()` factory; `/render` builds cfg through this
- `backend/medieval_forge/services/canvas_sidecars.py` — Phase 03
  emits sidecars per full run; `/render` either re-emits affected
  sidecars or skips (planner decides — depends on whether barony /
  condado labels change with slider drag, which they shouldn't unless
  `merge_small_blobs` reshapes baronies)

### Backend HTTP layer (template)
- `backend/medieval_forge/api/v3/generate.py` — Phase 03 D-22 pattern:
  per-project `_RUN_QUEUES` + `_RUN_TASKS`, `_make_on_stage` threadsafe
  bridge, `_emit` envelope `{event_type, stage, message, progress}`,
  terminal `None` sentinel, 409 single-flight gate. `/render` mirrors
  this shape (D-04)
- `backend/medieval_forge/api/v3/status.py` — `/status` manifest;
  Phase 04 may extend with `current_render: { in_flight, affected_stages }`
- `backend/medieval_forge/api/v3/artifacts.py` — `ARTIFACT_FILES`
  frozenset; Phase 04 may extend with intermediate-stage PNGs (Claude's
  Discretion)
- `backend/medieval_forge/main.py` — registers `v3.generate.router`;
  Phase 04 adds `v3.render.router` and `v3.render.cancel` routes

### Frontend reuse (template + extension targets)
- `frontend/src/stores/useRunStore.ts` — 5-state machine + 11
  `PIPELINE_STAGES` + `LOG_CAP=500`. Phase 04 either extends to a
  `rendering` state or flags it as incremental (Claude's Discretion);
  also expands `PIPELINE_STAGES` if D-01's 14-unit split surfaces
  to the frontend status panel
- `frontend/src/api/useGenerateStream.ts` — EventSource subscriber
  template. Phase 04 spawns a `useRenderStream` sibling that handles
  the `/render/stream` envelope (likely identical) and the new
  `stage_cancel` event from D-13
- `frontend/src/components/canvas/CanvasViewer.tsx` — read-only viewer;
  Phase 04 hooks `Konva.clearCache()` (per CLAUDE.md "What v3 is NOT")
  on every `cacheVersion` change. The viewer's hydration path (via
  `useCanvasArtifacts`) becomes stage-view-aware
- `frontend/src/hooks/useCanvasArtifacts.ts` — TanStack Query hook;
  Phase 04 re-keys queries on `(stage_view, token)` so a render swap
  refetches the appropriate raster
- `frontend/src/components/canvas/LayerTogglePanel.tsx` — D-12
  barony-name labels integrate here (or an adjacent Konva text layer)
- `frontend/src/components/workspace/WorkspaceToolbar.tsx` — status
  badge → Cancel button (D-16); add toggle for the new left sidebar
  panel (D-06)
- `package.json` — `zundo@^2.3.0` is already installed; Phase 04 does
  NOT wire it (D-15). Stays a pinned dependency for the future undo
  phase

### Phase carry-forward
- `.planning/phases/01-pipeline-parity-port-harness-together/01-CONTEXT.md`
  — D-01 (verbatim port) gives Phase 04 the room to refactor cleanup;
  D-02 (Stage/version_token DAG deferred to Phase 04 — this phase
  cashes that check)
- `.planning/phases/03-read-only-canvas-redesign/03-CONTEXT.md` — D-04
  (no cancel in Phase 03; per-step `stop_event` slot reserved for
  Phase 04 — Phase 04 wires it via D-14); D-22 (SSE pattern is the
  template for `/render`); D-09..D-10 (canvas + layer reuse stays
  read-only-friendly); D-19 (cache-bust on `updated_at` — Phase 04's
  incremental render does NOT bump `updated_at` because the project's
  persisted artifacts are unchanged until a full `/generate`)
- `.planning/phases/03-read-only-canvas-redesign/03-VERIFICATION.md` —
  Phase 03 acceptance state; Phase 04 must keep all four Phase 03 SCs
  green
- `tests/parity/test_iberia_868.py` — at-default-cfg parity must stay
  byte-equal after the D-01 split (D-17)

### v1-archive lessons
- `.planning/v1-archive/STATE.md` — read for the "compound undo gap"
  (drove the v1 Phase 4 deferral that PROJECT.md "Out of Scope"
  inherits) and the σ-out-of-range fragmentation bug (drives D-05's
  clamp). Also: `Konva.clearCache()` is non-negotiable after geometric
  mutation; CanvasViewer's GAP-05 ResizeObserver pattern carries.
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` — historical context for the
  cleanup-and-smooth fusion (it was fused for parity-of-port reasons,
  not algorithm reasons; splitting now is safe per D-17)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`run_pipeline(cfg)`** in `services/pipeline/__init__.py` — already
  emits `cfg.on_stage(stage, evt)` at the 11 canonical stage
  boundaries; D-01's split adds three new emit points (median,
  fragment, smooth, merge already separately tracked) and the
  orchestrator becomes a thin DAG walker.
- **`_make_on_stage(queue, loop)`** in `api/v3/generate.py` — threadsafe
  bridge between sync `cfg.on_stage` (worker thread) and the SSE queue
  (event loop). Phase 04's `/render` reuses this verbatim. Adds a new
  envelope type `stage_cancel` (D-13) and one new field per event
  (`token: str`) so the client can correlate stages with cache entries.
- **`_RUN_QUEUES` + `_RUN_TASKS`** module-level dicts — single-flight
  gate already keyed by `project_id`. `/render` uses the same maps
  (a render counts as a run for the gate's purposes).
- **`useRunStore`** + 5-state machine — already handles `start`,
  `appendLog`, `startStage`, `finishStage`, `finish`, `reset`. Phase 04
  extends with `cancel(prior_tokens)` action (or planner adds a
  `useRenderStore` sibling — Claude's Discretion).
- **`useGenerateStream`** EventSource hook — Phase 04 spawns a
  `useRenderStream` sibling with the same envelope shape; the only new
  event type is `stage_cancel`.
- **`InspectorSidebar`** + `WorkspaceToolbar` — shell components from
  Phase 03; Phase 04 adds a sibling left-side `ParameterSidebar`
  component, mirroring layout + collapse pattern.
- **Tailwind v4 + Radix Themes** — `Slider.Root` from `@radix-ui/themes`
  is the slider primitive; `Card`, `Button`, `Tooltip` already used
  elsewhere.
- **`_STAGE_CACHE`** — does not exist yet; Phase 04 introduces it as a
  module-level dict in a new `services/pipeline/cache.py` (planner may
  put it in `__init__.py`; cache.py recommended for testability).

### Established Patterns

- **SSE producer**: `asyncio.Queue` + `_emit` envelope + terminal
  `None`. `/render` follows the same shape; per-(project, step)
  `stop_event` lives on cfg.
- **Atomic commits per task**: `feat(04-NN): ...` / `chore(04-NN): ...`
  / `test(04-NN): ...` per the convention used 03-01..03-08.
- **pytest markers**: `unit`, `parity`, `integration`. Phase 04 adds
  unit tests for each split function (`tests/unit/test_cleanup_split.py`)
  + a parity regression test that runs the pipeline through the new
  `/render` endpoint at default cfg and asserts byte-equal output
  (`tests/parity/test_iberia_868_render_default.py`) — both
  `@pytest.mark.parity` so CI gates them.
- **Vitest tests next to component**: `__tests__/ParameterSidebar.test.tsx`,
  `__tests__/useRenderStream.test.ts`. Frontend coverage stays ≥80% in
  the new `parameter-studio/` namespace.
- **Playwright UAT**: at least one new scenario (drag σ from 3.0 to
  4.5, assert canvas pixels change within 500 ms via SC-3 timing).
- **Konva discipline**: every layer calls `clearCache()` before its
  next render when `cacheVersion` changes; convention already in
  `CanvasViewer` (D-19 carry-forward).

### Integration Points

- **Backend new files** (likely): `services/pipeline/cache.py`
  (the `_STAGE_CACHE` dict + helpers); `services/pipeline/dag.py`
  (the version_token derivation + DAG walker); `api/v3/render.py`
  (the new endpoint pair + cancel route); cleanup split into 4
  inside existing `services/pipeline/cleanup.py`.
- **Frontend new files** (likely): `components/canvas/ParameterSidebar.tsx`
  + `SliderCard.tsx` + `StageViewToggle.tsx` + tests; new
  `api/useRenderStream.ts` + `api/render.ts` (POST helper); a
  `usePipelineParams` Zustand store (or extension of `uiStore`).
- **Frontend modifications**: `WorkspaceToolbar.tsx` (status-badge →
  Cancel + sidebar toggle); `CanvasViewer.tsx` (clearCache hook on
  cacheVersion + stage_view → cached array re-routing); `useRunStore`
  (incremental-render state extension); `LayerTogglePanel.tsx` +
  barony-name label addition (D-12).
- **`main.py` registration**: add `from .api.v3 import render` +
  `app.include_router(render.router)`.

</code_context>

<specifics>
## Specific Ideas

- **"Explicit DAG with `version_token` per stage drawn BEFORE first
  slider"** — SC-1 sequencing rule. The first commit of Phase 04 is the
  DAG abstraction (Plan 04-01 likely), not a slider. Karpathy: structure
  before parameters; v1 paid the cost of doing it backwards.
- **"σ from 3.0 → 4.5 reformats territories visibly in <500 ms without
  full re-run"** — SC-3 is the live-render contract. This budgets:
  ≤250 ms slider debounce + ≤200 ms σ-only compute (smooth + merge,
  ~30 territories at 1920×1080) + ≤50 ms canvas hydrate. Anything
  costing more breaks the perception of liveness.
- **"Cancel restores prior state; `Konva.clearCache()` after every
  geometric mutation"** — SC-4. The cancel = O(1) prior_token swap
  (D-13) is what makes this cheap; clearCache is a discipline rule
  not an algorithm.
- **"Karpathy: avoid v1's compound-undo gap"** — ROADMAP SC-1 cites
  this explicitly. Compound undo is the wound v1 left; v3 closes it
  by NOT building it (D-15) until the data model + cache topology are
  proven. Phase 04 plants the seed (zundo pinned in package.json)
  without harvesting it.
- **"User said: barony names should appear when Baronies layer is on"**
  — captured during discussion as D-12. Side-note polish that fits
  Phase 04 because barony tier re-renders on `merge` slider changes.
- **"Sliders mutate cfg, but only a per-render copy"** — D-V3-05 says
  cfg is the only mutable input. D-18 reconciles: each `/render` call
  builds a fresh cfg from `iberia_config()` + applies overrides. The
  project's persisted cfg state is touched only on full `/generate`
  (or on an explicit "Save sliders" button if Claude's Discretion
  decides persistence is needed).

</specifics>

<deferred>
## Deferred Ideas

- **`zundo` `temporal` undo/redo across slider history** — PROJECT.md
  Out of Scope; Phase 04 plants the dependency, the undo phase that
  follows v3.0 launch wires it. Likely v3.1.
- **Disk-backed stage cache** — Phase 04 stays in-memory; if Phase 06
  export-gate or v3.1 ergonomics demand survival across server
  restarts, add `.npy` write-through to `project_dir/cache/`.
- **Sliders for `island_min_px`, `mountain_threshold`, `mountain_noise`,
  `coast_inner_width`** — only the four ROADMAP-named knobs ship in
  Phase 04. Add later when a Game Designer asks.
- **Region YAML loader** — Phase 05.
- **Schema validation gate on incremental renders** — Phase 06 export
  gate.
- **LLM-assisted parameter recommendation** — Phase 07 sidecar.
- **Persistence of slider values across sessions / project re-open** —
  Claude's Discretion; default = ephemeral; revisit on UAT.
- **LRU eviction beyond latest+prior** — Phase 04 keeps 2 versions per
  stage per project; planner may extend if measurement shows pressure.
- **Stage-view radio for border / hierarchy / lookup / metadata /
  export** — only the 5 visualizable units in D-10. Add later if
  debuggers need finer granularity.
- **Bypass-stage capability** (skip cleanup, skip smooth) — D-09
  rejected; user can achieve a similar effect by setting the slider to
  its "no-op" extreme (e.g., `median_passes=1`, `blob_merge_px=0`).
- **Hard-kill cancel via `asyncio.Task.cancel()`** — D-14 keeps the
  cooperative `stop_event` model because numpy/scipy CPU-bound code
  cannot be hard-killed mid-call.
- **Concurrent `/render` requests for the same project** — D-04
  enforces single-flight via `_RUN_TASKS`. Concurrent renders from
  multiple slider drags get coalesced by debounce + latest-wins
  (D-07).
- **Compound-undo button in the toolbar** — D-15 defers; the per-slider
  reset (D-08) is the only revert Phase 04 ships.
- **Mid-render error recovery** (e.g., `merge_small_blobs` raises) —
  Claude's Discretion; likely emits `stage_error` + swaps to the
  pre-render prior token mirroring D-13.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 04` returned `todo_count=0` at
gathering time.

</deferred>

---

*Phase: 04-parameter-studio-live-re-render*
*Context gathered: 2026-05-10*
