# Phase 4: Canvas Editing — Basic — Research

**Researched:** 2026-04-23
**Domain:** Interactive Konva canvas editing, zundo undo/redo, scipy Voronoi adjacency, Shapely geometry ops
**Confidence:** HIGH (stack verified from package.json and official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Capital drag UX:** Preview on release, no snap. Ghost position during drag; backend Voronoi recalc fires on mouseup; affected neighbor polygons update on response.

**D-02 — Border vertex affordance:** Explicit "Edit Vertices" mode (button or `V`); Douglas-Peucker decimation to ~12 handles per polygon; drag handles outside edit mode are invisible; exiting mode (Esc or click-elsewhere) persists to backend.

**D-03 — Merge: multi-select + trigger:** Rubber-band drag on empty Stage area selects condados by centroid containment; floating mini-toolbar shows Merge/Delete; `shapely.unary_union`; inherits primary condado name; non-adjacent merge is a warning, not a block.

**D-04 — Split: drawing mode:** Three sub-modes — Snap-to-edge (default), Polyline, Freehand (RDP-smoothed). Cut must enter and exit polygon; rejection with toast if not. Backend: `shapely.ops.split(polygon, cut_line)`.

**D-05 — Undo/redo: named transactions:** `zundo temporal` + `handleSet`; human-readable label per action; `partialize` excludes transient UI state; `diff` stores changed keys only (NOT `diff: true` — requires a custom function, see Standard Stack); `limit: 50`; compound ops wrapped with `temporal.pause()` / `temporal.resume()`; Ctrl+Z / Ctrl+Y.

**D-06 — Real-time validation:** Per-operation, affects only touched territories + immediate neighbors; Phase 4 rules: polygon validity, capital inside territory, non-empty polygon; inline badge (red dot); export gate on error-severity issues.

**D-07 — Persistence: configurable save strategy:** Three modes selectable at runtime (persisted to localStorage): Auto-save (1.5s debounce), Save per operation, Explicit save (Ctrl+S). Settings menu via Radix Dialog or Sheet.

**D-08 — Voronoi recalc scope:** Affected-neighbors-only recalc on capital drag; full adjacency rebuild on merge. Endpoint: `POST /api/projects/{id}/territories/{condado_id}/recalc`.

**D-09 — Edit mode gating:** Canvas starts read-only; "Edit" toggle button activates edit mode globally.

### Claude's Discretion

Nothing left explicitly to Claude's discretion — all major decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- Barony-level editing
- History panel UI (label stack exists, panel is future)
- Capital snap-to-grid
- Live Voronoi preview during drag
- llama.cpp local LLM provider
- GAP-09 label contrast fix
- Browser cache hygiene for `index.html`
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EDIT-01 | User can drag a capital marker; neighbors recalculate Voronoi in <500ms | Konva `draggable` + `onDragEnd`; scipy Voronoi full-recompute with neighbor filter via `ridge_points`; async FastAPI endpoint |
| EDIT-02 | User can select border vertices and drag individual nodes to reshape a polygon | Konva Circle handles over polygon vertices; `shapely.simplify(preserve_topology=True)` for decimation; `PATCH /api/.../geometry` |
| EDIT-03 | User can select 2+ adjacent territories and merge them into one | Rubber-band rect on Stage; `shapely.unary_union`; adjacency rebuild post-merge; `POST /api/.../merge` |
| EDIT-04 | User can split a territory by drawing a cut line across it | Three cut-line sub-modes; `shapely.ops.split`; RDP smoothing for freehand; `POST /api/.../split` |
| EDIT-07 | All edit operations support Ctrl+Z (undo) and Ctrl+Y (redo) with 50-step history | `zundo temporal` with `partialize` + `diff` (function) + `limit: 50`; keyboard hook extending existing `useKeyboardShortcuts` |
| EDIT-08 | Undo/redo groups compound side effects as single steps | `temporal.pause()` / `temporal.resume()` wrapping compound ops; registers as one undo step |
</phase_requirements>

---

## Summary

Phase 4 introduces interactive canvas editing on top of the read-only Phase 2 canvas. The four core operations (capital drag, vertex drag, merge, split) each require a Konva interaction layer plus a FastAPI backend endpoint that calls scipy/Shapely geometry services. The central risk is the zundo undo/redo store: the ROADMAP warns that full snapshots at 800 territories = 100-250MB. This is addressed by `partialize` (exclude transient UI state) + a custom `diff` function (store only the delta, not the full state). The `diff` option in zundo 2.3.0 is a **function**, not a boolean flag — this is the single most critical API detail for planners.

Compound operations (capital drag triggers N neighbor Voronoi recalcs) must register as one undo step. The canonical zundo pattern for this is `temporal.pause()` before the batch, apply all state mutations, `temporal.resume()` after — not `handleSet`. The `handleSet` option is appropriate for throttle/debounce patterns (e.g., vertex drag), not for grouping discrete async operations.

The existing codebase (Phase 2) provides all needed foundation: `CanvasViewer.tsx` with `stageRef`, `DecorationsLayer.tsx` with capital Circle nodes, `TerritoryLayer.tsx` with polygon rendering, and `useKeyboardShortcuts.ts` for keyboard bindings. The Zustand store currently has `useUIStore` (layer visibility, selection) and `useResearchStore`. Phase 4 adds `useProjectStore` (temporal-wrapped, geometry state) and `useEditorStore` (tool mode, not tracked).

**Primary recommendation:** Build `useProjectStore` with zundo `temporal` first (Plan 4.1), verify snapshot size with real Iberia data (~91 territories) before committing to the diff function strategy, then build the backend Voronoi service (Plan 4.2), then Konva interactions (Plans 4.3, 4.4).

---

## Standard Stack

### Core (verified from `frontend/package.json` and `backend/pyproject.toml`)

| Library | Installed Version | Purpose | Notes |
|---------|------------------|---------|-------|
| zundo | 2.3.0 | Undo/redo middleware for Zustand | v2 API; `temporal` middleware; `diff` is a function |
| zustand | 5.0.12 | State management | `temporal` wrapper lives here |
| react-konva | 19.2.3 | Canvas interaction layer | Tracks React 19 versioning |
| konva | 10.2.5 | Underlying canvas engine | `draggable`, `onDragEnd`, rubber-band rect |
| scipy | (from Phase 1) | Voronoi diagram computation | `scipy.spatial.Voronoi`; `ridge_points` adjacency |
| shapely | 2.x (from Phase 1) | Geometry ops: union, split, simplify | `ops.split`, `unary_union`, `simplify`, `orient` |
| FastAPI | 0.115.x | Async API endpoints for edit operations | New `api/edit.py` router |

[VERIFIED: package.json] Confirmed zundo 2.3.0, zustand 5.0.12, react-konva 19.2.3, konva 10.2.5.

### New Frontend Dependencies Needed

None — all required libraries are already installed.

### New Backend Dependencies Needed

None — scipy, Shapely, FastAPI already installed from Phase 1.

---

## Architecture Patterns

### Recommended Store Structure

```
frontend/src/stores/
├── uiStore.ts            (existing — layer visibility, selection — NOT tracked)
├── useResearchStore.ts   (existing — research results — NOT tracked)
├── useProjectStore.ts    (NEW — territory geometry, capitals — TEMPORAL-WRAPPED)
└── useEditorStore.ts     (NEW — tool mode, edit mode flag, vertex handles — NOT tracked)
```

**Rule:** Only `useProjectStore` gets the `temporal` wrapper. Editor tool state and UI state must NOT be tracked in undo history — this is enforced by `partialize`.

### Recommended Backend Structure

```
backend/medieval_forge/
├── api/
│   └── edit.py           (NEW — POST /recalc, /merge, /split, PATCH /geometry)
└── services/
    └── voronoi.py        (NEW — scipy Voronoi recompute + Shapely clip + adjacency)
```

### Pattern 1: zundo Temporal Store with partialize + diff

**What:** Wrap only geometry-bearing store slice with `temporal`; exclude transient UI state.

**When to use:** Any state that the user should be able to undo. Never wrap hover state, loading flags, or tool selection.

**Critical API detail:** `diff` is a **function** in zundo 2.3.0, not a boolean. [VERIFIED: GitHub charkour/zundo README]

```typescript
// Source: charkour/zundo README + official type signature
import { create } from 'zustand'
import { temporal } from 'zundo'

interface ProjectState {
  territories: Record<string, TerritoryGeometry>
  capitals: Record<string, [number, number]>
  // ...geometry fields only
}

export const useProjectStore = create<ProjectState>()(
  temporal(
    (set) => ({
      territories: {},
      capitals: {},
    }),
    {
      // partialize: exclude any transient/UI state that must NOT enter history
      partialize: (state) => ({
        territories: state.territories,
        capitals: state.capitals,
      }),

      // diff: store only changed keys, NOT the full snapshot
      // This is CRITICAL — full snapshot at 800 territories = 100-250MB
      // diff must return the delta (changed keys only) or null (no change)
      diff: (pastState, currentState) => {
        const result: Partial<ProjectState> = {}
        let changed = false
        for (const key of Object.keys(currentState) as Array<keyof typeof currentState>) {
          if (pastState[key] !== currentState[key]) {
            result[key] = currentState[key] as never
            changed = true
          }
        }
        return changed ? result : null
      },

      limit: 50,
    }
  )
)
```

### Pattern 2: Compound Action Batching with pause/resume

**What:** Wrap a compound operation (capital drag + N neighbor recalcs) so all state changes register as ONE undo step.

**When to use:** Any backend call that triggers multiple state updates (capital drag, merge, split). NOT for debounce/throttle (use `handleSet` for that).

```typescript
// Source: charkour/zundo README
const { pause, resume } = useProjectStore.temporal.getState()

async function handleCapitalDragEnd(condadoId: string, newLon: number, newLat: number) {
  pause()  // stop recording intermediate states
  try {
    const result = await api.post(`/api/projects/${projectId}/territories/${condadoId}/recalc`, {
      lon: newLon, lat: newLat
    })
    // Apply all N neighbor polygon updates — all are ONE undo step
    useProjectStore.setState((s) => ({
      territories: { ...s.territories, ...result.updatedGeometries },
      capitals: { ...s.capitals, [condadoId]: [newLon, newLat] },
    }))
  } finally {
    resume()  // one snapshot is recorded here
  }
}
```

### Pattern 3: Konva Draggable Capital Marker

**What:** Make existing capital Circle draggable in edit mode; trigger backend on `onDragEnd`.

**When to use:** Edit mode active + capitals layer visible.

```tsx
// Source: konvajs.org/docs/react/Drag_And_Drop.html
<Circle
  key={`cap-${c.id}`}
  x={x}
  y={y}
  radius={6}
  fill={color}
  draggable={isEditMode}  // conditional on edit mode gate (D-09)
  onDragEnd={(e) => {
    const canvasX = e.target.x()
    const canvasY = e.target.y()
    // Convert canvas coords back to geo coords using canvasToGeo()
    const [lon, lat] = canvasToGeo(canvasX, canvasY, projection)
    handleCapitalDragEnd(c.id, lon, lat)  // fires pause/resume batch
  }}
/>
```

**CRITICAL — `DecorationsLayer` `listening={false}` blocks drag events:** The existing `DecorationsLayer.tsx` has `<Layer listening={false}>`. Konva does NOT dispatch drag events to children of a `listening=false` Layer, even if the child Circle has `draggable={true}`. To make capitals draggable in edit mode:
- **Option A (recommended):** Change `<Layer listening={false}>` to `<Layer listening={isEditMode}>` in `DecorationsLayer.tsx`. In read-only mode `listening=false` is preserved; in edit mode events flow through.
- **Option B:** Extract capital Circles into a separate `CapitalsInteractiveLayer` (always `listening={true}`, conditionally rendered), keeping labels-only in the `listening=false` layer.

**Note:** In react-konva non-strict mode, dragged positions are preserved imperatively by Konva. Do NOT set `x`/`y` from state during drag — only update state on `onDragEnd` and let Konva manage interim position.

### Pattern 4: Rubber-Band Selection Rect

**What:** Konva has no built-in rubber-band selection. Implement with transparent Rect drawn on `mousemove`, centroid intersection test on `mouseup`.

**When to use:** When edit mode is active and user drags on empty Stage area.

```tsx
// Source: konvajs.org docs + community patterns verified via WebSearch
// In a dedicated selection Layer (above TerritoryLayer, below InteractionLayer):
const [selectionRect, setSelectionRect] = useState<{x:number,y:number,w:number,h:number} | null>(null)
const dragStartPos = useRef<{x:number,y:number} | null>(null)

// Stage onMouseDown (only if e.target === Stage):
const handleMouseDown = (e: KonvaEventObject<MouseEvent>) => {
  if (e.target !== e.target.getStage()) return  // only empty Stage area
  const pos = e.target.getStage()!.getRelativePointerPosition()!
  dragStartPos.current = pos
  setSelectionRect({ x: pos.x, y: pos.y, w: 0, h: 0 })
}

// Stage onMouseMove:
const handleMouseMove = (e: KonvaEventObject<MouseEvent>) => {
  if (!dragStartPos.current) return
  const pos = e.target.getStage()!.getRelativePointerPosition()!
  const start = dragStartPos.current
  setSelectionRect({
    x: Math.min(start.x, pos.x),
    y: Math.min(start.y, pos.y),
    w: Math.abs(pos.x - start.x),
    h: Math.abs(pos.y - start.y),
  })
}

// Stage onMouseUp: test centroid containment
const handleMouseUp = () => {
  if (!selectionRect) return
  const { x, y, w, h } = selectionRect
  const selected = condados.filter((c) => {
    const [cx, cy] = geoToCanvas(c.lon, c.lat, projection)
    return cx >= x && cx <= x + w && cy >= y && cy <= y + h
  })
  selectMultiple(selected.map(c => c.id))
  setSelectionRect(null)
  dragStartPos.current = null
}

// Render the rubber-band rect (dashed stroke, no fill):
{selectionRect && (
  <Rect
    x={selectionRect.x} y={selectionRect.y}
    width={selectionRect.w} height={selectionRect.h}
    stroke="#3b82f6" strokeWidth={1} dash={[4, 4]}
    fill="rgba(59,130,246,0.05)"
    listening={false}
  />
)}
```

**Stage.getRelativePointerPosition()** returns position relative to stage accounting for zoom/pan. Always use this, not raw pointer position, for correct coordinate math.

### Pattern 5: Voronoi Adjacency from ridge_points

**What:** Extract neighbor set from `scipy.spatial.Voronoi.ridge_points`; rebuild after merge.

```python
# Source: docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Voronoi.html
import numpy as np
from scipy.spatial import Voronoi

def build_adjacency(points: np.ndarray) -> dict[int, set[int]]:
    """Build index-to-neighbor-index adjacency from Voronoi ridge_points."""
    vor = Voronoi(points)
    adj: dict[int, set[int]] = {i: set() for i in range(len(points))}
    for p1, p2 in vor.ridge_points:
        if p1 >= 0 and p2 >= 0:
            adj[p1].add(p2)
            adj[p2].add(p1)
    return adj

def find_affected_neighbors(moved_idx: int, adj: dict[int, set[int]]) -> set[int]:
    """Return the moved condado index + all Voronoi neighbors to recalculate."""
    return {moved_idx} | adj.get(moved_idx, set())
```

**Performance note:** Full scipy Voronoi recompute for ~800 points runs in Python in well under 50ms on modern hardware (Qhull is O(n log n)). The 500ms budget is dominated by the Shapely land-mask clipping, not the Voronoi computation itself. [ASSUMED — no verified benchmark for this exact scale]

**After merge:** `ridge_points` indices shift because the seed list shrinks. The adjacency map MUST be rebuilt from scratch by calling `Voronoi(remaining_points)` again. Do NOT attempt to patch the existing adjacency map.

### Pattern 6: Shapely Geometry Operations

#### unary_union (merge)
```python
# Source: shapely.readthedocs.io
from shapely.ops import unary_union

def merge_territories(polygons: list) -> object:
    """Merge N polygons into one. Result may be MultiPolygon if non-adjacent."""
    merged = unary_union(polygons)
    # Always call orient to normalize winding order
    from shapely.geometry import shape
    from shapely import orient
    return orient(merged, sign=1.0)
```

#### ops.split (split territory)
```python
# Source: shapely.readthedocs.io + issue #1951 analysis
from shapely.ops import split
from shapely.geometry import LineString

def split_territory(polygon, cut_line: LineString):
    """
    Split a polygon by a LineString.
    
    CRITICAL: ops.split returns a GeometryCollection.
    If the cut line does NOT properly cross the polygon boundary at 2 points,
    split() returns a single-geometry collection (original polygon) — it does NOT
    raise an exception. (Issue #1951: wontfix)
    
    Validation: check len(result.geoms) >= 2 after the call.
    """
    result = split(polygon, cut_line)
    if len(result.geoms) < 2:
        raise ValueError(
            "Cut line does not properly bisect the territory. "
            "Ensure the line enters and exits the polygon boundary."
        )
    return [orient(g, sign=1.0) for g in result.geoms]
```

**Freehand path risk:** If RDP reduces the freehand path below 2 boundary crossings, `split()` silently returns the original polygon. The backend must check `len(result.geoms) >= 2` and return a 422 error so the frontend can show a toast. Pre-validate that the LineString intersects the polygon exterior at exactly 2 distinct points using `polygon.exterior.intersection(cut_line)`.

#### simplify (vertex decimation for EDIT-02)
```python
# Source: shapely.readthedocs.io/en/stable/reference/shapely.simplify.html
from shapely import simplify

def decimate_polygon(polygon, target_vertices: int = 12) -> object:
    """
    Reduce polygon to ~target_vertices draggable handles using Douglas-Peucker.
    preserve_topology=True prevents self-intersection but may produce > target_vertices.
    
    Binary search on tolerance:
    """
    low, high = 0.0, 1.0  # tolerance in coordinate units
    result = polygon
    for _ in range(20):  # binary search iterations
        mid = (low + high) / 2
        simplified = simplify(polygon, tolerance=mid, preserve_topology=True)
        n = len(simplified.exterior.coords)
        if n > target_vertices:
            low = mid
        elif n < target_vertices - 2:
            high = mid
        else:
            result = simplified
            break
    return result
```

**Known issue:** [VERIFIED: github.com/shapely/shapely/issues/2165] `simplify()` can return invalid geometries even with `preserve_topology=True` in some edge cases. Always call `is_valid` on the result and fall back to the undecimateed polygon if invalid.

### Anti-Patterns to Avoid

- **`diff: true` in zundo config:** The `diff` key requires a function, not a boolean. Using `diff: true` will silently ignore the option or cause a type error.
- **`handleSet` for compound op batching:** Use `pause()/resume()` instead. `handleSet` is for throttle/debounce of individual fast-fire events (vertex drag debounce).
- **`temporal` on `useUIStore` or `useEditorStore`:** These stores contain transient state (hover, tool mode) that must never enter undo history.
- **Tracking canvas Konva node positions in Zustand during drag:** Let Konva manage imperative position during drag; only sync to Zustand on `onDragEnd`.
- **Full GeoJSON snapshot per undo step:** At 800 territories, each GeoJSON is ~100-250KB compressed. 50 snapshots = 5-12MB minimum. The `diff` function must store only changed `territories` keys (1-6 entries per operation).
- **Patching adjacency map after merge:** After removing seed points, `ridge_points` indices are renumbered. Always call `Voronoi(remaining_points)` to rebuild from scratch.
- **`shapely.ops.split()` without result validation:** Silent failure (single-geometry result) — always check `len(result.geoms) >= 2`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Undo/redo | Custom history stack | `zundo temporal` | Handle concurrent state, partialize, time-travel already implemented |
| Polygon union | Manual point dedup | `shapely.unary_union` | Interior edge removal, multipolygon coalescence, winding order — all handled |
| Polygon split | Manual ring traversal | `shapely.ops.split` | Handles interior rings, degenerate cases, ensures valid output geometry |
| Vertex simplification | Custom RDP | `shapely.simplify(preserve_topology=True)` | GEOS-optimized, topology-preserving; handles self-intersection prevention |
| Voronoi adjacency | Manual neighbor search | `scipy.spatial.Voronoi.ridge_points` | Direct O(1) adjacency lookup; built by Qhull |
| Coordinate transforms | New projection math | Existing `geoToCanvas` / `canvasToGeo` in `lib/projection.ts` | Phase 2 already has tested, calibrated projection |

**Key insight:** The geometry domain has multiple known edge cases (degenerate polygons, non-manifold splits, winding order, floating-point intersections) that have taken GEOS/Shapely years to handle correctly. Any hand-rolled alternative will encounter these at production data scale.

---

## Runtime State Inventory

SKIPPED — This is a greenfield canvas editing phase, not a rename/refactor. No existing runtime state stores old names or identifiers that need migrating.

---

## Common Pitfalls

### Pitfall 1: `diff: true` is not a valid zundo config value
**What goes wrong:** ROADMAP and CONTEXT.md both say "use `diff`" but a developer reads this as `diff: true` in the config object. This silently does nothing (or causes a TypeScript error). Full snapshots are stored instead of deltas.
**Why it happens:** The docs call it "diff mode" but the config key takes a function that computes the delta.
**How to avoid:** Pass `diff: (past, current) => { /* return delta or null */ }` — always a function.
**Warning signs:** Memory growing proportionally to undo steps; `temporal.pastStates` array containing full territory Record objects.

### Pitfall 2: Stage drag and rubber-band drag conflict
**What goes wrong:** Stage is `draggable` for pan (Phase 2). When user tries to rubber-band-select, the Stage drag activates and pans instead.
**Why it happens:** Stage `draggable` intercepts all mousedown-drag sequences.
**How to avoid:** In edit mode, disable Stage `draggable` when the edit tool is "select" (rubber-band mode). Re-enable it when in pan mode. Store the active tool in `useEditorStore` and conditionally set `<Stage draggable={activeTool !== 'select'}>`.

### Pitfall 3: Voronoi adjacency rebuild after merge is mandatory
**What goes wrong:** After merging condados, the old adjacency map still references stale indices. A subsequent capital drag on a neighbor uses the stale map and recalcs the wrong set.
**Why it happens:** `scipy.spatial.Voronoi.ridge_points` contains integer indices into the seed array. After removing merged condados, all indices above the removal point shift.
**How to avoid:** After every merge, rebuild the full adjacency map from `Voronoi(remaining_seeds)`. Store it server-side (or in the project record) and re-fetch after merge.

### Pitfall 4: `shapely.ops.split()` silent failure
**What goes wrong:** Freehand cut path reduced by RDP no longer crosses the polygon boundary at 2 points. `split()` returns a GeometryCollection with 1 geometry (the original polygon). No exception is raised. Backend returns 200 OK with no actual split.
**Why it happens:** `split()` treats a non-bisecting line as a valid no-op. [VERIFIED: shapely issue #1951, closed wontfix]
**How to avoid:** Pre-validate: `polygon.exterior.intersection(cut_line)` must produce a MultiPoint or 2+ Point geometries. If not, return HTTP 422 with `"Cut line does not bisect the territory"`. Frontend shows toast.

### Pitfall 5: react-konva non-strict mode and position sync
**What goes wrong:** Capital Circle position is managed both by Konva imperatively (during drag) and by React state (after `onDragEnd`). If state update triggers a re-render mid-drag, Konva's position can be overwritten by the previous React prop.
**Why it happens:** react-konva in non-strict mode does NOT sync `x`/`y` unless they change in render. But if the state update fires a re-render that passes the OLD position (before the drag started), it can snap back.
**How to avoid:** During `onDragEnd`, update the store with the new geo coordinates. Pass `x`/`y` to the Circle from the store. Since the drag just ended, the store value will match Konva's imperative position. Do NOT call `setState` during `onDragMove`.

### Pitfall 6: Konva hit canvas desync after geometry change
**What goes wrong:** After a territory polygon is updated (Voronoi recalc), clicking the new polygon area may not register the hit — the hit canvas still shows the old shape.
**Why it happens:** Konva caches the hit canvas. When polygon points change, the cached hit area is stale.
**How to avoid:** After updating polygon points in a `TerritoryPolygon`, call `nodeRef.current?.clearCache()` to force hit canvas rebuild. This is documented in Phase 5 ROADMAP critical constraints and applies equally to Phase 4 geometry updates.
[ASSUMED — based on Konva documentation pattern and Phase 5 ROADMAP note; verify empirically during Plan 4.2 implementation]

### Pitfall 7: Undo step named label stack
**What goes wrong:** `temporal.pastStates` does not natively store labels. The CONTEXT.md D-05 decision requires human-readable labels (e.g., "Mover capital de León").
**Why it happens:** zundo stores state snapshots, not metadata.
**How to avoid:** Maintain a parallel label array in `useEditorStore` (not temporal-tracked): `actionLabels: string[]`. Push a label immediately before `resume()`. Pop from the front on undo, push to redo-labels stack on redo. This gives a synchronized label timeline without adding labels to the diff snapshot.

### Pitfall 8: `DecorationsLayer listening={false}` blocks capital drag events
**What goes wrong:** Pattern 3 sets `draggable={isEditMode}` on Circle nodes, but Konva does NOT dispatch any events (including drag) to children of a `<Layer listening={false}>` regardless of child node settings. The existing `DecorationsLayer.tsx` uses `<Layer listening={false}>`. Capital drag events will never fire.
**Why it happens:** Konva uses the Layer-level `listening` prop as an early-exit gate for ALL child event processing — a performance optimization that silently swallows drag events.
**How to avoid:** In `DecorationsLayer.tsx`, change `<Layer listening={false}>` to `<Layer listening={isEditMode}>`. Accept `isEditMode` as a prop from `CanvasViewer`. In read-only mode performance is preserved. In edit mode, events reach Circle nodes.
**Warning signs:** `onDragEnd` callback never fires; capital appears draggable but snaps back; no error thrown.

---

## Code Examples

### zundo TemporalState options (verified API)

```typescript
// Source: github.com/charkour/zundo README — verified 2026-04-23
type ZundoOptions<TState, PartialTState> = {
  partialize?: (state: TState) => PartialTState
  equality?: (pastState: PartialTState, currentState: PartialTState) => boolean
  limit?: number
  handleSet?: (handleSet: StoreApi<TState>['setState']) => StoreApi<TState>['setState']
  diff?: (
    pastState: Partial<PartialTState>,
    currentState: Partial<PartialTState>
  ) => Partial<PartialTState> | null
}

// Temporal state object methods (from useStore.temporal.getState()):
// undo(steps?: number)
// redo(steps?: number)
// pause()
// resume()
// clear()
// isTracking: boolean
```

### Backend edit endpoint skeleton (FastAPI)

```python
# Source: pattern from existing api/projects.py and api/generate.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_session
from ..services.voronoi import recalc_neighbors

router = APIRouter()

@router.post("/projects/{project_id}/territories/{condado_id}/recalc")
async def move_capital(
    project_id: str,
    condado_id: str,
    body: MoveCapitalRequest,
    session: AsyncSession = Depends(get_session),
):
    """EDIT-01: Recalc Voronoi for affected neighbors after capital drag."""
    try:
        updated = await recalc_neighbors(project_id, condado_id, body.lon, body.lat, session)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    return {"updated_territories": updated}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Full state snapshots per undo step | `zundo diff` function storing key-deltas only | ~99% memory reduction at 800 territories |
| Full Voronoi regen on any capital move | Neighbor-only recalc via `ridge_points` adjacency | ~N/800 recalculation (6-10 neighbors typical) |
| Rubber-band select with DOM events | Konva Stage `getRelativePointerPosition()` + Rect overlay | Zoom/pan immune; no coordinate system mismatch |
| `preserve_topology=False` simplify | `preserve_topology=True` | Prevents self-intersecting handle polygons |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Full scipy Voronoi recompute for ~800 points runs in <50ms, leaving headroom for Shapely clipping in the 500ms budget | Architecture Patterns / Pattern 5 | If clipping takes >450ms, need to pre-clip the land mask or cache clipped seeds |
| A2 | `clearCache()` on Konva polygon node is required after geometry update to prevent hit canvas desync | Common Pitfalls / Pitfall 6 | If Konva auto-invalidates hit cache on `points` prop change, `clearCache()` is unnecessary (harmless overhead) |
| A3 | Approximately 12 vertex handles is achievable via `shapely.simplify` for typical Spain-scale Voronoi cells without distorting the visible polygon shape | Architecture Patterns / Pattern 6 | Actual handles may vary 6-20 depending on cell complexity; tolerance tuning needed |

---

## Open Questions

1. **`diff` function memory validation at real scale**
   - What we know: The diff function stores only changed keys. A capital drag changes 1 capital + 6-10 territory polygons.
   - What's unclear: Actual size of a single GeoJSON territory polygon entry in the Iberia dataset.
   - Recommendation: Spike in Plan 4.1 — load real `territories.geojson`, measure `JSON.stringify(oneTerritory).length`, multiply by 50 steps * 10 neighbors. Target: <10MB total for 50-step history.

2. **Adjacency map storage location**
   - What we know: Rebuild is needed after every merge; it's O(n log n) for ~800 seeds.
   - What's unclear: Whether to compute adjacency on every recalc request or cache it in the project record (SQLite JSON column).
   - Recommendation: Compute on-the-fly in `voronoi.py` during each recalc call. Caching adds invalidation complexity. 800-seed Voronoi + adjacency build is fast enough not to need caching. [ASSUMED]

3. **Floating mini-toolbar positioning**
   - What we know: Radix Popover or a plain div positioned near the rubber-band selection rect.
   - What's unclear: Whether the toolbar should be canvas-coordinate-relative or viewport-relative (canvas is a `<canvas>` inside a `position:relative` div).
   - Recommendation: Viewport-relative absolutely-positioned div, updated on each rubber-band `mouseup`. Konva Stage gives viewport-space bounding rect of the selection — convert with `stage.container().getBoundingClientRect()`.

---

## Environment Availability

SKIPPED — Phase 4 adds no external dependencies beyond the Phase 1/2 stack (scipy, Shapely, FastAPI, React, Konva). All tools verified present from prior phases.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 (frontend) + pytest (backend) |
| Config file | `frontend/vitest.config.ts` (jsdom environment) |
| Quick run command | `cd frontend && npm test -- --run` |
| Full suite command | `cd frontend && npm test -- --run && cd ../backend && python -m pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EDIT-01 | capital drag fires `onDragEnd` with correct canvas position | unit | `npm test -- --run src/components/canvas/__tests__/DecorationsLayer.test.tsx` | ❌ Wave 0 |
| EDIT-01 | recalc_neighbors returns updated GeoJSON for moved condado | unit | `pytest tests/services/test_voronoi.py -x` | ❌ Wave 0 |
| EDIT-02 | simplify returns ≤15 vertices for typical Voronoi cell | unit | `pytest tests/services/test_voronoi.py::test_decimate -x` | ❌ Wave 0 |
| EDIT-03 | rubber-band select captures condados by centroid containment | unit | `npm test -- --run src/stores/__tests__/useEditorStore.test.ts` | ❌ Wave 0 |
| EDIT-03 | unary_union produces valid polygon from 2 adjacent territories | unit | `pytest tests/services/test_voronoi.py::test_merge -x` | ❌ Wave 0 |
| EDIT-04 | ops.split returns 2 polygons for valid bisecting line | unit | `pytest tests/services/test_voronoi.py::test_split -x` | ❌ Wave 0 |
| EDIT-04 | ops.split raises ValueError when line does not bisect | unit | `pytest tests/services/test_voronoi.py::test_split_invalid -x` | ❌ Wave 0 |
| EDIT-07 | Ctrl+Z fires `temporal.undo()` | unit | `npm test -- --run src/hooks/__tests__/useUndoShortcut.test.ts` | ❌ Wave 0 |
| EDIT-08 | pause/resume wraps compound op as single undo step | unit | `npm test -- --run src/stores/__tests__/useProjectStore.test.ts` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npm test -- --run`
- **Per wave merge:** Full suite (frontend + backend)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `frontend/src/stores/__tests__/useProjectStore.test.ts` — covers EDIT-07, EDIT-08 (zundo temporal config + pause/resume batching)
- [ ] `frontend/src/stores/__tests__/useEditorStore.test.ts` — covers EDIT-03 (rubber-band select state)
- [ ] `frontend/src/hooks/__tests__/useUndoShortcut.test.ts` — covers EDIT-07 (Ctrl+Z/Ctrl+Y key bindings)
- [ ] `backend/tests/services/test_voronoi.py` — covers EDIT-01, EDIT-02, EDIT-03, EDIT-04 backend geometry
- [ ] `frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx` — covers EDIT-01 interaction

---

## Security Domain

The edit endpoints (`/recalc`, `/merge`, `/split`, `/geometry`) accept GeoJSON coordinates and geometry payloads from the client. Phase 4 validation requirements:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Pydantic models with coordinate range validation (lon: -180..180, lat: -90..90); reject degenerate polygons via Shapely `is_valid` |
| V4 Access Control | yes | Project ID in path; verify project exists and belongs to current session (FastAPI Depends pattern from existing `projects.py`) |
| V2 Authentication | no | Local single-user tool; no auth layer |
| V6 Cryptography | no | No secrets in edit payloads |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Oversized GeoJSON payload (polygon DoS) | DoS | Pydantic `max_items` on coordinate arrays; FastAPI request size limit |
| Path traversal via project_id | Tampering | Validate project_id exists in DB before file ops; use `paths.py` whitelist pattern from existing code |
| Shapely geometry bomb (extremely complex polygon) | DoS | Validate `len(polygon.exterior.coords) < 10000` before processing |

---

## Sources

### Primary (HIGH confidence)
- [package.json verified 2026-04-23] — zundo 2.3.0, zustand 5.0.12, react-konva 19.2.3, konva 10.2.5
- [github.com/charkour/zundo README — fetched 2026-04-23] — `diff` type signature, `partialize`, `limit`, `pause()/resume()` API
- [konvajs.org/docs/react/Drag_And_Drop.html — fetched 2026-04-23] — `draggable`, `onDragEnd`, `e.target.x()/y()` pattern
- [docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Voronoi.html — fetched 2026-04-23] — `ridge_points` attribute definition

### Secondary (MEDIUM confidence)
- [konvajs.org rubber-band selection community pattern — WebSearch 2026-04-23] — `getRelativePointerPosition`, Rect overlay, `mousedown/mousemove/mouseup` on Stage
- [shapely.readthedocs.io — WebSearch 2026-04-23] — `ops.split`, `unary_union`, `simplify(preserve_topology=True)`
- [github.com/shapely/shapely/issues/1951 — fetched 2026-04-23] — `ops.split` silent failure behavior (closed wontfix)
- [github.com/shapely/shapely/issues/2165 — WebSearch 2026-04-23] — `simplify(preserve_topology=True)` can still produce invalid geometries

### Tertiary (LOW confidence / ASSUMED)
- scipy Voronoi performance at 800 seeds — estimated from Qhull O(n log n) characteristics, not benchmarked
- `clearCache()` requirement after polygon point update — inferred from Phase 5 ROADMAP note and Konva documentation pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all library versions verified from package.json
- zundo API: HIGH — fetched directly from GitHub README; `diff` type confirmed as function
- Architecture patterns: HIGH — based on existing codebase patterns + official docs
- Shapely split pitfalls: HIGH — verified from GitHub issues (closed wontfix)
- Voronoi performance: LOW — ASSUMED, not benchmarked at this scale

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (stable ecosystem; zundo 2.3.0 is current stable)
