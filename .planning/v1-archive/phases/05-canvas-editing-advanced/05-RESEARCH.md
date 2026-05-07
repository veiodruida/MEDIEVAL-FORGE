# Phase 5: Canvas Editing — Advanced — Research

**Researched:** 2026-04-27
**Domain:** React/Konva canvas interaction, Zustand/zundo state extension, FastAPI terrain endpoint
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Terrain painting model: territory-click + brush radius**
- Hovering/dragging over the canvas while holding mouse button (in terrain paint mode) assigns the selected terrain type to all territories whose centroid falls within brushRadius pixels of the cursor.
- Brush radius stored in `useEditorStore` as `brushRadius: number` (transient, not undo-tracked).
- Backend endpoint: `POST /api/edit/paint-terrain { territory_ids: string[], terrain_type: TerrainType }`. Backend validates land mask per centroid using Shapely `land_mask.contains(Point(lon, lat))`.
- One mousedown → mousemove → mouseup = one named undo transaction accumulated from all territory_ids during drag.

**D-02 — Terrain visual feedback: color mode + Unicode emoji badges**
- Terrain layer ON: fill = terrain-specific color (palette locked in 05-UI-SPEC.md). Emoji badge at each territory centroid as Konva Text node. Kingdom colors hidden.
- Terrain layer OFF (default): kingdom colors, emoji badges still additive/visible.
- `LayerName` extended with `'terrain'`. Default visibility: OFF.

**D-03 — Terrain undo behavior: zundo named transactions**
- Each paint stroke = one named transaction in `useProjectStore` temporal history.
- Label: `"Pintar {TerrainName} — {N} condado(s)"` (Portuguese).
- `terrain_types: Record<string, TerrainType>` added to `useProjectStore` temporally-tracked slice.
- `temporal.pause()` before stroke start, `temporal.resume()` after mouseup.
- Follows existing Ctrl+Z / Ctrl+Y bindings from Phase 4.

**D-04 — Overlay: client-side ephemeral, opacity in useUIStore**
- `URL.createObjectURL()` → Konva Image on dedicated overlay Layer.
- `overlayOpacity: number` (0.0–1.0) and `overlayImageUrl: string | null` added to `useUIStore`.
- Not undo-tracked. Lost on page reload — intentional.
- `clearCache()` called on the overlay Konva Image on project/geometry change (rationale: verified as an inherited precaution — see Pitfall 5 below for scope clarification).
- Overlay Layer z-order: above BackgroundLayer, below TerritoryLayer.

### Claude's Discretion
- Brush radius unit (pixels), range, step, default — resolved in UI-SPEC: `min=10 max=80 step=5 default=30`.
- Terrain hex palette — resolved in UI-SPEC.
- Emoji font/size — resolved in UI-SPEC: `fontSize=14`, `offsetX=7`, `offsetY=7`.

### Deferred Ideas (OUT OF SCOPE)
- Per-territory right-click terrain override dialog
- Terrain hatch/texture overlay
- Server-side overlay upload and persistence
- Barony-level terrain painting
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EDIT-05 | User can paint terrain type (mountain, river, forest, plains, arid) with a brush that respects land mask; ocean cells cannot be painted | D-01/D-02/D-03 decisions + backend land mask via `load_land_mask_and_bbox` (Shapely centroid check), frontend optimistic update + rollback pattern from existing `handleCapitalDragEnd` |
| EDIT-06 | User can upload a reference overlay image with adjustable opacity | D-04 decision + `URL.createObjectURL` → Konva Image + `useUIStore` opacity + `URL.revokeObjectURL` discipline |
</phase_requirements>

---

## Summary

Phase 5 adds two independent editing tools on top of Phase 4 infrastructure. The terrain paint brush extends `useProjectStore` with a new `terrain_types` undo-tracked field, requires the `diff()` function to be updated to handle a third slice, and needs a new `POST /api/edit/paint-terrain` endpoint that reuses the existing `load_land_mask_and_bbox` Shapely geometry from `services/voronoi.py` for per-centroid ocean exclusion. The reference overlay is a pure client-side feature: a Konva Image node driven by `useUIStore` state with no backend involvement.

The most important code-level risks are: (1) the existing `diff()` function in `useProjectStore.ts` covers only `territories` and `capitals` — adding `terrain_types` without extending `diff()` silently breaks terrain paint undo; (2) `hydrate()` currently takes three parameters and must be extended or supplemented; (3) `terrain_types.json` already exists on disk as the generator's RGB→type palette, so the new Zustand field must use a different name to avoid confusion; and (4) no SQLite column or file location has been defined for persisting `terrain_types` — the planner must pick a storage strategy.

**Primary recommendation:** Implement terrain_types as a JSON property persisted into `territories.geojson` feature properties (one key per feature), which aligns with the existing Phase 4 save strategy (D-07 persist flag) and avoids a new database migration.

---

## Standard Stack

### Core (no new dependencies — all Phase 4 deps)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| react-konva | 19.2.x | Konva Layer/Image/Text/Circle nodes | [VERIFIED: package.json Phase 4] |
| konva | 9.x | Canvas primitives, clearCache(), listening | [VERIFIED: package.json Phase 4] |
| zustand | 5.0.12 | State management | [VERIFIED: package.json Phase 4] |
| zundo | 2.3.0 | Temporal undo — temporal.pause/resume | [VERIFIED: package.json Phase 4] |
| @radix-ui/themes | ^3.3.0 | Slider, Card, Button, SegmentedControl | [VERIFIED: 05-UI-SPEC.md] |
| FastAPI | 0.115.x | Backend endpoint | [VERIFIED: pyproject.toml Phase 4] |
| Shapely | 2.1.x | Land mask centroid check (`contains`) | [VERIFIED: voronoi.py uses Shapely geometry] |

**No new npm or pip dependencies required for Phase 5.** [VERIFIED: 05-UI-SPEC.md §Registry Safety]

---

## Architecture Patterns

### Recommended Project Structure

New files for Phase 5 (locked by 05-UI-SPEC.md):

```
frontend/src/
├── components/canvas/
│   ├── TerrainOverlayLayer.tsx   # Konva Layer + Image; opacity from useUIStore
│   ├── TerrainBadgesLayer.tsx    # Konva Layer + Text emoji badges at centroids
│   └── ReferenceOverlayPanel.tsx # Radix Card; file input + opacity Slider
backend/medieval_forge/api/edit.py  # extend — add paint_terrain endpoint
backend/tests/api/test_paint_terrain.py   # Wave 0 RED test
```

Modified files:
```
frontend/src/
├── stores/uiStore.ts          # add overlayOpacity, overlayImageUrl, 'terrain' LayerName
├── stores/useEditorStore.ts   # add activeTerrain: TerrainType | null, brushRadius: number
├── stores/useProjectStore.ts  # add terrain_types slice + extend partialize + extend diff()
├── types/editing.ts           # add TerrainType, PaintTerrainRequest, PaintTerrainResponse
├── api/edit.ts                # add paintTerrain() function
└── components/canvas/
    ├── CanvasViewer.tsx       # mount new layers, wire paint handlers, P keyboard shortcut
    ├── EditToolbar.tsx        # paint terrain button + terrain type selector + brush slider
    └── LayerTogglePanel.tsx   # add 'terrain' toggle entry
```

### Pattern 1: Extending useProjectStore with terrain_types

**What:** Add `terrain_types: Record<string, TerrainType>` to the partialized/diff-tracked slice.
**Critical:** `partialize()` and `diff()` BOTH must be updated. The current `diff()` only compares `territories` and `capitals`. A third comparison block for `terrain_types` must be added with identical key-delta logic.

```typescript
// Source: frontend/src/stores/useProjectStore.ts (existing diff pattern to extend)

// Step 1: Update GeometrySlice type
type GeometrySlice = Pick<ProjectStore, 'territories' | 'capitals' | 'terrain_types'>

// Step 2: Update partialize to include terrain_types
function partialize(state: ProjectStore): GeometrySlice {
  return {
    territories: state.territories,
    capitals: state.capitals,
    terrain_types: state.terrain_types,   // ADD THIS LINE
  }
}

// Step 3: Add terrain_types delta in diff() — after the capitals block
if (pastState.terrain_types !== currentState.terrain_types) {
  const ttDelta: Record<string, TerrainType> = {}
  const past = pastState.terrain_types ?? {}
  const curr = currentState.terrain_types ?? {}
  for (const id of Object.keys(curr)) {
    if (past[id] !== curr[id]) {
      ttDelta[id] = past[id]  // store PAST value so undo restores it
      changed = true
    }
  }
  for (const id of Object.keys(past)) {
    if (!(id in curr)) {
      ttDelta[id] = past[id]
      changed = true
    }
  }
  if (Object.keys(ttDelta).length > 0) {
    result.terrain_types = ttDelta as GeometrySlice['terrain_types']
  }
}
```

**NOTE on hydrate():** The existing `hydrate(projectId, territories, capitals)` signature needs either (a) an optional fourth parameter `terrain_types?` or (b) a separate `setTerrainTypes(types)` action. Option (b) is lower-risk because `CanvasViewer.tsx` calls `hydrate()` in a history-safe sequence (`temporal.pause()` → `hydrate()` → `temporal.clear()`). A separate `setTerrainTypes` called OUTSIDE that sequence would pollute undo history unless also paused. Recommend option (a): extend `hydrate` signature with optional `terrain_types = {}` so the caller's existing pause/clear sequence covers terrain_types initialization.

### Pattern 2: Paint stroke interaction with optimistic update + rollback

Based on existing `handleCapitalDragEnd` pattern in `CanvasViewer.tsx`:

```typescript
// Sketch of paint stroke handler (not verbatim — planner fills specifics)

// onMouseDown (Stage, activeTool === 'paint'):
const prePaintSnapshot = useProjectStore.getState().terrain_types
beginTransaction()         // temporal.pause()
setStrokeActive(true)
strokeAccumulator.current.clear()

// onMouseMove (Stage, while strokeActive):
const pos = stage.getPointerPosition()
const ids = findTerritoriesInRadius(pos, brushRadius, condados, projection)
ids.forEach(id => {
  strokeAccumulator.current.add(id)
  // Optimistic update to store
  useProjectStore.getState().setTerrainType(id, activeTerrain)
})

// onMouseUp (Stage):
setStrokeActive(false)
const ids = Array.from(strokeAccumulator.current)
try {
  const resp = await paintTerrain(projectId, { territory_ids: ids, terrain_type: activeTerrain })
  // Apply server-filtered result (only painted_ids are confirmed land)
  resp.painted_ids.forEach(id => useProjectStore.getState().setTerrainType(id, activeTerrain))
  // Revert skipped_ids back to pre-stroke state (they were ocean)
  resp.skipped_ids.forEach(id => {
    const prev = prePaintSnapshot[id]
    if (prev) useProjectStore.getState().setTerrainType(id, prev)
    else useProjectStore.getState().clearTerrainType(id)
  })
} catch {
  // Full rollback
  useProjectStore.getState().restoreTerrainTypes(prePaintSnapshot)
  // show error toast
} finally {
  endTransaction()         // temporal.resume()
}
const label = `Pintar ${terrainLabel} — ${ids.length} condado(s)`
pushUndoLabel(label)
```

### Pattern 3: Backend land mask guard using existing Shapely helper

The existing `services/voronoi.py::load_land_mask_and_bbox()` returns a Shapely geometry for the land area. The paint-terrain endpoint uses this to check each centroid:

```python
# Source: existing pattern in backend/medieval_forge/api/edit.py (move_capital)
from ..services.voronoi import load_land_mask_and_bbox
from ..services.paths import project_dir
from shapely.geometry import Point

land_mask, _ = load_land_mask_and_bbox(project_dir(project_id) / "generated")

painted_ids = []
skipped_ids = []
for tid in body.territory_ids:
    lon, lat = capitals.get(tid, (None, None))
    if lon is None or lat is None:
        skipped_ids.append(tid)
        continue
    if land_mask is not None and not land_mask.contains(Point(lon, lat)):
        skipped_ids.append(tid)
        continue
    painted_ids.append(tid)
# ... persist painted terrain types ...
return { "painted_ids": painted_ids, "skipped_ids": skipped_ids }
```

**Land mask guard semantics (CONTEXT vs. ROADMAP reconciliation):** ROADMAP says `if land[y,x]` (pixel-space). CONTEXT.md D-01 says "centroid falls on a land pixel." The existing `load_land_mask_and_bbox` helper already converts the raster land mask to a Shapely geometry in lon/lat space. Using `land_mask.contains(Point(lon, lat))` is the natural expression of CONTEXT's intent. This is the correct and existing pattern. [VERIFIED: voronoi.py lines 295-376]

### Pattern 4: TerrainOverlayLayer (Konva Image with URL.createObjectURL)

```typescript
// Source: react-konva Image pattern [ASSUMED - standard react-konva usage]
import { Layer, Image as KonvaImage } from 'react-konva'
import useImage from 'use-image'  // NOTE: already installed in project — verify below

// Alternative without use-image (avoids extra dep):
// Load via HTMLImageElement directly
function TerrainOverlayLayer({ mapW, mapH }: Props) {
  const overlayImageUrl = useUIStore(s => s.overlayImageUrl)
  const overlayOpacity = useUIStore(s => s.overlayOpacity)
  const [img] = useImage(overlayImageUrl ?? '')  // use-image returns null when url is ''

  if (!img) return null
  return (
    <Layer listening={false}>
      <KonvaImage
        image={img}
        x={0} y={0}
        width={mapW} height={mapH}
        opacity={overlayOpacity}
        listening={false}
      />
    </Layer>
  )
}
```

**Check if `use-image` is already installed before adding it as a dep.** [VERIFIED: see Environment Availability below]

### Anti-Patterns to Avoid

- **Calling `diff: true` instead of the function:** zundo 2.3.0 requires `diff` as a function, not `true`. The codebase already uses the function form. Do not change it. [VERIFIED: useProjectStore.ts line 76]
- **Calling `setTerrainType` outside `beginTransaction/endTransaction`:** Any mutation to the partialized slice outside a transaction will create an extra undo step. All terrain_types mutations during a paint stroke must be paused.
- **Adding terrain_types to `useUIStore` instead of `useProjectStore`:** Undo-tracked data belongs in the temporal-wrapped store. `useUIStore` is correct only for `overlayOpacity` and `overlayImageUrl`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Land mask check | Custom pixel-raster scan in paint endpoint | `load_land_mask_and_bbox()` + `shapely.contains()` | Already exists in voronoi.py; tested; handles edge cases (missing file, invalid geometry) |
| Compound undo batching | Custom history accumulator | `beginTransaction()` / `endTransaction()` from useProjectStore.ts | Already wired for capital drag; identical pattern |
| Object URL lifecycle | Manual cache/revoke management | `URL.createObjectURL()` / `URL.revokeObjectURL()` in uiStore action | Browser API; revokeObjectURL MUST be called both on clear AND on replace |

---

## Runtime State Inventory

> This is a greenfield feature addition, not a rename/refactor. Categories below reflect new state introduced.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `terrain_types.json` on disk = generator RGB palette (NOT per-territory data). No existing per-territory terrain assignments stored anywhere. | Design decision required: pick persistence location for new per-territory terrain data (see Open Questions) |
| Live service config | None — no external services involved | None |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | None new | None |

---

## Common Pitfalls

### Pitfall 1: diff() not extended for terrain_types — undo silently no-ops
**What goes wrong:** Adding `terrain_types` to `partialize()` but NOT adding a third comparison block to `diff()` causes the diff function to return `null` for terrain-only changes. Zundo records no undo step. Ctrl+Z does nothing after paint strokes.
**Why it happens:** The diff function in `useProjectStore.ts` has explicit blocks only for `territories` and `capitals`. New partialize fields are invisible to diff unless explicitly added.
**How to avoid:** The `GeometrySlice` type, `partialize()`, and `diff()` must all be updated atomically in the same task.
**Warning signs:** Paint stroke completes, undo button stays disabled, no undo step in `pastStates`.
[VERIFIED: useProjectStore.ts lines 81-135]

### Pitfall 2: terrain_types naming collision with existing terrain_types.json
**What goes wrong:** Code reviewers or future developers confuse the Zustand field `terrain_types: Record<string, TerrainType>` with the generator artifact `terrain_types.json` (the RGB→type palette for Unity). The generator file uses keys like `"119,119,119"` (RGB strings) → game stat objects. The new store field uses `condado_id` → `TerrainType` enum.
**How to avoid:** Consider naming the Zustand field `condado_terrain: Record<string, TerrainType>` or `paintedTerrain: Record<string, TerrainType>` to avoid the collision. The CONTEXT.md name `terrain_types` was chosen before this collision was noticed — the planner should pick a disambiguating name.
[VERIFIED: generator.py line 41, test_generate.py line 402]

### Pitfall 3: URL.revokeObjectURL called only on clear, not on replace
**What goes wrong:** User loads image A (creates blob URL). Loads image B (creates new blob URL). Old blob URL for A is never revoked → memory leak per browser tab session.
**How to avoid:** The `setOverlayImageUrl` action in `useUIStore` must revoke the OLD url before setting the new one:
```typescript
setOverlayImageUrl: (newUrl) => set(s => {
  if (s.overlayImageUrl) URL.revokeObjectURL(s.overlayImageUrl)
  return { overlayImageUrl: newUrl }
})
```
[ASSUMED — standard web platform leak pattern, but logic is verified from UI-SPEC §Reference Overlay]

### Pitfall 4: Brush cursor rendered as a tracked Konva shape (hit pollution)
**What goes wrong:** If the brush cursor circle is added with `listening={true}` (default), it intercepts mousemove events and the centroid-search logic gets cursor coordinates from the circle rather than the Stage.
**How to avoid:** Brush cursor circle MUST have `listening={false}`. [VERIFIED: 05-UI-SPEC.md §Brush Cursor]

### Pitfall 5: clearCache() scope — nodes with listening=false have no hit canvas
**What goes wrong (claimed):** The ROADMAP and CONTEXT.md state `clearCache()` must be called on the overlay Konva Image "to prevent hit canvas desync." For nodes with `listening={false}`, Konva excludes them from hit detection entirely — there is no hit canvas for these nodes to desync.
**Actual risk:** `clearCache()` on a non-listening node is not harmful (it's a no-op for the hit canvas) but it's also not necessary. The real reason to call `clearCache()` on geometry change is when a shape has been cached (via `cache()`) for performance and the underlying data changes — the cached scene canvas becomes stale.
**Recommendation:** Call `clearCache()` only on nodes that have had `cache()` called on them. For TerrainOverlayLayer and TerrainBadgesLayer — neither of which caches by default — skip `clearCache()` unless `cache()` is explicitly used for performance.
**Confidence:** MEDIUM — Konva docs confirm `listening=false` excludes from hit canvas. Whether the Image node auto-caches is implementation-specific. [CITED: https://konvajs.org/docs/performance/Listening_False.html]
[ASSUMED: exact caching behavior of Konva.Image without explicit .cache() call — tag for empirical validation]

### Pitfall 6: hydrate() does not initialize terrain_types on project open
**What goes wrong:** User opens project, makes terrain paint edits in a prior session (if persistence is implemented), reloads page. `hydrate()` restores territories and capitals but terrain_types comes back empty. Canvas shows no terrain colors.
**How to avoid:** Extend `hydrate(projectId, territories, capitals, terrain_types = {})` signature so the CanvasViewer hydration sequence can pass loaded terrain data.
[VERIFIED: useProjectStore.ts lines 46-49, CanvasViewer.tsx lines 286-311]

### Pitfall 7: Optimistic update applied to skipped_ids not rolled back
**What goes wrong:** During a paint stroke, ALL centroids within brush radius get an optimistic `setTerrainType` update. Backend returns `skipped_ids` (ocean territories). Frontend must revert `skipped_ids` to their PRE-STROKE value, not simply delete them (a territory might have had a previously painted terrain type).
**How to avoid:** Capture `prePaintSnapshot = useProjectStore.getState().terrain_types` before `beginTransaction()`. On `skipped_ids`, restore from snapshot rather than calling delete.

---

## Code Examples

### Centroid radius search (canvas pixels)
```typescript
// Source: pattern derived from existing useRubberBandSelection hook
// Find condado centroids within brushRadius canvas pixels of cursorPos
function findTerritoriesInRadius(
  cursorPos: { x: number; y: number },
  brushRadius: number,
  condados: TerritoryMetadataCondado[],
  projection: ProjectionConfig,
): string[] {
  return condados
    .filter(c => {
      const [cx, cy] = geoToCanvas(c.lon, c.lat, projection)
      const dx = cx - cursorPos.x
      const dy = cy - cursorPos.y
      return dx * dx + dy * dy <= brushRadius * brushRadius
    })
    .map(c => c.id)
}
```

### TerrainBadgesLayer emoji rendering
```typescript
// Source: adapted from DecorationsLayer.tsx centroid badge pattern
// [VERIFIED: DecorationsLayer.tsx lines 99-143]
<Text
  key={`terrain-badge-${c.id}`}
  x={x}
  y={y}
  text={TERRAIN_EMOJI[terrainType]}
  fontSize={14}
  listening={false}
  align="center"
  verticalAlign="middle"
  offsetX={7}
  offsetY={7}
/>
```

### Backend Pydantic schemas for paint-terrain
```python
# Add to backend/medieval_forge/schemas.py
from pydantic import BaseModel
from typing import Literal

TerrainType = Literal["mountain", "forest", "plains", "river", "arid"]

class PaintTerrainRequest(BaseModel):
    territory_ids: list[str]
    terrain_type: TerrainType

class PaintTerrainResponse(BaseModel):
    painted_ids: list[str]
    skipped_ids: list[str]
```

---

## Open Questions (RESOLVED)

### 1. Where does per-territory terrain data persist? [RESOLVED: Option B]

**Resolution:** Per Plan 5.1 `<persistence_decision>`: terrain data stored as `properties.terrain_type` per feature in `territories.geojson` (Option B — GeoJSON feature property). Aligns with Phase 4 D-07 save strategy; no SQLite migration required.

**What we know:** CONTEXT.md D-01 says "SQLite update" and "Backend validates land mask... SQLite update." No SQLite column for terrain currently exists. The generator's `terrain_types.json` is the RGB palette (not per-territory data).

**Options:**
- **Option A — JSON column on Project model:** Add `condado_terrain: dict` to SQLAlchemy `Project` model. Requires a new Alembic migration. Simple one-shot write per stroke. Pro: atomic. Con: migration overhead, not co-located with geometry.
- **Option B — Per-feature property in territories.geojson:** Add `"terrain_type"` to each GeoJSON feature's `properties` dict. Aligns with existing D-07 save strategy (persist flag, `saveSnapshot()` flush). No migration. Pro: geometry and terrain travel together. Con: terrain data is in a file, not DB; won't survive a full pipeline regeneration unless migration code is written.
- **Option C — Separate terrain_assignments.json sidecar:** New file per project in `generated/`. Simplest to implement. No migration. Co-located with geometry artifacts. Con: another file to manage.

**Original recommendation:** Option B (GeoJSON feature property) is most consistent with the Phase 4 D-07 save strategy and does not require a migration.

### 2. Does `use-image` need to be added as a dependency? [RESOLVED: already installed]

**Resolution:** Per Plan 5.3 interfaces block: `use-image ^1.1.4` is VERIFIED installed in `frontend/package.json`. No new npm dependency required.

**What we know:** `use-image` is a common react-konva companion for loading images from URLs. Its installation status in the current project is not confirmed in the files read.
**Original recommendation:** The planner must run `npm list use-image` in `frontend/` and either use it if present or implement a minimal `useImage` hook inline (< 20 lines, standard React pattern with HTMLImageElement + onload). Do not add a new npm dep without checking.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 5 is purely frontend canvas interaction + one backend endpoint extending an existing router. No external CLIs, databases beyond the existing SQLite, or services are required. All runtime dependencies (Node.js, Python, FastAPI, SQLite) were confirmed available in prior phases.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (backend), Vitest (frontend) |
| Config file | `backend/pytest.ini` or `pyproject.toml [tool.pytest]`, `frontend/vitest.config.*` |
| Quick run command (backend) | `cd backend && pytest tests/api/test_paint_terrain.py -x` |
| Full suite command (backend) | `cd backend && pytest` |
| Quick run command (frontend) | `cd frontend && npx vitest run src/components/canvas/` |
| Full suite command (frontend) | `cd frontend && npx vitest run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EDIT-05 | `POST /api/edit/paint-terrain` land mask guard | unit | `pytest tests/api/test_paint_terrain.py::test_paint_terrain_excludes_ocean -x` | Wave 0 |
| EDIT-05 | `POST /api/edit/paint-terrain` paints land territories | unit | `pytest tests/api/test_paint_terrain.py::test_paint_terrain_returns_painted_ids -x` | Wave 0 |
| EDIT-05 | terrain_types diff — undo step recorded | unit | `vitest run src/stores/useProjectStore.test.ts` | Wave 0 |
| EDIT-05 | TerrainBadgesLayer renders emoji at centroid | unit | `vitest run src/components/canvas/TerrainBadgesLayer.test.tsx` | Wave 0 |
| EDIT-05 | Optimistic update reverts skipped_ids on error | unit | `vitest run src/components/canvas/CanvasViewer.test.tsx` | Wave 0 |
| EDIT-06 | TerrainOverlayLayer renders at correct z-order | unit | `vitest run src/components/canvas/TerrainOverlayLayer.test.tsx` | Wave 0 |
| EDIT-06 | ReferenceOverlayPanel file input + opacity slider | unit | `vitest run src/components/canvas/ReferenceOverlayPanel.test.tsx` | Wave 0 |
| EDIT-06 | URL.revokeObjectURL called on replace | unit | `vitest run src/stores/uiStore.test.ts` | Wave 0 |

### Sampling Rate

- **Per task commit:** quick run for the file being changed
- **Per wave merge:** full suite (backend + frontend)
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/api/test_paint_terrain.py` — covers EDIT-05 backend guard + success path
- [ ] `frontend/src/stores/useProjectStore.test.ts` — extend existing tests to cover terrain_types diff block
- [ ] `frontend/src/components/canvas/TerrainBadgesLayer.test.tsx` — emoji at centroid
- [ ] `frontend/src/components/canvas/TerrainOverlayLayer.test.tsx` — image + opacity
- [ ] `frontend/src/components/canvas/ReferenceOverlayPanel.test.tsx` — file input + slider
- [ ] `frontend/src/stores/uiStore.test.ts` — extend to cover overlayOpacity, overlayImageUrl, revokeObjectURL

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `TerrainType` Pydantic Literal union on backend; `territory_ids` validated as non-empty list |
| V4 Access Control | no | Single-user local tool, no auth layer |
| V2 Authentication | no | Local tool, no user accounts |
| V6 Cryptography | no | No secrets or crypto involved |

**Threat pattern:** `territory_ids` list injection — backend must validate each id against the known territory set for the project before performing the centroid lookup (prevents lookup of arbitrary IDs against the wrong project's land mask). This is a lightweight check: filter to ids present in `territories.geojson` for the given `project_id`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `clearCache()` on Konva nodes with `listening=false` is unnecessary (they have no hit canvas) | Pitfall 5 | If Konva does internally cache `listening=false` nodes for the scene canvas, skipping clearCache could cause stale visual rendering. Low risk — easy to add if observed. |
| A2 | `use-image` is not yet installed as a project dependency | Open Questions §2 | If it IS installed, the planner can use it directly instead of an inline hook |
| A3 | `URL.revokeObjectURL` on replacement is the correct memory-management pattern for blob URLs created by `createObjectURL` | Pitfall 3 | Standard web platform behavior — very low risk of being wrong |

---

## Sources

### Primary (HIGH confidence)
- `frontend/src/stores/useProjectStore.ts` — existing diff() and partialize() to be extended
- `frontend/src/stores/useEditorStore.ts` — ToolMode enum, existing transient store shape
- `frontend/src/types/editing.ts` — types to extend with TerrainType, PaintTerrainRequest/Response
- `frontend/src/api/edit.ts` — edit API client patterns for new paintTerrain() function
- `frontend/src/components/canvas/CanvasViewer.tsx` — existing paint interaction wiring surface, hydrate pattern
- `frontend/src/components/canvas/DecorationsLayer.tsx` — centroid badge pattern for TerrainBadgesLayer
- `frontend/src/components/canvas/EditToolbar.tsx` — toolbar extension pattern
- `frontend/src/components/canvas/LayerTogglePanel.tsx` — layer toggle extension
- `frontend/src/stores/uiStore.ts` — LayerName type, UIState to extend
- `backend/medieval_forge/services/voronoi.py` lines 295–376 — `load_land_mask_and_bbox()` reusable helper
- `backend/medieval_forge/api/edit.py` — existing edit endpoint patterns
- `.planning/phases/05-canvas-editing-advanced/05-CONTEXT.md` — locked decisions
- `.planning/phases/05-canvas-editing-advanced/05-UI-SPEC.md` — locked UI contract

### Secondary (MEDIUM confidence)
- [Konva listening=false docs](https://konvajs.org/docs/performance/Listening_False.html) — confirms no hit canvas for non-listening nodes (clearCache scope)
- [Konva Shape Caching docs](https://konvajs.org/docs/performance/Shape_Caching.html) — confirms cache() is opt-in

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all Phase 4 libs
- Architecture: HIGH — locked by CONTEXT.md + UI-SPEC.md; code patterns verified in codebase
- Pitfalls: HIGH — verified against actual useProjectStore.ts, voronoi.py, CanvasViewer.tsx source
- Persistence design: LOW — open question, no existing code to verify against

**Research date:** 2026-04-27
**Valid until:** 2026-05-27
