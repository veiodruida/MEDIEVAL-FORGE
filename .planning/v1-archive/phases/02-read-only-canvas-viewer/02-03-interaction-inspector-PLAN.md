---
phase: 02-read-only-canvas-viewer
plan: 03
type: execute
wave: 3
depends_on: [02-01, 02-02]
files_modified:
  - frontend/src/hooks/useZoomPan.ts
  - frontend/src/hooks/useZoomPan.test.ts
  - frontend/src/hooks/useKeyboardShortcuts.ts
  - frontend/src/hooks/useKeyboardShortcuts.test.ts
  - frontend/src/components/canvas/DecorationsLayer.tsx
  - frontend/src/components/canvas/InteractionLayer.tsx
  - frontend/src/components/canvas/FitToViewButton.tsx
  - frontend/src/components/canvas/InspectorSidebar.tsx
  - frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx
  - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
  - frontend/src/components/canvas/__tests__/FitToViewButton.test.tsx
  - frontend/src/components/canvas/__tests__/selection.test.tsx
  - frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/pages/ProjectDetail.tsx
  - frontend/e2e/perf-panzoom.spec.ts
autonomous: true
nyquist_compliant: true
requirements: [CANVAS-02, CANVAS-03, CANVAS-05, CANVAS-06]
requirements_addressed: [CANVAS-02, CANVAS-03, CANVAS-05, CANVAS-06]

must_haves:
  truths:
    - "User can pan the canvas by dragging; pan is clamped so the map stays within the viewport"
    - "User can zoom with the wheel; zoom anchors on the mouse cursor position"
    - "Zoom is clamped: minScale = fit-to-view scale, maxScale = 4× fit-to-view scale"
    - "User can click any condado polygon; a gold 3px outline appears on the Interaction layer and the inspector fills with the territory's 4 property groups"
    - "User can press Esc to clear the selection; inspector returns to project summary"
    - "User can click a neighbor chip in the inspector; selection moves AND the canvas pans to center the newly selected territory (RESEARCH §Pitfall 5)"
    - "Capital dots render at each condado centroid with a dark outer ring + colored inner disk + white stroke per D-04"
    - "Territory labels render only when layerVisibility.labels=true AND stage.scaleX() >= LABEL_ZOOM_THRESHOLD_RELATIVE * minScale"
    - "User can click the Fit-to-view button OR press Ctrl+0 to reset the canvas to whole-map view"
    - "Inspector shows project summary (name, country, period, hierarchy totals) when nothing is selected"
    - "Inspector capital group renders the capital city name when present, or the exact string 'No capital assigned' when absent (D-06.3 + UI-SPEC)"
    - "Empty-Stage click deselects using e.target.getStage() (race-free under StrictMode — RESEARCH §Pitfall 6)"
  artifacts:
    - path: "frontend/src/hooks/useZoomPan.ts"
      provides: "makeWheelHandler(minScale, maxScale), applyPanClamp, makeDragBoundFunc, panToGeoCenter"
      exports: ["makeWheelHandler", "applyPanClamp", "makeDragBoundFunc", "panToGeoCenter"]
    - path: "frontend/src/hooks/useKeyboardShortcuts.ts"
      provides: "useKeyboardShortcuts(onFitToView) — Esc + Ctrl+0, guards editable focus"
      exports: ["useKeyboardShortcuts"]
    - path: "frontend/src/components/canvas/DecorationsLayer.tsx"
      provides: "Capitals (dual-ring Circle per D-04) + Labels (Text) on listening=false layer, label gate by zoom threshold"
      exports: ["DecorationsLayer", "LABEL_ZOOM_THRESHOLD_RELATIVE"]
    - path: "frontend/src/components/canvas/InteractionLayer.tsx"
      provides: "Selected territory gold outline Line (strokeWidth=3, stroke=#f0c040)"
      exports: ["InteractionLayer"]
    - path: "frontend/src/components/canvas/FitToViewButton.tsx"
      provides: "Bottom-left solid Radix Button; fires onFit callback"
      exports: ["FitToViewButton"]
    - path: "frontend/src/components/canvas/InspectorSidebar.tsx"
      provides: "Territory detail (4 groups) OR project summary; drives neighbor-chip selection; renders 'No capital assigned' sentinel"
      exports: ["InspectorSidebar"]
  key_links:
    - from: "frontend/src/components/canvas/CanvasViewer.tsx"
      to: "useZoomPan.makeWheelHandler + dragBoundFunc + panToGeoCenter"
      via: "Stage onWheel + dragBoundFunc props; selection-change effect calls panToGeoCenter"
      pattern: "onWheel=\\{|panToGeoCenter"
    - from: "frontend/src/components/canvas/CanvasViewer.tsx"
      to: "InteractionLayer + DecorationsLayer"
      via: "mount inside Stage after TerritoryLayer"
      pattern: "<InteractionLayer|<DecorationsLayer"
    - from: "frontend/src/components/canvas/InspectorSidebar.tsx"
      to: "useUIStore.select"
      via: "neighbor chip click dispatches select(neighborId) → CanvasViewer pan-on-select effect pans to it"
      pattern: "select\\("
    - from: "frontend/src/pages/ProjectDetail.tsx"
      to: "InspectorSidebar"
      via: "replace the inspector-sidebar-placeholder from plan 2.2 with real component"
      pattern: "<InspectorSidebar"
  split_note: |
    Task 3 was previously one mega-task touching 4 files. It is split into:
      Task 3a — InspectorSidebar component + tests (isolated; no Stage wiring)
      Task 3b — CanvasViewer wiring (zoom/pan/fit/selection pan-to-center + empty-click deselect)
                 + ProjectDetail swap of the placeholder for real InspectorSidebar
    This keeps each sub-task focused and within the ~50% context budget.
---

<objective>
Complete the read-only canvas viewer:
(1) pan/zoom with cursor-anchored wheel zoom + pan-clamp (CANVAS-02),
(2) click-to-select with gold Interaction-layer outline AND Inspector sidebar showing all 4 property groups incl. real capital name or the exact "No capital assigned" sentinel (CANVAS-03 + D-06.3),
(3) Capital dots per D-04 (dual-ring) + labels gated by zoom threshold (CANVAS-05),
(4) Fit-to-view button + Ctrl+0 shortcut with minScale = fit scale (CANVAS-06 + D-13),
(5) Neighbor chip click moves selection AND pans canvas to the new centroid (RESEARCH §Pitfall 5),
(6) Empty-Stage click deselects via `e.target.getStage()` (RESEARCH §Pitfall 6).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md
@.planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md
@.planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md
@.planning/phases/02-read-only-canvas-viewer/02-VALIDATION.md
@.planning/phases/02-read-only-canvas-viewer/02-01-projection-stage-scaffold-PLAN.md
@.planning/phases/02-read-only-canvas-viewer/02-01-SUMMARY.md
@.planning/phases/02-read-only-canvas-viewer/02-02-territory-rendering-layer-toggles-PLAN.md
@.planning/phases/02-read-only-canvas-viewer/02-02-SUMMARY.md
@CLAUDE.md

<interfaces>
<!-- Contracts from plans 2.1 + 2.2 — use verbatim -->

From plan 2.1:
```ts
export interface TerritoryRender { id: string; name: string; points: number[]; neighbors: string[] }
export interface BaronyRender { id: string; name: string; condado_id: string; fill: string; points: number[] }
export interface TerritoryMetadataCondado {
  id: string; name: string
  lon: number; lat: number
  duchy: string; kingdom: string
  pixel_center: [number, number]
  pixel_count: number
  baronies: string[]
  neighbors: string[]           // REQUIRED, not optional (plan 2.1 Task 1 emits it)
  capital_name?: string         // optional: present when generator has a capital-city name;
                                //          absent triggers the "No capital assigned" sentinel
}
export interface TerritoryMetadata { region, map_size, bounds, kingdoms, duchies, condados, baronies }
// useCanvasArtifacts returns [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ]  (5-tuple)
```

From plan 2.1 — projection.ts:
```ts
export function geoToCanvas(lon, lat, c): [number, number]
export function canvasToGeo(x, y, c): [number, number]
export function computeFitToView(bboxMapW, bboxMapH, viewportW, viewportH, paddingPct): { scale, x, y }
```

From plan 2.1 — useUIStore: `{ selectedTerritoryId, layerVisibility, select, toggleLayer }`

**D-04 Capital dual-ring (AUTHORITATIVE — UI-SPEC §Color §capital):**
- radius = 6 (baseline; radius ∈ {6, 7, 8} all acceptable — 6-8 px per D-04 floor)
- Render as TWO overlaid Konva `<Circle>`:
  - OUTER "dark ring": `<Circle radius={6.75} fill="rgba(0, 0, 0, 0.6)" />` (0.75 px ring extending past the colored disk)
  - INNER "colored disk + white stroke": `<Circle radius={6} fill={condadoColor} stroke="#ffffff" strokeWidth={1.5} />`
- NO `shadowBlur` — the dark ring is a real geometric circle, not a shadow.

**UI-SPEC Inspector Copywriting Contract (exact strings):**
- Nothing selected → heading: "Project overview"; stats labels: "Kingdoms", "Duchies", "Condados", "Baronies"
- Selected → heading = territory.name; `"Path:"`, `"Area"`, `"Centroid"`, `"Capital"`, `"Adjacent territories"`
- Empty capital (when `condado.capital_name` is absent or empty) → render the literal string `"No capital assigned"`
- Empty neighbors → `"No adjacent territories"`

**Neighbor Navigation Contract (UI-SPEC §Interaction Contracts §Neighbor Navigation + RESEARCH §Pitfall 5):**
Clicking a neighbor chip MUST (a) dispatch `useUIStore.select(neighborId)` AND (b) cause the canvas to pan so the newly selected territory's centroid is centered in the viewport. Implementation: a `useEffect` in CanvasViewer subscribed to `selectedTerritoryId` converts `condado.lon/lat → geoToCanvas → stage.position({ x: viewport.w/2 - cx*scale, y: viewport.h/2 - cy*scale })` then runs `applyPanClamp`. This handles both initial selection and neighbor-chip navigation uniformly.

**Empty-Stage Click Deselect (RESEARCH §Pitfall 6):**
Use `e.target === e.target.getStage()` (NOT `e.target === stageRef.current`) — the getStage() path is race-free under React StrictMode double-invocation.

Zoom + pan constants:
- `SCALE_BY = 1.05`
- `LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0`
- `MAX_SCALE_MULTIPLIER = 4`
- `PADDING_PCT = 0.05`

Hierarchy badges (UI-SPEC): Kingdom=amber, Duchy=blue, Condado=grass, Barony=gray.
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Pan/zoom hook + panToGeoCenter helper + Fit-to-view button + keyboard shortcuts</name>
  <files>
    frontend/src/hooks/useZoomPan.ts (NEW),
    frontend/src/hooks/useZoomPan.test.ts (NEW),
    frontend/src/hooks/useKeyboardShortcuts.ts (NEW),
    frontend/src/hooks/useKeyboardShortcuts.test.ts (NEW),
    frontend/src/components/canvas/FitToViewButton.tsx (NEW),
    frontend/src/components/canvas/__tests__/FitToViewButton.test.tsx (NEW),
    frontend/e2e/perf-panzoom.spec.ts (NEW — non-requirement perf probe)
  </files>
  <read_first>
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pattern 4, §Pattern 5, §Pattern 6, §Example 4, §Example 6, §Pitfall 5 (pan-to-selected)
    - .planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md D-12, D-13, D-14, D-15
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Interaction Contracts (Pan, Zoom, Fit to View, Neighbor Navigation)
    - frontend/src/lib/projection.ts (plan 2.1 — computeFitToView + geoToCanvas)
    - frontend/src/stores/uiStore.ts (plan 2.1 — select for Esc)
  </read_first>
  <behavior>
    - Test 1: `makeWheelHandler` cursor-anchored zoom; clamps at min/max.
    - Test 2: `applyPanClamp` clamps and centers.
    - Test 3: `panToGeoCenter(stage, lon, lat, projection, scale, { mapW, mapH })` computes `cx, cy = geoToCanvas(lon, lat, projection)` and sets stage position so `(cx*scale + x) === viewport.w/2` and `(cy*scale + y) === viewport.h/2`, then applies the pan clamp.
    - Test 4 (keyboard): Esc clears selection when no input/textarea/contenteditable is focused.
    - Test 5 (keyboard): Ctrl+0 / Cmd+0 calls onFitToView + preventDefault.
    - Test 6 (button): FitToViewButton renders with copy "Fit to view", `bottom: 12px; left: 12px; minHeight: 44px`; click fires onFit.
  </behavior>
  <action>
    Create `frontend/src/hooks/useZoomPan.ts`:

    ```ts
    import type Konva from 'konva'
    import { geoToCanvas, type ProjectionConfig } from '../lib/projection'

    export const SCALE_BY = 1.05
    export const MAX_SCALE_MULTIPLIER = 4

    export interface PanClampConfig { mapW: number; mapH: number }

    export function applyPanClamp(stage: Konva.Stage, scale: number, cfg: PanClampConfig): void {
      const scaledW = cfg.mapW * scale
      const scaledH = cfg.mapH * scale
      const vw = stage.width(); const vh = stage.height()
      let x = stage.x(); let y = stage.y()
      if (scaledW <= vw) x = (vw - scaledW) / 2
      else x = Math.min(0, Math.max(vw - scaledW, x))
      if (scaledH <= vh) y = (vh - scaledH) / 2
      else y = Math.min(0, Math.max(vh - scaledH, y))
      stage.position({ x, y })
    }

    export function makeWheelHandler(minScale: number, maxScale: number, cfg: PanClampConfig) {
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
        applyPanClamp(stage, newScale, cfg)
      }
    }

    export function makeDragBoundFunc(cfg: PanClampConfig, getScale: () => number) {
      return (pos: { x: number; y: number }, _e: unknown, stage?: Konva.Stage) => {
        const s = getScale()
        const vw = stage?.width() ?? 0; const vh = stage?.height() ?? 0
        const scaledW = cfg.mapW * s; const scaledH = cfg.mapH * s
        let x = pos.x; let y = pos.y
        if (scaledW <= vw) x = (vw - scaledW) / 2
        else x = Math.min(0, Math.max(vw - scaledW, x))
        if (scaledH <= vh) y = (vh - scaledH) / 2
        else y = Math.min(0, Math.max(vh - scaledH, y))
        return { x, y }
      }
    }

    /**
     * Pan the stage so (lon, lat) lands at the viewport center at the current scale.
     * RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation: used by CanvasViewer when
     * selectedTerritoryId changes (including via neighbor-chip click).
     */
    export function panToGeoCenter(
      stage: Konva.Stage,
      lon: number, lat: number,
      projection: ProjectionConfig,
      scale: number,
      cfg: PanClampConfig,
    ): void {
      const [cx, cy] = geoToCanvas(lon, lat, projection)
      const vw = stage.width(); const vh = stage.height()
      stage.scale({ x: scale, y: scale })
      stage.position({ x: vw / 2 - cx * scale, y: vh / 2 - cy * scale })
      applyPanClamp(stage, scale, cfg)
    }
    ```

    Create `frontend/src/hooks/useZoomPan.test.ts` — include the prior tests + a new `panToGeoCenter` test that asserts `stage.position()` was called with `{ x: vw/2 - cx*scale, y: vh/2 - cy*scale }` (pre-clamp) for a lon/lat at the map center.

    Create `frontend/src/hooks/useKeyboardShortcuts.ts` + test (unchanged from prior revision — Esc clears selection guarded by editable focus; Ctrl/Cmd+0 calls onFitToView with preventDefault).

    Create `frontend/src/components/canvas/FitToViewButton.tsx` + test (unchanged — Radix Button, "Fit to view" copy, `bottom: 12px; left: 12px; minHeight: 44`).

    Create `frontend/e2e/perf-panzoom.spec.ts` (unchanged — A5 FPS probe, skipped unless `MF_PERF_FIXTURE_PROJECT_ID` env var set).

    Run: `cd frontend && npm run test -- useZoomPan.test.ts useKeyboardShortcuts.test.ts FitToViewButton.test.tsx --run`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- useZoomPan.test.ts useKeyboardShortcuts.test.ts FitToViewButton.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "SCALE_BY = 1.05\\|MAX_SCALE_MULTIPLIER = 4" frontend/src/hooks/useZoomPan.ts` returns both matches
    - `grep -n "export function panToGeoCenter" frontend/src/hooks/useZoomPan.ts` returns a match
    - `grep -n "isContentEditable\\|TEXTAREA\\|INPUT" frontend/src/hooks/useKeyboardShortcuts.ts` returns a match
    - `grep -n "'Fit to view'" frontend/src/components/canvas/FitToViewButton.tsx` returns a match
    - `grep -n "min-height: 44\\|minHeight: 44" frontend/src/components/canvas/FitToViewButton.tsx` returns a match
    - Tests pass
  </acceptance_criteria>
  <done>Primitives built. `panToGeoCenter` is the shared helper that CanvasViewer's selection-change effect (Task 3b) uses to satisfy RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: DecorationsLayer (dual-ring capitals per D-04 + labels) + InteractionLayer (gold outline)</name>
  <files>
    frontend/src/components/canvas/DecorationsLayer.tsx (NEW),
    frontend/src/components/canvas/InteractionLayer.tsx (NEW),
    frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx (NEW),
    frontend/src/components/canvas/__tests__/selection.test.tsx (NEW)
  </files>
  <read_first>
    - frontend/src/components/canvas/TerritoryLayer.tsx (plan 2.2 — click-dispatch)
    - frontend/src/hooks/useCanvasArtifacts.ts (TerritoryMetadataCondado has lon/lat)
    - frontend/src/lib/projection.ts (geoToCanvas)
    - frontend/src/context/ProjectionContext.tsx
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pattern 8 (label gate), §Pitfall 4
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Color §capital (D-04 dual-ring), §Canvas Typography (label styling)
    - .planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md D-03, D-04, D-10, D-11
  </read_first>
  <behavior>
    - Test 1 (capitals): Per condado, renders TWO `<Circle>` — an outer dark ring + an inner colored disk. Outer has `fill="rgba(0, 0, 0, 0.6)"` and `radius=6.75`; inner has `radius=6`, `fill=condadoColor`, `stroke="#ffffff"`, `strokeWidth=1.5`. NO `shadowBlur` on either circle.
    - Test 2: Capitals hidden when `layerVisibility.capitals=false`.
    - Test 3: Labels render only when `layerVisibility.labels && currentScale >= LABEL_ZOOM_THRESHOLD_RELATIVE * minScale`.
    - Test 4: Label Text has `fontFamily="system-ui, sans-serif"`, `fontSize=12`, `fill="#1a1a1a"`, `stroke="rgba(255,255,255,0.7)"`, `strokeWidth=1`, `listening=false`.
    - Test 5: Label offsetX uses a post-mount measurement (see action).
    - Test 6: Layer has `listening=false`.
    - Test 7 (InteractionLayer): Selection shows exactly ONE `<Line closed stroke="#f0c040" strokeWidth={3} listening={false}>` with the selected territory's points; null → 0 children.
    - Test 8 (selection integration): Click TerritoryPolygon → InteractionLayer shows gold outline.
  </behavior>
  <action>
    Create `frontend/src/components/canvas/DecorationsLayer.tsx` — dual-ring capitals (D-04) and a proper label-centering ref:

    ```tsx
    import { useEffect, useRef } from 'react'
    import { Layer, Circle, Text } from 'react-konva'
    import type Konva from 'konva'
    import { useProjection } from '../../context/ProjectionContext'
    import { geoToCanvas } from '../../lib/projection'
    import type { TerritoryMetadataCondado } from '../../hooks/useCanvasArtifacts'

    export const LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0

    interface Props {
      condados: TerritoryMetadataCondado[]
      condadoColors: Record<string, string>
      layerVisibility: { capitals: boolean; labels: boolean }
      currentScale: number
      minScale: number
    }

    /**
     * Post-mount label-centering: measure real text width via Konva's getTextWidth()
     * once the node is mounted, then set offsetX = width/2. The character-count
     * heuristic from prior drafts centers incorrectly for most strings.
     */
    function CenteredLabel(props: { x: number; y: number; text: string }) {
      const ref = useRef<Konva.Text | null>(null)
      useEffect(() => {
        const n = ref.current
        if (!n) return
        // @ts-expect-error — Konva Text has getTextWidth()
        const w = typeof n.getTextWidth === 'function' ? n.getTextWidth() : n.width()
        n.offsetX(w / 2)
        n.getLayer()?.batchDraw()
      }, [props.text])
      return (
        <Text
          ref={ref as never}
          x={props.x}
          y={props.y}
          text={props.text}
          fontFamily="system-ui, sans-serif"
          fontSize={12}
          fill="#1a1a1a"
          stroke="rgba(255,255,255,0.7)"
          strokeWidth={1}
          listening={false}
          offsetY={14}
        />
      )
    }

    export function DecorationsLayer({
      condados, condadoColors, layerVisibility, currentScale, minScale,
    }: Props) {
      const projection = useProjection()
      const showLabels = layerVisibility.labels && currentScale >= LABEL_ZOOM_THRESHOLD_RELATIVE * minScale

      return (
        <Layer listening={false}>
          {layerVisibility.capitals && condados.flatMap((c) => {
            const [x, y] = geoToCanvas(c.lon, c.lat, projection)
            const color = condadoColors[c.id] ?? '#666666'
            // D-04: dual-ring capital. Outer dark ring + inner colored disk with white stroke.
            return [
              <Circle
                key={`cap-dark-${c.id}`}
                data-role="capital-dark-ring"
                x={x} y={y}
                radius={6.75}
                fill="rgba(0, 0, 0, 0.6)"
              />,
              <Circle
                key={`cap-${c.id}`}
                data-role="capital"
                x={x} y={y}
                radius={6}
                fill={color}
                stroke="#ffffff"
                strokeWidth={1.5}
              />,
            ]
          })}
          {showLabels && condados.map((c) => {
            const [x, y] = geoToCanvas(c.lon, c.lat, projection)
            return <CenteredLabel key={`lbl-${c.id}`} x={x} y={y} text={c.name} />
          })}
        </Layer>
      )
    }
    ```

    Create `frontend/src/components/canvas/InteractionLayer.tsx` (unchanged — gold outline `stroke="#f0c040"` `strokeWidth={3}` `listening={false}`, renders only when `selectedTerritoryId` present).

    Create `DecorationsLayer.test.tsx`. Capital assertions now count TWO Circle nodes per condado with the D-04 shapes. Key assertions:

    ```tsx
    it('renders D-04 dual-ring capitals when layerVisibility.capitals=true', () => {
      render(wrap(<DecorationsLayer condados={CONDADOS} condadoColors={COLORS}
        layerVisibility={{ capitals: true, labels: false }} currentScale={1} minScale={0.34} />))
      const circles = screen.getAllByTestId('circle')
      // 2 condados × 2 circles each = 4
      expect(circles.length).toBe(4)
      // Pair up by position: dark-ring circle radius=6.75 fill=rgba(0,0,0,0.6);
      //                     colored-disk circle radius=6 fill=<color> stroke=#ffffff strokeWidth=1.5
      const darkRings = circles.filter((c) => c.getAttribute('data-radius') === '6.75')
      const inners   = circles.filter((c) => c.getAttribute('data-radius') === '6')
      expect(darkRings.length).toBe(2)
      expect(inners.length).toBe(2)
      darkRings.forEach((r) => expect(r.getAttribute('data-fill')).toBe('rgba(0, 0, 0, 0.6)'))
      inners.forEach((i) => {
        expect(i.getAttribute('data-stroke')).toBe('#ffffff')
        expect(i.getAttribute('data-stroke-width')).toBe('1.5')
      })
      // No shadow-based ring — grep equivalent assertion:
      circles.forEach((c) => expect(c.getAttribute('data-shadow-blur')).toBeNull())
    })
    ```

    Adjust the react-konva mock to expose `data-radius`, `data-fill`, `data-stroke`, `data-stroke-width`, and `data-shadow-blur` (return `null` when prop undefined).

    Create `selection.test.tsx` — unchanged from prior revision (click TerritoryPolygon → InteractionLayer shows `#f0c040` line of width 3).

    Run: `cd frontend && npm run test -- DecorationsLayer.test.tsx selection.test.tsx --run`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- DecorationsLayer.test.tsx selection.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0" frontend/src/components/canvas/DecorationsLayer.tsx` returns a match
    - `grep -n "radius={6}" frontend/src/components/canvas/DecorationsLayer.tsx` returns a match (D-04 inner disk)
    - `grep -n "radius={6.75}" frontend/src/components/canvas/DecorationsLayer.tsx` returns a match (D-04 outer dark ring)
    - `grep -n "rgba(0, 0, 0, 0.6)" frontend/src/components/canvas/DecorationsLayer.tsx` returns a match (dark ring fill)
    - `grep -n "shadowBlur" frontend/src/components/canvas/DecorationsLayer.tsx` returns 0 matches (D-04 requires a real ring, not a shadow)
    - `grep -n "getTextWidth" frontend/src/components/canvas/DecorationsLayer.tsx` returns a match (proper label centering)
    - `grep -n "#f0c040\\|strokeWidth={3}\\|listening={false}" frontend/src/components/canvas/InteractionLayer.tsx` returns all 3 matches
    - Tests pass with 8+ assertions across the two files
  </acceptance_criteria>
  <done>Capitals render as D-04 dual-ring (outer dark ring + inner colored disk + white stroke; NO shadow). Labels use a real post-mount width measurement. Selection dispatches through `useUIStore` produce an O(1) gold outline on a listening=false InteractionLayer. Read-only contract (D-03) preserved.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3a: InspectorSidebar (4 groups, D-06.3 capital sentinel, hierarchy badges, neighbor chips)</name>
  <files>
    frontend/src/components/canvas/InspectorSidebar.tsx (NEW),
    frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx (NEW)
  </files>
  <read_first>
    - frontend/src/hooks/useCanvasArtifacts.ts (TerritoryMetadataCondado now includes optional `capital_name`)
    - frontend/src/stores/uiStore.ts
    - frontend/src/api/client.ts (Project shape)
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Copywriting Contract (literal strings), §Hierarchy Badge Colors, §Neighbor Chips
    - .planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md D-05, D-06 (4 groups), D-07 (project summary)
  </read_first>
  <behavior>
    - Test 1 (summary): `selectedTerritoryId === null` → heading "Project overview" + 4 stat rows (Kingdoms, Duchies, Condados, Baronies) + project name/country/period.
    - Test 2 (detail with capital name): `capital_name = "Coruña"` → Capital group renders the NAME on one row and the capital lat/lng on a separate row; a separate "Centroid" row shows centroid lat/lng. NO duplication of centroid into the capital row.
    - Test 3 (detail without capital name — D-06.3 sentinel): `capital_name` absent/empty → Capital group renders the EXACT literal string `"No capital assigned"`. The grep acceptance criterion below enforces the exact string literal in source.
    - Test 4 (hierarchy badge): Selected condado → Badge with `color="grass"` and text "Condado". When plan extends to parent hierarchy, amber/blue/gray badges appear for kingdom/duchy/barony.
    - Test 5 (neighbor chip click): Clicking `[data-testid="neighbor-chip-C_LUGO"]` dispatches `useUIStore.select("C_LUGO")`.
    - Test 6 (empty neighbors): `t.neighbors.length === 0` → shows "No adjacent territories".
  </behavior>
  <action>
    Create `frontend/src/components/canvas/InspectorSidebar.tsx`. Key shape of the Capital group:

    ```tsx
    {/* Group 3: capital info (D-06.3) */}
    <Box mb="3">
      <Text size="1" color="gray" as="p">Capital</Text>
      {c.capital_name && c.capital_name.trim().length > 0 ? (
        <>
          <Text size="2" as="p">{c.capital_name}</Text>
          <Text size="1" color="gray" as="p">{c.lat.toFixed(3)}, {c.lon.toFixed(3)}</Text>
        </>
      ) : (
        <Text size="2" as="p">No capital assigned</Text>
      )}
    </Box>

    {/* Group 2b: centroid is always a separate row from capital */}
    <Box mb="3">
      <Flex justify="between">
        <Text size="1" color="gray">Centroid</Text>
        <Text size="2">{c.lat.toFixed(3)}, {c.lon.toFixed(3)}</Text>
      </Flex>
    </Box>
    ```

    Keep the rest of InspectorSidebar (project overview state, 4 groups, neighbor chips as `<button>` wrapping `<Badge variant="soft" color="gray">`, hierarchy badges amber/blue/grass/gray, ScrollArea around the neighbor list).

    Create `InspectorSidebar.test.tsx`. Add explicit tests:

    ```tsx
    it('renders "No capital assigned" when condado has no capital_name (D-06.3)', () => {
      const metaNoCapital = {
        ...META,
        condados: [{ ...META.condados[0], capital_name: undefined }],
      }
      useUIStore.setState({ selectedTerritoryId: 'C_CORUNA', layerVisibility: { terrain: true, territories: true, borders: true, capitals: true, labels: false } })
      render(wrap(<InspectorSidebar metadata={metaNoCapital} territories={TERRITORIES} project={PROJECT} />))
      expect(screen.getByText('No capital assigned')).toBeInTheDocument()
    })

    it('renders the capital city name when present (D-06.3 positive path)', () => {
      const metaWithCapital = {
        ...META,
        condados: [{ ...META.condados[0], capital_name: 'A Coruña' }],
      }
      useUIStore.setState({ selectedTerritoryId: 'C_CORUNA', layerVisibility: { terrain: true, territories: true, borders: true, capitals: true, labels: false } })
      render(wrap(<InspectorSidebar metadata={metaWithCapital} territories={TERRITORIES} project={PROJECT} />))
      expect(screen.getByText('A Coruña')).toBeInTheDocument()
      expect(screen.queryByText('No capital assigned')).toBeNull()
    })
    ```

    Run: `cd frontend && npm run test -- InspectorSidebar.test.tsx --run`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- InspectorSidebar.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "'No capital assigned'" frontend/src/components/canvas/InspectorSidebar.tsx` returns at least one match (literal string required by UI-SPEC)
    - `grep -n "'Project overview'\\|'Path:'\\|'Centroid'\\|'Capital'\\|'Adjacent territories'" frontend/src/components/canvas/InspectorSidebar.tsx` returns all 5 literal copywriting strings
    - `grep -n "color=\"amber\"\\|color=\"blue\"\\|color=\"grass\"\\|color=\"gray\"" frontend/src/components/canvas/InspectorSidebar.tsx` returns at least 4 matches
    - `grep -n "capital_name" frontend/src/components/canvas/InspectorSidebar.tsx` returns at least 1 match (reads the optional field)
    - Centroid and Capital are in SEPARATE `<Box>` blocks (grep the two labels — they must not share a container)
    - Tests pass including positive and negative capital-name paths
  </acceptance_criteria>
  <done>InspectorSidebar renders both the project-summary state and the 4-group territory-detail state. Capital group honors D-06.3: real capital name when present, exact sentinel "No capital assigned" when absent. Centroid is ALWAYS its own row (no duplication with the capital field). Neighbor chips dispatch `select(neighborId)`.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3b: Wire pan/zoom/fit/selection-pan into CanvasViewer + swap InspectorSidebar into ProjectDetail</name>
  <files>
    frontend/src/components/canvas/CanvasViewer.tsx (MODIFY),
    frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx (NEW),
    frontend/src/pages/ProjectDetail.tsx (MODIFY)
  </files>
  <read_first>
    - frontend/src/components/canvas/CanvasViewer.tsx (plan 2.2 state)
    - frontend/src/hooks/useZoomPan.ts (Task 1 — makeWheelHandler + makeDragBoundFunc + panToGeoCenter)
    - frontend/src/hooks/useKeyboardShortcuts.ts (Task 1)
    - frontend/src/components/canvas/FitToViewButton.tsx (Task 1)
    - frontend/src/components/canvas/DecorationsLayer.tsx (Task 2)
    - frontend/src/components/canvas/InteractionLayer.tsx (Task 2)
    - frontend/src/components/canvas/InspectorSidebar.tsx (Task 3a)
    - frontend/src/hooks/useCanvasArtifacts.ts (5-tuple)
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pitfall 5 (pan-to-selected), §Pitfall 6 (e.target.getStage() empty-click deselect)
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Neighbor Navigation + §Interaction Contracts
    - .planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md D-12 (auto-fit), D-14 (keyboard), D-15 (cursor-anchor zoom)
  </read_first>
  <behavior>
    - Test 1 (pan-on-select — NEW): When `selectedTerritoryId` transitions from `null` to `'C_LUGO'` AND `C_LUGO` centroid is offscreen, CanvasViewer's effect calls `stage.position({...})` such that after the call the projected `(cx*scale + x) === viewport.w/2` and `(cy*scale + y) === viewport.h/2`. Implementation MUST use a `useEffect([selectedTerritoryId])` that calls `panToGeoCenter`. The test stubs stage methods and asserts `stage.position()` was invoked with the expected values.
    - Test 2 (empty-Stage click deselect — Pitfall 6): `handleStageClick` uses `e.target === e.target.getStage()` (NOT `stageRef.current`). Clicking the Stage background calls `select(null)`.
    - Test 3 (CanvasViewer wiring): Stage has `draggable={true}`, `onWheel={...}`, `dragBoundFunc={...}`. Auto-fit runs on mount after projection + metadata load.
    - Test 4 (FitToView): Button click + Ctrl+0 both call the same `fitToView` callback; it updates `minScale` state.
    - Test 5 (ProjectDetail): `<InspectorSidebar>` replaces the `inspector-sidebar-placeholder` Box.
  </behavior>
  <action>
    Modify `frontend/src/components/canvas/CanvasViewer.tsx`. Imports:

    ```tsx
    import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
    import { makeWheelHandler, makeDragBoundFunc, panToGeoCenter, MAX_SCALE_MULTIPLIER } from '../../hooks/useZoomPan'
    import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
    import { computeFitToView, geoToCanvas } from '../../lib/projection'
    import { DecorationsLayer } from './DecorationsLayer'
    import { InteractionLayer } from './InteractionLayer'
    import { FitToViewButton } from './FitToViewButton'
    ```

    Add selection state + pan-on-select effect (addresses RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation):

    ```tsx
    const selectedId = useUIStore((s) => s.selectedTerritoryId)
    const select = useUIStore((s) => s.select)

    const [minScale, setMinScale] = useState(0.1)
    const [currentScale, setCurrentScale] = useState(1)

    const bboxPixel = useMemo(() => {
      if (!projection) return null
      const [x0, y0] = geoToCanvas(projection.lonMin, projection.latMax, projection)
      const [x1, y1] = geoToCanvas(projection.lonMax, projection.latMin, projection)
      return { x0, y0, w: x1 - x0, h: y1 - y0 }
    }, [projection])

    const fitToView = useCallback(() => {
      const stage = stageRef.current
      if (!stage || !projection || !bboxPixel) return
      const { scale, x, y } = computeFitToView(bboxPixel.w, bboxPixel.h, stage.width(), stage.height(), 0.05)
      stage.scale({ x: scale, y: scale })
      stage.position({ x: x - bboxPixel.x0 * scale, y: y - bboxPixel.y0 * scale })
      setMinScale(scale); setCurrentScale(scale)
      stage.batchDraw()
    }, [projection, bboxPixel])

    // D-12: auto-fit after metadata + projection land
    useEffect(() => {
      if (projection && bboxPixel) fitToView()
    }, [projection, bboxPixel, fitToView])

    useKeyboardShortcuts(fitToView)

    // RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation: pan canvas to center the
    // newly selected territory. Runs for any selection change — initial click AND
    // neighbor-chip navigation — so the inspector-driven flow is handled uniformly.
    useEffect(() => {
      const stage = stageRef.current
      if (!stage || !projection || !selectedId || !metadata) return
      const condado = metadata.condados.find((c) => c.id === selectedId)
      if (!condado) return
      panToGeoCenter(stage, condado.lon, condado.lat, projection, currentScale, {
        mapW: projection.mapW, mapH: projection.mapH,
      })
      setCurrentScale(stage.scaleX())  // panToGeoCenter sets scale deterministically
      stage.batchDraw()
    }, [selectedId, projection, metadata, currentScale])

    const wheelHandler = useMemo(
      () => projection ? makeWheelHandler(minScale, minScale * MAX_SCALE_MULTIPLIER, { mapW: projection.mapW, mapH: projection.mapH }) : undefined,
      [projection, minScale],
    )

    const dragBound = useMemo(
      () => projection ? makeDragBoundFunc({ mapW: projection.mapW, mapH: projection.mapH }, () => stageRef.current?.scaleX() ?? 1) : undefined,
      [projection],
    )

    const handleWheel = useCallback((e: any) => {
      if (wheelHandler) wheelHandler(e)
      const s = stageRef.current?.scaleX()
      if (typeof s === 'number') setCurrentScale(s)
    }, [wheelHandler])

    // RESEARCH §Pitfall 6: canonical empty-Stage click deselect. Use e.target.getStage()
    // — race-free under React StrictMode double-invocation. DO NOT compare against stageRef.current.
    const handleStageClick = useCallback((e: any) => {
      if (e.target === e.target.getStage()) select(null)
    }, [select])
    ```

    Update `<Stage>`:
    ```tsx
    <Stage
      ref={stageRef}
      width={viewport.w}
      height={viewport.h}
      draggable
      dragBoundFunc={dragBound}
      onWheel={handleWheel}
      onClick={handleStageClick}
      onTap={handleStageClick}
    >
      <BackgroundLayer ... />
      <TerritoryLayer ... />
      <BaronyLayer ... />
      <DecorationsLayer
        condados={metadata.condados}
        condadoColors={condadoColorsQ.data}
        layerVisibility={{ capitals: layerVisibility.capitals, labels: layerVisibility.labels }}
        currentScale={currentScale}
        minScale={minScale}
      />
      <InteractionLayer territories={territoriesQ.data} />
    </Stage>
    <LayerTogglePanel />
    <FitToViewButton onFit={fitToView} />
    ```

    Create `frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx`. Core of the test: stub the Konva Stage, dispatch `useUIStore.getState().select('C_LUGO')` where `C_LUGO`'s centroid projects to (cx, cy) near the edge, and assert:

    ```tsx
    const setPosMock = vi.fn()
    const setScaleMock = vi.fn()
    const stubStage: any = {
      width: () => 1000, height: () => 800,
      scale: setScaleMock,
      scaleX: () => 1,
      position: setPosMock,
      x: () => 0, y: () => 0,
      batchDraw: vi.fn(),
      getPointerPosition: () => null,
      getStage() { return this },
    }
    // Inject stubStage via the stageRef after initial render.
    // After select('C_LUGO'):
    await act(async () => useUIStore.getState().select('C_LUGO'))
    expect(setPosMock).toHaveBeenCalled()
    const call = setPosMock.mock.calls.at(-1)![0]
    // Expected: cx = geoToCanvas(lugo.lon, lugo.lat, projection)[0]
    // Expected: x = 1000/2 - cx * 1
    expect(call.x).toBeCloseTo(500 - expectedCx, 3)
    expect(call.y).toBeCloseTo(400 - expectedCy, 3)
    ```

    Also add a test that `handleStageClick` uses `e.target.getStage()`: dispatch a mock click event where `e.target` is the stage itself (via `e.target.getStage()` returning the same object) and assert `select(null)` is called.

    Modify `frontend/src/pages/ProjectDetail.tsx` — replace `inspector-sidebar-placeholder` Box with:

    ```tsx
    import { InspectorSidebar } from '../components/canvas/InspectorSidebar'
    import { useCanvasArtifacts } from '../hooks/useCanvasArtifacts'
    import { buildProjectionConfig } from '../lib/projection'

    function InspectorSidebarWrapper({ projectId, project }: { projectId: string; project: Project }) {
      const artifacts0 = useCanvasArtifacts(projectId, null)
      const metaQ = artifacts0[4]  // metadata at index 4 (5-tuple)
      const bbox = (project.bbox_lon_min != null && project.bbox_lon_max != null && project.bbox_lat_min != null && project.bbox_lat_max != null)
        ? { lonMin: project.bbox_lon_min, lonMax: project.bbox_lon_max, latMin: project.bbox_lat_min, latMax: project.bbox_lat_max }
        : null
      const projection = useMemo(() => {
        if (!metaQ.data || !bbox) return null
        const [mapW, mapH] = metaQ.data.map_size
        return buildProjectionConfig(bbox, mapW, mapH)
      }, [metaQ.data, bbox])
      const artifacts = useCanvasArtifacts(projectId, projection)
      const tQ = artifacts[0]
      if (metaQ.isPending || tQ.isPending) return <Text size="2" color="gray">Loading…</Text>
      if (!metaQ.data || !tQ.data) return <Text size="2" color="gray">No data.</Text>
      return <InspectorSidebar metadata={metaQ.data} territories={tQ.data} project={{
        name: project.name, country_qid: project.country_qid,
        period_start: project.period_start, period_end: project.period_end,
      }} />
    }
    ```

    Run: `cd frontend && npm run test -- --run && npm run build`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- --run && npm run build</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "panToGeoCenter" frontend/src/components/canvas/CanvasViewer.tsx` returns a match inside a useEffect
    - `grep -n "useEffect.*selectedId\\|\\[selectedId" frontend/src/components/canvas/CanvasViewer.tsx` returns a match (effect subscribed to selection)
    - `grep -n "stage.position" frontend/src/components/canvas/CanvasViewer.tsx` returns matches inside a selection-change effect AND `panToGeoCenter` is called
    - `grep -n "e.target === e.target.getStage()" frontend/src/components/canvas/CanvasViewer.tsx` returns a match (Pitfall 6 canonical pattern)
    - `grep -n "stageRef.current" frontend/src/components/canvas/CanvasViewer.tsx | grep -c "handleStageClick\\|e.target === stageRef"` returns 0 (the old stageRef comparison pattern must NOT be used in the click handler)
    - `grep -n "draggable\\|onWheel\\|dragBoundFunc\\|useKeyboardShortcuts" frontend/src/components/canvas/CanvasViewer.tsx` returns all 4
    - `grep -n "<InspectorSidebar" frontend/src/pages/ProjectDetail.tsx` returns a match; `grep -n "inspector-sidebar-placeholder" frontend/src/pages/ProjectDetail.tsx` returns 0 matches
    - `cd frontend && npm run test -- CanvasViewer.panOnSelect.test.tsx --run` exits 0 with pan-on-select assertions green
    - `cd frontend && npm run test -- --run && npm run build` exits 0
  </acceptance_criteria>
  <done>CanvasViewer wires pan/zoom/drag + auto-fit + Esc/Ctrl+0 + FitToViewButton + DecorationsLayer + InteractionLayer + pan-on-select effect + Pitfall-6-canonical empty-Stage deselect. ProjectDetail swaps the placeholder for a real `<InspectorSidebar>`. Neighbor chip click → `select()` → pan-on-select effect pans the canvas. All D-02/D-03/D-04/D-06.3 decisions are honored in full.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

Plan 2.3 is frontend-only.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-02-03-01 | Tampering (XSS in name/capital_name) | InspectorSidebar renders `c.name`, `c.capital_name`, duchy/kingdom names in Radix `<Heading>`/`<Text>`/`<Badge>` | mitigate | React auto-escapes. `grep -rn "dangerouslySetInnerHTML" frontend/src/components/canvas/` MUST return 0. |
| T-02-03-02 | Tampering (Konva Text) | DecorationsLayer renders `c.name` as Konva Text | accept | Canvas-text, not HTML. |
| T-02-03-03 | DoS (wheel flood) | makeWheelHandler on every wheel tick | mitigate | O(1); short-circuits at clamp boundaries. |
| T-02-03-04 | Info disclosure (Esc inside input) | useKeyboardShortcuts window listener | mitigate | Explicit INPUT/TEXTAREA/contentEditable guard; Task 1 Test 4. |
| T-02-03-05 | Config correctness (Pitfall 2) | Radix-heavy InspectorSidebar | mitigate | Plan 2.1 Task 2 visual-regression smoke remains green. |
| T-02-03-06 | DoS (selection re-render) | Zustand state changes | mitigate | Narrow selectors + memo'd TerritoryPolygon. |
| T-02-03-07 | Logic (pan-on-select overrides user pan) | Selection effect re-centers canvas | accept | Desired behavior per UI-SPEC §Neighbor Navigation. User can drag afterwards; pan-clamp still active. |
</threat_model>

<verification>
Full-phase checks:

1. `cd frontend && npm run test -- --run` — every test file green (projection, uiStore, CanvasViewer, CanvasViewer.panOnSelect, TerritoryLayer, BaronyLayer, LayerTogglePanel, useZoomPan, useKeyboardShortcuts, FitToViewButton, DecorationsLayer, selection, InspectorSidebar)
2. `cd frontend && npm run test:e2e -- smoke-tailwind-radix.spec.ts` — Pitfall 2 visual regression green
3. `cd frontend && npm run build` — TS compiles
4. Manual Iberia 868 AD fixture:
   - Auto-fit on open (~5% padding)
   - Drag-pan clamps at edges
   - Wheel-zoom anchors on cursor
   - Zoom clamp [fit, 4×fit]
   - Click condado → gold outline + inspector 4 groups; capital row shows either the real capital name or "No capital assigned"
   - Click neighbor chip → selection moves AND canvas pans to center the new territory (visible movement when the neighbor is offscreen)
   - Esc clears selection → inspector shows "Project overview"
   - Toggle Labels: below 2× minScale no labels; above threshold they appear
   - Ctrl+0 OR Fit-to-view button resets view
   - Click empty Stage background → selection clears (uses e.target.getStage())
5. Pixel-parity spot check (VALIDATION.md): 5 condado fills match `lookup_condado_colors.json` exactly (D-01).
</verification>

<success_criteria>
Phase 2 complete when plan 2.3 lands:
- [ ] CANVAS-01 — condado polygons with correct colors (from plan 2.2)
- [ ] CANVAS-02 — pan + wheel-zoom with cursor-anchor + clamps [fit, 4×fit]
- [ ] CANVAS-03 — click-to-select → gold outline + full 4-group Inspector; neighbor chips navigate AND pan canvas (Pitfall 5); Esc clears; empty-Stage click clears using `e.target.getStage()` (Pitfall 6)
- [ ] CANVAS-04 — 5 layer toggles (from plan 2.2)
- [ ] CANVAS-05 — labels gated by `scale >= 2.0 * minScale`, real post-mount text width for centering
- [ ] CANVAS-06 — Fit-to-view button + Ctrl+0 reset to minScale
- [ ] D-04 — capital dual-ring rendering (outer dark ring + inner colored disk with white stroke; radius=6; NO shadowBlur)
- [ ] D-06.3 — Capital group shows real capital name when present, literal "No capital assigned" when absent; Centroid is a separate row
- [ ] All acceptance_criteria pass
- [ ] Pitfall 2 smoke still green
</success_criteria>

<output>
After completion, create `.planning/phases/02-read-only-canvas-viewer/02-03-SUMMARY.md` summarizing:
- Final Konva Stage composition: Background + Territories + Baronies + Decorations + Interaction (5 layers)
- Interaction hooks API (`makeWheelHandler`, `makeDragBoundFunc`, `panToGeoCenter`, `useKeyboardShortcuts`) — reusable for Phase 4 editing primitives
- InspectorSidebar consumer contract
- D-04 dual-ring capital implementation (two Circle nodes per capital; NO shadowBlur)
- D-06.3 capital name fallback policy + "No capital assigned" sentinel
- Pitfall 5 (pan-to-selected) implemented via selection-change useEffect + panToGeoCenter
- Pitfall 6 (empty-Stage deselect) implemented via `e.target === e.target.getStage()` canonical pattern
- Known open items for Phase 4+: barony-level selection, dynamic label anti-collision if UAT flags clutter
- Confirmed adherence to read-only contract (D-03): NO geometry mutation during selection
</output>
</content>
</invoke>