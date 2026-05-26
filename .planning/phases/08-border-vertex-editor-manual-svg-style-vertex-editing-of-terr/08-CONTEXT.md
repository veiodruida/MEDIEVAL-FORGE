# Phase 8: border-vertex-editor — Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 delivers a **manual SVG-style vertex editor** for territory polygons
(barony as source of truth) plus a **named-branch + auto-snapshot project
model**. The editor reuses the Konva 5-layer canvas from Phase 03, introduces
a new pipeline DAG stage `manual_edit` (between `merge` and `hierarchy`), and
wires `zundo` `temporal` for the first time (D-15 of Phase 04 finally lands —
scoped to editor ops only, not cross-stage compound undo).

**In scope:** vertex move/add/delete, polygon split/merge, whole-territory
translate, Douglas-Peucker simplify, editable landmask (with manual + auto
re-clip toggle), named branches with auto-snapshots every 25 edits,
topology validation (block self-intersect + neighbour gaps), shared-edge
multi-territory move, keyboard shortcuts (V/A/D/S/M/Esc + Ctrl+Z/Y),
60fps drag with viewport culling, SQLite auto-save + local-only telemetry.

**Out of scope (deferred):** 3-way geometric branch merge, mobile/touch
support, mid-drag latency telemetry export, multi-user concurrency,
custom keybind UI, hierarchy-tier toggle in toolbar, condado-tier direct
editing.

</domain>

<decisions>
## Implementation Decisions

### Edit-operation scope

- **D-01 (Vertex ops):** Editor supports move (drag), add (click on edge),
  delete (Backspace/Delete), and Douglas-Peucker simplify (toolbar button
  with tolerance slider). All four ship in Phase 8.
- **D-02 (Polygon ops):** Split (draw a line cutting a polygon → produces
  two), merge (select 2 adjacent → produces one), and translate (drag
  polygon interior) all ship. No deferral.
- **D-03 (Editable tier):** Only **barony**-tier polygons are directly
  editable. Condado/duchy/kingdom are re-derived by the `hierarchy` stage
  from edited baronies (CLAUDE.md Rule #4 — `original_idx` invariant
  preserved across re-derivation).
- **D-04 (Landmask is editable):** The land mask / coastline IS editable
  in Phase 8. It is a single editable polygon ("Landmask Editor" layer);
  PT/ES border (38 pts) stays a separate read-only layer (CLAUDE.md
  Rule #3 — KD-tree routing assumption).
- **D-05 (Landmask re-clip mode toggle):** TWO modes available, user
  picks per session:
  - **Manual mode** (default): user batches edits, clicks "Apply
    landmask" — cascade (voronoi+cleanup+smooth+merge+hierarchy+render+
    lookup) runs once. Recommended for big edits.
  - **Auto-immediate mode**: every landmask vertex drag triggers full
    cascade. Honest preview, slow (~10s/edit on Iberia 868). For
    fine-tuning final detail.
  Toggle lives in the Landmask Editor layer header.
- **D-06 (Vertex cap):** Hard cap 1000 vertices per barony — `add vertex`
  is disabled at the cap. Simplify is always available. Warning badge
  at 500.

### Split / merge semantics

- **D-07 (Split id assignment):** New polygon **auto-inherits** parent
  condado; name = `"<original name> (2)"`; `original_idx` =
  `max(existing original_idx in branch) + 1`. User renames later via
  inspector. Zero modal interrupt during split.
- **D-08 (Merge winner rule):** First-selected territory wins (id, name,
  parent condado, `original_idx`). Second is absorbed; its `original_idx`
  is freed. No prompt — drag-multi-select order is the rule.
- **D-09 (Merge constraint):** No cross-condado restriction in Phase 8 —
  user can merge baronies across condados; hierarchy re-derivation
  handles the case. (Hierarchy stage may relocate the merged barony if
  its centroid crosses condado boundary.)

### Branching model

- **D-10 (Branch + snapshot hybrid):** Each project has named branches
  (manual create/switch/delete, `main` is default and protected from
  deletion). Within a branch, **auto-snapshots every 25 edits** plus a
  manual "Snapshot now" button. Snapshots are versioned within their
  branch, surfaced as a sub-timeline.
- **D-11 (Branch creation trigger):** Explicit toolbar button
  "New branch from <current>" only — no fork-on-first-edit magic. Prompts
  for name. Editing `main` is allowed (it's protected from *deletion*,
  not from edits).
- **D-12 (Branch storage):** Each branch row in SQLite holds a complete
  snapshot blob (post-edit GeoJSON + RegionConfig + edit-op log). No
  patch-replay. Higher disk cost, zero replay-bug surface.
- **D-13 (Branch picker UI):** Dropdown in toolbar, left of "Generate
  Map" button. Shows current branch name + list (sortable by recent),
  "New branch", "Rename", "Delete" (disabled for `main`).
- **D-14 (No geometric merge between branches):** Branches are isolated
  experiments. To promote: "Copy <branch> → main" replaces `main`'s
  snapshot wholesale with a confirmation modal. 3-way vertex merge is
  explicitly deferred (not a Phase 8 goal).
- **D-15 (Main is undeletable):** UI delete button disabled on `main`.
  Rename is allowed. If user wants a fresh start, they re-create the
  project (Phase 02 territory).
- **D-16 (Export uses active branch):** Export ZIP (12-file Unity
  contract) snapshots the currently-active branch. Manifest includes
  `branch_name` + `snapshot_id` + `snapshot_timestamp`.

### DAG integration

- **D-17 (Edits overwrite post-merge GeoJSON):** Manual edits become the
  output of a new pipeline stage `manual_edit`, slotted between `merge`
  and `hierarchy`. Stages downstream (`hierarchy → render → lookup →
  metadata → export`) re-run normally over the edited geometry. Stages
  upstream (`landmask → border → voronoi → cleanup → smooth → merge`)
  remain cached unless landmask is edited (D-04) or a Phase 04 slider
  changes (D-19).
- **D-18 (`manual_edit` `version_token`):** Token =
  `sha256(stage_name + edit_op_count + sha256(edit_op_log))`. Honours
  Phase 04 D-02 (DAG token derivation). Empty edit log produces a
  stable token equal to a "pass-through" identity.
- **D-19 (Slider conflict resolution):** When a Phase 04 slider changes
  while edits exist on the active branch, the front-end DAG detects
  that an upstream stage's token will invalidate `manual_edit`. It (a)
  auto-snapshots the branch *first*, (b) opens a confirmation modal
  ("Slider change will re-render geometry from scratch and discard
  in-flight edits — restore from snapshot N if you reconsider"),
  (c) on confirm, re-runs the cascade. User can cancel.
- **D-20 (Landmask edit cascades like a slider):** Editing the landmask
  layer invalidates the `landmask` stage's `version_token` → full
  downstream cascade (per-country KD-tree rebuild + voronoi + cleanup
  + smooth + merge + manual_edit replay + hierarchy + render + lookup
  + metadata). CLAUDE.md Rule #3 (KD-tree per country) preserved.
- **D-21 (Lookup PNG re-render):** `render` + `lookup` stages re-run
  automatically after `manual_edit`. NEAREST upscale (CLAUDE.md Rule
  #1) preserved. Cost ~3-5s; that is the budget. No
  selective-barony-only incremental render in Phase 8 (Karpathy:
  don't optimise hypothetically).
- **D-22 (`original_idx` for new baronies):** `max(original_idx) + 1`
  within the branch's metadata counter. CLAUDE.md Rule #4 — every
  territory has a unique stable `original_idx`. Branch metadata stores
  the high-water-mark counter.
- **D-23 (DAG cache scope):** Cache key =
  `(project_id, branch_id, stage, version_token)`. Switching branches
  is a cache hit if the target branch's stages were ever generated.
  Disk cost grows linearly with branches; LRU eviction policy is *not*
  introduced in Phase 8 (Phase 04 D-03's "latest+prior" rule applies
  per `(project_id, branch_id)` pair).
- **D-24 (Coast = landmask boundary synonym):** Coast is the boundary
  of the landmask polygon. They are not separate layers. PT/ES border
  is a different layer and stays read-only in Phase 8.

### Undo + topology + UX

- **D-25 (Wire zundo, editor ops only):** Phase 8 is the phase that
  CLAUDE.md `Out of Scope` referred to. `zundo` `temporal` middleware
  wraps the editor store. Scope: vertex move/add/delete, polygon
  split/merge, translate. Excluded from history: branch switch,
  snapshot create, Phase 04 sliders. Ctrl+Z / Ctrl+Shift+Z. History
  cap ~100 ops; oldest evicted. Cleared on branch switch (each branch
  has its own redo stack).
- **D-26 (Topology validation — block):** Self-intersect and gap
  between neighbouring baronies are **blocking** — drag is rejected
  on mouseup if the result violates either. Shapely `is_valid` +
  `touches` predicate on neighbours. Drag feedback: handle/edge turns
  red during invalid drag, snaps back on release.
- **D-27 (Topology validation — warn):** Duplicate vertex (same
  (lat, lon) within 1e-6) shows a yellow badge but does not block.
  Sliver polygons (<0.001° area) get a yellow badge.
- **D-28 (Snap behaviour):** Auto-snap to neighbour vertex within 5px
  + auto-snap to neighbour edge. Visual: yellow circle on the target
  vertex/edge. Hold Alt to disable snap during the current drag.
- **D-29 (Selection UX):** Click vertex selects; Shift-click adds;
  marquee drag selects within rectangle. Multi-select can cross
  territories. Delete removes all selected vertices in one undoable
  op.
- **D-30 (Shared vertex moves together):** When a vertex is shared
  between adjacent baronies (coincident within snap tolerance),
  moving it moves the shared vertex in **all** baronies simultaneously.
  This is the default and only behaviour. Snap (D-28) guarantees
  coincident vertices are recognised as the same.
- **D-31 (Shared edge visual):** Hovering a shared edge highlights it
  in purple; the two endpoint vertices on that edge also highlight,
  signalling "moving this vertex affects N neighbours". No always-on
  highlight (too noisy).
- **D-32 (Keyboard shortcuts):** Single-letter shortcuts active only
  when canvas is focused: `V` select, `A` add-vertex tool, `D` delete,
  `S` split, `M` merge, `Esc` cancel current tool. Plus `Ctrl+Z` /
  `Ctrl+Shift+Z` undo/redo, `Delete` for selected vertices. Listed in
  inspector help panel. No custom rebinding in Phase 8.
- **D-33 (Coord tooltip):** Drag tooltip shows `(lat, lon)` in float
  6 decimals, follows the cursor. No pixel readout. Game-Designer
  audience thinks in geographic terms.
- **D-34 (Performance budget):** Target 60fps drag up to ~5k visible
  vertex handles. Konva viewport culling: handles outside viewport +
  10% margin are skipped. Drag updates throttled to 16ms via RAF
  batching. No LOD / zoom-gated handles in Phase 8.
- **D-35 (Telemetry — local only):** Each edit op (move/add/delete/
  split/merge/translate/simplify) is logged to a new SQLite table
  `edit_events` with `(timestamp, project_id, branch_id, op_type,
  payload_json)`. No external transmission. Used for post-mortem
  debugging and snapshot replay.
- **D-36 (Mobile/touch — deferred):** Phase 8 is desktop-only. Konva
  receives mouse/pen pointer events; touch is not designed for. UA
  detection shows a "Desktop required" banner on touch-primary
  devices. Future phase can layer touch on top.
- **D-37 (Auto-save + crash recovery):** Auto-save to SQLite triggers
  on the same cadence as auto-snapshot (every 25 edits) — snapshot
  IS the save. Plus `localStorage` stores `active_branch_id` so a
  browser refresh restores the active branch. Worst-case crash =
  losing < 25 edits since last snapshot. No per-drag auto-save.

### Claude's Discretion

- Exact CSS for the purple shared-edge highlight, yellow snap circle,
  red invalid-drag glow. Pick anything consistent with the Mapbox-like
  shell defined in Phase 03.
- Toolbar tool icons and the help-panel layout. UX-checker / UI-phase
  may refine.
- The decimal precision of intermediate coord computation (the visible
  tooltip is fixed at 6 decimals; storage precision is the planner's
  call but should not regress GeoJSON round-trip).
- Whether `Apply landmask` is a primary button (filled) or secondary
  (outlined) — both work.
- Whether the branch-picker dropdown shows `(N edits since snapshot)`
  per branch row, or omits to stay compact.
- The undo-history sentinel structure inside zundo's `partialize` —
  planner picks the diff representation as long as ops round-trip.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline contract (must preserve)

- `CLAUDE.md` — v3 pipeline contract; Rules #1 (NEAREST upscale),
  #3 (KD-tree per country), #4 (`original_idx` invariant) directly
  constrain Phase 8.
- `inicio/map_generator.py` — 620-line gold-standard reference for the
  geometric pipeline. The new `manual_edit` stage must not require any
  upstream stage to change behaviour.
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` — every paid-for lesson;
  Phase 8 must not violate the lessons documented here.

### Pipeline DAG and project model

- `.planning/phases/04-parameter-studio-live-re-render/04-CONTEXT.md`
  §`<decisions>` — D-02 (`version_token` derivation),
  D-03 (cache policy "latest+prior"), D-15 (zundo deferred — Phase 8
  lifts the defer).
- `.planning/phases/04.1-parameter-studio-polish-cancel-race-hardening/04.1-CONTEXT.md`
  — cancel/race semantics that the new `manual_edit` stage must respect.
- `.planning/phases/03-read-only-canvas-redesign/03-CONTEXT.md` §D-09 +
  §D-10 — the Konva 5-layer stack to be reused; the v1 edit components
  that were deleted (rebuild from scratch, NOT restore).
- `.planning/phases/02-ingestion-adapter/02-CONTEXT.md` — ProjectDataset
  contract (GeoJSON input) the editor mutates.

### Export contract

- `.planning/phases/06-export-contract-validation-gate/06-CONTEXT.md` —
  12-file Unity ZIP; manifest extension for branch metadata must not
  break the existing parity tests.

### Project-level

- `.planning/PROJECT.md` — Key Decisions D-V3-04 (no dead code resurrection
  — Phase 8 rebuilds, does not restore), D-V3-05 (RegionConfig single
  mutable input — Phase 8 *extends* this to include the edit-op log).
- `.planning/REQUIREMENTS.md` (currently empty for Phase 8 — fill during
  planning).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- `frontend/src/components/canvas/CanvasViewer.tsx` + the 5-layer Konva
  stack (`BackgroundLayer`, `TerritoryLayer`, `BaronyLayer`,
  `DecorationsLayer`, `InteractionLayer`) — reuse verbatim; the editor
  adds a new layer (`VertexEditLayer` — rebuild, NOT restoration of the
  deleted `VertexHandlesLayer`).
- `frontend/src/components/canvas/InspectorSidebar.tsx` — host the new
  edit-tool help panel + branch metadata.
- `frontend/src/lib/projection.ts` + `ProjectionContext` — lat/lon ↔
  pixel conversion is already centralised; the tooltip (D-33) hooks here.
- `useZoomPan`, `useKeyboardShortcuts` — extend; the deleted
  `useEditKeyboardMap` and `useUndoShortcut` are NOT restored, new ones
  written from scratch per D-V3-04.
- `package.json` — `zundo@^2.3.0` is already installed (Phase 04 planted
  the dep). Phase 8 wires it (D-25).
- `backend/medieval_forge/services/pipeline/` — the DAG host. New
  module: `manual_edit.py` slots between `merge` and `hierarchy`.

### Established patterns

- DAG stage pattern: each stage exports `compute(inputs, config) → output`
  + `version_token(config, upstream_tokens) → str`. New `manual_edit`
  stage follows this contract.
- Per-stage cache pattern: in-memory dict keyed by `(project_id, stage,
  version_token)`. Phase 8 extends the key with `branch_id`.
- SQLite persistence pattern: `backend/medieval_forge/db/` — new tables
  `branches`, `snapshots`, `edit_events` follow existing migrations
  pattern.
- Zustand store pattern: `frontend/src/stores/` — new `useEditorStore`
  (NOT the deleted v1 one) wraps with zundo `temporal`.

### Integration points

- Toolbar: branch dropdown (D-13) goes left of "Generate Map" button —
  toolbar already structured for this in Phase 03 D-01.
- Inspector sidebar: edit-tool help + selected-vertex coords readout.
- Generate button: must trigger the snapshot pre-cascade (D-19) when
  edits exist.
- Export endpoint: must inject `branch_name` + `snapshot_id` into the
  Unity manifest (D-16).

### Creative options enabled

- Because the DAG already isolates `version_token` per stage, the
  `manual_edit` stage can short-circuit when its log is empty (identity
  pass-through). Costs only `len(edit_log) == 0` check on cache hit.
- Snap (D-28) reuses scipy's KD-tree pattern from voronoi — quick
  neighbour lookup at editor-build time, refreshed on edit-end.

</code_context>

<specifics>
## Specific Ideas

- The two-mode landmask toggle (D-05) was a user-driven addition over
  the recommended single-mode option — "1 manual e outro com edicao
  imediata". Both modes ship.
- Branching modelled as **hybrid** named-branch + auto-snapshot (D-10) —
  user picked the most powerful option, not the minimal "named branches
  only" recommendation. Snapshot cadence = every 25 edits.
- Editor ops mirror Figma/Illustrator shortcuts (V/A/D/S/M/Esc) — the
  user chose the full single-letter set, not the minimal Delete+Esc
  option.
- Shared-vertex moves are ALWAYS coupled across neighbours (D-30) — no
  "hold Shift to move only active" escape hatch. The snap + coupling
  guarantee topology by construction.

</specifics>

<deferred>
## Deferred Ideas

- **3-way geometric merge between branches** — branch merge is replace-only
  (D-14). Real vertex-level merge is complex and rare; future phase.
- **Mobile/touch support** — D-36 defers. Konva supports pointer events;
  a touch UX phase can layer on later (handle tap-size, pinch zoom
  during drag, two-finger pan).
- **LOD / zoom-gated handle visibility** — D-34 picks viewport culling
  only. Zoom-based handle hide/show is a later perf phase if needed.
- **Selective per-barony incremental lookup re-render** — D-21 picks
  full re-render. Optimise later if measured-slow.
- **Custom keybind rebinding UI** — D-32 ships fixed set. Settings phase
  could add rebind later.
- **Hierarchy-tier toggle** (edit at condado tier directly) — D-03
  picks barony-only. Condado-direct editing is its own phase if needed.
- **Cross-condado merge guardrail** — D-09 allows it; if it produces
  hierarchy issues in practice, add a guardrail later.
- **Telemetry export bundle for bug reports** — D-35 keeps it local.
  Opt-in export is a small future improvement.
- **LRU cache eviction beyond (latest, prior) per branch** — D-23
  inherits Phase 04 D-03 policy. If disk grows, add per-project quota
  later.

</deferred>

---

*Phase: 08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr*
*Context gathered: 2026-05-26*
