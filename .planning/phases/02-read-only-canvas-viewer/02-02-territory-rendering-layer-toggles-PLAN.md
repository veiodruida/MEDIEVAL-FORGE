---
phase: 02-read-only-canvas-viewer
plan: 02
type: execute
wave: 2
depends_on: [02-01]
files_modified:
  - frontend/src/components/canvas/TerritoryPolygon.tsx
  - frontend/src/components/canvas/TerritoryLayer.tsx
  - frontend/src/components/canvas/BaronyLayer.tsx
  - frontend/src/components/canvas/LayerTogglePanel.tsx
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx
  - frontend/src/components/canvas/__tests__/BaronyLayer.test.tsx
  - frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
nyquist_compliant: true
requirements: [CANVAS-01, CANVAS-04]
requirements_addressed: [CANVAS-01, CANVAS-04]

must_haves:
  truths:
    - "User sees all condado polygons on the Konva canvas with colors from lookup_condado_colors.json"
    - "Territory borders (default stroke) render as rgba(0,0,0,0.35), 1px, closed polygons"
    - "User sees all barony polygons rendered at 85% opacity when the Borders/Baronies toggle is ON (D-02 — real geometry, not empty)"
    - "Floating Radix Card in top-left corner of canvas shows 5 layer toggle checkboxes (Terrain, Territories, Borders, Capitals, Labels)"
    - "Checkbox state persists in useUIStore and hiding a layer immediately removes its shapes from the Stage"
    - "Default layer state on open matches D-09: terrain/territories/borders/capitals ON, labels OFF"
    - "TerritoryPolygon is React.memo'd so selection changes in plan 2.3 only re-render the affected polygon"
  artifacts:
    - path: "frontend/src/components/canvas/TerritoryPolygon.tsx"
      provides: "memoized <Line closed points fill stroke onClick> component"
      exports: ["TerritoryPolygon"]
    - path: "frontend/src/components/canvas/TerritoryLayer.tsx"
      provides: "Konva Layer rendering all condado polygons"
      exports: ["TerritoryLayer"]
    - path: "frontend/src/components/canvas/BaronyLayer.tsx"
      provides: "Konva Layer rendering barony polygons at 85% opacity from baronies.geojson (D-02)"
      exports: ["BaronyLayer"]
    - path: "frontend/src/components/canvas/LayerTogglePanel.tsx"
      provides: "Floating Radix Card with 5 Checkbox rows, absolute-positioned top-left"
      exports: ["LayerTogglePanel"]
  key_links:
    - from: "frontend/src/components/canvas/TerritoryLayer.tsx"
      to: "frontend/src/hooks/useCanvasArtifacts.ts"
      via: "useCanvasArtifacts returns TerritoryRender[] with memoized points"
      pattern: "useCanvasArtifacts"
    - from: "frontend/src/components/canvas/BaronyLayer.tsx"
      to: "frontend/src/hooks/useCanvasArtifacts.ts"
      via: "BaronyRender[] from baronies.geojson (plan 2.1 Task 1)"
      pattern: "BaronyRender"
    - from: "frontend/src/components/canvas/TerritoryPolygon.tsx"
      to: "lookup_condado_colors.json"
      via: "fill prop comes directly from the JSON via condadoColors[id]"
      pattern: "colors\\[\\w"
    - from: "frontend/src/components/canvas/LayerTogglePanel.tsx"
      to: "frontend/src/stores/uiStore.ts"
      via: "reads layerVisibility + dispatches toggleLayer"
      pattern: "toggleLayer"
    - from: "frontend/src/components/canvas/CanvasViewer.tsx"
      to: "TerritoryLayer + BaronyLayer + LayerTogglePanel"
      via: "mounts all three inside the existing Stage scaffold from plan 2.1"
      pattern: "<TerritoryLayer|<LayerTogglePanel"
---

<objective>
Render condado polygons with colors from `lookup_condado_colors.json` (D-01, pixel-parity with terrain.png), render the Barony overlay layer at 85% opacity from real geometry in `baronies.geojson` (D-02 — plan 2.1 Task 1 emits this file so the layer renders actual polygons, NOT an empty placeholder), and mount the floating Radix Card layer-toggle panel (D-08). Checkbox state is held in `useUIStore` from plan 2.1; toggling a layer immediately hides/shows the corresponding Konva nodes.

Purpose: CANVAS-01 (condado polygons) + CANVAS-04 (layer toggles) are the read-only-viewer requirements unlocking selection, inspection, and viewport interactions in plan 2.3. D-02 is delivered in full — baronies render with real polygons, not a toggle-over-empty-layer fallback.

Output: User opens a generated project, sees all condado polygons in their Unity-ready palette, sees baronies overlaid at 85% opacity when the Borders toggle is ON, and can toggle any of the 5 layers on/off.
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
@CLAUDE.md

<interfaces>
<!-- Contracts from plan 2.1 — use verbatim -->

From `frontend/src/stores/uiStore.ts` (plan 2.1):
```ts
export type LayerName = 'terrain' | 'territories' | 'borders' | 'capitals' | 'labels'
useUIStore: Store<{ selectedTerritoryId, layerVisibility, select, toggleLayer }>
```

From `frontend/src/hooks/useCanvasArtifacts.ts` (plan 2.1 — 5-tuple):
```ts
// Returns [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metadataQ]
// - territoriesQ.data: TerritoryRender[]    { id, name, points, neighbors: string[] }
// - baroniesQ.data:    BaronyRender[]       { id, name, condado_id, fill, points }
// - condadoColorsQ.data: Record<string,string>
// - baronyColorsQ.data:  Record<string,string>
// - metadataQ.data: TerritoryMetadata
```

BaronyRender already carries `fill` (resolved server-side from `lookup_barony_colors.json`) and a projected `points` array. BaronyLayer renders without any further lookup.

From `frontend/src/components/canvas/CanvasViewer.tsx` (plan 2.1):
```tsx
<ProjectionProvider value={projection}>
  <div ref={containerRef} ...>
    <Stage ref={stageRef} width={viewport.w} height={viewport.h}>
      <BackgroundLayer src={...} mapW={...} mapH={...} visible={layerVisibility.terrain} />
      {/* TerritoryLayer + BaronyLayer + LayerTogglePanel mount HERE in plan 2.2 */}
      {/* DecorationsLayer + InteractionLayer added in plan 2.3 */}
    </Stage>
  </div>
</ProjectionProvider>
```

Visual contract (UI-SPEC §Color + §Konva Stage Architecture):
- Condado border default: `stroke="rgba(0, 0, 0, 0.35)"`, `strokeWidth={1}`
- Condado fill: `condadoColors[id]` (hex)
- Barony overlay: `opacity={0.85}` on the Layer, per-polygon `fill={b.fill}` from BaronyRender, `listening={false}`
- LayerTogglePanel: Radix `<Card variant="surface">` at `position: absolute; top: 12px; left: 12px; z-index: 10`
- 5 checkboxes in fixed order: Terrain, Territories, Borders, Capitals, Labels
- Panel title: `<Text size="2" weight="bold">Layers</Text>`

NOTE: The "Borders" checkbox now controls barony visibility per D-02 (baronies render as internal borders inside condados). Plan 2.3's DecorationsLayer remains responsible for capital dots and labels (independent toggles).
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: TerritoryPolygon + TerritoryLayer + BaronyLayer (condado + barony rendering from GeoJSON)</name>
  <files>
    frontend/src/components/canvas/TerritoryPolygon.tsx (NEW),
    frontend/src/components/canvas/TerritoryLayer.tsx (NEW),
    frontend/src/components/canvas/BaronyLayer.tsx (NEW — renders BaronyRender[] from plan 2.1 Task 1),
    frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx (NEW),
    frontend/src/components/canvas/__tests__/BaronyLayer.test.tsx (NEW)
  </files>
  <read_first>
    - frontend/src/hooks/useCanvasArtifacts.ts (TerritoryRender + BaronyRender shapes — plan 2.1)
    - frontend/src/stores/uiStore.ts (selection subscription pattern)
    - frontend/src/components/canvas/CanvasViewer.tsx (plan 2.1 mount point; must NOT be edited in this task — Task 3 wires it)
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pattern 3 (React.memo + Zustand selector), §Pitfall 7 (points array identity)
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Canvas Color System + §Konva Stage Architecture
    - .planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md D-01, D-02, D-03
  </read_first>
  <behavior>
    - Test 1 (TerritoryLayer): Given 3 TerritoryRender + colors map, renders exactly 3 `<Line closed stroke="rgba(0,0,0,0.35)" strokeWidth={1}>` with correct fills.
    - Test 2 (TerritoryLayer fallback fill): Missing color id → `#666666`.
    - Test 3 (TerritoryPolygon memo): Unrelated polygon's fill change does NOT re-render siblings.
    - Test 4 (BaronyLayer renders real polygons): Given 2 BaronyRender items, renders exactly 2 `<Line closed fill={b.fill} listening={false}>` inside a `<Layer listening={false} opacity={0.85}>`.
    - Test 5 (BaronyLayer visibility): `visible=false` → Layer has `visible=false` (children still mounted; Konva hides the layer).
    - Test 6 (TerritoryLayer selection): TerritoryLayer subscribes via `useUIStore((s) => s.selectedTerritoryId)`; only the matching polygon gets `isSelected === true`.
  </behavior>
  <action>
    Create `frontend/src/components/canvas/TerritoryPolygon.tsx` (unchanged from prior revision — memo, areEqual, `rgba(0, 0, 0, 0.35)` stroke, closed Line, click handler).

    Create `frontend/src/components/canvas/TerritoryLayer.tsx` (unchanged — narrow Zustand selector, FALLBACK_FILL='#666666', maps to TerritoryPolygon).

    Create `frontend/src/components/canvas/BaronyLayer.tsx` — NOW RENDERS REAL POLYGONS from `BaronyRender[]`:

    ```tsx
    import { Layer, Line } from 'react-konva'
    import type { BaronyRender } from '../../hooks/useCanvasArtifacts'

    interface Props {
      baronies: BaronyRender[]
      visible: boolean
    }

    /**
     * D-02: baronies render at 85% opacity above condados when the Borders toggle is ON.
     * Plan 2.1 Task 1 emits baronies.geojson (via read-back from lookup_barony.png +
     * lookup_barony_colors.json + territory_metadata.json). Each BaronyRender already
     * carries its `fill` (hex) and projected `points`, so this layer is a pure renderer.
     *
     * listening=false on the Layer — selection uses condados only (D-03 scope).
     */
    export function BaronyLayer({ baronies, visible }: Props) {
      return (
        <Layer listening={false} visible={visible} opacity={0.85}>
          {baronies.map((b) => (
            <Line
              key={b.id}
              points={b.points}
              closed
              fill={b.fill}
              stroke="rgba(0, 0, 0, 0.25)"
              strokeWidth={0.5}
              listening={false}
            />
          ))}
        </Layer>
      )
    }
    ```

    Create `frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx` (unchanged from prior revision — 3 tests).

    Create `frontend/src/components/canvas/__tests__/BaronyLayer.test.tsx`:

    ```tsx
    import { describe, it, expect, vi } from 'vitest'
    import { render, screen } from '@testing-library/react'
    import { BaronyLayer } from '../BaronyLayer'
    import type { BaronyRender } from '../../../hooks/useCanvasArtifacts'

    vi.mock('react-konva', () => ({
      Layer: ({ children, listening, visible, opacity }: any) => (
        <div data-testid="layer" data-listening={String(listening)} data-visible={String(visible)} data-opacity={String(opacity)}>
          {children}
        </div>
      ),
      Line: (p: any) => (
        <div data-testid="line" data-fill={p.fill} data-closed={String(p.closed)} data-listening={String(p.listening)} />
      ),
    }))

    const B: BaronyRender[] = [
      { id: 'B_A1', name: 'B_A1', condado_id: 'C_A', fill: '#ff0000', points: [0,0,10,0,10,10,0,10] },
      { id: 'B_B1', name: 'B_B1', condado_id: 'C_B', fill: '#00ff00', points: [20,0,30,0,30,10,20,10] },
    ]

    describe('BaronyLayer', () => {
      it('renders one Line per barony with fill from the BaronyRender.fill field', () => {
        render(<BaronyLayer baronies={B} visible />)
        const lines = screen.getAllByTestId('line')
        expect(lines.length).toBe(2)
        expect(lines[0].getAttribute('data-fill')).toBe('#ff0000')
        expect(lines[1].getAttribute('data-fill')).toBe('#00ff00')
        lines.forEach((l) => {
          expect(l.getAttribute('data-closed')).toBe('true')
          expect(l.getAttribute('data-listening')).toBe('false')
        })
      })
      it('Layer has listening=false and opacity=0.85', () => {
        render(<BaronyLayer baronies={B} visible />)
        const layer = screen.getByTestId('layer')
        expect(layer.getAttribute('data-listening')).toBe('false')
        expect(layer.getAttribute('data-opacity')).toBe('0.85')
      })
      it('respects visible prop', () => {
        const { rerender } = render(<BaronyLayer baronies={B} visible />)
        expect(screen.getByTestId('layer').getAttribute('data-visible')).toBe('true')
        rerender(<BaronyLayer baronies={B} visible={false} />)
        expect(screen.getByTestId('layer').getAttribute('data-visible')).toBe('false')
      })
      it('renders an empty Layer when baronies list is empty', () => {
        render(<BaronyLayer baronies={[]} visible />)
        expect(screen.queryAllByTestId('line').length).toBe(0)
      })
    })
    ```

    Run: `cd frontend && npm run test -- TerritoryLayer.test.tsx BaronyLayer.test.tsx --run`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- TerritoryLayer.test.tsx BaronyLayer.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `frontend/src/components/canvas/TerritoryPolygon.tsx` exports `TerritoryPolygon` as a `memo(...)` component
    - `grep -n "rgba(0, 0, 0, 0.35)" frontend/src/components/canvas/TerritoryPolygon.tsx` returns a match
    - `frontend/src/components/canvas/BaronyLayer.tsx` imports `BaronyRender` from `useCanvasArtifacts` and maps over `baronies`
    - `grep -n "opacity={0.85}" frontend/src/components/canvas/BaronyLayer.tsx` returns a match
    - `grep -n "listening={false}" frontend/src/components/canvas/BaronyLayer.tsx` returns at least 2 matches (Layer + Line)
    - `grep -n "b.fill" frontend/src/components/canvas/BaronyLayer.tsx` returns a match (fill driven by BaronyRender)
    - `cd frontend && npm run test -- TerritoryLayer.test.tsx BaronyLayer.test.tsx --run` exits 0
  </acceptance_criteria>
  <done>Condados render with correct fills + memo-stable polygons. Baronies render as REAL polygons from `baronies.geojson` (plan 2.1 Task 1) at 85% opacity with per-feature fills — D-02 delivered in full, not as an empty toggle placeholder.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: LayerTogglePanel (floating Radix Card with 5 checkboxes)</name>
  <files>
    frontend/src/components/canvas/LayerTogglePanel.tsx (NEW),
    frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx (NEW)
  </files>
  <read_first>
    - frontend/src/stores/uiStore.ts
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Component Inventory + §Layout Architecture + §Copywriting Contract
    - .planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md D-08, D-09
    - frontend/src/components/canvas/__smoke__/CanvasRadixOverlaySmoke.tsx (plan 2.1) — pattern for Radix Card + Checkbox
  </read_first>
  <behavior>
    - Test 1: Renders 5 rows in order: Terrain, Territories, Borders, Capitals, Labels.
    - Test 2: Default state matches D-09.
    - Test 3: Clicking Labels flips store.
    - Test 4: Card variant="surface" at `position: absolute; top: 12px; left: 12px; z-index: 10`.
    - Test 5: Header reads "Layers".
  </behavior>
  <action>
    Create `LayerTogglePanel.tsx` and its test file (unchanged from prior revision).

    Run: `cd frontend && npm run test -- LayerTogglePanel.test.tsx --run`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- LayerTogglePanel.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - Imports Card, Flex, Text, Checkbox from `@radix-ui/themes`
    - Contains all 5 layer keys + `'Layers'` literal + `variant="surface"` + `position: 'absolute'`
    - Tests pass (5 passing)
  </acceptance_criteria>
  <done>Layer toggle panel is a pure component driven by `useUIStore`. Checkbox state is the single source of truth.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire TerritoryLayer + BaronyLayer + LayerTogglePanel into CanvasViewer; expand ProjectDetail to UI-SPEC two-region layout</name>
  <files>
    frontend/src/components/canvas/CanvasViewer.tsx (MODIFY),
    frontend/src/pages/ProjectDetail.tsx (MODIFY)
  </files>
  <read_first>
    - frontend/src/components/canvas/CanvasViewer.tsx (plan 2.1 — 5-tuple destructure from useCanvasArtifacts)
    - frontend/src/components/canvas/TerritoryLayer.tsx, BaronyLayer.tsx, LayerTogglePanel.tsx (Task 1 + 2)
    - frontend/src/hooks/useCanvasArtifacts.ts (5-tuple: territories, baronies, condadoColors, baronyColors, metadata)
    - frontend/src/pages/ProjectDetail.tsx (current full page)
    - .planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md §Layout Architecture
    - .planning/phases/02-read-only-canvas-viewer/02-RESEARCH.md §Pattern 2, §Pitfall 1
  </read_first>
  <behavior>
    - Test 1: Stage contains 3 layers (Background + Territories + Baronies). DecorationsLayer/InteractionLayer land in 2.3.
    - Test 2: `<LayerTogglePanel>` is a sibling of `<Stage>` inside the canvas container.
    - Test 3: Toggling `layerVisibility.borders` flips BaronyLayer's `visible` prop.
    - Test 4: ProjectDetail renders two-region flex layout for `generated`/`exported` status, replacing the fixed 600px Box from plan 2.1.
  </behavior>
  <action>
    Modify `frontend/src/components/canvas/CanvasViewer.tsx`. Destructure the 5-tuple from `useCanvasArtifacts` (now including baronies):

    ```tsx
    import { TerritoryLayer } from './TerritoryLayer'
    import { BaronyLayer } from './BaronyLayer'
    import { LayerTogglePanel } from './LayerTogglePanel'
    // ...
    const artifacts = useCanvasArtifacts(projectId, projection)
    const [territoriesQ, baroniesQ, condadoColorsQ, _baronyColorsQ, metaQ] = artifacts
    void _baronyColorsQ  // consumed only if a fallback path needs raw colors; BaronyRender carries fill inline
    ```

    In the gating logic, require `baroniesQ.data` as well:
    ```tsx
    if (isLoading || !projection || !metadata || !territoriesQ.data || !condadoColorsQ.data || !baroniesQ.data) {
      return <Box p="6"><Text size="2">Loading map…</Text></Box>
    }
    ```

    Inside `<Stage>`:
    ```tsx
    <BackgroundLayer src={terrainSrc} mapW={projection.mapW} mapH={projection.mapH} visible={layerVisibility.terrain} />
    <TerritoryLayer
      territories={territoriesQ.data}
      condadoColors={condadoColorsQ.data}
      visible={layerVisibility.territories}
    />
    <BaronyLayer baronies={baroniesQ.data} visible={layerVisibility.borders} />
    {/* DecorationsLayer (capitals + labels) added in plan 2.3 */}
    {/* InteractionLayer (gold selection outline) added in plan 2.3 */}
    ```

    After `</Stage>` but inside the container div:
    ```tsx
    <LayerTogglePanel />
    ```

    Modify `ProjectDetail.tsx` — replace the fixed 600px Box from plan 2.1 with the two-region flex layout: canvas area (flex:1) + inspector-sidebar-placeholder (340px fixed). Inspector content lands in plan 2.3.

    Extend `CanvasViewer.test.tsx` — add a `baronies.geojson` mock response returning a FeatureCollection with one barony so the 3-layer assertion passes.

    Run: `cd frontend && npm run test -- CanvasViewer.test.tsx TerritoryLayer.test.tsx BaronyLayer.test.tsx LayerTogglePanel.test.tsx --run && npm run build`.
  </action>
  <verify>
    <automated>cd frontend && npm run test -- CanvasViewer.test.tsx TerritoryLayer.test.tsx BaronyLayer.test.tsx LayerTogglePanel.test.tsx --run && npm run build</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "TerritoryLayer\\|BaronyLayer\\|LayerTogglePanel" frontend/src/components/canvas/CanvasViewer.tsx` returns at least 3
    - `grep -n "baroniesQ.data" frontend/src/components/canvas/CanvasViewer.tsx` returns at least 2 matches (gating + props)
    - `grep -n "<LayerTogglePanel" frontend/src/components/canvas/CanvasViewer.tsx` shows the panel OUTSIDE any `<Stage>` block
    - `grep -n "canvas-region\\|inspector-sidebar-placeholder" frontend/src/pages/ProjectDetail.tsx` returns matches
    - `grep -n "height: 600" frontend/src/pages/ProjectDetail.tsx` returns 0 matches
    - All frontend tests pass; `npm run build` exits 0
  </acceptance_criteria>
  <done>`/projects/:id` shows Background + real Territories + real Baronies (from baronies.geojson) + floating LayerTogglePanel in the two-region flex layout. Checkbox toggles hide/show layers immediately. D-02 is delivered with real geometry — no "Phase 4+" deferral.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

Plan 2.2 is frontend-only. No new backend surface.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-02-02-01 | Tampering (XSS via name) | TerritoryRender.name / BaronyRender.name | accept | Not rendered as HTML here; React escapes all JSX strings. |
| T-02-02-02 | Tampering (config — V14) | index.css Radix-before-Tailwind | mitigate | Plan 2.1 Task 2 visual regression smoke remains green in CI. |
| T-02-02-03 | Tampering (fill color injection) | BaronyRender.fill used as Konva Line fill | accept | `fill` is a hex string from generator; Konva uses it as canvas color only, not as a URL or script. |
| T-02-02-04 | DoS (re-render storm) | TerritoryLayer selection change | mitigate | Memoized TerritoryPolygon + narrow Zustand selectors. |
</threat_model>

<verification>
1. `cd frontend && npm run test -- --run` — all green
2. `cd frontend && npm run test:e2e -- smoke-tailwind-radix.spec.ts` — visual regression still green (LayerTogglePanel is Radix-heavy)
3. `cd frontend && npm run build` — TS compiles
4. Manual: open a generated Iberia project → all ~91 condados painted, baronies visible at 85% opacity with subtle internal borders when toggle ON, 5-row Layer panel top-left
</verification>

<success_criteria>
Plan 2.2 complete when:
- [ ] All condado polygons render with fills from `lookup_condado_colors.json` (CANVAS-01)
- [ ] All baronies render from `baronies.geojson` at 85% opacity (D-02 — delivered in full)
- [ ] Default border stroke is `rgba(0, 0, 0, 0.35)` 1px
- [ ] LayerTogglePanel shows 5 checkboxes in fixed order (CANVAS-04)
- [ ] Checkbox state drives layer visibility in Konva
- [ ] TerritoryPolygon is React.memo'd; selector re-renders are O(1)
- [ ] ProjectDetail two-region flex layout with sidebar placeholder
- [ ] All task acceptance_criteria pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-read-only-canvas-viewer/02-02-SUMMARY.md` summarizing:
- TerritoryPolygon memo + areEqual contract
- BaronyLayer rendering pipeline: plan 2.1 backend read-back → baronies.geojson → BaronyRender[] → per-feature `fill` inline → Konva Line nodes
- LayerTogglePanel state model
- Two-region layout applied in ProjectDetail
- D-02 status: DELIVERED in full with real geometry (no deferral)
</output>
</content>
</invoke>