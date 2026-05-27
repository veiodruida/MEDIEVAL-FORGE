# Phase 8: border-vertex-editor — Research

**Researched:** 2026-05-26
**Domain:** Interactive vector-polygon editor + DAG cache extension + branch/snapshot persistence
**Confidence:** HIGH for stack/library APIs (Shapely 2.x, zundo 2.3, Konva 10.x, scipy KDTree, SQLAlchemy 2.0); MEDIUM for Konva 5k-handle perf upper bound; HIGH for integration points (codebase grep-verified).

## Summary

Phase 8 inserts a `manual_edit` stage between `merge` and `hierarchy`, adds three SQLite tables (`branches`, `snapshots`, `edit_events`) keyed off existing `projects.id`, and wires `zundo@2.3.0`'s `temporal` middleware to a new `useEditorStore`. Every Phase 04 invariant (cache key shape, `version_token` derivation, single-flight gate, parity-at-default) extends rather than replaces. Every CLAUDE.md non-negotiable rule survives: barony edits feed the existing `hierarchy → render → lookup → metadata → export` cascade, `original_idx` is allocated by branch-scoped high-water-mark (D-22), NEAREST upscale is preserved (D-21 — no selective re-render), KD-tree-per-country is preserved (D-20 forces full rebuild on landmask edit).

The geometric primitives map cleanly to Shapely 2.x stdlib: `make_valid` / `is_valid` (topology block, D-26), `ops.split` (D-02 split tool), `unary_union` + `simplify` (merge + D-01 Douglas-Peucker), `STRtree` (shared-vertex KD lookup, D-30). The 60fps target at ~5k handles is achievable in Konva with viewport culling + dragmove RAF batching + `listening: false` on non-active layers, but **requires** isolating the editor layer's `batchDraw` from the 5 read-only layers (which keep `Konva.clearCache()` discipline from D-19/CLAUDE.md). The biggest unspecified integration is the `manual_edit` token derivation — it cannot use the existing `STAGE_READS` cfg-field machinery because the edit log is not on `RegionConfig`. Resolution: add `manual_edit` to a sibling `STAGE_TOKEN_OVERRIDES: dict[str, Callable]` map (this research recommends, planner confirms).

**Primary recommendation:** ship in three planning bands — (1) **backend foundation** (DDL + `manual_edit` stage + DAG/cache extension with `branch_id`), (2) **frontend editor** (`VertexEditLayer` + `useEditorStore` with zundo + tool palette + topology validation endpoint), (3) **branching UX** (branch picker + dialogs + snapshot timeline + manifest extension). Each band is independently testable against the existing parity test (empty edit log = byte-equal output) and the three-layer pyramid.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Edit-operation scope**
- **D-01:** Vertex ops = move (drag), add (click-on-edge), delete (Backspace/Delete), Douglas-Peucker simplify (toolbar + tolerance slider). All four ship.
- **D-02:** Polygon ops = split (line cut → two), merge (select 2 adjacent → one), translate (drag interior). All three ship.
- **D-03:** Only **barony**-tier polygons are directly editable. Condado/duchy/kingdom re-derived by `hierarchy`. CLAUDE.md Rule #4 (`original_idx`) preserved.
- **D-04:** Landmask IS editable; single editable polygon ("Landmask Editor" layer). PT/ES border (38 pts) stays read-only.
- **D-05:** Landmask has TWO modes per session — **Manual** (batched, click "Apply") and **Auto-immediate** (every drag triggers full cascade ~10s). Toggle in layer header.
- **D-06:** Hard cap 1000 vertices per barony — add-vertex disabled at cap. Warning badge at 500. Simplify always available.

**Split / merge semantics**
- **D-07:** Split → new polygon auto-inherits parent condado; name = `"<orig> (2)"`; `original_idx = max+1`. Zero modal interrupt.
- **D-08:** Merge winner = first-selected (id, name, condado, `original_idx`). Second absorbed; its `original_idx` is freed but **never reused** (D-22 high-water-mark wins).
- **D-09:** No cross-condado merge restriction. Hierarchy re-derivation handles relocation if centroid crosses boundary.

**Branching model**
- **D-10:** Named branches (manual create/switch/delete, `main` default + delete-protected) + auto-snapshot every 25 edits + manual "Snapshot now". Snapshots are a sub-timeline per branch.
- **D-11:** Explicit "New branch from <current>" toolbar button only. No fork-on-first-edit. Editing `main` is allowed.
- **D-12:** Each branch row stores complete snapshot blob (post-edit GeoJSON + RegionConfig + edit-op log). No patch-replay.
- **D-13:** Branch picker = Radix Select dropdown in toolbar, left of "Generate Map". Shows current branch + list, "New", "Rename", "Delete" (disabled on `main`).
- **D-14:** No 3-way geometric merge. "Copy <branch> → main" wholesale-replaces `main` after confirmation modal.
- **D-15:** `main` undeletable in UI; rename allowed.
- **D-16:** Export ZIP snapshots active branch; manifest gains `branch_name` + `snapshot_id` + `snapshot_timestamp`.

**DAG integration**
- **D-17:** `manual_edit` is a new pipeline stage between `merge` and `hierarchy`. Downstream re-runs normally; upstream stays cached unless landmask edit (D-04) or slider change (D-19).
- **D-18:** `manual_edit.version_token = sha256(stage_name + edit_op_count + sha256(edit_op_log))`. Honors Phase 04 D-02. Empty edit log → pass-through identity token.
- **D-19:** Slider change while edits exist → auto-snapshot first, then confirmation modal ("discard in-flight edits, restore from snapshot N if you reconsider"). User can cancel.
- **D-20:** Landmask edit invalidates `landmask` stage → full cascade with per-country KD-tree rebuild. CLAUDE.md Rule #3 preserved.
- **D-21:** `render` + `lookup` re-run after `manual_edit`. NEAREST upscale preserved. Cost ~3-5s = budget. No selective per-barony render in Phase 8.
- **D-22:** `original_idx` for new baronies = branch metadata high-water-mark + 1. Freed idx never reused.
- **D-23:** Cache key = `(project_id, branch_id, stage, version_token)`. Branch switch = cache hit if branch was generated. Phase 04 D-03 "latest+prior" policy applies per `(project_id, branch_id)` pair. No LRU in Phase 8.
- **D-24:** Coast = landmask boundary (synonym). Not a separate layer. PT/ES border stays read-only.

**Undo + topology + UX**
- **D-25:** Wire `zundo` `temporal` middleware, **editor ops only** (vertex move/add/delete, polygon split/merge, translate). Excluded: branch switch, snapshot create, Phase 04 sliders. Ctrl+Z / Ctrl+Shift+Z. History cap ~100 ops. Cleared on branch switch.
- **D-26:** Topology block: self-intersect + neighbour gap. Shapely `is_valid` + `touches`. Drag rejected on mouseup if invalid; handle/edge red during invalid drag; snaps back.
- **D-27:** Warn (non-blocking): duplicate vertex within 1e-6, sliver polygons <0.001° area. Yellow badge.
- **D-28:** Snap to neighbour vertex within 5px + neighbour edge. Yellow circle on target. Hold Alt to disable for current drag.
- **D-29:** Click vertex selects; Shift-click adds; marquee selects within rect. Multi-select crosses territories. Delete removes all in one undoable op.
- **D-30:** Shared vertex moves together across all baronies — default and only behaviour. Snap (D-28) guarantees identification.
- **D-31:** Hover shared edge → purple highlight + endpoint vertex enlargement.
- **D-32:** Keyboard: V/A/D/S/M/Esc + Ctrl+Z/Y + Del. No custom rebind in Phase 8.
- **D-33:** Drag tooltip: `(lat, lon)` float 6 decimals, follows cursor. No pixel readout.
- **D-34:** 60fps drag up to ~5k visible handles. Viewport culling: skip outside viewport + 10% margin. Drag updates throttled to 16ms via RAF. No LOD in Phase 8.
- **D-35:** Edit ops logged to `edit_events` table `(timestamp, project_id, branch_id, op_type, payload_json)`. Local-only, no external transmission.
- **D-36:** Desktop-only. UA detect → "Desktop required" banner. Touch deferred.
- **D-37:** Auto-save = auto-snapshot every 25 edits (snapshot IS the save). `localStorage` stores `active_branch_id`. Worst-case crash = <25 edits lost.

### Claude's Discretion

- Exact CSS for purple shared-edge highlight, yellow snap circle, red invalid-drag glow (UI-SPEC already specifies hex values — planner takes UI-SPEC verbatim).
- Toolbar tool icons and help-panel layout (UI-SPEC pins; UX-checker refines).
- Decimal precision of intermediate coord computation (tooltip fixed at 6; storage precision is planner's call but must not regress GeoJSON round-trip).
- "Apply landmask" primary (filled) vs secondary (outlined) — UI-SPEC picks `outline` (secondary).
- Branch-picker dropdown showing `(N edits since snapshot)` per row — UI-SPEC says YES include.
- Undo-history sentinel structure inside zundo's `partialize` — planner picks diff representation as long as ops round-trip.

### Deferred Ideas (OUT OF SCOPE)

- 3-way geometric branch merge (branch merge is replace-only, D-14).
- Mobile/touch support (D-36).
- LOD / zoom-gated handle visibility.
- Selective per-barony incremental lookup re-render (D-21 picks full).
- Custom keybind rebinding UI.
- Hierarchy-tier toggle (edit at condado tier directly).
- Cross-condado merge guardrail (D-09 allows; add later if breaks hierarchy in practice).
- Telemetry export bundle for bug reports (D-35 keeps local).
- LRU cache eviction beyond `latest+prior` per branch.

</user_constraints>

<phase_requirements>
## Phase Requirements (proposed REQ-IDs — planner to ratify)

REQUIREMENTS.md is empty for Phase 8 at research time. This table maps proposed REQ-IDs to the 37 locked decisions and the research findings that support them.

| Proposed ID | Description | Source Decision(s) | Research Support |
|----|-------------|------|------------------|
| **EDIT-VERTEX-01** | User can drag a single vertex; mouseup commits if topology valid, snaps back if not | D-01, D-26, D-30 | §Standard Stack (Shapely `is_valid`); §Architecture Patterns (Konva drag + topology callback); §Code Examples (Shapely validate) |
| **EDIT-VERTEX-02** | User can click on an edge to add a new vertex; disabled at 1000-vertex cap | D-01, D-06 | §Architecture Patterns (Konva edge hit detection); §Don't Hand-Roll (use Shapely `Point.distance(LineString)`) |
| **EDIT-VERTEX-03** | User can select and delete vertices (single or multi-select); marquee, Shift-click supported | D-01, D-29 | §Architecture Patterns (Konva selection); §Code Examples (multi-select delete as one undo op) |
| **EDIT-VERTEX-04** | Douglas-Peucker simplify with live vertex-count preview; tolerance slider 0.00001–0.01 | D-01 | §Standard Stack (Shapely `simplify`); §Code Examples |
| **EDIT-VERTEX-05** | Drag tooltip shows `(lat, lon)` 6-decimal monospace following cursor | D-33 | §Architecture Patterns (DOM overlay, not Radix Tooltip — Konva canvas constraint) |
| **EDIT-POLYGON-01** | User can split a polygon by drawing a 2-point line cut; child auto-inherits parent condado; `original_idx = max+1` | D-02, D-07, D-22 | §Standard Stack (`shapely.ops.split`); §Pitfalls (#1) |
| **EDIT-POLYGON-02** | User can merge 2 adjacent baronies → winner = first-selected | D-02, D-08, D-09 | §Standard Stack (`shapely.unary_union`); §Pitfalls (#2 adjacency check) |
| **EDIT-POLYGON-03** | User can drag polygon interior to translate; shared vertices coupled | D-02, D-30 | §Architecture Patterns (shared-vertex coupling via Shapely STRtree) |
| **LANDMASK-01** | Landmask editable as single polygon; PT/ES border read-only | D-04, D-24 | §Pitfalls (#3 — PT/ES border identification) |
| **LANDMASK-02** | Two modes (Manual = batch + Apply button; Auto-immediate = drag triggers full cascade) | D-05 | §Architecture Patterns (mode state in useEditorStore) |
| **BRANCH-01** | Project has named branches (create/switch/rename/delete); `main` is default + delete-protected | D-10, D-11, D-13, D-15 | §Standard Stack (SQLAlchemy 2.0 models); §Code Examples |
| **BRANCH-02** | Auto-snapshot every 25 edits + manual "Snapshot now"; snapshots are sub-timeline per branch | D-10, D-37 | §Architecture Patterns (op-counter in useEditorStore subscribes to temporal) |
| **BRANCH-03** | Branch storage = complete snapshot blob (GeoJSON + RegionConfig + edit-op log); no patch-replay | D-12 | §Standard Stack (gzip+JSON or zstandard); §Don't Hand-Roll (use stdlib `gzip`) |
| **BRANCH-04** | "Copy <branch> → main" wholesale-replaces main after confirmation | D-14 | — |
| **BRANCH-05** | Export ZIP snapshots active branch; manifest extends with `branch_name` + `snapshot_id` + `snapshot_timestamp` | D-16 | §Pitfalls (#4 — manifest schema bump + Phase 06 parity test compat) |
| **DAG-01** | New pipeline stage `manual_edit` slots between `merge` and `hierarchy`; downstream re-runs; upstream cached | D-17 | §Architecture Patterns (DAG insertion); §Pitfalls (#5 — `STAGE_TOKEN_OVERRIDES` for non-cfg derivation) |
| **DAG-02** | `manual_edit.version_token = sha256(stage_name + edit_op_count + sha256(edit_op_log))`; empty log = identity | D-18 | §Architecture Patterns (token derivation extension) |
| **DAG-03** | Slider change while edits exist → auto-snapshot + confirmation modal | D-19 | §Architecture Patterns (frontend DAG diff detection) |
| **DAG-04** | Landmask edit invalidates `landmask` stage → full per-country KD-tree rebuild cascade | D-20 | §Pitfalls (#3 — KD-tree per country, CLAUDE.md Rule #3) |
| **DAG-05** | Cache key extended to `(project_id, branch_id, stage, version_token)`; LRU stays at `latest+prior` per branch | D-23 | §Architecture Patterns (cache signature change); §Pitfalls (#6 — all callsites must update) |
| **TOPO-01** | Self-intersect and neighbour gap are blocking; drag rejected on mouseup; visual red feedback during invalid drag | D-26 | §Standard Stack (Shapely `is_valid`, `touches`); §Code Examples |
| **TOPO-02** | Duplicate vertex (1e-6) + sliver polygon (<0.001°) are non-blocking warnings (yellow badge) | D-27 | §Standard Stack (Shapely `area`) |
| **TOPO-03** | Auto-snap to neighbour vertex/edge within 5px; Alt disables for current drag | D-28 | §Architecture Patterns (scipy `KDTree` for vertex set; Shapely `STRtree` for edges); §Pitfalls (#7 — screen-px → world-coord) |
| **TOPO-04** | Shared vertex (coincident within snap tolerance) moves in all adjacent baronies simultaneously | D-30 | §Architecture Patterns (build shared-vertex index on edit-mode entry, refresh on mouseup) |
| **PERF-01** | 60fps drag up to ~5k visible vertex handles; viewport culling + 10% margin; RAF throttle 16ms | D-34 | §Pitfalls (#8 — Konva per-node overhead; sceneFunc alternative noted but not required by D-34) |
| **PERSIST-01** | SQLite tables `branches`, `snapshots`, `edit_events` created via existing `Base.metadata.create_all` lifecycle | D-10, D-12, D-35 | §Standard Stack (SQLAlchemy 2.0 mapped_column); §Code Examples |
| **PERSIST-02** | Auto-save = auto-snapshot every 25 edits; `localStorage` stores `active_branch_id`; worst-case crash <25 edits lost | D-37 | §Architecture Patterns (op-counter trigger) |
| **UX-01** | Keyboard shortcuts V/A/D/S/M/Esc + Ctrl+Z/Ctrl+Shift+Z + Del; canvas-focused only | D-25, D-32 | §Architecture Patterns (extend `useKeyboardShortcuts`, no v1 restoration per D-V3-04) |
| **UX-02** | Desktop-only — "Desktop required" banner on touch-primary UA | D-36 | §Code Examples (UA detection one-liner) |
| **UNDO-01** | zundo `temporal` middleware wraps `useEditorStore`; scope = vertex/polygon ops only; history cleared on branch switch | D-25 | §Standard Stack (zundo 2.3.0); §Code Examples (partialize + diff) |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

The planner MUST verify compliance with these directives — they have authority equal to locked CONTEXT.md decisions.

| # | Constraint | Phase 8 Touchpoint |
|---|-----------|---------------------|
| 1 | **NEAREST upscale only** for lookup PNGs | D-21 — `render` re-run after `manual_edit` must call `Image.NEAREST` (existing `render.py` already does; do not regress) |
| 2 | **σ ∈ [3.0, 4.5]** for smoothing | Not directly touched by Phase 8 (smooth stage is upstream of manual_edit), but Phase 8 must not change `smooth.py` |
| 3 | **KD-trees per country**, never global | D-20 — landmask edit triggers per-country KD-tree rebuild; preserve `voronoi.py` per-country structure |
| 4 | **`original_idx` in every territory** | D-22, D-08, EDIT-POLYGON-01 — every new barony from split gets unique high-water-mark `original_idx`; merge winner keeps `original_idx`, loser's idx is freed but never reused |
| 5 | **`ocean=-1`, `ignore=9999` sentinels** in median pass | Not directly touched; preserve in cleanup stages |
| 6 | **2x masks are independent renders** at 3840×2160 | Preserved by D-21 (full re-render after edits, no upscale of lookup) |
| 7 | **`byOriginalIdx` on Unity side** | D-22 high-water-mark guarantees uniqueness; export manifest D-16 must not break Phase 06 schema for this |
| - | **Tech stack lock**: Python 3.11+ / FastAPI / SQLite / React 19 / TypeScript / Vite 6 / Konva.js / Zustand v5 / zundo 2.3.0 / TanStack Query v5 / Radix UI Themes 3.x / Shapely / scipy | Phase 8 introduces NO new top-level deps. `zundo` is already in `package.json` (pinned 2.3.0, Phase 04 planted). Shapely 2.0.x already in `pyproject.toml`. |
| - | **GSD Workflow Enforcement**: file edits go through GSD commands | Plans land via `/gsd-execute-phase` waves |
| - | **No `sys.modules` patching / no `importlib.reload`** | `manual_edit` stage extends DAG cleanly; no module re-import |
| - | **No hand-rolled compound undo** — `zundo` `temporal` + `partialize` + `diff` is the contract | D-25 follows verbatim |
| - | **No upscale interpolation** (Rule #1 echoed in NOT list) | D-21 preserves |
| - | **No global Voronoi** | D-20 preserves |
| - | **No v1 code resurrection** (PROJECT.md D-V3-04) | `VertexEditLayer`, `useEditorStore`, `useEditKeyboardMap`, `useUndoShortcut` are NEW files written from scratch (UI-SPEC §Notes #1) |

**Karpathy skill (`.claude/skills/karpathy/SKILL.md`)** — auto-loaded. Direct touchpoints for Phase 8: (a) D-21 "no selective per-barony render in Phase 8 (don't optimise hypothetically)"; (b) D-34 "no LOD in Phase 8" — viewport culling only, add LOD if measured-slow; (c) every new file should trace to a locked decision; (d) tests with descriptive names + explicit numeric fixtures (user feedback memory).

## Standard Stack

### Core (backend)
| Library | Version (pinned) | Purpose | Why Standard |
|---------|------------------|---------|--------------|
| `shapely` | `>=2.0,<3.0` `[VERIFIED: pyproject.toml]` | Topology validation, polygon ops, geometric primitives | Industry-standard GEOS-backed Python geometry; already a project dep; Shapely 2.0 prepares geometries for vectorized ops |
| `scipy` | `>=1.13,<2.0` `[VERIFIED: pyproject.toml]` | `scipy.spatial.KDTree` for snap (D-28) + shared-vertex index (D-30) | Already used for Voronoi (`voronoi.py`); zero-cost reuse |
| `sqlalchemy` | `>=2.0,<2.1` `[VERIFIED: pyproject.toml]` | `branches`, `snapshots`, `edit_events` ORM models | Already used for `Project`, `LLMCredential`, `ResearchCache`; same `Base`, same `Mapped[..]` pattern |
| `aiosqlite` | `>=0.20,<0.22` `[VERIFIED: pyproject.toml]` | Async SQLite driver | Project default; `~/.medieval-forge/medieval_forge.db` |
| stdlib `hashlib` | py3.11 | `manual_edit.version_token` derivation per D-18 | Matches `dag.compute_version_token` pattern (sha256→16 hex) |
| stdlib `gzip` | py3.11 | Compress snapshot blobs (D-12, ~100KB GeoJSON per snapshot × 25-edit cadence per branch) | Stdlib avoids new dep; ~3-5× compression on GeoJSON is sufficient — `zstandard` would be ~7× but adds a dep |

### Core (frontend)
| Library | Version (pinned) | Purpose | Why Standard |
|---------|------------------|---------|--------------|
| `konva` | `^10.2.5` `[VERIFIED: package.json]` | `VertexEditLayer` rendering | Already in stack; Phase 03 5-layer pattern extends to 6 |
| `react-konva` | `^19.2.3` `[VERIFIED: package.json]` | React reconciliation for Konva nodes | Already in stack; React 19 + concurrent mode |
| `zustand` | `^5.0.12` `[VERIFIED: package.json]` | `useEditorStore` (tool, selection, vertices, edit-op log) | Project default |
| `zundo` | `^2.3.0` `[VERIFIED: package.json]` | `temporal` middleware around editor store (D-25) | Pinned by Phase 04; Phase 8 wires it. CLAUDE.md fixes zundo as the contract. |
| `@tanstack/react-query` | `^5.99.0` `[VERIFIED: package.json]` | Branch list query, snapshot timeline query, topology-validate mutation | Project default |
| `@radix-ui/themes` | `^3.3.0` `[VERIFIED: package.json]` | Dialog, Select, Slider, Toast (Toast exists per `@radix-ui/react-toast@^1.2.15`) | Project default; UI-SPEC §Component Inventory pins primitives |
| `@radix-ui/react-toast` | `^1.2.15` `[VERIFIED: package.json]` | Auto-snapshot toast "Snapshot N salvo automaticamente" (UI-SPEC §10) | Already in deps — UI-SPEC §10's caveat resolved here; do NOT add a new Toast dep |
| `use-debounce` | `^10.1.1` `[VERIFIED: package.json]` | Auto-snapshot trigger debounce + slider-conflict detection | Project default |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `shapely.ops.split` | shapely 2.x | Polygon split (D-02, EDIT-POLYGON-01) | Line-cuts-polygon (single call, returns GeometryCollection of pieces) |
| `shapely.ops.unary_union` | shapely 2.x | Polygon merge (D-02, EDIT-POLYGON-02) | Adjacent baronies merge into single MultiPolygon → take exterior |
| `shapely.STRtree` | shapely 2.x | Bulk spatial index for shared-vertex / shared-edge lookup (D-30, D-31) | Build once on edit-mode entry; refresh on mouseup |
| `shapely.simplify(tolerance, preserve_topology=True)` | shapely 2.x | Douglas-Peucker simplify (D-01, EDIT-VERTEX-04) | Toolbar simplify button; `preserve_topology=True` is non-negotiable to avoid breaking neighbours |
| `shapely.make_valid` | shapely 2.x | Repair self-intersection if backend ever needs to coerce (D-26 blocks at UI, so make_valid not used on hot path) | Only inside imports / migration paths — not the validation path |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `gzip` (snapshot blob compression) | `zstandard` | zstd is ~2× faster + ~2× higher ratio, but adds a dep. Snapshot writes are background (every 25 edits), gzip is fine. |
| stdlib `hashlib.sha256` for D-18 | `xxhash` | xxhash faster, but Phase 04 D-02 uses sha256 — consistency over speed (token is computed once per edit batch, not on hot path). |
| `scipy.spatial.KDTree` for shared-vertex snap | `shapely.STRtree` | KDTree is point-only and faster for nearest-vertex; STRtree handles edges + polygons. Use **both**: KDTree for D-28 vertex snap, STRtree for D-28 edge snap + D-31 hover. |
| WASM-Shapely (browser-side topology validation) | HTTP endpoint to Shapely server | WASM-Shapely adds ~3-5 MB to bundle for a single-user local tool. localhost round-trip is <2 ms — well under perceived-instant. **Decision: HTTP endpoint** `POST /api/v3/projects/{id}/editor/validate`. |
| Per-node `Konva.Circle` for 5k handles | Single `Konva.Shape` with custom `sceneFunc` | D-34 explicitly picked viewport culling only. Per-node Circle is simpler; viewport culling cuts visible count well below 5k in normal zoom. Custom sceneFunc deferred unless 60fps fails in measurement. |

**Installation:** No new dependencies. Every library listed above is already pinned in `pyproject.toml` or `frontend/package.json`. **`[VERIFIED: pyproject.toml + package.json]` — read 2026-05-26.**

**Version verification commands** (planner runs before declaring done):
```bash
python -c "import shapely; print(shapely.__version__)"   # expect 2.0.x
python -c "import scipy; print(scipy.__version__)"        # expect 1.13.x
node -p "require('konva/package.json').version"           # expect 10.2.5+
node -p "require('zundo/package.json').version"           # expect 2.3.0
```

## Architecture Patterns

### Recommended Module Layout (deltas only — preserves Phase 03/04 layout)

**Backend new files** (~6):
```
backend/medieval_forge/
├── services/pipeline/
│   ├── manual_edit.py             # NEW: stage compute + token override
│   └── topology.py                # NEW: Shapely is_valid+touches helpers
├── services/branches/             # NEW subpackage (mirrors services/export/)
│   ├── __init__.py
│   ├── service.py                 # CRUD: create/switch/rename/delete branch
│   └── snapshot.py                # serialize/deserialize snapshot blob (gzip GeoJSON+cfg+log)
├── api/v3/
│   ├── branches.py                # NEW: branch CRUD endpoints
│   └── editor.py                  # NEW: POST /editor/validate, POST /editor/apply
└── models.py                      # EXTEND: 3 new SQLAlchemy classes
```

**Backend modified files**:
```
services/pipeline/dag.py           # DAG_ORDER inserts 'manual_edit'; DAG_PARENTS update; STAGE_READS=frozenset()
                                    # NEW: STAGE_TOKEN_OVERRIDES dict (manual_edit derives from edit log, not cfg fields)
services/pipeline/cache.py         # cache_get/put/clear signatures gain branch_id
services/pipeline/__init__.py      # orchestrator slots manual_edit between merge and hierarchy
services/pipeline/contracts.py     # RegionConfig gains: manual_edit_log: list = [], branch_id: str | None
api/v3/render.py                   # /render builds cfg with active branch's edit log
api/v3/export.py                   # manifest gains branch_name + snapshot_id + snapshot_timestamp
main.py                            # mount api.v3.branches + api.v3.editor
```

**Frontend new files** (14 per UI-SPEC §Component Inventory) — see UI-SPEC §Component Inventory verbatim.

### Pattern 1: New DAG stage extension (`manual_edit`)

**What:** Insert a stage that doesn't derive its `version_token` from `RegionConfig` fields.

**When to use:** Any stage whose inputs come from outside `cfg` (here, the edit-op log persisted in `snapshots` table).

**Resolution to the "manual_edit breaks STAGE_READS" tension:**

```python
# backend/medieval_forge/services/pipeline/dag.py — EXTEND

# Phase 8: insert manual_edit between merge and hierarchy
DAG_ORDER: tuple[str, ...] = (
    "landmask", "border", "voronoi", "median", "fragment",
    "smooth", "merge", "manual_edit", "hierarchy",   # <-- inserted
    "render", "lookup", "metadata", "export",
)

# manual_edit reads NOTHING from cfg (its inputs are out-of-band)
STAGE_READS["manual_edit"] = frozenset()

# Override map for stages whose token cannot derive from cfg fields
# (only manual_edit in Phase 8; pattern reserved for future research-overlay sidecars)
STAGE_TOKEN_OVERRIDES: dict[str, Callable[[RegionConfig, Iterable[str]], str]] = {
    "manual_edit": _manual_edit_token,
}

def _manual_edit_token(cfg: RegionConfig, upstream_tokens: Iterable[str]) -> str:
    """D-18: token = sha256(stage + edit_op_count + sha256(edit_op_log)) + upstream."""
    log = cfg.manual_edit_log  # list of op dicts; empty list = pass-through identity
    log_hash = hashlib.sha256(json.dumps(log, sort_keys=True).encode()).hexdigest()
    parts = ["manual_edit", f"count={len(log)}", f"loghash={log_hash}"]
    for tok in sorted(upstream_tokens):
        parts.append(tok)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

DAG_PARENTS["manual_edit"] = ("merge",)
DAG_PARENTS["hierarchy"] = ("manual_edit",)  # was ("merge",)
```

The DAG walker in `pipeline/__init__.py` (`run_pipeline_incremental`) calls `STAGE_TOKEN_OVERRIDES.get(stage_name, compute_version_token)`.

**Why this pattern:** Preserves Phase 04 D-02 invariant (token derives from declared inputs) while permitting non-cfg input sources. Empty `cfg.manual_edit_log` produces a stable identity token → parity tests stay byte-equal (D-17 carry-forward).

### Pattern 2: Cache key extension `(project_id, branch_id, stage, version_token)`

**What:** Existing `_STAGE_CACHE[project_id][stage_name]` becomes `_STAGE_CACHE[(project_id, branch_id)][stage_name]`.

**When to use:** Every branch needs its own cache slice so branch switch = O(1) cache hit (D-23).

**Migration tactic — surgical, all-at-once:**

The grep above found these callsites that need updating in lockstep:
- `services/pipeline/cache.py` (`cache_get`, `cache_put`, `cache_clear_project` signatures)
- `services/pipeline/__init__.py` (orchestrator passes branch_id through)
- `api/v3/render.py` (reads active branch_id from request, passes to run_pipeline_incremental)
- `api/v3/generate.py` (full generate uses branch_id too — every project has at least `main` branch)
- `tests/unit/test_stage_cache.py` (rewrite to assert branch-scoped behaviour)
- `tests/integration/test_render_endpoint.py` (must pass branch_id)
- `tests/integration/test_render_cancel.py` (cancel-restore is per-branch)
- `tests/parity/test_iberia_868_render_default.py` (passes branch_id="main")

**Default branch convention:** Projects existing before Phase 8 get a `main` branch lazily on first read (one-time migration on first endpoint hit). New projects (Phase 02 `POST /projects/`) create `main` branch in the same transaction.

### Pattern 3: SQLAlchemy 2.0 mapped models for branches/snapshots/edit_events

**What:** Three new ORM classes added to `models.py`. Same `Mapped[..]` + `mapped_column` pattern as `Project` / `LLMCredential`.

**Schema** (planner refines field-by-field):

```python
# backend/medieval_forge/models.py — EXTEND
class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_idx_high_water: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # D-22
    edits_since_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)     # D-10 cadence counter
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_branch_project_name"),)

class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)   # 1, 2, 3, ... per branch
    blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # gzip(json(geojson + cfg + edit_log))
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)  # "auto" | "manual" | "pre_slider_change"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("branch_id", "seq", name="uq_snapshot_branch_seq"),)

class EditEvent(Base):
    __tablename__ = "edit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    op_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "vertex_move", "vertex_add", "split", "merge", etc.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
```

**Schema lifecycle:** `Base.metadata.create_all` in `main.py` lifespan handles creation on startup (existing pattern at `main.py:31`). No alembic migration needed (project uses `create_all` per `[VERIFIED: backend/medieval_forge/main.py:31]`).

### Pattern 4: zundo `temporal` middleware on `useEditorStore`

**What:** Wrap a Zustand store to gain undo/redo via past+future history stacks with diff-based partializing.

**When to use:** D-25 — editor ops only. Branch switch, snapshot create, Phase 04 sliders are NOT in this store.

**Pattern (`[CITED: github.com/charkour/zundo README, v2.x]`)**:

```typescript
// frontend/src/stores/useEditorStore.ts
import { create } from 'zustand';
import { temporal } from 'zundo';
import { diff as microDiff } from 'microdiff';  // optional — zundo accepts any diff fn

interface EditorState {
  activeTool: 'V' | 'A' | 'D' | 'S' | 'M' | null;
  selectedVertexIds: string[];
  vertices: Record<string, { lat: number; lon: number }>;  // canonical world coords
  editLog: EditOp[];
}

interface EditorActions {
  selectTool: (t: EditorState['activeTool']) => void;        // NOT undoable
  moveVertex: (id: string, lat: number, lon: number) => void; // UNDOABLE
  addVertex: ...
  // ...
}

export const useEditorStore = create<EditorState & EditorActions>()(
  temporal(
    (set) => ({ /* initial state + actions */ }),
    {
      partialize: (s) => ({ vertices: s.vertices, editLog: s.editLog }),
      // selectedVertexIds + activeTool excluded from history (D-25)
      limit: 100,                          // D-25 cap
      equality: (a, b) => a === b,         // shallow ref check; partialize already narrows
      // optional: handleSet hook to skip recording during snapshot restore
    }
  )
);

// Clear history on branch switch
export function switchBranch(branchId: string) {
  // ... fetch branch geojson, rehydrate vertices ...
  useEditorStore.temporal.getState().clear();
}
```

**API reference (verified):** `zundo`'s `temporal` exports a `temporal` proxy at `useStore.temporal.getState()` with `.undo()`, `.redo()`, `.clear()`, `pastStates`, `futureStates`. The `limit` option caps history length. `[CITED: zundo 2.3 README]`

### Pattern 5: Konva 60fps drag with viewport culling

**What:** D-34 says viewport culling + RAF batching. Implementation pattern:

```typescript
// VertexEditLayer.tsx
const VertexEditLayer: React.FC<Props> = ({ activeTerritoryId, vertices, viewport }) => {
  // Cull: only render handles within viewport + 10% margin (D-34)
  const visibleVertices = useMemo(() => {
    if (!viewport || !activeTerritoryId) return [];
    const margin = 0.1;
    const [x0, y0, x1, y1] = expandedBBox(viewport, margin);
    return vertices.filter(v => v.x >= x0 && v.x <= x1 && v.y >= y0 && v.y <= y1);
  }, [vertices, viewport, activeTerritoryId]);

  // Throttle drag updates to RAF (16ms)
  const dragRef = useRef<number | null>(null);
  const onDragMove = useCallback((id: string, x: number, y: number) => {
    if (dragRef.current != null) cancelAnimationFrame(dragRef.current);
    dragRef.current = requestAnimationFrame(() => {
      useEditorStore.getState().moveVertexPreview(id, x, y);
      dragRef.current = null;
    });
  }, []);

  return (
    <Layer listening={activeTerritoryId !== null}>
      {visibleVertices.map(v => (
        <Circle key={v.id} x={v.x} y={v.y} radius={5}
                fill={v.selected ? '#f0c040' : '#4a9eff'}
                draggable onDragMove={(e) => onDragMove(v.id, e.target.x(), e.target.y())}
                onDragEnd={(e) => commitDragEnd(v.id, e.target.x(), e.target.y())} />
      ))}
    </Layer>
  );
};
```

**Discipline:** Only call `useEditorStore.setState()` (which is the undoable path) on `onDragEnd`. `onDragMove` writes to a local preview state outside zundo's history (avoids 60 undo entries per drag).

**Set `listening: false` on the 5 read-only layers during drag** to bypass their hit-testing.

### Anti-Patterns to Avoid

- **Calling `useEditorStore.setState()` (the undoable path) on every `onDragMove`** — would create 60 entries per drag. Use a preview path + single commit on `onDragEnd`.
- **Storing pixel coords in the editor store** — D-33 says coord tooltip is `(lat, lon)`. Store world coords; project to pixels at render time. Otherwise zoom/pan breaks history.
- **Building one global `STRtree` across all baronies for shared-vertex lookup** — CLAUDE.md Rule #3 (KD-tree per country) — keep per-country index. Cross-country baronies cannot share vertices.
- **Re-deriving `original_idx` from any algorithm other than branch high-water-mark** — D-22 + Rule #4. Never reuse a freed idx (D-08 collision risk).
- **Using `shapely.simplify(preserve_topology=False)` for D-01** — would break shared edges with neighbours. Always `preserve_topology=True`.
- **Restoring deleted v1 `VertexHandlesLayer` / `useEditKeyboardMap`** — PROJECT.md D-V3-04 + UI-SPEC §Notes #1. Rebuild from scratch.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Topology validation (self-intersect, neighbour gap) | Custom polygon-intersection routines | `shapely.is_valid` + `polygon.touches(neighbour)` | GEOS-backed C++; vetted on millions of GIS workloads. Custom routines miss collinear edge cases, near-degeneracies, ring orientation. |
| Polygon split by line | Hand-rolled line-polygon cut | `shapely.ops.split(polygon, line)` | Handles tangencies, multi-piece results, holes, GeometryCollection unpacking. |
| Polygon merge | Manual edge stitching | `shapely.unary_union([p1, p2])` | Handles non-coincident vertices, sliver gaps, holes. |
| Douglas-Peucker simplify | Custom DP implementation | `shapely.simplify(tolerance, preserve_topology=True)` | `preserve_topology=True` is the key — homemade DP breaks shared edges. |
| Spatial index for shared-vertex/edge lookup | Naive O(n²) pairwise distance | `scipy.spatial.KDTree` (vertices) + `shapely.STRtree` (edges/polygons) | scipy KDTree is C; STRtree wraps GEOS R-tree. Both bulk-built once per edit session. |
| Undo/redo history | Custom action stack | `zundo` `temporal` middleware (already in package.json, pinned by CLAUDE.md as the contract) | Diff-based partializing, configurable limit, `clear()` for branch switch — exactly D-25's contract. |
| Snapshot blob compression | Custom binary format | stdlib `gzip` on `json.dumps` | 3-5× compression, zero deps, fast enough for background save. |
| Token derivation | New crypto routine | Reuse `services/pipeline/dag.compute_version_token` pattern + `STAGE_TOKEN_OVERRIDES` for non-cfg stages | Phase 04 D-02 already canonical. |
| WASM-Shapely browser-side validation | Bundle 3-5 MB WASM | HTTP `POST /api/v3/projects/{id}/editor/validate` to Shapely server | Localhost <2 ms; bundle stays slim. |
| Patch-replay branching | Operational-transform algorithms | D-12: each branch stores full snapshot blob | D-12 already locked. CRDT/OT is its own research project. |
| UA-based desktop detection | `navigator.userAgent` parsing | `navigator.maxTouchPoints > 0 && !window.matchMedia('(pointer: fine)').matches` | UI-SPEC §Notes #8 already pins; modern + reliable. |
| Toast / snapshot notification | New Toast library | `@radix-ui/react-toast` (already in package.json `^1.2.15` `[VERIFIED]`) | Resolves UI-SPEC §10's "check if Radix Themes v3 has Toast" question definitively. |

**Key insight:** Phase 8's geometric operations are 1-call-each in Shapely 2.x. The temptation to "make it more efficient" by hand-rolling will produce subtle topology bugs that the Reconquista pipeline's downstream stages will exhibit as visible Unity-side artifacts. GEOS has been hardened against these for 20 years.

## Common Pitfalls

### Pitfall 1: `original_idx` collision on branch switch + new split
**What goes wrong:** User splits a barony on branch `A` (gets `original_idx=93`), switches to branch `B`, splits another (also gets `original_idx=93` if high-water-mark is per-project). Two baronies with the same idx ship to Unity → Nájera bug repeats.
**Why it happens:** Per-project counter instead of per-branch.
**How to avoid:** D-22 mandates the high-water-mark counter live on the `branches` row (`Branch.original_idx_high_water`), not on `projects`. Each branch monotonically allocates within its own snapshot blob's metadata.
**Warning signs:** Unit test (numeric fixture): create project, create branch B, split barony on A → assert idx=93, switch to B, split → assert idx=93 (each branch has its own counter) → assert idx values exist in respective branch snapshot blobs only.

### Pitfall 2: Polygon merge across non-adjacent baronies
**What goes wrong:** UI doesn't block selection of two non-adjacent baronies in Merge tool. `unary_union` returns a `MultiPolygon` (two separate pieces) — pipeline downstream assumes single Polygon → render fails or produces invisible barony.
**Why it happens:** Adjacency check skipped because D-09 allows cross-condado merge.
**How to avoid:** Backend `/editor/apply` for merge op verifies `p1.touches(p2)` (Shapely) is True before persisting. UI shows brief "Territórios não são adjacentes" Callout (UI-SPEC §Merge Tool). Cross-condado merge is allowed (D-09); cross-non-adjacent merge is NOT.
**Warning signs:** Unit test (descriptive name): `test_merge_rejects_non_adjacent_baronies_with_specific_error_code`.

### Pitfall 3: PT/ES border identification in landmask edit
**What goes wrong:** D-04 says landmask is editable BUT PT/ES border stays read-only. If frontend lets user grab a vertex of the PT/ES border (because it visually overlaps with landmask boundary), the edit silently writes to landmask GeoJSON → CLAUDE.md Rule #3 (KD-tree per country) breaks (vertex doesn't move with country-aware routing).
**Why it happens:** Two overlapping polygon layers; pointer events go to whichever Konva node is hit last.
**How to avoid:** Render PT/ES border on a separate Konva node with `listening: false` (read-only). VertexEditLayer's handles for landmask are derived ONLY from landmask polygon, never PT/ES. PT/ES border length is **40 points, not 38** per Phase 01 STATE note ("Rule 1 deviation": CLAUDE.md mis-counted as 38) `[VERIFIED: STATE.md line 53]` — planner must use 40-point PT/ES polygon as the read-only baseline.
**Warning signs:** Integration test: edit landmask near PT/ES boundary → assert PT/ES polygon `is_geometrically_equal` to baseline pre-edit.

### Pitfall 4: Phase 06 manifest schema bump
**What goes wrong:** D-16 adds `branch_name`, `snapshot_id`, `snapshot_timestamp` to the manifest. Phase 06 parity test `tests/parity/test_iberia_868_yaml.py` (D-16 of Phase 06) asserts `manifest["validation_report"]["passed"] == true` and the `MANIFEST.json` schema is `schema_version: 2` (Phase 06 D-07). Naive additive change breaks pydantic strict-validation.
**Why it happens:** Phase 06's `ManifestSchema` model is `extra='forbid'` by default (pydantic v2 BaseModel) — adding 3 fields without bumping schema_version and updating the model = parity test failure.
**How to avoid:** Bump `MANIFEST_SCHEMA_VERSION` to `3` in `services/export/schemas.py`; extend `ManifestSchema` with optional `branch_name: str | None`, `snapshot_id: str | None`, `snapshot_timestamp: datetime | None` (None for projects with no Phase 8 branch state — backward-compat with Iberia gold path); update Phase 06 parity test to expect `schema_version: 3`.
**Warning signs:** Run `pytest backend/tests/e2e/test_export_gate_iberia.py` after manifest change — must still pass.

### Pitfall 5: `manual_edit` token derivation breaks STAGE_READS pattern
**What goes wrong:** D-18's token formula uses `edit_op_log` which is NOT a `RegionConfig` field. `dag.compute_version_token(stage, STAGE_READS["manual_edit"], cfg, upstream)` returns the same token for ALL edit log states → cache returns stale geometry → user thinks edits saved, sees old map.
**Why it happens:** Direct copy of Phase 04 pattern doesn't handle out-of-band inputs.
**How to avoid:** Add `STAGE_TOKEN_OVERRIDES: dict[str, Callable] = {"manual_edit": _manual_edit_token}` in `dag.py`. Walker checks override first. Either thread `cfg.manual_edit_log` field into `RegionConfig` (cleanest, keeps single-mutable-input invariant) OR keep override callback. **Recommendation: thread `manual_edit_log: list[dict]` into RegionConfig** — preserves D-V3-05 "RegionConfig is single mutable input" and lets the override stay a 1-liner reading from cfg.
**Warning signs:** Unit test: token for `manual_edit_log=[]` != token for `manual_edit_log=[{op:"move",...}]`; token is stable across runs for same log.

### Pitfall 6: Cache key extension blast radius
**What goes wrong:** Updating `cache_get(project_id, stage)` → `cache_get(project_id, branch_id, stage)` in one commit and missing a callsite = silent cache miss or `KeyError`.
**Why it happens:** 9 callsites identified via grep (see Pattern 2 list above).
**How to avoid:** Single atomic plan updates all 9 callsites + cache module signature + 3 test files in one commit. Pre-merge `pytest backend/tests/parity` MUST stay green.
**Warning signs:** CI parity job goes red.

### Pitfall 7: Screen-pixel snap tolerance ≠ world-coord tolerance
**What goes wrong:** D-28 says "snap within 5px". User zooms in 10× → snap should still be 5 screen-pixels = 0.5 world-pixels. Naive implementation hardcodes 5 world-pixels → snap becomes invisible at high zoom, wrong at low zoom.
**Why it happens:** Forgetting the screen-pixel ↔ world-coord conversion when scale changes.
**How to avoid:** Compute `snapWorldDist = 5 / stage.scaleX()` inside snap calculation. Frontend's existing `useZoomPan` exposes scale.
**Warning signs:** Manual UAT: zoom to 5× → snap should still feel 5px-radius from cursor.

### Pitfall 8: Konva per-node overhead at 5k handles
**What goes wrong:** Naive `<Circle/>` per vertex × 5k = 5k DOM-ish nodes in Konva's tree. `batchDraw` becomes slow.
**Why it happens:** Konva creates a render node per `Circle`. 60fps requires <16ms per frame.
**How to avoid:** D-34 picked viewport culling — typical visible count after culling is 200-800 (small region focus). If perf measurement shows >2000 visible handles in normal use, fallback is custom `<Shape sceneFunc={...}>` that draws all handles in one canvas pass. **Do NOT pre-optimize** (Karpathy #2). Phase 8 ships with `<Circle/>` per handle + viewport culling + RAF throttling; revisit only on measured fail.
**Warning signs:** Playwright UAT measures FPS via `requestAnimationFrame` deltas during a known-busy drag.

### Pitfall 9: Slider-conflict modal vs auto-snapshot race (D-19)
**What goes wrong:** D-19 says auto-snapshot fires FIRST, then modal opens. If snapshot save errors out, modal opens claiming "snapshot N saved" but the snapshot row doesn't exist → user clicks "Restore N" later → 500.
**Why it happens:** Naive sequential code without error handling.
**How to avoid:** Backend `POST /api/v3/projects/{id}/branches/{branch_id}/snapshot` returns 201 + `{snapshot_id, seq}`. Frontend ONLY shows modal if response is 201. On error, show error toast, do NOT proceed with slider change.
**Warning signs:** Integration test: simulated snapshot failure → assert modal does NOT open + slider value reverts.

### Pitfall 10: `Konva.clearCache()` discipline regression
**What goes wrong:** Phase 04 D-19 + CLAUDE.md "What v3 is NOT" mandates `Konva.clearCache()` on every layer after every geometric mutation. VertexEditLayer dragmove doesn't call it → stale cache from prior render shows behind handles.
**Why it happens:** Phase 03 set the discipline; Phase 8 adds a NEW layer that must honor it.
**How to avoid:** `VertexEditLayer` mount has `useEffect(() => { return () => stage.clearCache() }, [activeTerritoryId])`. Plus the existing CanvasViewer hook on `cacheVersion` change covers the swap-when-edit-commits case.
**Warning signs:** UAT: edit vertex, commit, observe artifacts behind handles → fail.

## Runtime State Inventory

Not applicable — Phase 8 is a greenfield additive feature (new stage + new tables + new layer). No rename / refactor / migration of existing identifiers.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — new tables only (`branches`, `snapshots`, `edit_events`). Existing `projects` table gains no new columns. | None |
| Live service config | None — no external service touches Phase 8 | None |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | None — `Base.metadata.create_all` lifecycle handles DDL on next startup; no Python package re-install needed | None |

**Verified by:** grep of codebase for any rename indicators (none); CONTEXT.md explicitly says "new pipeline DAG stage" + "SQLite gains 3 tables".

## Code Examples

### Shapely topology validate (D-26)
```python
# backend/medieval_forge/services/pipeline/topology.py
# Source: shapely.org/docs/manual.html#object.is_valid
from shapely.geometry import Polygon
from shapely.validation import explain_validity

def validate_edit(
    target: Polygon,
    neighbours: list[Polygon],
) -> tuple[bool, str | None]:
    """D-26: returns (valid, error_code) for a single barony post-edit.

    Blocking errors:
      - target is invalid (self-intersection): SELF_INTERSECT
      - target doesn't touch a neighbour it did before (gap): NEIGHBOUR_GAP
    """
    if not target.is_valid:
        return False, "SELF_INTERSECT"
    for n in neighbours:
        # Neighbour must still share an edge (touches) — disjoint = gap
        if target.disjoint(n):
            return False, "NEIGHBOUR_GAP"
    return True, None
```
`[VERIFIED: Shapely 2.0 API — is_valid, disjoint, touches all stdlib]`

### Shapely polygon split (D-02, EDIT-POLYGON-01)
```python
# Source: shapely.org/docs/manual.html#shapely.ops.split
from shapely.geometry import LineString, Polygon
from shapely.ops import split as shapely_split

def split_barony(polygon: Polygon, cut: LineString) -> list[Polygon]:
    """Return the pieces produced by cutting polygon with the 2-point line."""
    result = shapely_split(polygon, cut)  # GeometryCollection
    pieces = [g for g in result.geoms if isinstance(g, Polygon) and g.area > 0]
    if len(pieces) != 2:
        raise ValueError(f"split produced {len(pieces)} pieces; expected 2")
    return pieces
```

### zundo `useEditorStore` with branch-clear
```typescript
// frontend/src/stores/useEditorStore.ts
// Source: github.com/charkour/zundo v2.3 README + Phase 04 patterns
import { create } from 'zustand';
import { temporal } from 'zundo';

export const useEditorStore = create<EditorState & EditorActions>()(
  temporal(
    (set, get) => ({
      activeTool: null,
      selectedVertexIds: [],
      vertices: {},
      editLog: [],
      moveVertex: (id, lat, lon) => set((s) => ({
        vertices: { ...s.vertices, [id]: { lat, lon } },
        editLog: [...s.editLog, { op: 'move', id, lat, lon, ts: Date.now() }],
      })),
      // ... other undoable actions ...
    }),
    {
      partialize: (s) => ({ vertices: s.vertices, editLog: s.editLog }),
      limit: 100,
    }
  )
);

export function switchBranch(branchSnapshot: BranchSnapshot) {
  useEditorStore.setState({
    vertices: branchSnapshot.vertices,
    editLog: branchSnapshot.editLog,
    selectedVertexIds: [],
    activeTool: null,
  });
  useEditorStore.temporal.getState().clear();  // D-25 history cleared on branch switch
}
```

### UA detection for desktop-required banner (D-36)
```typescript
// Source: developer.mozilla.org navigator.maxTouchPoints + matchMedia('(pointer:fine)')
export function isDesktopRequired(): boolean {
  if (typeof window === 'undefined') return false;
  return navigator.maxTouchPoints > 0
      && !window.matchMedia('(pointer: fine)').matches;
}
```

### SQLAlchemy 2.0 Branch CRUD
```python
# backend/medieval_forge/services/branches/service.py
# Source: sqlalchemy.org 2.0 docs — async select/insert patterns; matches existing services/credential_store.py shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Branch

async def create_branch(db: AsyncSession, project_id: str, name: str, parent_branch_id: str | None) -> Branch:
    branch = Branch(project_id=project_id, name=name, is_main=(name == "main"))
    if parent_branch_id:
        parent = (await db.execute(select(Branch).where(Branch.id == parent_branch_id))).scalar_one()
        branch.original_idx_high_water = parent.original_idx_high_water  # inherit (D-22)
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch
```

## State of the Art

| Old Approach (v1 / pre-Phase 8) | Current (Phase 8) | When Changed | Impact |
|---------------------------------|--------------------|--------------|--------|
| v1 `VertexHandlesLayer` (deleted in Phase 03) | New `VertexEditLayer` from scratch | Phase 03 cleanup → Phase 8 rebuild | PROJECT.md D-V3-04: no v1 code resurrection |
| Phase 04 stage cache `(project_id, stage)` | Phase 8 stage cache `(project_id, branch_id, stage)` | Phase 8 D-23 | All callsites updated atomically |
| Phase 04 D-15 zundo deferred | Phase 8 D-25 wires zundo `temporal` (editor ops only) | Phase 8 | First zundo use; cross-stage compound undo still deferred |
| Phase 06 MANIFEST schema_version=2 | Phase 8 MANIFEST schema_version=3 (adds `branch_name`, `snapshot_id`, `snapshot_timestamp`) | Phase 8 D-16 | Phase 06 parity test extended |
| 11-stage DAG (Phase 03) → 12-stage (Phase 04 cleanup split) | 13-stage (Phase 8 inserts `manual_edit`) | Phase 8 D-17 | DAG_ORDER tuple grows by 1; `hierarchy` parents change from `merge` to `manual_edit` |

**Deprecated/outdated:**
- v1 `useEditKeyboardMap`, `useUndoShortcut` — NOT to be restored (PROJECT.md D-V3-04 + UI-SPEC §Notes #1).
- WASM-Shapely browser-side validation — considered, rejected (bundle cost vs HTTP <2ms localhost).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Base.metadata.create_all` will pick up the 3 new SQLAlchemy models on next FastAPI startup without explicit migration | Pattern 3 | Existing projects on dev machines won't see new tables until they delete `~/.medieval-forge/medieval_forge.db` or run a one-off DDL — needs a startup-time `CREATE TABLE IF NOT EXISTS` (which `create_all` does by default `[VERIFIED: SQLAlchemy 2.0 docs]`, so this is verified — risk LOW) |
| A2 | `microdiff` is the right diff library for zundo if planner wants diff-based partialize | Pattern 4 | Planner may pick built-in `Object.is` equality + full state snapshots (zundo's default). Both work. |
| A3 | Snapshot blob size ~100 KB compressed for a typical Iberia branch (post-edit GeoJSON + cfg + edit_log) | Pattern 3 / Pitfall — | If blobs reach MB-scale (large branches with thousands of edits), SQLite BLOB performance degrades. Mitigation: zstd compression upgrade. |
| A4 | Topology validation can run server-side under 20ms per drag commit (single Shapely `is_valid` + N neighbour `touches` for typical N≤6) | Don't Hand-Roll | If slow, debounce commit by 100ms or move validation client-side via simpler signed-area self-intersection check. |
| A5 | Konva 5k-handle 60fps achievable with viewport culling + RAF only (no sceneFunc rewrite) | Pitfall 8 | If measurement fails, fallback is `<Shape sceneFunc>` consolidation — additional ~2 days of planning work. |

**These 5 assumptions need user/planner confirmation before locking.** All other claims in this research are `[VERIFIED]` or `[CITED]`.

## Open Questions

1. **`manual_edit_log` placement: in `RegionConfig` or sidecar?**
   - What we know: D-V3-05 says RegionConfig is the single mutable input. Adding `manual_edit_log: list[dict]` as a field is the cleanest extension.
   - What's unclear: edit logs can grow to MB; passing a fat cfg through every cache lookup wastes memory.
   - Recommendation: thread `manual_edit_log_hash: str` into RegionConfig (16 hex chars). Full log lives in `snapshots` table. `_manual_edit_token` consumes the hash directly. Resolves Pitfall 5 cleanly.

2. **Apply landmask cascade — sync or background job?**
   - What we know: D-20 says full cascade. D-05 Auto-immediate mode triggers per-drag. ~10s/edit on Iberia 868.
   - What's unclear: 10s blocking is bad UX even in Auto mode. Should the cascade run as a background SSE-streamed task (reusing Phase 04 `_RUN_QUEUES` pattern)?
   - Recommendation: yes — reuse the Phase 04 single-flight + SSE infrastructure. Add `landmask` to the events the frontend listens for. Planner confirms.

3. **Snapshot restoration UI: timeline scrubber or list?**
   - What we know: D-10 says "surfaced as a sub-timeline".
   - What's unclear: UI-SPEC doesn't enumerate the snapshot list/scrubber component.
   - Recommendation: defer to planner / ui-checker. Likely a `Card` listing snapshots reverse-chronologically with "Restore" button each. Defer scrubber until UAT asks.

4. **Branch limit per project?**
   - What we know: D-23 says no LRU in Phase 8 — cache grows linearly per branch.
   - What's unclear: should there be a hard cap (e.g., 10 branches/project) to prevent runaway disk use?
   - Recommendation: no hard cap in Phase 8. Surface count in branch picker; let user observe. Add limit later if measured-problem.

5. **Topology validate endpoint: per-drag-commit or batch?**
   - What we know: D-26 says validation on mouseup.
   - What's unclear: marquee-delete of N vertices = N round-trips OR one batch?
   - Recommendation: batch. `POST /editor/validate` accepts a list of post-edit polygons; returns per-polygon valid/code. Frontend sends one request per atomic edit (1 vertex move = 1 request; marquee delete of N = 1 request).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Backend stage + endpoints | ✓ | per pyproject `requires-python = ">=3.11"` | — |
| shapely 2.0.x | Topology + split + simplify + STRtree | ✓ | `>=2.0,<3.0` in pyproject | — |
| scipy 1.13.x | KDTree for snap + shared-vertex | ✓ | `>=1.13,<2.0` in pyproject | — |
| sqlalchemy 2.0.x | New models | ✓ | `>=2.0,<2.1` in pyproject | — |
| aiosqlite 0.20+ | Async SQLite | ✓ | `>=0.20,<0.22` in pyproject | — |
| konva 10.2.5 | VertexEditLayer | ✓ | `^10.2.5` in package.json | — |
| react-konva 19.2.3 | React reconciliation | ✓ | `^19.2.3` in package.json | — |
| zundo 2.3.0 | temporal middleware | ✓ | `^2.3.0` in package.json (pinned by CLAUDE.md) | — |
| @radix-ui/themes 3.3.0 | Dialog / Select / Slider / Toast | ✓ | `^3.3.0` in package.json | — |
| @radix-ui/react-toast 1.2.15 | Auto-snapshot toast | ✓ | `^1.2.15` in package.json | — |
| Playwright | UAT (FPS measurement, branch picker flow) | ✓ | per devDeps `^1.59.1` | — |
| Reconquista Maps dir (parity ground truth) | Parity tests | Assumed present at `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` | — | Skip parity test with explicit marker if absent on agent machine |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

Phase 8 ships with zero new dependencies. All Verified 2026-05-26 via direct read of `pyproject.toml` and `frontend/package.json`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.x + pytest-asyncio 0.23 (asyncio_mode = auto) — `[VERIFIED: pyproject.toml]` |
| Backend config | `pyproject.toml` `[tool.pytest.ini_options]` (markers: unit/parity/integration/uat/e2e/slow/anthropic) |
| Frontend framework | vitest 3.2.4 + Testing Library |
| Frontend config | `frontend/vite.config.ts` (existing) |
| UAT framework | Playwright 1.59.1 |
| Quick run (backend unit) | `pytest backend/tests/unit -m unit -x` |
| Quick run (frontend) | `cd frontend && npm test -- --run` |
| Full backend suite | `pytest backend/tests` |
| Full frontend suite | `cd frontend && npm test -- --run && npm run test:e2e` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EDIT-VERTEX-01 | move + topology validate + snap-back | unit (backend) | `pytest backend/tests/unit/test_topology_validate.py -x` | ❌ Wave 0 |
| EDIT-VERTEX-01 | drag UX | uat | `playwright test tests/uat/08-vertex-drag.spec.ts` | ❌ Wave 0 |
| EDIT-VERTEX-02 | add vertex; cap at 1000 | unit (frontend) | `npm test -- VertexEditLayer.test.tsx` | ❌ Wave 0 |
| EDIT-VERTEX-03 | multi-select delete as one undo | unit (frontend) | `npm test -- useEditorStore.test.ts` | ❌ Wave 0 |
| EDIT-VERTEX-04 | DP simplify with explicit vertex-count fixtures | unit (backend) | `pytest backend/tests/unit/test_manual_edit_simplify.py -x` | ❌ Wave 0 |
| EDIT-POLYGON-01 | split via Shapely ops.split, explicit-numeric fixture | unit (backend) | `pytest backend/tests/unit/test_manual_edit_split.py -x` | ❌ Wave 0 |
| EDIT-POLYGON-02 | merge + adjacency block | unit (backend) | `pytest backend/tests/unit/test_manual_edit_merge.py -x` | ❌ Wave 0 |
| EDIT-POLYGON-03 | translate + shared-vertex coupling | unit (backend) | `pytest backend/tests/unit/test_shared_vertex_coupling.py -x` | ❌ Wave 0 |
| LANDMASK-01 | edit landmask without touching PT/ES (Pitfall 3) | integration | `pytest backend/tests/integration/test_landmask_edit.py -x` | ❌ Wave 0 |
| LANDMASK-02 | manual + auto-immediate modes cascade correctly | integration | same file | ❌ Wave 0 |
| BRANCH-01..05 | CRUD + main protection + copy-to-main + manifest extension | integration | `pytest backend/tests/integration/test_branches_endpoint.py -x` | ❌ Wave 0 |
| DAG-01 | manual_edit slot + downstream cascade | unit | `pytest backend/tests/unit/test_dag_manual_edit.py -x` | ❌ Wave 0 |
| DAG-02 | token derivation: empty log = identity, non-empty = stable | unit | same file | ❌ Wave 0 |
| DAG-03 | slider-conflict auto-snapshot + modal | uat | `playwright test tests/uat/08-slider-conflict.spec.ts` | ❌ Wave 0 |
| DAG-04 | landmask edit triggers per-country KD-tree rebuild | integration | `pytest backend/tests/integration/test_landmask_cascade.py -x` | ❌ Wave 0 |
| DAG-05 | cache key includes branch_id; branch switch = cache hit | unit | `pytest backend/tests/unit/test_stage_cache_branch.py -x` | ❌ Wave 0 (rewrite of existing test_stage_cache.py) |
| TOPO-01 | self-intersect + neighbour gap block | unit (backend) | `pytest backend/tests/unit/test_topology_validate.py -x` | ❌ Wave 0 |
| TOPO-02 | duplicate vertex + sliver warn (yellow badge) | unit (frontend) | `npm test -- VertexCapBadge.test.tsx` | ❌ Wave 0 |
| TOPO-03 | snap behavior — KDTree + STRtree, screen→world scaling (Pitfall 7) | unit (frontend) | `npm test -- snap.test.ts` | ❌ Wave 0 |
| TOPO-04 | shared vertex move couples across neighbours | unit (frontend) | `npm test -- sharedVertex.test.ts` | ❌ Wave 0 |
| PERF-01 | 60fps drag with 5k handles + viewport culling | uat (manual + automated FPS sample) | `playwright test tests/uat/08-perf-drag-60fps.spec.ts` — measures rAF deltas; flag as manual confirmation gate if CI is unreliable | ❌ Wave 0 |
| PERSIST-01 | DDL via metadata.create_all | unit | `pytest backend/tests/unit/test_models_branches.py -x` | ❌ Wave 0 |
| PERSIST-02 | snapshot blob roundtrip + edit-event log | integration | `pytest backend/tests/integration/test_snapshot_persistence.py -x` | ❌ Wave 0 |
| UX-01 | keyboard shortcuts canvas-focused only | unit (frontend) | `npm test -- useKeyboardShortcuts.test.ts` | ❌ Wave 0 |
| UX-02 | desktop-only banner UA gate | unit (frontend) | `npm test -- DesktopRequiredBanner.test.tsx` | ❌ Wave 0 |
| UNDO-01 | zundo temporal: history cap, branch-switch clear, scope | unit (frontend) | `npm test -- useEditorStore.test.ts` | ❌ Wave 0 |
| Phase 04 parity preservation | `manual_edit` with empty log = byte-equal Iberia output | parity | `pytest backend/tests/parity/test_iberia_868.py` (extended) | ✅ exists; needs assertion added |
| Phase 06 manifest schema_version=3 | Iberia gate stays green with new fields | parity | `pytest backend/tests/parity/test_iberia_868_yaml.py` | ✅ exists; needs `schema_version: 3` update |

### Sampling Rate (Nyquist)
- **Per task commit:** `pytest backend/tests/unit -m unit -x && cd frontend && npm test -- --run` (~30s)
- **Per wave merge:** Full unit + integration suite for changed package + parity smoke
- **Phase gate:** Full suite (unit + integration + parity + UAT) green before `/gsd-verify-work`

### Wave 0 Gaps
Test scaffolds to land BEFORE Wave 1 implementation (skip-marked, no production import dependency):

**Backend (15 files):**
- [ ] `backend/tests/unit/test_topology_validate.py` — covers EDIT-VERTEX-01, TOPO-01
- [ ] `backend/tests/unit/test_manual_edit_simplify.py` — covers EDIT-VERTEX-04
- [ ] `backend/tests/unit/test_manual_edit_split.py` — covers EDIT-POLYGON-01
- [ ] `backend/tests/unit/test_manual_edit_merge.py` — covers EDIT-POLYGON-02
- [ ] `backend/tests/unit/test_shared_vertex_coupling.py` — covers EDIT-POLYGON-03
- [ ] `backend/tests/unit/test_dag_manual_edit.py` — covers DAG-01, DAG-02
- [ ] `backend/tests/unit/test_stage_cache_branch.py` — covers DAG-05 (rewrites existing `test_stage_cache.py`)
- [ ] `backend/tests/unit/test_models_branches.py` — covers PERSIST-01
- [ ] `backend/tests/integration/test_branches_endpoint.py` — covers BRANCH-01..05
- [ ] `backend/tests/integration/test_landmask_edit.py` — covers LANDMASK-01, LANDMASK-02
- [ ] `backend/tests/integration/test_landmask_cascade.py` — covers DAG-04
- [ ] `backend/tests/integration/test_snapshot_persistence.py` — covers PERSIST-02
- [ ] `backend/tests/integration/test_editor_validate_endpoint.py` — covers Pitfall 5 batch endpoint
- [ ] `backend/tests/integration/test_render_with_branch.py` — covers render endpoint signature change
- [ ] `backend/tests/parity/test_iberia_868.py` extension — assert manual_edit identity pass-through

**Frontend (10 files):**
- [ ] `frontend/src/stores/__tests__/useEditorStore.test.ts` — covers UNDO-01, EDIT-VERTEX-03
- [ ] `frontend/src/components/canvas/__tests__/VertexEditLayer.test.tsx` — covers EDIT-VERTEX-02
- [ ] `frontend/src/components/editor/__tests__/BranchPicker.test.tsx` — covers BRANCH-01
- [ ] `frontend/src/components/editor/__tests__/VertexCapBadge.test.tsx` — covers TOPO-02
- [ ] `frontend/src/lib/__tests__/snap.test.ts` — covers TOPO-03 (Pitfall 7)
- [ ] `frontend/src/lib/__tests__/sharedVertex.test.ts` — covers TOPO-04
- [ ] `frontend/src/hooks/__tests__/useKeyboardShortcuts.test.ts` (extension) — covers UX-01
- [ ] `frontend/src/components/__tests__/DesktopRequiredBanner.test.tsx` — covers UX-02
- [ ] `frontend/src/components/editor/__tests__/SliderConflictDialog.test.tsx` — covers DAG-03 (Pitfall 9)
- [ ] `frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx` — covers LANDMASK-02

**UAT (3 files):**
- [ ] `frontend/tests/uat/08-vertex-drag.spec.ts` — covers EDIT-VERTEX-01 end-to-end
- [ ] `frontend/tests/uat/08-slider-conflict.spec.ts` — covers DAG-03 modal flow
- [ ] `frontend/tests/uat/08-perf-drag-60fps.spec.ts` — covers PERF-01 (FPS sampling via rAF; tolerate CI jitter; mark manual-confirmation if needed)

**Framework install:** None — all frameworks already installed.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local-only single-user tool; no auth |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Same — single-user local |
| V5 Input Validation | **yes** | Validate every coord from frontend (must be valid float, within map bounds); validate branch names (length, character set); validate snapshot blob size at decompress; reject malformed edit-op payloads at endpoint. Use pydantic for endpoint bodies (project default). |
| V6 Cryptography | no | sha256 used for token derivation only (not for security); no secrets handled in Phase 8 |
| V7 Error Handling | yes | Editor validate endpoint returns structured error codes (`SELF_INTERSECT`, `NEIGHBOUR_GAP`, `NOT_ADJACENT`, `CAP_EXCEEDED`) following Phase 06 D-08 envelope pattern |
| V8 Data Protection | yes | Snapshot blobs may contain user-specific edit logs; stored in `~/.medieval-forge/medieval_forge.db` (D-03 of Phase 01) — same protection as existing data |
| V12 Files | yes | Snapshot blob decompression — set `gzip` decompress limit to e.g. 10 MB to prevent zip-bomb DoS even though attack surface is local-only |
| V13 API | yes | New endpoints (`POST /editor/validate`, `POST /editor/apply`, `POST/GET branches`, `POST snapshots`) follow existing v3 router pattern; pydantic body validation; project_id UUID guard via `is_valid_uuid`; single-flight gate where cascade fires |

### Known Threat Patterns for {python+fastapi+sqlite+react+konva} stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via branch name | Tampering | SQLAlchemy 2.0 ORM with `Mapped[..]` always uses parameterized queries — verified by existing models pattern; no raw SQL anywhere in Phase 8 |
| Path traversal via project_id | Tampering | Reuse existing `services/paths.is_valid_uuid` + `project_dir` (UI-SPEC §components) |
| Resource exhaustion via huge edit log | DoS | Cap edit log size (e.g., max 10,000 ops per branch) before serializing; snapshot blob decompression size limit |
| XSS via branch name in inspector | Tampering | React auto-escapes text content; never use `dangerouslySetInnerHTML` for branch names |
| Cross-branch data leak via cache | Information disclosure | Cache key includes `branch_id` (D-23); test that branch A's render is never served when active branch is B |
| Topology validation bypass via direct API call | Tampering | `/editor/apply` re-runs topology validation server-side; never trusts the frontend's "client said valid" — Pitfall 11 |

**Karpathy reminder:** Phase 8 is local-only single-user; do NOT over-engineer security (no JWT, no rate limit middleware, no audit log encryption). Apply ASVS proportionally.

## Sources

### Primary (HIGH confidence — Verified)
- `pyproject.toml` (read 2026-05-26) — backend dep versions
- `frontend/package.json` (read 2026-05-26) — frontend dep versions
- `backend/medieval_forge/services/pipeline/dag.py` (read) — STAGE_READS, DAG_ORDER, DAG_PARENTS, compute_version_token
- `backend/medieval_forge/services/pipeline/cache.py` (read) — _STAGE_CACHE shape + cache_get/put/clear signatures
- `backend/medieval_forge/services/pipeline/__init__.py` (read) — orchestrator + _VORONOI_CACHE pattern
- `backend/medieval_forge/models.py` (read) — SQLAlchemy 2.0 Mapped[..] pattern; Base from DeclarativeBase
- `backend/medieval_forge/database.py` (read) — `~/.medieval-forge/medieval_forge.db` location, async engine + AsyncSessionLocal
- `backend/medieval_forge/main.py:31` (read) — `Base.metadata.create_all` in lifespan
- `.planning/STATE.md` (read) — Phase 01 PT/ES border length = 40 (not 38 — CLAUDE.md mis-count); Phase 04..07 stack invariants
- `.planning/phases/08-.../08-CONTEXT.md` (read) — 37 locked decisions verbatim
- `.planning/phases/08-.../08-UI-SPEC.md` (read) — UI contract + component inventory + Konva colors + 14 new components
- `.planning/phases/04-.../04-CONTEXT.md` (read) — DAG token formula, cache policy, zundo defer (now lifted)
- `.planning/phases/06-.../06-CONTEXT.md` (read) — MANIFEST schema_version=2, validation report shape
- `.claude/skills/karpathy/SKILL.md` (read) — surgical changes, simplicity-first, goal-driven discipline
- `CLAUDE.md` (read) — 7 non-negotiable rules, "What v3 is NOT" forbidden patterns

### Secondary (MEDIUM confidence — Cited)
- Shapely 2.0 docs (shapely.readthedocs.io) — is_valid, ops.split, unary_union, simplify, STRtree — `[CITED]`
- zundo 2.3 README (github.com/charkour/zundo) — temporal middleware API, partialize, limit, clear() — `[CITED]`
- SQLAlchemy 2.0 docs — async engine, Mapped[..], `create_all` idempotence — `[CITED]`
- MDN navigator.maxTouchPoints + matchMedia('(pointer:fine)') — UA detection pattern — `[CITED]`
- Konva docs (konvajs.org) — layer listening, batchDraw, drag events — `[CITED]`

### Tertiary (LOW confidence — needs validation)
- Konva 60fps at 5k handles with viewport culling alone — `[ASSUMED]` based on Konva docs + Phase 03 5-layer perf baseline. Planner should measure during Wave 1 spike; fallback to sceneFunc consolidation if fails.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libs are `[VERIFIED]` in pyproject.toml/package.json
- Architecture: HIGH — patterns mirror existing Phase 04/06 implementations verbatim
- Pitfalls: HIGH — 10 named pitfalls each cite a concrete code location (Phase 01 STATE.md, dag.py, cache.py callsites)
- Konva 5k-handle perf: MEDIUM — D-34 explicitly picked viewport culling, but empirical confirmation deferred to Wave 1 spike
- Manual_edit token derivation: HIGH — Pattern 1 reconciles D-18 with Phase 04 D-02 cleanly via STAGE_TOKEN_OVERRIDES

**Research date:** 2026-05-26
**Valid until:** 2026-06-26 (30 days — stack is stable; shapely + zundo + konva are mature)
