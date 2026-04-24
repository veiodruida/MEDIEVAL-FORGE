# Phase 4: Canvas Editing — Basic — Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

User can edit the canvas interactively: drag capital markers to reshape Voronoi territories (<500ms recalc), drag border vertices to reshape polygons, merge adjacent territories into one, and split a territory by drawing a cut line. All operations support 50-step named undo/redo. Edits are persisted to SQLite with a user-configurable save strategy. Real-time inline validation highlights invalid states and blocks export.

**In scope (EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-07, EDIT-08):**
- Capital drag → Voronoi recalc for affected neighbors only (<500ms target)
- Border vertex drag (explicit edit mode, decimated vertex set)
- Territory merge via rubber-band multi-select + floating mini-toolbar
- Territory split via toolbar with 3 sub-modes (Freehand / Snap-to-edge / Polyline)
- Named undo/redo with 50-step history and compound step grouping
- Real-time validation with inline badges and export gate
- Configurable persistence strategy (settings menu)

**Out of scope:**
- Terrain paint brush with land mask (Phase 5: EDIT-05)
- Reference overlay + opacity slider (Phase 5: EDIT-06)
- Full validation UI panel (Phase 6)
- Export ZIP regeneration (Phase 6)
- LLM re-research after edits
- Barony-level editing (barony selection not yet wired; deferred)

</domain>

<decisions>
## Implementation Decisions

### D-01 — Capital drag UX
- **Preview on release, no snap.** While dragging, the capital marker moves freely with the cursor (ghost position). On mouseup, the backend Voronoi recalc fires; affected neighbor polygons update on response. No snap-to-grid, no live recalc during drag.
- Rationale: live recalc on every mousemove risks latency spikes; snap adds friction for precise placement.

### D-02 — Border vertex affordance
- **Explicit edit mode + decimated vertices.**
  - A dedicated "Edit Vertices" button (or keyboard shortcut `V`) enters vertex-edit mode for the selected condado.
  - On entering edit mode, the polygon is decimated via Douglas-Peucker (~12 handle points per polygon) — not all raw Voronoi vertices. This keeps draggable handles sparse and usable.
  - While in edit mode, the handles are draggable; outside edit mode, the canvas behaves as Phase 02 (selection only, no vertex handles visible).
  - Exiting edit mode (Esc or clicking elsewhere) persists the edited polygon to the backend.

### D-03 — Merge: multi-select + trigger
- **Rubber-band (drag) multi-select + floating mini-toolbar.**
  - Dragging on an empty area of the Stage creates a selection rectangle. All condados whose centroid falls inside are selected.
  - A floating mini-toolbar appears near the selection with icons: **Merge**, **Delete**, (future: Group).
  - Merge: computes `shapely.unary_union` of selected polygons on the backend. Result inherits the name of the "primary" condado (first one selected / highest area). User can rename immediately in the Inspector.
  - Adjacency requirement: if selected condados are not all adjacent, show a validation toast but still allow the merge (non-adjacent merge creates a multipolygon — flag as validation warning).

### D-04 — Split: drawing mode
- **Toolbar with 3 selectable sub-modes for the cut line.**
  - A "Split" tool button activates split mode. A segmented control in the toolbar offers:
    1. **Snap-to-edge** (default) — click two points on the polygon boundary; they snap to the nearest edge. Produces a straight cut.
    2. **Polyline** — click to place nodes; double-click to finish. Cut follows the clicked path.
    3. **Freehand** — click-drag to draw a free-form path; smoothed after release (Ramer-Douglas-Peucker on the drawn path).
  - The cut line must enter and exit the polygon. If not, the operation is rejected with a toast.
  - Backend: `shapely.ops.split(polygon, cut_line)`. Returns two polygons; both inherit base attributes; user renames the second one.

### D-05 — Undo/redo: named transactions
- **Named transactions via `zundo temporal` + `handleSet`.**
  - Each atomic user action passes a human-readable label to `handleSet`: e.g., `"Mover capital de León"`, `"Fundir León + Castela"`, `"Dividir Castela"`, `"Editar vértice — Toledo"`.
  - `partialize`: exclude transient UI state (hover, cursor position, loading flags). Store only geometry, selection, and metadata diffs.
  - `diff: true`: store changed keys only — not full snapshots. Critical at 800+ territories (full snapshot = 100–250MB; diff = <1KB per operation).
  - `limit: 50`.
  - Compound operations (capital drag → N neighbor recalcs) are wrapped: `temporal.pause()` before the batch, apply all state changes, `temporal.resume()` after — registers as one undo step.
  - Keyboard: Ctrl+Z / Ctrl+Y (Cmd+Z / Cmd+Y on Mac).
  - Future: history panel reads the label stack.

### D-06 — Real-time validation
- **Per-operation validation, inline badges, export gate.**
  - After each operation finalizes (mouseup, confirm merge, confirm split), re-validate only the affected territories and their immediate neighbors (not full map scan).
  - Validation rules for Phase 4: polygon validity (no self-intersections), capital inside territory, non-empty polygon.
  - Display: condados with issues get a colored badge on the canvas (red dot overlay). InspectorSidebar shows the issue detail when the condado is selected.
  - Export button is disabled (with tooltip "Fix validation errors first") while any error-severity issues exist. Warnings do not block.
  - Phase 6 adds the full validation panel with VALIDATE-01..07 rules.

### D-07 — Persistence: configurable save strategy
- **User-selectable via a Settings menu panel.**
  - Three options selectable at runtime (persisted to localStorage):
    1. **Auto-save** (default) — PATCH fires after 1.5s debounce following the last edit. Status indicator in header: "Saved ✓" / "Saving…".
    2. **Save per operation** — PATCH fires immediately when each atomic operation finalizes. No unsaved state, highest write frequency.
    3. **Explicit save** — edits stay in Zustand until user presses Ctrl+S or clicks "Save". Header shows "Unsaved changes". `beforeunload` warning if unsaved.
  - The Settings menu is a Radix Dialog or Sheet accessible from the top navigation.

### D-08 — Voronoi recalc scope (performance constraint from ROADMAP)
- **Affected-neighbors-only recalc, not full regen.**
  - On capital drag: identify the moved condado + all condados that shared a Voronoi ridge with it (from stored adjacency map). Recalc only those N+1 seeds. Target: <500ms.
  - After merge: rebuild adjacency lookup from scratch (ridge_points indices shift after seed removal). This is a one-time cost per merge, not per drag.
  - Backend endpoint: `POST /api/projects/{id}/territories/{condado_id}/recalc` accepting the new capital position and returning updated GeoJSON for the affected polygons only.

### D-09 — Edit mode gating (read-only vs. editable)
- Canvas starts in read-only mode (Phase 02 behavior). An "Edit" toggle button in the toolbar activates edit mode globally.
- In edit mode: rubber-band select activates, capital markers become draggable, the Split/Merge tools appear in the toolbar.
- In read-only mode: all Phase 02 interactions work as before (click-select, inspect, pan, zoom, labels). This ensures accidental edits don't happen during review.

</decisions>

<risk_notes>
## Risks / Open Questions for Research Agent

1. **`shapely.ops.split` + freehand path**: The freehand path must be converted to a valid `LineString` that intersects the polygon boundary at exactly 2 points. Smoothing (Ramer-Douglas-Peucker) may reduce the path to fewer than 2 boundary crossings. Research agent should validate robust handling.

2. **Douglas-Peucker vertex count for decimation**: ~12 vertices is a UX estimate. Research agent should check if `shapely.simplify(tolerance, preserve_topology=True)` gives stable results for typical Voronoi cells at Spain-scale, and what tolerance achieves ~12 handles without distorting the visible shape too much.

3. **zundo `diff` option API**: Confirm current `zundo` 2.3.0 API for `diff` — whether it accepts `diff: true` or requires a custom equality function. The ROADMAP mentions `partialize+diff` as a critical constraint.

4. **Rubber-band select + Konva**: Konva does not have a built-in rubber-band selection. Research agent should document the approach: transparent `Rect` drawn on `mousemove`, intersection test against condado centroids on `mouseup`.

5. **Voronoi ridge adjacency after merge**: After merging N condados, the seed-point list changes size. The adjacency map (built from `scipy.spatial.Voronoi.ridge_points`) must be rebuilt. Confirm that a full rebuild takes <200ms for 800 condados (pre-computed; not blocking UI thread).

6. **`beforeunload` in Electron/Tauri context**: If the app is ever packaged as a desktop app, `beforeunload` dialogs may be suppressed. Note for future — not a Phase 4 blocker.

</risk_notes>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 scope anchors
- `.planning/ROADMAP.md` §"Phase 4: Canvas Editing — Basic" — goal, requirements, success criteria, critical constraints
- `.planning/REQUIREMENTS.md` EDIT-01..04, EDIT-07, EDIT-08

### Tech stack constraints
- `CLAUDE.md` §"Potential Issues #2 zundo" — `temporal` middleware, `partialize`, `diff`, `limit`, `handleSet`, `pause()/resume()` API
- `CLAUDE.md` §"Tech Stack" — Zustand 5, zundo 2.3.0, react-konva 19.x, Shapely 2.x, scipy Voronoi, FastAPI async

### Existing Phase 02 canvas patterns (read before touching canvas code)
- `frontend/src/components/canvas/CanvasViewer.tsx` — Stage setup, zoom/pan, click-select, ResizeObserver
- `frontend/src/components/canvas/TerritoryLayer.tsx` — polygon rendering
- `frontend/src/components/canvas/DecorationsLayer.tsx` — capital markers, labels
- `frontend/src/hooks/useZoomPan.ts` — zoom/pan state
- `frontend/src/store/` — Zustand store structure (add `temporal` wrapper here)

### Backend geometry patterns
- `backend/medieval_forge/services/generator.py` — Voronoi generation (recalc scope: reuse seed-extraction logic)
- `backend/medieval_forge/models/` — Project + territory SQLAlchemy models

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CanvasViewer.tsx` Stage + ResizeObserver pattern — edit mode is a new Zustand flag, not a new component.
- `DecorationsLayer.tsx` capital markers — make draggable when in edit mode.
- `TerritoryLayer.tsx` — add vertex handle overlay in vertex-edit mode.
- Zustand store — wrap with `temporal` from `zundo`; add `partialize` to exclude UI-only slices.

### New Integration Points
- New endpoint: `POST /api/projects/{id}/territories/{id}/recalc` (capital drag → Voronoi recalc)
- New endpoint: `POST /api/projects/{id}/territories/merge` (merge N condados)
- New endpoint: `POST /api/projects/{id}/territories/{id}/split` (split by LineString)
- New endpoint: `PATCH /api/projects/{id}/territories/{id}/geometry` (vertex drag save)
- Toolbar component (new): `EditToolbar.tsx` — Edit mode toggle, Split tool selector, Merge trigger
- Mini-toolbar component (new): `SelectionFloatingToolbar.tsx` — appears on rubber-band select
- Settings panel (new): Radix Sheet or Dialog with persistence-strategy selector

### Performance Constraint (from ROADMAP critical constraints)
- `zundo` partialize + diff is NOT optional — full snapshots at 800 territories = 100-250MB. Must be designed in from the first undo commit.
- Voronoi adjacency map must be rebuilt after every merge (ridge_points indices shift).

</code_context>

<deferred>
## Deferred Ideas

- Barony-level editing (barony selection not wired until Phase 4/5 per design)
- History panel UI showing named undo steps (label stack exists, panel is future)
- Capital snap-to-grid (explicitly rejected in D-01)
- Live Voronoi preview during drag (too expensive; preview-on-release is the decision)
- llama.cpp local LLM provider (Option B adapter — separate quick task, not Phase 4)
- GAP-09 label contrast fix (DecorationsLayer luminance-based text color — separate quick task)
- Browser cache hygiene for `index.html` (low-priority follow-up from Phase 02 UAT)

</deferred>

---

*Phase: 04-canvas-editing-basic*
*Context gathered: 2026-04-23*
