# Requirements (v3)

This document inventories functional/non-functional requirements per phase.
Requirement IDs are stable identifiers referenced by PLAN.md `requirements:` frontmatter.

---

## Phase 08 — Border Vertex Editor + Branching

Source: `.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-CONTEXT.md` (37 locked decisions D-01..D-37) and `08-RESEARCH.md` (proposed REQ-ID map).

### Edit Operations

| ID | Description | Source Decisions |
|----|-------------|------------------|
| EDIT-VERTEX-01 | Drag a single vertex; mouseup commits if topology valid, snaps back if not; shared-vertex coupling applies | D-01, D-26, D-30 |
| EDIT-VERTEX-02 | Click an edge to add a new vertex; disabled when polygon has 1000 vertices; warning badge at 500 | D-01, D-06 |
| EDIT-VERTEX-03 | Select and delete vertices (single, Shift-click, marquee); multi-select delete is one undoable op | D-01, D-29 |
| EDIT-VERTEX-04 | Douglas-Peucker simplify with tolerance slider 0.00001–0.01 (preserve_topology=True) | D-01 |
| EDIT-VERTEX-05 | Drag tooltip shows `(lat, lon)` 6-decimal monospace following cursor | D-33 |
| EDIT-POLYGON-01 | Split polygon by 2-point line cut; child inherits parent condado; name = `<orig> (2)`; `original_idx = max+1` | D-02, D-07, D-22 |
| EDIT-POLYGON-02 | Merge 2 adjacent baronies → winner = first-selected (id, name, condado, original_idx) | D-02, D-08, D-09 |
| EDIT-POLYGON-03 | Drag polygon interior to translate; shared vertices remain coupled | D-02, D-30 |

### Landmask

| ID | Description | Source Decisions |
|----|-------------|------------------|
| LANDMASK-01 | Landmask editable as single polygon; PT/ES border (40-pt) remains read-only | D-04, D-24 |
| LANDMASK-02 | Two modes per session: Manual (batch + Apply button) and Auto-immediate (per-drag cascade) | D-05 |

### Branching + Snapshots

| ID | Description | Source Decisions |
|----|-------------|------------------|
| BRANCH-01 | Named branches: create/switch/rename/delete; `main` is default and delete-protected | D-10, D-11, D-13, D-15 |
| BRANCH-02 | Auto-snapshot every 25 edits + manual "Snapshot now"; sub-timeline per branch | D-10, D-37 |
| BRANCH-03 | Branch storage = complete snapshot blob (gzip JSON of GeoJSON + RegionConfig + edit-op log); no patch-replay | D-12 |
| BRANCH-04 | "Copy <branch> → main" wholesale-replaces main after confirmation | D-14 |
| BRANCH-05 | Export ZIP snapshots active branch; manifest extends with `branch_name`+`snapshot_id`+`snapshot_timestamp`; bump MANIFEST_SCHEMA_VERSION→3 | D-16 |

### DAG / Cache

| ID | Description | Source Decisions |
|----|-------------|------------------|
| DAG-01 | New pipeline stage `manual_edit` slotted between `merge` and `hierarchy`; downstream re-runs; upstream cached | D-17 |
| DAG-02 | `manual_edit.version_token = sha256(stage_name + edit_op_count + sha256(edit_op_log))`; empty log → identity pass-through | D-18 |
| DAG-03 | Slider change while edits exist → auto-snapshot FIRST, then confirmation modal; cancel allowed | D-19 |
| DAG-04 | Landmask edit invalidates `landmask` stage → full per-country KD-tree rebuild cascade (CLAUDE.md Rule #3) | D-20 |
| DAG-05 | Cache key extended to `(project_id, branch_id, stage, version_token)`; latest+prior per `(project_id, branch_id)` | D-23 |

### Topology / UX

| ID | Description | Source Decisions |
|----|-------------|------------------|
| TOPO-01 | Self-intersect + neighbour gap are BLOCKING; drag rejected on mouseup; visual red feedback during invalid drag | D-26 |
| TOPO-02 | Duplicate vertex (≤1e-6) + sliver polygon (<0.001°) are non-blocking warnings (yellow badge) | D-27 |
| TOPO-03 | Auto-snap to neighbour vertex/edge within 5 screen-px (scale-aware); Alt disables snap for current drag | D-28 |
| TOPO-04 | Shared vertex (coincident within snap tolerance) moves in all adjacent baronies simultaneously | D-30 |
| PERF-01 | 60fps drag up to ~5k visible vertex handles; viewport culling + 10% margin; RAF throttle 16ms | D-34 |
| UX-01 | Keyboard shortcuts V/A/D/S/M/Esc + Ctrl+Z/Ctrl+Shift+Z + Del; canvas-focused only | D-25, D-32 |
| UX-02 | Desktop-only — "Desktop required" banner on touch-primary UA | D-36 |
| UNDO-01 | zundo `temporal` wraps `useEditorStore`; scope = vertex/polygon ops; history cleared on branch switch; cap 100 | D-25 |

### Persistence

| ID | Description | Source Decisions |
|----|-------------|------------------|
| PERSIST-01 | SQLite tables `branches`, `snapshots`, `edit_events` created via `Base.metadata.create_all` | D-10, D-12, D-35 |
| PERSIST-02 | Auto-save = auto-snapshot every 25 edits; `localStorage` holds `active_branch_id`; worst-case crash < 25 edits | D-37 |
| TELEM-01 | Each edit op logged to `edit_events` (timestamp, project_id, branch_id, op_type, payload_json); local-only | D-35 |

### Decision Coverage Matrix (D-XX → REQ-ID → Plan)

| D-XX | REQ-ID(s) | Plan |
|------|-----------|------|
| D-01 | EDIT-VERTEX-01..04 | 08-06a, 08-06b |
| D-02 | EDIT-POLYGON-01..03 | 08-07 |
| D-03 | (barony-only constraint, applied across plans) | 08-06a |
| D-04 | LANDMASK-01 | 08-08 |
| D-05 | LANDMASK-02 | 08-08 |
| D-06 | EDIT-VERTEX-02 (cap) | 08-06a |
| D-07 | EDIT-POLYGON-01 | 08-07 |
| D-08 | EDIT-POLYGON-02 | 08-07 |
| D-09 | EDIT-POLYGON-02 | 08-07 |
| D-10 | BRANCH-01, BRANCH-02, PERSIST-01 | 08-03a, 08-03b |
| D-11 | BRANCH-01 | 08-03a, 08-09 |
| D-12 | BRANCH-03, PERSIST-01 | 08-03a, 08-03b |
| D-13 | BRANCH-01 | 08-09 |
| D-14 | BRANCH-04 | 08-09 |
| D-15 | BRANCH-01 | 08-03a |
| D-16 | BRANCH-05 | 08-10 |
| D-17 | DAG-01 | 08-01 |
| D-18 | DAG-02 | 08-01 |
| D-19 | DAG-03 | 08-09 |
| D-20 | DAG-04 | 08-08 |
| D-21 | (NEAREST upscale preserved) | 08-01 (assertion) |
| D-22 | EDIT-POLYGON-01 (high-water-mark) | 08-03a, 08-07 |
| D-23 | DAG-05 | 08-02 |
| D-24 | LANDMASK-01 | 08-08 |
| D-25 | UNDO-01, UX-01 | 08-04 |
| D-26 | TOPO-01 | 08-06b |
| D-27 | TOPO-02 | 08-06b |
| D-28 | TOPO-03 | 08-06b |
| D-29 | EDIT-VERTEX-03 | 08-05, 08-06a |
| D-30 | TOPO-04 | 08-06b |
| D-31 | (shared-edge purple) | 08-05 |
| D-32 | UX-01 | 08-04, 08-05 |
| D-33 | EDIT-VERTEX-05 | 08-05 |
| D-34 | PERF-01 | 08-05 |
| D-35 | TELEM-01, PERSIST-01 | 08-03b |
| D-36 | UX-02 | 08-05 |
| D-37 | PERSIST-02 | 08-03b, 08-04 |

Every D-XX maps to at least one REQ-ID and at least one plan. Full fidelity preserved.

---

## Phase 08.3 — Pen Tool Barony Contour Authoring

Source: `.planning/phases/08.3-pen-tool-barony-contour-authoring/08.3-CONTEXT.md` (decisions D-19..D-27).

### Carve / Enclave Operations

| ID | Description | Source Decisions |
|----|-------------|------------------|
| CARVE-ENCLAVE-01 | A closed loop drawn fully inside barony X becomes a new barony N = drawn ∩ X, with X reshaped to a polygon-with-hole (X − N); N inherits X's condado/duchy/kingdom and a server-allocated original_idx (never reused, >= barony_floor) | D-23, D-24, D-26, D-27 |
| CARVE-HOLE-RT-01 | The parent's interior ring (hole) survives the full round-trip store → reload → re-Apply (both pure-carve and carve+parent-Bézier-edit), and no -1/9999 sentinel is created inside X's exterior by the difference() operation | D-25, D-27 |
