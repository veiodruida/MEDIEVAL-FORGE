# Phase 2: Read-Only Canvas Viewer - Research

**Researched:** 2026-04-17
**Domain:** Interactive Konva 2D map canvas (React 19 + react-konva 19.x), geo→pixel projection, Zustand selection slice, TanStack Query v5 data loading, Tailwind v4 + Radix integration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Visual Style & Color Coding**
- **D-01:** Territory fill colors are read from `lookup_condado_colors.json` and `lookup_barony_colors.json` (produced by `map_generator.py` in Phase 1). The canvas never generates its own palette — guarantees pixel-parity with the PNG previews so there is no drift between Konva render and exported Unity assets.
- **D-02:** Condados are the primary fill level by default. Baronies render only when their layer toggle is ON (stacked above condados at reduced opacity or via thinner internal borders — planner's call within this constraint).
- **D-03:** Selection highlight is a thicker bright-stroke border (2–3 px gold/yellow) drawn on top of the existing fill. The selected territory's fill color stays unchanged so hierarchy context remains readable at all zoom levels. No dimming of non-selected polygons.
- **D-04:** Capitals render as filled circles (6–8 px) using the owning territory's color, with a white/dark ring outline for contrast against both light and dark backgrounds. No SVG icons, no persistent city-name text (labels are separate layer).

**Inspector Panel Layout & Content**
- **D-05:** Fixed, always-visible right sidebar (320–360 px wide) on `/projects/:id`. No drawer animations, no floating popover. Canvas area fills the remaining viewport width.
- **D-06:** When a territory is selected, the inspector shows all four property groups (core identity, geometry stats, capital info, neighbors list with clickable chips).
- **D-07:** When nothing is selected, the inspector shows a project summary (project name, country, period, hierarchy totals). Layer toggles are NOT merged into the inspector.

**Layer Toggle UX & Label Behavior**
- **D-08:** Layer toggles live in a floating Radix Card pinned to the top-left corner of the canvas. Five checkboxes in fixed order: Terrain, Territories, Borders, Capitals, Labels.
- **D-09:** Default layer state: Terrain + Territories + Borders + Capitals = ON; Labels = OFF.
- **D-10:** Labels appear via a single hard zoom threshold (~1.5×). No hierarchy tiering.
- **D-11:** Label text shows the territory name only.

**Navigation & Viewport Behavior**
- **D-12:** On project open, the canvas auto-fits the territory bounding box with ~5% padding. No per-project viewport persistence.
- **D-13:** Zoom limits: min = fit-to-view scale, max = 4× native. Pan clamped to map bounds.
- **D-14:** Two keyboard shortcuts only: `Esc` = deselect, `Ctrl+0` = fit-to-view. A visible "Fit to view" button is also required (success criterion 5). All other shortcuts deferred to Phase 4.
- **D-15:** Wheel zoom anchors on the mouse cursor position.

### Claude's Discretion
- Exact threshold value for the label zoom cutoff (D-10) — derive from the Iberia test dataset
- Exact zoom-in max multiplier (nominally 4×, can be tuned 3–6×) and fit-to-view padding percentage
- Font family and font-size for labels; anti-collision strategy
- Baronies rendering style when toggle is ON
- Right-sidebar exact width within 320–360 px band
- `react-konva`/`konva` exact version pin within the 19.x line; `--legacy-peer-deps` usage
- Internal layer architecture of the Konva Stage (3 layers as roadmap hints, or 4–5 if needed for perf)
- GeoJSON loading/caching pattern (TanStack Query config, error-on-missing handling)

### Deferred Ideas (OUT OF SCOPE)
- Persist last viewport per project
- Full keyboard navigation set (Ctrl+/- zoom, arrow-key pan) — deferred to Phase 4
- Multi-select
- Minimap (v2 Requirement)
- Tiered label zoom and smart-by-polygon-size label filtering
- Crown/star capital icons
- Mobile/small-screen responsive layout
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CANVAS-01 | User can view all territories on a Konva canvas with correct colors and borders | Standard Stack (react-konva), Architecture Patterns (Konva Stage layers, `Line` closed polygon pattern), Code Example 1 (projection), 3 (TerritoryPolygon memo), Don't Hand-Roll (projection/polygon serialization) |
| CANVAS-02 | User can pan and zoom the canvas (Stage drag + wheel zoom) | Architecture Patterns (Stage draggable + wheel handler), Code Example 2 (zoom-anchor-on-cursor), Common Pitfalls (pan clamp bug, zoom-at-limit) |
| CANVAS-03 | User can click a territory to select it and see its properties in the right panel | Architecture Patterns (Zustand selection slice, Interaction layer pattern), Code Example 4 (selection slice + Esc hook), Common Pitfalls (Stage-level click on empty space) |
| CANVAS-04 | Canvas shows layer toggles (terrain, territories, borders, capitals, labels) | Architecture Patterns (layerVisibility slice), UI-SPEC decorations vs territories layers, Tailwind v4 + Radix smoke test |
| CANVAS-05 | Canvas shows territory labels at appropriate zoom levels | D-10 single-threshold approach, Code Example 5 (zoom-threshold label gate), Common Pitfalls (label anti-collision) |
| CANVAS-06 | User can fit the map to view (reset zoom/pan) | Architecture Patterns (fit-to-view math + keyboard hook), Code Example 6 (fit-to-view formula), D-13/D-14 constraints |
</phase_requirements>

## Summary

Phase 2 wires a Konva 2D canvas into the existing `/projects/:id` route. The work splits cleanly into three layers: (1) a **pure projection module** (`lib/projection.ts`) that translates WGS84 `(lon, lat)` to canvas pixels using the *same affine formula* the Python generator uses (`map_generator.py` `geo_to_pixel` / `pixel_to_geo`), guaranteeing Konva polygons sit pixel-perfect on top of `terrain.png`; (2) **three to four Konva layers** (Background PNG `listening=false`, Territory polygons interactive, Decorations for capitals/labels `listening=false`, plus an Interaction layer for the selection outline); and (3) **pan/zoom/selection wiring** via Zustand selection slice + a `window` keydown hook for `Esc` / `Ctrl+0`.

The stack is already in place: React 19.2, Vite 6.4, Tailwind 4.2 with `@tailwindcss/vite`, Radix Themes 3.3, TanStack Query 5.99, Zustand 5.0, zundo 2.3. Phase 2 only adds `konva` + `react-konva` to `frontend/package.json`. react-konva 19.2.3 declares React 19.2 as peer (VERIFIED via `npm view`) so **`--legacy-peer-deps` is NOT required**.

**Critical blocker surfaced by this research:** `territory_metadata.json` as produced by the current `map_generator.py` **does not contain polygon geometry or neighbor lists**. It stores `pixel_center` + `pixel_count` + hierarchy only. The canvas needs polygon rings from GeoJSON (`raw/municipalities.geojson` is the municipality source; the generator itself rasterizes to a `int16` territory grid but does not emit per-condado polygon GeoJSON). The planner must decide between (a) adding a generator post-step to emit `territories.geojson` from the `pc` (pixel-to-condado) integer raster via contour/marching-squares, or (b) tracing polygons client-side from `lookup_condado.png`. Option (a) is strongly recommended: do it once on the server using Shapely + `rasterio.features.shapes` or scikit-image `find_contours`, store a per-condado MultiPolygon in a `territories.geojson` file served alongside existing lookups. This research documents both paths but the planner should pick (a).

**Primary recommendation:** 4-layer Konva Stage (Background + Territories + Decorations + Interaction), affine projection mirroring `map_generator.py` exactly (`lon_scale = cos(center_lat_radians)`), Zustand slice for selection + layer visibility, TanStack Query with `staleTime: Infinity` for all phase artifacts, server-side `territories.geojson` emission in a small Phase-2 backend task (plan 2.1 or 2.2), and a first-task Tailwind v4 + Radix + Konva smoke test before sinking plan work.

## Standard Stack

### Core
| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| react-konva | 19.2.3 [VERIFIED: npm view 2026-04-17] | React binding for Konva 2D canvas | Only maintained React binding for Konva; version number mirrors React major. |
| konva | 10.2.5 [VERIFIED: npm view 2026-04-17] | Underlying 2D canvas engine (Stage/Layer/Shape) | Industry-standard for map-like 2D scenes in React; batched rendering, built-in hit-testing, caching. react-konva 19.2.3 peers accept `konva ^8 || ^9 || ^10`. |
| zustand | 5.0.12 [VERIFIED: npm view 2026-04-17] | Selection + layer-visibility state | Already the project's state pattern (Phase 1 wired; zundo middleware unused here). Minimal boilerplate, `useSyncExternalStore` under the hood. |
| @tanstack/react-query | 5.99.0 [VERIFIED: npm view 2026-04-17] | Load GeoJSON + lookup JSONs + metadata from FastAPI | Already wired in Phase 1. Handles caching, refetch-on-focus disable, suspense-compatible. |
| @radix-ui/themes | 3.3.0 [VERIFIED: npm view 2026-04-17] | Inspector + layer panel + Fit-to-view Button + Badge | Already wired in `main.tsx` (`accentColor="iris"`, `radius="medium"`). |
| tailwindcss + @tailwindcss/vite | 4.2.2 [VERIFIED: npm view 2026-04-17] | Layout utilities for the two-region split + floating overlay card | Already wired. Radix CSS imported before `@import "tailwindcss"` in `index.css` (VERIFIED by reading the file; already correct). |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none required) | — | — | All existing deps are sufficient. Resist the urge to add geo libraries — the projection is a 6-line affine, and GeoJSON parsing is `JSON.parse` of a backend response. Hand-rolling a 40-line `projection.ts` beats pulling in `proj4`, `d3-geo`, or `turf`. |

**Installation:**
```bash
# From frontend/
npm install konva@^10 react-konva@^19
# No --legacy-peer-deps needed: React 19.2 + react-konva 19.2.3 peer match
```

[VERIFIED: npm view react-konva@19.2.3 peerDependencies] →
```
{ konva: "^8.0.1 || ^7.2.5 || ^9.0.0 || ^10.0.0", react: "^19.2.0", "react-dom": "^19.2.0" }
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-konva | d3-geo + raw `<canvas>` | More manual; loses hit-testing, scene graph, and React diffing. react-konva wins for click-to-select maps. |
| react-konva | pixi.js + @pixi/react | PIXI is faster for 10k+ sprites but adds a WebGL dependency; Konva handles ~91 polygons on Canvas2D effortlessly. |
| Zustand selection slice | useState in a Context | Works, but the inspector + canvas both subscribe; Zustand avoids Context re-render cascade and aligns with phase 4 zundo wiring. |

**Version verification:** All versions confirmed against npm registry on 2026-04-17 via `npm view <pkg> version`. The UI-SPEC's "react-konva 19.2.x + konva 9.x" guidance should be updated to "konva 10.x" (the peer range accepts 9 and 10; 10 is the current stable with minor improvements). [VERIFIED: npm view konva version = 10.2.5]

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── lib/
│   └── projection.ts              # Pure functions: geoToCanvas, canvasToGeo, geoRingToKonvaPoints, fitToViewScale
├── context/
│   └── ProjectionContext.tsx      # Holds ProjectionConfig (map bbox + map_w/map_h + lon_scale)
├── stores/
│   └── uiStore.ts                 # Zustand: selectedTerritoryId + layerVisibility + LABEL_ZOOM_THRESHOLD
├── hooks/
│   ├── useCanvasArtifacts.ts      # TanStack Query: GeoJSON + lookups + metadata
│   ├── useKeyboardShortcuts.ts    # Esc + Ctrl+0 window listener
│   └── useZoomPan.ts              # Wheel handler + pan clamp helpers
├── pages/
│   └── ProjectDetail.tsx          # Existing page — add <CanvasViewer> + <InspectorSidebar>
└── components/
    └── canvas/
        ├── CanvasViewer.tsx       # Top-level: Stage + 4 Layers + state wiring
        ├── BackgroundLayer.tsx    # KonvaImage(terrain.png), listening={false}
        ├── TerritoryLayer.tsx     # map(condados) → <TerritoryPolygon>
        ├── TerritoryPolygon.tsx   # React.memo(areEqual) → <Line closed points fill stroke onClick>
        ├── DecorationsLayer.tsx   # Capitals (<Circle>) + Labels (<Text>), listening={false}
        ├── InteractionLayer.tsx   # Selected polygon outline only, drawn on top
        ├── LayerTogglePanel.tsx   # Floating Radix Card with 5 Checkbox rows
        ├── InspectorSidebar.tsx   # Selected territory 4-group panel or project summary
        └── FitToViewButton.tsx    # bottom-left Button; also triggered by Ctrl+0 hook
```

### Pattern 1: Affine Projection Module — mirror `map_generator.py` exactly
**What:** Pure TypeScript functions that take ProjectionConfig + `(lon, lat)` and return `(x, y)` in canvas pixels, and inverse. Must produce the *identical* pixel coordinates the Python generator used, or the terrain PNG and the polygon overlays will disagree.

**When to use:** Everywhere that translates between geographic and pixel space (polygon rendering, centroid placement, click → geo coords, fit-to-view bounding box).

**Source:** Ported from `inicio/map_generator.py` lines 152–171 [CITED: inicio/map_generator.py].

```typescript
// lib/projection.ts
export interface ProjectionConfig {
  lonMin: number; lonMax: number;
  latMin: number; latMax: number;
  mapW: number;   mapH: number;    // final pixel dimensions (= map_w * upscale, map_h * upscale in the generator)
  lonScale: number;                // cos(radians((latMin+latMax)/2))
}

export function buildProjectionConfig(bounds: {
  lonMin: number; lonMax: number; latMin: number; latMax: number;
}, mapW: number, mapH: number): ProjectionConfig {
  const centerLat = (bounds.latMin + bounds.latMax) / 2
  const lonScale = Math.cos((centerLat * Math.PI) / 180)
  return { ...bounds, mapW, mapH, lonScale }
}

export function geoToCanvas(lon: number, lat: number, c: ProjectionConfig): [number, number] {
  const span = (c.lonMax - c.lonMin) * c.lonScale
  const x = ((lon - c.lonMin) * c.lonScale / span) * c.mapW
  const y = (1.0 - (lat - c.latMin) / (c.latMax - c.latMin)) * c.mapH
  return [x, y]
}

export function canvasToGeo(x: number, y: number, c: ProjectionConfig): [number, number] {
  const span = (c.lonMax - c.lonMin) * c.lonScale
  const lon = (x / c.mapW) * span / c.lonScale + c.lonMin
  const lat = c.latMax - (y / c.mapH) * (c.latMax - c.latMin)
  return [lon, lat]
}

/** Flatten a GeoJSON linear ring ([[lon,lat],...]) into Konva Line points [x0,y0,x1,y1,...]. */
export function geoRingToKonvaPoints(ring: [number, number][], c: ProjectionConfig): number[] {
  const out: number[] = new Array(ring.length * 2)
  for (let i = 0; i < ring.length; i++) {
    const [x, y] = geoToCanvas(ring[i][0], ring[i][1], c)
    out[2*i] = x; out[2*i+1] = y
  }
  return out
}
```

**Important:** The Python code uses `int(...)` on both `px` and `py`. Do NOT replicate this truncation in TypeScript — Konva renders sub-pixel floats cleanly, and truncating introduces visible shifts at large zoom. Int truncation in the Python side is a rasterization artifact, not part of the projection math. [ASSUMED: small visual tests at 4× will show this; noted as validation target in Open Questions]

### Pattern 2: Four-layer Konva Stage (z-order bottom→top)
**What:** Separate layers for terrain PNG, territory polygons, decorations (labels + capitals), and interaction (selection). UI-SPEC specifies this exact split.

**When to use:** Entire phase. Listens-per-layer is a Konva performance lever [CITED: https://konvajs.org/docs/performance/All_Performance_Tips.html — "each layer has an incremental performance overhead so we should keep the number of layers to a minimum" + "If you have a layer on which none of the shapes need to react to events, take this burden away by setting `layer.listening(false)`"].

| # | Name | `listening` | Children | Why |
|---|------|-------------|----------|-----|
| 0 | Background | `false` | 1× KonvaImage (terrain.png) | Never interacts; huge bitmap does not cost hit-test cycles. |
| 1 | Territories | `true` | ~91 condado `Line` + optional baronies | Only interactive polygons. Hit-test cost is linear in this layer only. |
| 2 | Decorations | `false` | ~91 capital `Circle` + ~91 label `Text` | No clicks; disables hit cost for ~180 shapes. |
| 3 | Interaction | `false` | 0 or 1 gold-outline `Line` for selected | Redrawn only on selection change. Doesn't intercept clicks (empty-click deselect goes to Stage). |

**Why 4 not 3:** The UI-SPEC already locks this to 4. Splitting Decorations from Interaction is cheap (most of the time InteractionLayer has 0 nodes) and keeps the selected-outline redraw O(1) instead of forcing TerritoryLayer to re-batch when selection changes.

**Why not split baronies into a 5th layer:** Baronies are OFF by default and only ~200–400 polygons max per country. Adding a fifth layer costs more than rendering them inside TerritoryLayer conditionally via the `layerVisibility.territories` + `layerVisibility.borders` toggles. [VERIFIED: Konva docs explicitly warn against layer inflation.]

### Pattern 3: React.memo'd TerritoryPolygon with tight equality
**What:** Each condado is a `<TerritoryPolygon>` wrapped in `React.memo` with a custom `areEqual` that only re-renders on geometry, fill, or selection changes. Without this, any Zustand selection change would re-render all ~91 polygons.

**Source:** Standard React pattern; reference identity stability via TanStack Query's `select` + the fact that GeoJSON is loaded once and its ring arrays never mutate within a session.

```typescript
// components/canvas/TerritoryPolygon.tsx
import { memo } from 'react'
import { Line } from 'react-konva'

interface Props {
  id: string
  points: number[]              // precomputed flattened [x0,y0,x1,y1,...] (stable ref)
  fill: string
  isSelected: boolean           // only true for the one selected id; false for the other 90
  onSelect: (id: string) => void
}

function TerritoryPolygonInner({ id, points, fill, isSelected, onSelect }: Props) {
  return (
    <Line
      points={points}
      closed
      fill={fill}
      stroke="rgba(0,0,0,0.35)"
      strokeWidth={1}
      listening={true}
      onClick={() => onSelect(id)}
      onTap={() => onSelect(id)}
    />
  )
}

function areEqual(prev: Props, next: Props) {
  return (
    prev.id === next.id &&
    prev.points === next.points &&  // reference equality — arrays are memoized upstream
    prev.fill === next.fill &&
    prev.isSelected === next.isSelected
  )
}

export const TerritoryPolygon = memo(TerritoryPolygonInner, areEqual)
```

**Selection subscription trick (critical):** Do NOT pass the full selection object down through TerritoryLayer. Instead, make `TerritoryLayer` subscribe with a selector that only fires when the specific `id === selectedTerritoryId` changes:

```typescript
// Inside TerritoryLayer
const selectedId = useUIStore((s) => s.selectedTerritoryId)
// In map(condados): compute isSelected = c.id === selectedId inline.
// Because React.memo checks isSelected, only the polygon whose id transitions in/out of selection re-renders.
```

### Pattern 4: Zoom-anchor-on-cursor — the canonical Konva formula
**Source:** [CITED: https://konvajs.org/docs/sandbox/Zooming_Relative_To_Pointer.html — exact recipe from official docs]

```typescript
// hooks/useZoomPan.ts (excerpt)
import type Konva from 'konva'

const SCALE_BY = 1.05 // 5% per wheel notch; tune 1.01–1.1 based on UX

export function handleWheel(e: Konva.KonvaEventObject<WheelEvent>, minScale: number, maxScale: number) {
  e.evt.preventDefault()
  const stage = e.target.getStage()
  if (!stage) return

  const oldScale = stage.scaleX()
  const pointer = stage.getPointerPosition()
  if (!pointer) return

  // 1) Cursor position in STAGE coords (pre-scale).
  const mousePointTo = {
    x: (pointer.x - stage.x()) / oldScale,
    y: (pointer.y - stage.y()) / oldScale,
  }

  // 2) Direction + new scale with clamp.
  const direction = e.evt.deltaY > 0 ? -1 : 1
  let newScale = direction > 0 ? oldScale * SCALE_BY : oldScale / SCALE_BY
  newScale = Math.max(minScale, Math.min(maxScale, newScale))
  if (newScale === oldScale) return // hit a limit; skip repaint

  // 3) Reposition so the cursor point remains fixed.
  const newPos = {
    x: pointer.x - mousePointTo.x * newScale,
    y: pointer.y - mousePointTo.y * newScale,
  }

  stage.scale({ x: newScale, y: newScale })
  stage.position(newPos)

  // 4) Apply pan clamp AFTER scale/position so the map can't escape the viewport.
  applyPanClamp(stage, newScale)
}
```

Interaction with `draggable={true}`: Stage drag already mutates `stage.position()`; call `applyPanClamp(stage, stage.scaleX())` in `onDragEnd` and `onDragMove` to clamp continuously. Konva 9+ supports `dragBoundFunc` on Stage as well — prefer `dragBoundFunc` over `onDragMove`-and-setPosition because it's called synchronously inside Konva's drag loop and doesn't produce flicker. [CITED: Konva docs sandbox examples routinely use `dragBoundFunc` for this].

### Pattern 5: Pan clamp (keep map inside viewport)
**Source:** UI-SPEC Interaction Contracts + general map-UX norm.

```typescript
function applyPanClamp(stage: Konva.Stage, scale: number) {
  const scaledW = projectionConfig.mapW * scale
  const scaledH = projectionConfig.mapH * scale
  const vw = stage.width()
  const vh = stage.height()

  let x = stage.x()
  let y = stage.y()

  if (scaledW <= vw) {
    x = (vw - scaledW) / 2            // center horizontally if map is smaller than viewport
  } else {
    x = Math.min(0, Math.max(vw - scaledW, x)) // clamp: 0 ≥ x ≥ vw - scaledW
  }
  if (scaledH <= vh) {
    y = (vh - scaledH) / 2
  } else {
    y = Math.min(0, Math.max(vh - scaledH, y))
  }
  stage.position({ x, y })
}
```

At `minScale = fitToViewScale` the scaled map is exactly the viewport size (minus padding), so both branches of the clamp degenerate to "center". No special casing needed.

### Pattern 6: Fit-to-view math
```typescript
export function computeFitToView(
  bboxMapW: number, bboxMapH: number,    // territory bbox in pixel space (after geoToCanvas)
  viewportW: number, viewportH: number,
  paddingPct = 0.05,
): { scale: number; x: number; y: number } {
  const usableW = viewportW * (1 - paddingPct)
  const usableH = viewportH * (1 - paddingPct)
  const scale = Math.min(usableW / bboxMapW, usableH / bboxMapH)
  // center the bbox in viewport
  const x = (viewportW - bboxMapW * scale) / 2
  const y = (viewportH - bboxMapH * scale) / 2
  return { scale, x, y }
}
```

This same `scale` value is stored in the uiStore as `minScale` so the wheel zoom clamp can't zoom out past whole-map view (D-13).

### Pattern 7: Zustand UI slice (read-only, no zundo wrap)
```typescript
// stores/uiStore.ts
import { create } from 'zustand'

export type LayerName = 'terrain' | 'territories' | 'borders' | 'capitals' | 'labels'

interface UIState {
  selectedTerritoryId: string | null
  layerVisibility: Record<LayerName, boolean>
  select: (id: string | null) => void
  toggleLayer: (name: LayerName) => void
}

export const useUIStore = create<UIState>((set) => ({
  selectedTerritoryId: null,
  layerVisibility: {
    terrain: true, territories: true, borders: true, capitals: true, labels: false, // D-09
  },
  select: (id) => set({ selectedTerritoryId: id }),
  toggleLayer: (name) => set((s) => ({
    layerVisibility: { ...s.layerVisibility, [name]: !s.layerVisibility[name] },
  })),
}))
```

**zundo wiring:** Phase 2 is read-only. Do NOT wrap `useUIStore` with `temporal`. The first real undo-tracked store lands in Phase 4 (`useProjectStore` per ROADMAP). Attempting to wire zundo here prematurely couples UI state to history — CONTEXT.md deferred list explicitly flags this.

### Pattern 8: Label gate by zoom threshold
```typescript
// components/canvas/DecorationsLayer.tsx (excerpt)
const visible = useUIStore((s) => s.layerVisibility)
const scale = useStageScale()  // subscribe via a getPointerPosition-less ref or stage.scaleX() from Stage ref

// Only render label <Text> nodes when BOTH the layer is on AND zoom crosses threshold.
const showLabels = visible.labels && scale >= LABEL_ZOOM_THRESHOLD // default 1.5× minScale

return (
  <Layer listening={false}>
    {visible.capitals && condados.map(c => <Circle key={c.id} ... />)}
    {showLabels && condados.map(c => <Text key={`lbl-${c.id}`} ... />)}
  </Layer>
)
```

**Threshold derivation:** For Iberia, the generator emits a 3840×2160 terrain (map_w=1920 × upscale=2). A typical viewport is 1440×800 (after subtracting 340 px sidebar and a ~60 px header). Fit-to-view scale ≈ min(1368/3840, 740/2160) ≈ 0.342. A recommended initial threshold is `scale >= fitToViewScale * 2.0` — about 0.68 absolute — which shows labels when the user has clearly zoomed in but keeps them hidden at overview. Tune during UAT. Store as an exported constant `LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0` multiplied by `minScale`.

### Anti-Patterns to Avoid
- **Re-projecting polygons on every render / zoom tick.** The projection is fixed at mount (ProjectionConfig never changes after load). Flatten all rings to Konva `points` arrays ONCE, memoize, pass references. Konva's Stage `scale` does the zoom — your arrays stay identical. Success criterion 2 ("polygons remain pixel-aligned and do not re-project on zoom") directly forbids this.
- **Wrapping `<Stage>` children in unnecessary `<Group>` components.** Adds hit-test cost and confuses event bubbling. Use Layers as the grouping primitive.
- **Using Radix `Button` as a wrapper around every neighbor chip.** UI-SPEC explicitly calls this out — use a `Badge variant="soft"` inside a plain `<button>` or `role="button"` `<Box>`.
- **Loading GeoJSON on every route visit.** TanStack Query `staleTime: Infinity` + `gcTime: Infinity` for the project's artifacts — they only change on regeneration.
- **Wiring `Esc` as a React key handler on the Stage.** Konva `<Stage>` does not receive keyboard events unless `tabIndex` is set on the container. Use a `window.addEventListener('keydown', ...)` in `useKeyboardShortcuts.ts` and guard against `document.activeElement` being an `input`/`textarea`/`[contenteditable]`.
- **Mutating `<Line>` stroke on selection to show the gold outline.** D-03 is explicit: draw selected outline as a *separate Line on the Interaction layer*, leaving the base polygon untouched. This preserves the read-only contract and makes selection changes O(1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Map projection | A full `proj4` / Mercator pipeline | 6-line affine `geoToCanvas` (matches `map_generator.py` exactly) | The generator itself uses simple equirectangular with `cos(center_lat)` longitude correction. Anything fancier breaks pixel-parity with the PNG. |
| Hit-testing polygons | A manual point-in-polygon ray-cast | Konva `<Line closed>` with `onClick` | Konva's hit canvas is opt-in, fast, and handles edge cases. |
| Pan/zoom state machine | A custom drag/pinch system | Konva `Stage draggable` + `onWheel` + `dragBoundFunc` | Konva solves damping, touch/mouse unification, and sub-pixel math. |
| Polygon array memoization | `useMemo` with deep-compare | Compute `points` arrays at GeoJSON load time (inside TanStack Query `select`) | One-time cost; arrays are referentially stable for the session. |
| GeoJSON neighbor adjacency | Topology computation in the browser | Precompute `neighbors: string[]` server-side as part of `territory_metadata.json` | Adjacency needs shared-edge detection; Shapely does it in milliseconds, JS would be a 200-line headache. **NOTE: current `territory_metadata.json` has no `neighbors` field** — planner must add it (see Open Questions). |
| Territory polygon extraction from raster | Re-running Voronoi in JS | Backend post-step emits `territories.geojson` via `rasterio.features.shapes(pc)` | Same reason as adjacency: Python side already has the raster; one-shot emit. |
| Label anti-collision | A physics-based layout solver | First-come-first-rendered at a single zoom threshold (D-10) | 91 condado labels at zoom 2× fit without collisions in practice. If UAT reveals clutter, add the polygon-bbox-width gate described in Pitfall 4 below. |
| Keyboard shortcut manager | `react-hotkeys` | Plain `window.addEventListener('keydown')` | Only two shortcuts. A library is overkill and adds bundle size. |

**Key insight:** The entire phase is "let Konva do the canvas work, let the Python backend do the geometry work, let React do the state work." Every boundary in the phase is one of these three systems talking to another. Hand-rolling in any of those three is the failure mode.

## Runtime State Inventory

Phase 2 is a greenfield frontend phase — no renames, no migrations. Inventory SKIPPED per guidance ("Omit entirely for greenfield phases").

## Common Pitfalls

### Pitfall 1: React 19 StrictMode double-invoke + Konva Stage refs
**What goes wrong:** StrictMode mounts components twice in development. If `<CanvasViewer>` stores a Konva Stage ref via `useRef` and attaches a wheel listener in `useEffect` without cleanup, the listener ends up registered twice.
**Why it happens:** React 19 preserves StrictMode's intentional double-effect behavior; Konva's imperative event hooks don't auto-unregister.
**How to avoid:** Always return a cleanup function from every `useEffect` that touches Konva. Use `stage.off('wheel')` / `stage.off('dragmove')` in the cleanup even when you used the react-konva `onWheel` prop elsewhere, because mixing declarative and imperative attachments is the classic footgun. Prefer *only* the declarative JSX props (`<Stage onWheel={handleWheel}>`).
**Warning signs:** Zoom factor doubles per wheel tick in dev mode; disappears in production build. Classic double-listener tell.
[CITED: React 19 StrictMode docs; standard pattern.]

### Pitfall 2: Tailwind v4 + Radix transparency (GitHub #17137)
**What goes wrong:** After Tailwind v4 upgrade some Radix components (especially Card, Dropdown, Select in shadcn-style setups) render transparent because Tailwind's `@layer base` overrides Radix's CSS variable declarations for `--color-panel-solid` etc.
**Why it happens:** CSS layer ordering — Tailwind's reset wins against Radix's default stylesheet if Radix is imported after Tailwind.
**How to avoid:** Import Radix Themes CSS **before** `@import "tailwindcss"`. The current `frontend/src/index.css` already does this correctly (VERIFIED by reading the file: line 2 is `@import "@radix-ui/themes/styles.css";`, line 3 is `@import "tailwindcss";`). Planner must add a Wave-0 smoke test that mounts a Radix `Card` (the layer toggle panel spec) with `variant="surface"` over a Konva Stage and visually confirms the card is opaque. Break the test on purpose (swap import order) to prove it catches the regression.
**Warning signs:** Layer-toggle card shows the canvas through it at ~50% opacity; text readable but visual breaks cards/dropdowns/popover feel. [CITED: https://github.com/tailwindlabs/tailwindcss/discussions/17137]

### Pitfall 3: Pan clamp + fit-to-view interaction bug
**What goes wrong:** User zooms in, pans to edge, hits Ctrl+0. If the fit-to-view handler sets scale but applies the pan clamp *before* setting position, the clamp uses the old scale and the map snaps to a nonsense location.
**Why it happens:** State updates in Konva are synchronous but order-dependent.
**How to avoid:** Atomic update: compute `{ scale, x, y }` in one go, then `stage.to({ scaleX, scaleY, x, y, duration: 0.2 })` for smooth transition or set all four synchronously. Never apply clamp inside the Ctrl+0 handler — fit-to-view output is already clamp-safe by construction.
**Warning signs:** Ctrl+0 produces a jumpy or off-center reset; only after zoom-and-pan, not from steady state.

### Pitfall 4: Label overlap at the boundary of small condados
**What goes wrong:** At zoom 1.5× several small condados in Galicia render labels that overlap each other (single hard threshold per D-10).
**Why it happens:** Labels render as overlapping floating text because there's no layout system in Konva.
**How to avoid (tiered fallback):**
1. **First choice — do nothing.** For Iberia at zoom ≥ 2× most labels fit. Ship it, check UAT, decide later.
2. **Second choice — polygon-bbox gate.** For each condado, precompute `bbox_width_px` at scale 1. Only render the label if `bbox_width_px * currentScale >= labelTextWidth + padding`. This is the "clip-by-polygon" strategy from the research brief but measured as "polygon width vs label width" — cheap and deterministic.
3. **Third choice — first-come-first-rendered with rectangle-overlap test.** Iterate label candidates in priority order (bigger polygon wins); skip candidates whose bounding rectangle intersects any already-placed rectangle. O(n²) for n=91 is fine.

Recommend shipping with strategy 1 and escalating to strategy 2 only if UAT flags clutter.
**Warning signs:** At the threshold zoom, two condados' labels fuse into unreadable text. Fix with strategy 2.

### Pitfall 5: Neighbor chip click → selection → canvas doesn't pan
**What goes wrong:** User clicks a neighbor chip in the inspector; selection moves but the camera stays put, so the selected territory may be offscreen.
**Why it happens:** UI-SPEC says "Canvas pans to center the newly selected territory (pan only; no zoom change)" — this must be wired.
**How to avoid:** In the `select(id)` action, look up the territory's centroid (from `territory_metadata.json`), project it with `geoToCanvas`, and update Stage position so that centroid lands at viewport center. Don't change scale. Apply pan clamp afterward.
**Warning signs:** Clicking a chip for a territory far from the current view causes the inspector to update but the gold outline is invisible (off-camera).

### Pitfall 6: Stage click vs territory click — empty-area click must clear selection
**What goes wrong:** Clicking the terrain PNG between polygons doesn't fire anything, or worse, it falls through to a div behind the Stage.
**Why it happens:** Background layer has `listening=false`, so clicks on terrain don't bubble to a handler.
**How to avoid:** Put an `onClick` directly on `<Stage>`. When `e.target === e.target.getStage()` (i.e., the click landed on empty canvas and nothing intercepted), call `select(null)`. This is the Konva-idiomatic "click empty space to deselect" pattern.

### Pitfall 7: `points` array identity thrashing
**What goes wrong:** Polygons re-render on every Zustand state change because their `points` array was recomputed via `useMemo(..., [condado])` inside the component body — new array each render if dependency comparison is wrong.
**Why it happens:** `useMemo` inside the child re-runs when the parent re-renders.
**How to avoid:** Flatten and memoize `points` arrays ONCE at load time, inside TanStack Query's `select`:
```typescript
useQuery({
  queryKey: ['territories', projectId],
  queryFn: fetchTerritoriesGeoJSON,
  select: (raw) => raw.features.map(f => ({
    id: f.properties.id,
    points: geoRingToKonvaPoints(f.geometry.coordinates[0], projectionConfig),
    // ... other stable fields
  })),
  staleTime: Infinity,
})
```
TanStack Query v5 caches the `select` result — the same `points` array reference is returned across renders until the query key changes. [CITED: https://tanstack.com/query/latest/docs/framework/react/guides/render-optimizations]
**Warning signs:** React DevTools Profiler shows all 91 polygons re-render when just the selection changes.

## Code Examples

Verified patterns from official sources and the project's own `map_generator.py`:

### Example 1: Projection module (ported verbatim from Python)
```typescript
// lib/projection.ts
// Source: inicio/map_generator.py lines 152–171 [CITED: project code]
// Mirror EXACTLY — any divergence breaks pixel-parity with terrain.png.

export interface ProjectionConfig {
  lonMin: number; lonMax: number; latMin: number; latMax: number;
  mapW: number; mapH: number; lonScale: number;
}

export function geoToCanvas(lon: number, lat: number, c: ProjectionConfig): [number, number] {
  const span = (c.lonMax - c.lonMin) * c.lonScale
  const x = ((lon - c.lonMin) * c.lonScale / span) * c.mapW
  const y = (1 - (lat - c.latMin) / (c.latMax - c.latMin)) * c.mapH
  return [x, y]
}

export function canvasToGeo(x: number, y: number, c: ProjectionConfig): [number, number] {
  const span = (c.lonMax - c.lonMin) * c.lonScale
  const lon = (x / c.mapW) * span / c.lonScale + c.lonMin
  const lat = c.latMax - (y / c.mapH) * (c.latMax - c.latMin)
  return [lon, lat]
}

export function geoRingToKonvaPoints(ring: [number, number][], c: ProjectionConfig): number[] {
  const out = new Array(ring.length * 2)
  for (let i = 0; i < ring.length; i++) {
    const [x, y] = geoToCanvas(ring[i][0], ring[i][1], c)
    out[2*i] = x
    out[2*i+1] = y
  }
  return out
}
```

### Example 2: Zoom-anchor-on-cursor wheel handler
```typescript
// hooks/useZoomPan.ts — based on the official Konva sandbox recipe
// Source: https://konvajs.org/docs/sandbox/Zooming_Relative_To_Pointer.html [CITED]
import type Konva from 'konva'

const SCALE_BY = 1.05

export function makeWheelHandler(minScale: number, maxScale: number) {
  return (e: Konva.KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault()
    const stage = e.target.getStage()
    if (!stage) return

    const oldScale = stage.scaleX()
    const pointer = stage.getPointerPosition()
    if (!pointer) return

    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    }

    const direction = e.evt.deltaY > 0 ? -1 : 1
    let newScale = direction > 0 ? oldScale * SCALE_BY : oldScale / SCALE_BY
    newScale = Math.max(minScale, Math.min(maxScale, newScale))
    if (newScale === oldScale) return

    stage.scale({ x: newScale, y: newScale })
    stage.position({
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    })
    applyPanClamp(stage, newScale) // Pitfall 3
  }
}
```

### Example 3: React.memo'd territory polygon (with Zustand selector)
```typescript
// components/canvas/TerritoryPolygon.tsx
import { memo } from 'react'
import { Line } from 'react-konva'

interface TerritoryPolygonProps {
  id: string
  points: number[]
  fill: string
  isSelected: boolean
  onSelect: (id: string) => void
}

function Inner({ id, points, fill, isSelected, onSelect }: TerritoryPolygonProps) {
  return (
    <Line
      points={points}
      closed
      fill={fill}
      stroke={isSelected ? '#f0c040' : 'rgba(0,0,0,0.35)'}
      strokeWidth={isSelected ? 0 : 1}  // actual selected outline is on InteractionLayer; keep base stroke subtle
      onClick={() => onSelect(id)}
      onTap={() => onSelect(id)}
    />
  )
}

function areEqual(a: TerritoryPolygonProps, b: TerritoryPolygonProps): boolean {
  return (
    a.id === b.id &&
    a.points === b.points &&   // reference equality (arrays memoized at load time)
    a.fill === b.fill &&
    a.isSelected === b.isSelected
  )
}

export const TerritoryPolygon = memo(Inner, areEqual)
```

### Example 4: Zustand UI slice + Esc/Ctrl+0 hook
```typescript
// stores/uiStore.ts
import { create } from 'zustand'

type LayerName = 'terrain' | 'territories' | 'borders' | 'capitals' | 'labels'

export const useUIStore = create<{
  selectedTerritoryId: string | null
  layerVisibility: Record<LayerName, boolean>
  select: (id: string | null) => void
  toggleLayer: (n: LayerName) => void
}>((set) => ({
  selectedTerritoryId: null,
  layerVisibility: { terrain: true, territories: true, borders: true, capitals: true, labels: false },
  select: (id) => set({ selectedTerritoryId: id }),
  toggleLayer: (n) => set((s) => ({
    layerVisibility: { ...s.layerVisibility, [n]: !s.layerVisibility[n] },
  })),
}))

// hooks/useKeyboardShortcuts.ts
import { useEffect } from 'react'
import { useUIStore } from '../stores/uiStore'

export function useKeyboardShortcuts(fitToView: () => void) {
  const select = useUIStore((s) => s.select)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = document.activeElement
      const isEditable = t instanceof HTMLElement && (
        t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable
      )
      if (isEditable) return

      if (e.key === 'Escape') { select(null); return }
      if ((e.ctrlKey || e.metaKey) && e.key === '0') { e.preventDefault(); fitToView(); return }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [select, fitToView])
}
```

### Example 5: TanStack Query v5 for phase artifacts
```typescript
// hooks/useCanvasArtifacts.ts
import { useQueries } from '@tanstack/react-query'
import { geoRingToKonvaPoints, type ProjectionConfig } from '../lib/projection'

export function useCanvasArtifacts(projectId: string, projection: ProjectionConfig | null) {
  return useQueries({
    queries: [
      {
        queryKey: ['territories-geojson', projectId],
        queryFn: () => fetch(`/api/projects/${projectId}/artifacts/territories.geojson`).then(r => {
          if (!r.ok) throw new Error(r.status === 404 ? 'MAP_NOT_GENERATED' : 'FETCH_FAILED')
          return r.json()
        }),
        enabled: Boolean(projectId && projection),
        staleTime: Infinity,
        gcTime: Infinity,
        select: (raw: GeoJSON.FeatureCollection) => raw.features.map((f) => ({
          id: f.properties!.id as string,
          name: f.properties!.name as string,
          points: geoRingToKonvaPoints(
            (f.geometry as GeoJSON.Polygon).coordinates[0] as [number, number][],
            projection!,
          ),
        })),
      },
      {
        queryKey: ['condado-colors', projectId],
        queryFn: () => fetch(`/api/projects/${projectId}/artifacts/lookup_condado_colors.json`).then(r => r.json()),
        enabled: Boolean(projectId),
        staleTime: Infinity,
      },
      {
        queryKey: ['territory-metadata', projectId],
        queryFn: () => fetch(`/api/projects/${projectId}/artifacts/territory_metadata.json`).then(r => r.json()),
        enabled: Boolean(projectId),
        staleTime: Infinity,
      },
    ],
  })
}
```

**Query key structure:** `['<artifact>', projectId]` — narrow, predictable, easy to invalidate from Phase 4 editing actions later.
**Error handling:** Distinguish 404 (map not generated — render the "No map generated yet" empty state from UI-SPEC) from other failures ("Failed to load territory data. Check the server is running.").

### Example 6: Fit-to-view button + computation
```typescript
// components/canvas/FitToViewButton.tsx
import { Button } from '@radix-ui/themes'

export function FitToViewButton({ onFit }: { onFit: () => void }) {
  return (
    <Button
      variant="solid" size="2"
      onClick={onFit}
      style={{ position: 'absolute', bottom: 12, left: 12, minHeight: 44 }}
    >
      Fit to view
    </Button>
  )
}

// Hoisted fitToView function (called by button AND Ctrl+0 hook)
function fitToView(stageRef: React.RefObject<Konva.Stage>, bbox: BBox, projection: ProjectionConfig, setMinScale: (s: number) => void) {
  const stage = stageRef.current
  if (!stage) return
  const [x0, y0] = geoToCanvas(bbox.lonMin, bbox.latMax, projection) // top-left of bbox (lat inverted)
  const [x1, y1] = geoToCanvas(bbox.lonMax, bbox.latMin, projection) // bottom-right
  const bboxW = x1 - x0
  const bboxH = y1 - y0
  const { scale, x, y } = computeFitToView(bboxW, bboxH, stage.width(), stage.height(), 0.05)
  // Offset by the bbox origin in projected space:
  stage.scale({ x: scale, y: scale })
  stage.position({ x: x - x0 * scale, y: y - y0 * scale })
  setMinScale(scale) // minimum zoom = fit-to-view (D-13)
}
```

### Example 7: Tailwind v4 + Radix + Konva smoke test (Wave 0)
```typescript
// components/__smoke__/CanvasRadixOverlay.tsx — FIRST TASK of Phase 2
// Validates that Pitfall 2 (transparency bug #17137) is NOT biting before real work.
import { Stage, Layer, Rect } from 'react-konva'
import { Card, Text, Flex, Checkbox } from '@radix-ui/themes'

export function CanvasRadixOverlaySmoke() {
  return (
    <div style={{ position: 'relative', width: 800, height: 600 }}>
      <Stage width={800} height={600}>
        <Layer><Rect x={0} y={0} width={800} height={600} fill="#ff00ff" /></Layer>
      </Stage>
      <Card variant="surface" style={{ position: 'absolute', top: 12, left: 12 }}>
        <Flex direction="column" gap="2">
          <Text size="2" weight="bold">Layers</Text>
          <Flex align="center" gap="2"><Checkbox defaultChecked /><Text size="2">Terrain</Text></Flex>
          <Flex align="center" gap="2"><Checkbox defaultChecked /><Text size="2">Territories</Text></Flex>
        </Flex>
      </Card>
    </div>
  )
}
// Test pass criterion: the Card must be VISUALLY OPAQUE. The magenta stage must NOT bleed through.
// Run as a Vitest+playwright snapshot OR a manual visual check in the plan — planner's call.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `react-konva@18.x` + React 18 + `--legacy-peer-deps` | `react-konva@19.2.3` + React 19.2 clean install | Oct 2024 (react-konva 19 release) | No legacy-peer-deps flag required for this project. [VERIFIED: npm view 2026-04-17] |
| `konva@9.x` | `konva@10.2.5` | Early 2025 | Minor API changes; react-konva 19.2.3 peers `^8 || ^9 || ^10`, pin to `^10`. |
| Tailwind v3 `tailwind.config.js` | Tailwind v4 CSS-first `@theme` + `@tailwindcss/vite` | Jan 2025 | Already done in Phase 1. |
| Zustand `middleware/immer` + manual history arrays | Zustand 5 + zundo 2.3 `temporal` middleware | Mid 2024 (zundo 2 rewrite) | Not used in Phase 2 (read-only). First real use in Phase 4. |
| TanStack Query v4 | v5 | Oct 2023 | Already in use. `keepPreviousData` replaced by `placeholderData` — irrelevant here since we use `staleTime: Infinity`. |

**Deprecated/outdated:**
- `useMemo` with array deep-compare for polygon `points` arrays — use TanStack Query `select` instead (Pitfall 7).
- Separate `<Group>` wrappers per territory — a bare `<Line>` with `closed` renders identically and avoids hit-test overhead.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `territory_metadata.json` will need a `neighbors: string[]` field added to support the inspector's clickable neighbor chips (D-06). Current file (per `map_generator.py` lines 686–726) has no neighbor field. | Don't Hand-Roll, Open Questions | HIGH — inspector can't ship D-06 group 4 without adjacency data. Planner must add a small Phase-2 backend task (recommended) or descope D-06.4 to a follow-up. |
| A2 | `territories.geojson` per-condado polygon data does NOT exist as a generator output today. The generator produces a `pc` numpy int raster but does not serialize polygon rings. | Summary, Don't Hand-Roll, Open Questions | HIGH — canvas literally cannot render polygons without this. Planner must pick: (a) server-side emit via `rasterio.features.shapes`, or (b) extract polygons from `lookup_condado.png` in the browser. Recommendation: (a). |
| A3 | The `LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0` (i.e., labels show when scale ≥ 2× fit-to-view) is a reasonable default for Iberia's ~91 condados. | Pattern 8 | LOW — threshold is tuned during UAT, not a locked decision. If the default is wrong the visible symptom is label clutter or lack of labels; easy to change. |
| A4 | `sub-pixel fractional coordinates` from `geoToCanvas` render cleanly in Konva at zoom 4× and do not produce visible seams along shared borders between condados. | Pattern 1 note | MEDIUM — if seams appear, the fix is to round to integer pixels at scale 1 (matching `map_generator.py`'s `int(...)` cast). Easy one-line change. |
| A5 | `~91 polygons × ~50–200 vertices each` stays at 60fps on a modest laptop during pan/zoom in Konva Canvas2D, without needing shape caching or WebGL. | Validation Architecture | MEDIUM — Konva official performance tips cite 1000s of shapes as the scale where optimization matters. 91 is well under that. If profiler shows issue, cache each territory shape with `.cache()` after mount. |
| A6 | Terrain PNG served by FastAPI at `GET /api/projects/{id}/preview/terrain.png` is exactly `map_w * upscale` × `map_h * upscale` pixels (Iberia: 3840×2160). | Example 6, Validation | LOW — VERIFIED from `map_generator.py` line 688 (`"map_size": [cfg.map_w * cfg.upscale, cfg.map_h * cfg.upscale]`). Written to `territory_metadata.json["map_size"]`. |
| A7 | The fit-to-view bbox should be computed from the *territory centroids* (per UI-SPEC) — not the full `terrain.png` dimensions — so small island clusters in the data don't force a tiny zoom. | Pattern 6 | LOW — UI-SPEC explicitly says "bounding box of all territory centroids". Could alternatively use `bounds` from metadata (lon_min..lon_max covering the full generator extent) if centroid bbox proves to show irrelevant whitespace. |

Every claim tagged `[ASSUMED]` above should be confirmed before or during planning. Claims tagged `[VERIFIED]` or `[CITED]` inline throughout the document are already confirmed against tools or official docs.

## Open Questions

1. **Does `territories.geojson` exist or must we add it?** (A2 above)
   - What we know: `map_generator.py` builds a `pc` (int16) raster where each pixel ∈ {0..N-1} maps to condado index. It writes `lookup_condado.png` and `visual_condado.png` but never serializes polygon rings.
   - What's unclear: Is there an appetite to modify the generator in Phase 2, or should the canvas be constrained to work from lookup PNGs (harder)?
   - Recommendation: Add a small backend task to `services/generator.py` that, after generation, calls `rasterio.features.shapes(pc.astype('int32'))` → `shapely.geometry.shape(...)` → `shapely.ops.unary_union` per condado → write `territories.geojson` with `{id, name, geometry}` features. Cost ~50 lines, one new dependency if rasterio isn't already available (check `backend/pyproject.toml`). This is the lowest-risk path.

2. **Does `territory_metadata.json` need a `neighbors` field?** (A1 above)
   - What we know: D-06 group 4 (neighbor chips) requires adjacency data. Current metadata has none.
   - What's unclear: Whether the planner wants to extend `export_metadata()` or compute adjacency client-side from the new `territories.geojson`.
   - Recommendation: Server-side. Add `neighbors: List[str]` to each condado entry. Compute via `shapely.STRtree` + `touches()` in Python — 10 lines and runs in ms for 91 condados. Single source of truth, no client duplication.

3. **Sub-pixel vs integer projection output** (A4 above)
   - What we know: Python uses `int(...)` on both pixel coords; TypeScript version returns floats.
   - What's unclear: Does this cause visible border seams at 4× zoom?
   - Recommendation: Ship with floats. Add a visual check in Validation Architecture: zoom to 4× on a shared border and confirm no white seam. If seams appear, add `Math.round(...)` at the output of `geoToCanvas` to match Python exactly.

4. **Labels position — centroid vs pole-of-inaccessibility**
   - What we know: UI-SPEC says labels use the centroid (CONTEXT D-10, D-11 don't specify).
   - What's unclear: Geometric centroid can fall outside concave polygons (Italy-shaped condados). Pole-of-inaccessibility is better but needs a small JS impl.
   - Recommendation: Ship with centroid (simpler, reads from metadata's `lon, lat`). If UAT shows labels floating outside weird-shaped condados, add `polylabel` npm package (tiny, 30 lines) in a follow-up.

## Environment Availability

Phase 2 is frontend-only + one optional backend task (see Open Question 1). External dependency audit:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite build | Expected (Phase 1 sets this up) | ≥ 20 | — |
| npm | package install | Expected | ≥ 10 | — |
| `konva` + `react-konva` | Canvas rendering | NOT YET INSTALLED | target ^10.2.5 / ^19.2.3 | — (hard dep; `npm install` on plan start) |
| `rasterio` (backend, if OQ1 picks path a) | `rasterio.features.shapes` for `territories.geojson` emission | Expected (Phase 1 deps pinned `rasterio>=1.4,<1.5`) | 1.4.x | Fallback: `scikit-image.measure.find_contours` + Shapely — adds a dep but works without rasterio. |
| Browser with Canvas2D | react-konva runtime | Universal | Any modern browser | — |

**Missing dependencies with no fallback:**
- None, assuming Phase 1 shipped cleanly.

**Missing dependencies with fallback:**
- `rasterio.features.shapes` → `skimage.measure.find_contours` + `shapely` (both are already transitive deps of Phase 1's geometry stack).

## Validation Architecture

*Included per config.json `workflow.nyquist_validation: true` — this seeds VALIDATION.md.*

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest (frontend unit/integration) + Playwright (E2E/smoke) — install in Wave 0 if absent |
| Config file | `frontend/vite.config.ts` (existing) + add `vitest.config.ts` (Wave 0 if missing) |
| Quick run command | `cd frontend && npm run test` (vitest watch: `-- --run` for CI) |
| Full suite command | `cd frontend && npm run test && npm run test:e2e` (adds Playwright smoke) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CANVAS-01 | Territory polygons render with correct `fill` + `stroke` from lookup JSON | integration (vitest + react-konva test util) | `npm run test -- TerritoryLayer.test.tsx -- --run` | ❌ Wave 0 |
| CANVAS-01 | Projection round-trip: `canvasToGeo(geoToCanvas(lon, lat))` within 1e-9° for 1000 random Iberia points | unit | `npm run test -- projection.test.ts -- --run` | ❌ Wave 0 |
| CANVAS-01 | Polygon vertex count preserved: `geoRingToKonvaPoints(ring).length === ring.length * 2` | unit | (same file as above) | ❌ Wave 0 |
| CANVAS-01 | Polygon rendering at Iberia scale: first-paint render time < 500 ms for 91 polygons of typical vertex count | integration + `performance.now()` | `npm run test -- CanvasViewer.perf.test.tsx -- --run` | ❌ Wave 0 |
| CANVAS-02 | Wheel handler moves cursor-anchored point: cursor at `(400, 300)` before zoom should map to same geo point after zoom | unit | `npm run test -- useZoomPan.test.ts -- --run` | ❌ Wave 0 |
| CANVAS-02 | Pan clamp keeps map inside viewport: after drag to `(-∞, 0)`, stage x equals `viewport.w - scaled.w` | unit | (same file) | ❌ Wave 0 |
| CANVAS-02 | Zoom limit floor = fit-to-view scale (cannot zoom out past whole-map view) | unit | (same file) | ❌ Wave 0 |
| CANVAS-02 | Zoom limit ceiling = 4× fit-to-view scale | unit | (same file) | ❌ Wave 0 |
| CANVAS-03 | Click on polygon sets `useUIStore.selectedTerritoryId` to that id | integration (RTL + react-konva test utility) | `npm run test -- selection.test.tsx -- --run` | ❌ Wave 0 |
| CANVAS-03 | Inspector renders all 4 property groups when `selectedTerritoryId !== null` | integration | `npm run test -- InspectorSidebar.test.tsx -- --run` | ❌ Wave 0 |
| CANVAS-03 | Inspector renders project summary when `selectedTerritoryId === null` | integration (same file) | (same) | ❌ Wave 0 |
| CANVAS-03 | `Esc` clears selection (except when input focused) | integration | `npm run test -- useKeyboardShortcuts.test.ts -- --run` | ❌ Wave 0 |
| CANVAS-03 | Neighbor chip click updates selection + pans camera | integration | (same as selection.test.tsx) | ❌ Wave 0 |
| CANVAS-04 | 5 checkboxes present in layer panel, reflecting default state from D-09 | integration | `npm run test -- LayerTogglePanel.test.tsx -- --run` | ❌ Wave 0 |
| CANVAS-04 | Toggling `capitals` checkbox hides all `<Circle>` nodes on DecorationsLayer | integration | (same) | ❌ Wave 0 |
| CANVAS-04 | **Tailwind v4 + Radix transparency smoke test**: Layer Card over magenta Stage — card pixel at centre is NOT magenta | Playwright visual | `npm run test:e2e -- smoke-tailwind-radix.spec.ts` | ❌ Wave 0 |
| CANVAS-05 | Labels render only when `layerVisibility.labels && scale >= LABEL_ZOOM_THRESHOLD_RELATIVE * minScale` | unit | `npm run test -- DecorationsLayer.test.tsx -- --run` | ❌ Wave 0 |
| CANVAS-06 | `Ctrl+0` restores stage to fit-to-view scale + centered position | integration | (extends useKeyboardShortcuts.test.ts) | ❌ Wave 0 |
| CANVAS-06 | "Fit to view" button triggers same behavior as `Ctrl+0` | integration | `npm run test -- FitToViewButton.test.tsx -- --run` | ❌ Wave 0 |
| (non-req) | Pan/zoom frame rate on Iberia dataset ≥ 55 fps sustained during a 2-second drag | Playwright + `performance.mark` | `npm run test:e2e -- perf-panzoom.spec.ts` — manual inspection OK as fallback | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `npm run test -- --run` (vitest only; ~sec). Required after every task in plans 2.1/2.2/2.3.
- **Per wave merge:** `npm run test -- --run && npm run test:e2e` (adds Playwright smoke, ~30s).
- **Phase gate:** Full suite green before `/gsd-verify-work`. Visual smoke (Tailwind+Radix) must pass.

### Wave 0 Gaps
- [ ] `frontend/vitest.config.ts` — Vitest config (jsdom env + tsconfig paths)
- [ ] `frontend/playwright.config.ts` — Playwright config (optional if team already has) 
- [ ] `frontend/src/lib/projection.test.ts` — unit test skeleton for projection round-trip + vertex preservation
- [ ] `frontend/src/hooks/useZoomPan.test.ts` — unit test for wheel handler math + pan clamp
- [ ] `frontend/src/hooks/useKeyboardShortcuts.test.ts` — unit test for Esc + Ctrl+0 + input-focus guard
- [ ] `frontend/src/stores/uiStore.test.ts` — unit test for selection + layer toggle
- [ ] `frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx` — integration with RTL
- [ ] `frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx` — integration
- [ ] `frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx` — integration
- [ ] `frontend/e2e/smoke-tailwind-radix.spec.ts` — Playwright visual test (Pitfall 2)
- [ ] `frontend/e2e/perf-panzoom.spec.ts` — Playwright perf probe (A5)
- [ ] Framework install commands (if Vitest/Playwright absent in Phase 1): `npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom @playwright/test` + `npx playwright install chromium`

### Invariant Checks (guaranteed-to-hold properties that VALIDATION.md should list)
1. **Projection round-trip accuracy:** `|canvasToGeo(geoToCanvas(p)).lon - p.lon| < 1e-9` for all p within Iberia bbox. 1000 random-point sample.
2. **Projection reverse round-trip accuracy:** `|geoToCanvas(canvasToGeo(px, py)).x - px| < 1e-6` for all (px, py) within `(0..mapW, 0..mapH)`.
3. **Polygon fidelity:** For every GeoJSON Feature, `geoRingToKonvaPoints(ring).length === ring.length * 2`. No vertex dropped.
4. **Fill parity:** For every condado in `lookup_condado_colors.json`, the `<Line fill>` prop equals the exact hex value from the JSON (string equality; no color-space conversion).
5. **Selection-outline non-mutation:** After selecting any territory, `territoriesLayer.getChildren()[i].attrs.points` is *identical by reference* to the pre-selection value for all i. (Confirms D-03's read-only contract.)
6. **Zoom clamp hard limits:** After any wheel event, `stage.scaleX() >= minScale && stage.scaleX() <= maxScale`.
7. **Pan clamp invariant:** After any drag or wheel, `stage.x() <= 0` OR (viewport is wider than scaled map); symmetric for y.
8. **Keyboard guard:** When `document.activeElement instanceof HTMLInputElement`, `Esc` keypress does NOT alter `useUIStore.selectedTerritoryId`.
9. **Label gate:** Label `<Text>` count === condado count only when `visible.labels && scale >= threshold`; 0 otherwise.
10. **Layer listening flags:** After mount, `stage.getLayers()[0].listening() === false` (Background) and `[2].listening() === false` (Decorations).

### Performance Budget
- First meaningful paint of canvas with Iberia data: **< 500 ms** from route enter (A5).
- Sustained drag-pan frame rate: **≥ 55 fps** on modest laptop (Intel i5, integrated graphics). Measure via Playwright `page.evaluate(() => performance.now())` taken before/after a scripted drag.
- Wheel-zoom response time: **< 16 ms** per event (within 1 frame).
- Memory: TanStack Query cache for Iberia (~91 polygons × ~100 vertices × 8 bytes × 2 coords ≈ 140 KB) + lookup JSONs (<20 KB) + metadata (<50 KB) — total data payload well under 1 MB.

### Test Methodology for Assumption A5 (91 polygons at 60fps)
1. Load Iberia fixture (use `.planning/phases/` test data or a mock GeoJSON with 91 random polygons).
2. Mount `<CanvasViewer>` at 1440×800 viewport.
3. Script a 2-second drag via Playwright, sampling `requestAnimationFrame` timestamps.
4. Assert: median frame-interval < 18 ms (≈ 55 fps) and 95th percentile < 25 ms.
5. If fail: add `.cache()` call to each `<Line>` after mount (React-Konva `onMount` via ref) and retry.

### Test Methodology for Tailwind v4 + Radix Transparency (Pitfall 2)
1. Render `<CanvasRadixOverlaySmoke>` (Example 7) to a Playwright page.
2. Sample the pixel at the center of the Card using `page.evaluate(() => getComputedStyle + readPixel)` or a visual snapshot against a known baseline.
3. Assert the center pixel RGB is NOT the magenta `#ff00ff` of the Stage fill (i.e., the Card is opaque).
4. Negative control: flip `index.css` import order (swap Tailwind before Radix), re-run — test must FAIL. Revert.

## Security Domain

`security_enforcement` not set in `.planning/config.json` — treat as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local single-user tool. No auth layer in Phase 2. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | partial | Phase 1 already enforces `project_id` validation (UUID) + file whitelist on `/preview/{filename}`. Phase 2 adds `/artifacts/{filename}` routes (if OQ1 picks path a) — reuse the whitelist pattern; do not add raw path traversal. |
| V5 Input Validation | yes | `project_id` must continue to be UUID-validated via `is_valid_uuid()` (VERIFIED: `backend/medieval_forge/services/paths.py` exists). New artifact filenames (e.g., `territories.geojson`) must be added to the existing `GENERATED_FILE_WHITELIST`. |
| V6 Cryptography | no | No crypto in Phase 2. |
| V7 Error Handling | partial | Don't leak filesystem paths in error responses to the frontend — existing FastAPI 404/500 handling is sufficient; keep it. |
| V14 Configuration | partial | Tailwind v4 + Radix CSS import order is a *configuration* correctness concern with visual-integrity impact — covered in Pitfall 2 + smoke test. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `GET /api/projects/{id}/artifacts/{filename}` | Tampering | Extend `GENERATED_FILE_WHITELIST` to include `territories.geojson`. Reject anything else with 400. Reuse existing `is_valid_uuid(project_id)` guard. (VERIFIED: pattern already exists in `backend/medieval_forge/api/generate.py` `get_preview`.) |
| Large GeoJSON causing browser OOM (user opens a generated Russia at ~50k municipalities) | DoS | Not a Phase 2 concern — Iberia is 91 condados. Phase 2 only renders condados (not raw municipalities). Note for Phase 4/5 editing: validate polygon count before rendering; consider pagination or sampling. |
| XSS via territory name in tooltip/inspector | Tampering | Territory names come from generator output (Python-controlled) — LOW risk. But the inspector renders `{territory.name}` in Radix `Heading` which auto-escapes. Do NOT use `dangerouslySetInnerHTML` anywhere in the inspector. |
| Stored XSS via user-provided project name shown in sidebar | Tampering | Already mitigated by React's default JSX escaping (confirmed in ProjectDetail.tsx). No action needed. |

## Project Constraints (from CLAUDE.md)

From `./CLAUDE.md` — directives that bind Phase 2 planning:

1. **Tech stack locked:** Python 3.11+ / FastAPI / SQLite backend (Phase 2 does NOT change backend stack); React 18+ (project is on 19.2) + TypeScript + Vite + Konva.js frontend. **Constraint:** do not swap in an alternative 2D canvas lib.
2. **State management locked:** Zustand + zundo middleware for undo/redo. **Constraint:** Phase 2 introduces a Zustand slice but does NOT wrap it in `temporal` (zundo is wired for Phase 4).
3. **Cache layer locked:** TanStack Query v5. **Constraint:** all data fetching in Phase 2 uses TanStack Query, not raw `fetch` in components.
4. **Styling locked:** Tailwind CSS v4 + Radix UI primitives. **Constraint:** Phase 2 uses Radix Themes components for inspector + layer panel + button (already locked in UI-SPEC).
5. **GSD workflow enforcement:** "Before using Edit, Write, or other file-changing tools, start work through a GSD command..." **Constraint:** all Phase 2 work goes through `/gsd-execute-phase` or equivalent.
6. **Potential Issues §1 (react-konva peer-dep):** Project is on React 19 — the peer-dep problem is avoided. **No `--legacy-peer-deps` flag should be added.** Verified: `npm view react-konva@19.2.3 peerDependencies → react: ^19.2.0` matches project's React 19.2.0.
7. **Potential Issues §3 (Tailwind v4 + Radix transparency #17137):** Already handled in `frontend/src/index.css` (Radix imported before Tailwind). **Constraint:** planner MUST include a Wave-0 smoke test that proves this integration; ordering regressions are silent and high-cost.

## Sources

### Primary (HIGH confidence)
- `inicio/map_generator.py` lines 52–171, 680–726 — projection formulas and metadata structure [CITED: project code]
- `backend/medieval_forge/services/generator.py` — file whitelist + artifact pipeline [CITED: project code]
- `frontend/package.json` — verified current versions match research [CITED: project code]
- `frontend/src/index.css` — verified Radix-before-Tailwind CSS import order [CITED: project code]
- https://konvajs.org/docs/sandbox/Zooming_Relative_To_Pointer.html — official cursor-anchored zoom recipe [CITED]
- https://konvajs.org/docs/performance/All_Performance_Tips.html — listening=false + layer count guidance [CITED]
- https://tanstack.com/query/latest/docs/framework/react/guides/render-optimizations — `select` for stable references [CITED]
- https://github.com/tailwindlabs/tailwindcss/discussions/17137 — Tailwind v4 + Radix transparency (CLAUDE.md Pitfall 3) [CITED]
- `npm view react-konva@19.2.3 peerDependencies` — returned `react: ^19.2.0`, `konva: ^8||^9||^10` [VERIFIED 2026-04-17]
- `npm view konva version` → `10.2.5` [VERIFIED 2026-04-17]
- `npm view @radix-ui/themes version` → `3.3.0` [VERIFIED 2026-04-17]

### Secondary (MEDIUM confidence)
- Konva 3-layer + decorations pattern — derived from official perf tips + UI-SPEC lock [CITED + ASSUMED for optimal split at N=91]
- Threshold derivation for `LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0` — order-of-magnitude math from Iberia viewport, not empirically tested [ASSUMED]

### Tertiary (LOW confidence)
- Sub-pixel seam behavior at 4× zoom (A4) — not empirically tested. Flagged as Open Question 3.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions freshly verified against npm 2026-04-17; react-konva peer-dep unambiguously matches project React 19.2.
- Architecture (4-layer Konva, projection, Zustand slice): HIGH — UI-SPEC locks most of it; projection math ported verbatim from working Python generator.
- Pitfalls (StrictMode, transparency, clamp): HIGH — all cited with source or reproduced from project code.
- Data availability (territories.geojson + neighbors): MEDIUM — direct inspection of `map_generator.py` confirms these fields are NOT currently emitted, but the *fix* is a small backend task the planner must schedule (see Open Questions 1 and 2).
- Performance assumptions (91 polygons at 60fps): MEDIUM — based on Konva docs + general 2D canvas performance intuition; empirical validation methodology provided in Validation Architecture.

**Research date:** 2026-04-17
**Valid until:** ~30 days (stack versions change slowly; react-konva/konva release cadence is multi-month). Re-verify versions in mid-May 2026 if Phase 2 work slips.
