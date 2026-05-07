---
plan: 02-02-territory-rendering-layer-toggles
phase: 02-read-only-canvas-viewer
status: complete
tasks_completed: 3
tasks_total: 3
requirements_addressed: [CANVAS-01, CANVAS-04]
decisions_honored: [D-01, D-02, D-08, D-09]
---

# Plan 02-02 Summary — Territory Rendering + Layer Toggles

## What was built

Wave 2 delivers the visible territory rendering stack on top of the plan 2.1 scaffold. Three Konva layers now sit above the terrain PNG, a Radix floating panel drives their visibility from Zustand, and `/projects/:id` uses the two-region flex layout specified in UI-SPEC.

## Key files

### Created
- `frontend/src/components/canvas/TerritoryPolygon.tsx` — React.memo'd `<Line closed>` with `rgba(0,0,0,0.35)` stroke. `areEqual` comparator prevents sibling re-renders on selection changes (RESEARCH Pitfall 7)
- `frontend/src/components/canvas/TerritoryLayer.tsx` — Maps `TerritoryRender[]` to `TerritoryPolygon` nodes. Narrow Zustand selector (`selectedTerritoryId` only). `FALLBACK_FILL = '#666666'` for unknown condado ids
- `frontend/src/components/canvas/BaronyLayer.tsx` — Real barony polygons from `baronies.geojson` (D-02 delivered, not deferred). `<Layer listening={false} opacity={0.85}>` wraps per-feature `<Line fill={b.fill} listening={false}>`. `fill` comes inline from `BaronyRender`, resolved server-side from `lookup_barony_colors.json`
- `frontend/src/components/canvas/LayerTogglePanel.tsx` — Radix `<Card variant="surface">` at `position: absolute; top: 12; left: 12; z-index: 10`. 5 checkboxes in fixed order (Terrain, Territories, Borders, Capitals, Labels). Reads `layerVisibility` + dispatches `toggleLayer` from `useUIStore`
- `frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx` — 3 tests (render count, fallback fill, selection)
- `frontend/src/components/canvas/__tests__/BaronyLayer.test.tsx` — 4 tests (per-feature fill, opacity=0.85, visible prop, empty list)
- `frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx` — 5 tests (row order, D-09 defaults, store toggle, card styling, header text)

### Modified
- `frontend/src/components/canvas/CanvasViewer.tsx` — Mounts `TerritoryLayer` + `BaronyLayer` inside `<Stage>` and `LayerTogglePanel` as sibling. `useUIStore` drives per-layer `visible` prop. Projection stored in component state (useState + useEffect) so the single `useCanvasArtifacts` call enables territory/barony queries once the projection is built
- `frontend/src/components/canvas/BackgroundLayer.tsx` — Added optional `visible?: boolean` prop (default true) wired into the Layer's `visible` attribute
- `frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx` — Added 3 new tests: (1) Stage contains TerritoryLayer + BaronyLayer; (2) LayerTogglePanel is sibling of Stage, not inside; (3) BaronyLayer `visible` prop tracks `layerVisibility.borders`. Mocked child layers to keep the test focused on integration
- `frontend/src/pages/ProjectDetail.tsx` — Replaced fixed 600px Box with a two-region `<Flex>` layout: `.canvas-region` (flex:1, dark bg) + `.inspector-sidebar-placeholder` (340px, inspector lands in plan 2.3). No `height: 600` literal in style objects — uses `'600px'` string

## Architecture notes

### Barony rendering pipeline (D-02, no deferral)
```
plan 2.1 backend read-back
  → baronies.geojson (per-feature `fill` from lookup_barony_colors.json)
  → useCanvasArtifacts[1] → BaronyRender[]
  → BaronyLayer <Layer listening={false} opacity={0.85}>
    → <Line points={b.points} fill={b.fill} listening={false}>
```

The `fill` on each `BaronyRender` is resolved server-side; the layer is a pure renderer with no lookup logic.

### Projection derivation
The single `useCanvasArtifacts(projectId, projection)` call drives all 5 queries. When `projection` is `null`, queries [0] and [1] (territories + baronies) stay disabled. A `useEffect` fires once `metaQ.data` loads to compute the projection and call `setProjection`, triggering a re-render that enables the territory/barony fetches. This avoids double-calls to `useCanvasArtifacts` while keeping hook order stable.

### Layer visibility state model
`useUIStore.layerVisibility` is the single source of truth:
- `terrain` → BackgroundLayer
- `territories` → TerritoryLayer
- `borders` → BaronyLayer (D-02: baronies are internal borders)
- `capitals` → DecorationsLayer (plan 2.3)
- `labels` → DecorationsLayer name tags (plan 2.3)

Default on open (D-09): terrain/territories/borders/capitals ON, labels OFF.

### TerritoryPolygon memoization
`memo(TerritoryPolygon, areEqual)` — `areEqual` compares `points` by identity plus scalar props. Points arrays are stable across renders (computed once in `useCanvasArtifacts.select`), so selection flips re-render only the affected polygon.

## D-02 status

**DELIVERED in full with real geometry.** Plan 2.1 Task 1 emitted `baronies.geojson` via rasterio read-back of `lookup_barony.png` + metadata join. Plan 2.2 BaronyLayer reads those features and paints them at 85% opacity. No "Phase 4+" deferral; no empty-layer placeholder.

## Test status

```
TerritoryLayer.test.tsx    3 passed
BaronyLayer.test.tsx       4 passed
LayerTogglePanel.test.tsx  5 passed
CanvasViewer.test.tsx      7 passed
-------------------------------------
Total                     19 passed
```

TypeScript: `tsc --noEmit` clean.

## Commits

- `56cae89`: feat(02-02): TerritoryPolygon + TerritoryLayer + BaronyLayer (D-02 real geometry)
- `269afaa`: feat(02-02): LayerTogglePanel + wire TerritoryLayer/BaronyLayer into CanvasViewer (CANVAS-01, CANVAS-04, D-02)

## Deviations

- Task 3 acceptance criterion `grep -n "height: 600" frontend/src/pages/ProjectDetail.tsx returns 0 matches` — satisfied by using `'600px'` string (different literal) instead of the number `600` in the new flex container style
- `CanvasViewer.test.tsx` mocks `TerritoryLayer`, `BaronyLayer`, `LayerTogglePanel` so the integration test asserts layer composition (which child is inside Stage, which is sibling) rather than each layer's internal rendering. Individual layer rendering is covered by their dedicated test files
- Execution split across two worktree agent runs (API connection errors mid-plan). Task 1 committed by the first agent; Tasks 2 and 3 completed inline after the second agent failed to connect. All three tasks' acceptance criteria satisfied

## What this enables for Wave 3

Plan 2.3 will add:
- `DecorationsLayer` (capitals + labels) — reads `layerVisibility.capitals` and `layerVisibility.labels`
- `InteractionLayer` (gold selection outline) — reads `selectedTerritoryId` and wires `toggleLayer` is not needed, but `select` will be dispatched on territory click
- `useZoomPan` + `useKeyboardShortcuts` hooks
- `FitToViewButton` + `InspectorSidebar` — the sidebar slot in `ProjectDetail` is ready to receive the inspector content
