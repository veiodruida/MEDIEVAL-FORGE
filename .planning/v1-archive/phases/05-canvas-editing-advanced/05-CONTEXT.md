# Phase 5: Canvas Editing — Advanced — Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Two independent editing tools: terrain paint brush with land mask (EDIT-05) and reference overlay with opacity slider (EDIT-06). Both run on top of the Phase 4 editing infrastructure (edit mode gate, undo stack, persistence strategy) without touching Voronoi recalc or polygon boolean ops.

**In scope (EDIT-05, EDIT-06):**
- Terrain paint brush: territory-click + radius model, adjustable brush size, undo-tracked, terrain layer toggle with color + emoji badges
- Reference overlay: client-side file picker → Konva Image, opacity slider in useUIStore (not undo-tracked), ephemeral (lost on reload)

**Out of scope:**
- Raster/pixel brush (terrain stays per-territory, not per-pixel)
- Server-side overlay upload or persistence
- Barony-level terrain painting
- Any validation gate or export changes (Phase 6)

</domain>

<decisions>
## Implementation Decisions

### D-01 — Terrain painting model: territory-click + brush radius
- Hovering/dragging over the canvas while holding the mouse button (in terrain paint mode) assigns the selected terrain type to all territories whose centroid falls within the brush radius of the cursor position.
- Brush radius is configurable via a slider in the terrain toolbar; stored in `useEditorStore` as transient UI state (not undo-tracked).
- Backend endpoint: `POST /api/edit/paint-terrain { territory_ids: string[], terrain_type: TerrainType }`. Backend validates land mask: each territory_id is checked (centroid falls on a land pixel). Ocean territories are silently excluded from the result.
- A single mousedown → mousemove → mouseup sequence is one named undo transaction. The transaction accumulates all territory_ids painted during the drag; the named label is generated on mouseup.

### D-02 — Terrain visual feedback: color mode + Unicode emoji badges
- When the 'terrain' layer toggle is ON: territory fill color switches to a terrain-specific color (mountain=gray, forest=dark green, plains=yellow-green, river=teal, arid=tan). Kingdom colors are hidden in terrain view.
- When the 'terrain' layer toggle is OFF (default): territory fills use kingdom colors (current behavior). This is a display toggle, not a data change.
- A small Unicode emoji badge is rendered at each territory centroid as a Konva Text node: mountain=⛰️, forest=🌲, plains=🌾, river=🌊, arid=🏜️. Badge is visible regardless of terrain layer toggle (it's additive, not exclusive).
- `LayerName` in `uiStore.ts` must be extended to include `'terrain'`. Default visibility: OFF.

### D-03 — Terrain undo behavior: undo-tracked via zundo named transactions
- Each terrain paint stroke (mousedown → mouseup) is a named transaction in the `useProjectStore` temporal history.
- Transaction label format: e.g. `"Pintar Montanha — 3 condados"` (terrain type + count).
- The temporal snapshot diff covers `terrain_types: Record<string, TerrainType>` added to `useProjectStore`. With diff:true, only the changed keys are stored (small per operation, even at 800 territories).
- `temporal.pause()` before stroke start, `temporal.resume()` after mouseup — same compound-step pattern as Phase 4 D-05.
- Follows the same Ctrl+Z / Ctrl+Y keyboard bindings already wired in Phase 4.

### D-04 — Overlay: client-side ephemeral, opacity in useUIStore
- File picker (HTML `<input type="file">`) → `URL.createObjectURL()` → Konva Image node on a dedicated overlay Layer behind territory polygons.
- Opacity state: `overlayOpacity: number` (0.0–1.0) and `overlayImageUrl: string | null` added to `useUIStore`. Neither is undo-tracked.
- No server upload, no SQLite persistence. The overlay is lost on page reload — intentional (reference-only tool).
- On project change or canvas geometry update: `clearCache()` called on the overlay Konva Image to prevent hit canvas desync.
- The overlay Layer z-order: above BackgroundLayer, below TerritoryLayer (sits behind territory polygons).

### Claude's Discretion
- Exact brush radius unit (pixels vs. geographic km) — Claude picks the most natural unit for the Konva canvas coordinate system.
- Terrain color palette exact hex values — Claude selects visually distinct, historically appropriate colors.
- Slider range and step size for brush radius — Claude picks sensible defaults (e.g., 1–100px radius, step 5).
- Emoji font/size in the badge Konva Text node — Claude picks a readable size at typical zoom levels.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 scope anchors
- `.planning/ROADMAP.md` §"Phase 5: Canvas Editing — Advanced" — goal, requirements, success criteria, critical constraints, plan outlines
- `.planning/REQUIREMENTS.md` EDIT-05, EDIT-06

### Phase 4 editing infrastructure (read before touching editing code)
- `.planning/phases/04-canvas-editing-basic/04-CONTEXT.md` — all Phase 4 decisions: edit mode gate (D-09), zundo partialize+diff (D-05), persistence strategy (D-07), ToolMode enum

### Tech stack constraints
- `CLAUDE.md` §"Potential Issues #2 zundo" — temporal middleware, partialize, diff, limit, handleSet, pause()/resume() API
- `CLAUDE.md` §"Tech Stack" — Zustand 5, zundo 2.3.0, react-konva 19.x, FastAPI async

### Existing canvas patterns (read before editing canvas code)
- `frontend/src/components/canvas/CanvasViewer.tsx` — Stage setup, layer order, edit mode gating
- `frontend/src/stores/uiStore.ts` — LayerName type (extend with 'terrain'), useUIStore shape
- `frontend/src/stores/useEditorStore.ts` — ToolMode enum (extend with 'paint'), transient UI state
- `frontend/src/types/editing.ts` — all editing type contracts (extend with TerrainType, PaintTerrainRequest/Response)
- `frontend/src/stores/useProjectStore.ts` — zundo temporal wrapper (add terrain_types slice here)
- `frontend/src/api/edit.ts` — existing edit API client patterns (add paintTerrain call here)

### Backend geometry patterns
- `backend/medieval_forge/services/generator.py` — land mask generation (source of `land[y,x]` check used in paint-terrain guard)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CanvasViewer.tsx` — Layer ordering pattern; add overlay Layer below TerritoryLayer and terrain emoji Layer above TerritoryLayer
- `DecorationsLayer.tsx` — centroid badge pattern (already renders capital markers at centroids); emoji badges follow the same approach
- `EditToolbar.tsx` — add terrain paint tool button + terrain type selector here; brush radius slider also lives here
- `useEditorStore.ts` — add `activeTerrain: TerrainType | null` and `brushRadius: number` (transient, not in temporal)
- `LayerTogglePanel.tsx` — add 'terrain' toggle entry (uiStore already has toggleLayer action)
- `useProjectStore.ts` — add `terrain_types: Record<string, TerrainType>` to the temporally-tracked state slice

### New Integration Points
- New endpoint: `POST /api/edit/paint-terrain` → `{ territory_ids, terrain_type }` → land mask guard → SQLite update → returns `{ painted_ids, skipped_ids }`
- New store fields: `useUIStore` += `overlayImageUrl`, `overlayOpacity`
- New store fields: `useEditorStore` += `activeTerrain`, `brushRadius`
- New store fields: `useProjectStore` += `terrain_types` (undo-tracked)
- New component: `TerrainOverlayLayer.tsx` — Konva Image node for reference overlay
- New component: `TerrainBadgesLayer.tsx` — Konva Text emoji badges at centroids

### Paint Interaction Pattern (territory-click + radius)
- On `mousemove` over Stage (while mousedown held, in paint tool mode):
  1. Get cursor position in canvas coordinates
  2. Find all territory centroids within `brushRadius` pixels
  3. Send `POST /api/edit/paint-terrain` with those territory_ids
  4. Optimistic update: apply new terrain_type to those territories in Zustand immediately
  5. Revert on error

### Performance Constraint
- zundo diff:true already wired from Phase 4 — terrain_types diff per stroke will be <1KB even for large radius brushes (only changed territory ids + terrain type).

</code_context>

<specifics>
## Specific Ideas

- Terrain layer toggle is a VIEW MODE switch, not a data filter: turning it ON replaces kingdom colors with terrain colors; turning it OFF restores kingdom colors. The emoji badges are always visible (not toggled by the terrain layer).
- The overlay image sits BEHIND the territory polygons (between BackgroundLayer and TerritoryLayer), so territory borders and colors remain legible. The user blends it in subtly with the opacity slider.
- The land mask guard on the backend is a pre-check using the same land-mask array already computed by `map_generator.py`. If a territory centroid pixel is ocean, the territory is silently excluded from the `painted_ids` response — no error toast.

</specifics>

<deferred>
## Deferred Ideas

- Per-territory manual terrain override dialog (right-click → "Set terrain type") — a quick task if the brush approach feels coarse; not Phase 5 scope
- Terrain hatch/texture overlay (diagonal lines, tree icons as SVG) — deferred to v2
- Server-side overlay upload and persistence — deferred to v2 requirements
- Barony-level terrain painting — barony selection not wired until after Phase 5

</deferred>

---

*Phase: 05-canvas-editing-advanced*
*Context gathered: 2026-04-27*
