---
phase: 260420-hkr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/hooks/useCanvasArtifacts.ts
  - frontend/src/components/ErrorBoundary.tsx
  - frontend/src/App.tsx
  - frontend/src/stores/uiStore.ts
  - frontend/src/stores/uiStore.test.ts
  - frontend/src/components/canvas/LayerTogglePanel.tsx
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/LegendCard.tsx
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
requirements: [BUG-FIX-hkr]
must_haves:
  truths:
    - "Clicking a territory does not blank the page"
    - "Inspector sidebar shows neighbor chips when a condado is selected"
    - "If rendering throws, user sees a fallback UI with recovery actions (not a white screen)"
    - "LayerTogglePanel shows Condados/Baronias/Fronteiras/Capitais/Nomes in Portuguese"
    - "Toggling the Baronias layer hides/shows the BaronyLayer"
    - "A legend card is visible on the canvas explaining the amber/blue/grass badge colors"
  artifacts:
    - path: "frontend/src/hooks/useCanvasArtifacts.ts"
      provides: "neighbors hoisting from territories.geojson into metadata.condados"
    - path: "frontend/src/components/ErrorBoundary.tsx"
      provides: "React class ErrorBoundary with fallback UI + recovery actions"
    - path: "frontend/src/stores/uiStore.ts"
      provides: "LayerName = 'condados' | 'baronies' | 'borders' | 'capitals' | 'labels'"
    - path: "frontend/src/components/canvas/LegendCard.tsx"
      provides: "Static floating legend card with Reino/Duquia/Condado swatches"
  key_links:
    - from: "useCanvasArtifacts.ts"
      to: "InspectorSidebar.tsx"
      via: "condado.neighbors populated on metadata (hoisted from territories.geojson)"
      pattern: "neighbors: f\\.properties\\.neighbors"
    - from: "App.tsx"
      to: "ErrorBoundary.tsx"
      via: "wraps <ProjectDetail /> route element"
      pattern: "<ErrorBoundary"
    - from: "LayerTogglePanel.tsx"
      to: "CanvasViewer.tsx"
      via: "layerVisibility.condados / layerVisibility.baronies"
      pattern: "layerVisibility\\.(condados|baronies)"
---

<objective>
Fix the blank-page crash triggered by clicking a territory, harden the canvas against future runtime errors with an ErrorBoundary, rename the layer toggles to the actual domain hierarchy (Condados/Baronias), and add a static legend card explaining the badge colors.

Purpose: Unblock the Phase 2 canvas viewer (InspectorSidebar currently throws on every selection), improve resilience, and align UI vocabulary with the documented hierarchy (terrain was never implemented; it belongs to Phase 05).
Output: Working territory inspector with neighbor chips, fallback UI on errors, renamed + expanded layer list, and a color legend card.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md
@frontend/src/hooks/useCanvasArtifacts.ts
@frontend/src/components/canvas/InspectorSidebar.tsx
@frontend/src/components/canvas/LayerTogglePanel.tsx
@frontend/src/components/canvas/CanvasViewer.tsx
@frontend/src/stores/uiStore.ts
@frontend/src/stores/uiStore.test.ts
@frontend/src/pages/ProjectDetail.tsx
@frontend/src/App.tsx

<interfaces>
From frontend/src/hooks/useCanvasArtifacts.ts:
```typescript
export interface TerritoryMetadataCondado {
  id: string
  name: string
  lon: number
  lat: number
  duchy: string
  kingdom: string
  pixel_center: [number, number]
  pixel_count: number
  baronies: string[]
  neighbors: string[]         // CURRENTLY required by type, but missing in metadata JSON
  capital_name?: string
}
export interface TerritoryMetadata {
  region: string
  map_size: [number, number]
  bounds: { lon_min: number; lon_max: number; lat_min: number; lat_max: number }
  kingdoms: Record<string, string>
  duchies: Record<string, { kingdom: string; name: string }>
  condados: TerritoryMetadataCondado[]
  baronies: Array<{ name: string; condado_idx: number; duchy: string; pixel_count: number }>
}
// useCanvasArtifacts returns a 5-tuple of useQueries results:
//   [0] TerritoryRender[] (has .neighbors from territories.geojson .properties.neighbors)
//   [4] TerritoryMetadata (lacks .neighbors on condados in source JSON)
```

From frontend/src/stores/uiStore.ts (current — to be replaced):
```typescript
export type LayerName = 'terrain' | 'territories' | 'borders' | 'capitals' | 'labels'
```

From frontend/src/components/canvas/CanvasViewer.tsx (consumers to update):
```typescript
visible={layerVisibility.terrain}       // line 342 — BackgroundLayer → becomes .condados
visible={layerVisibility.territories}   // line 347 — TerritoryLayer → becomes .condados
// BaronyLayer currently uses layerVisibility.borders — must switch to layerVisibility.baronies
// DecorationsLayer uses .capitals and .labels — unchanged
```

Radix badge colors used by InspectorSidebar (match in LegendCard):
```typescript
<Badge color="amber">  // Kingdom / Reino
<Badge color="blue">   // Duchy / Duquia
<Badge color="grass">  // Condado
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Hoist territories.geojson neighbors into metadata in useCanvasArtifacts</name>
  <files>frontend/src/hooks/useCanvasArtifacts.ts</files>
  <action>
Fix the root cause of the blank-page crash. `territory_metadata.json` on disk does NOT contain `neighbors` on condados; only `territories.geojson` features do. The type declaration lies about this, and InspectorSidebar crashes at `neighbors.length` when a territory is clicked.

Implementation:
1. Keep `useCanvasArtifacts` returning a 5-tuple (do not break the destructuring shape used by `CanvasViewer.tsx` line 134 and `ProjectDetail.tsx` lines 410/429/430). Hoist inside the existing function.
2. In the `select` for query [4] (`territory_metadata.json`), we cannot access query [0]'s data — so instead, add a POST-query merge step. Leave query [4]'s `select` as-is (returns raw TerritoryMetadata). Then wrap the returned `useQueries` result with a `useMemo` that produces a NEW 5-tuple where the `[4].data` has `neighbors` merged in from `[0].data`.
3. The cleanest approach: after the `useQueries` call, compute `const results = useQueries(...)`. Build `const mergedMeta = useMemo(() => {...}, [results[0].data, results[4].data])` that:
   - If `results[4].data` is undefined, return `results[4].data` unchanged.
   - If `results[0].data` is undefined, return `results[4].data` with `condados` mapped so each condado gets `neighbors: []` (fallback — sidebar will still render but show "No adjacent territories" instead of crashing).
   - Otherwise, build a `Map<string, string[]>` from `results[0].data` (keyed by `territory.id` → `territory.neighbors`), then return `{ ...results[4].data, condados: results[4].data.condados.map(c => ({ ...c, neighbors: neighborMap.get(c.id) ?? [] })) }`.
4. Return a new tuple: `[results[0], results[1], results[2], results[3], { ...results[4], data: mergedMeta }] as const`. Preserve `isPending`, `error`, etc., so consumers like `CanvasViewer` (which checks `metaQ.isPending`, `metaQ.error`) still work unchanged.
5. Update the `TerritoryMetadataCondado.neighbors` JSDoc comment to accurately reflect the hoist mechanism (stop claiming it comes from the JSON).

Critical: the 5-tuple's element types must remain compatible — return type for element [4] is `UseQueryResult<TerritoryMetadata, Error>` shape. Use `{ ...results[4], data: mergedMeta }` — do not spread into a new object that loses methods/getters. If TanStack's result object has non-enumerable getters (it doesn't in v5 — results are plain objects), this is safe; verify by running the existing tests.

Do NOT introduce `--legacy-peer-deps` changes, do NOT touch queryKeys or URLs, do NOT add a new query.
  </action>
  <verify>
    <automated>cd frontend && npx vitest run src/hooks --reporter=basic 2>&1 | tail -20</automated>
  </verify>
  <done>
    - `useCanvasArtifacts` merges neighbors from territories.geojson into metadata.condados before returning.
    - Existing tests (if any reference the hook) still pass; no crash when `metadata.condados[i].neighbors` is accessed.
    - Manual smoke: selecting a territory in the canvas no longer throws; neighbor chips appear.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add ErrorBoundary and wrap ProjectDetail route</name>
  <files>frontend/src/components/ErrorBoundary.tsx, frontend/src/App.tsx</files>
  <action>
Create `frontend/src/components/ErrorBoundary.tsx` as a React class component (React does not yet support functional error boundaries). Shape:

```typescript
import { Component, type ReactNode } from 'react'
import { Button, Card, Flex, Heading, Text } from '@radix-ui/themes'
import { Link } from 'react-router-dom'
import { useUIStore } from '../stores/uiStore'

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }
  static getDerivedStateFromError(error: Error): State { return { error } }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] Captured:', error, info)
  }
  private reset = () => {
    useUIStore.getState().select(null)
    this.setState({ error: null })
  }
  render() {
    if (!this.state.error) return this.props.children
    const msg = this.state.error.message.slice(0, 300)
    return (
      <Flex align="center" justify="center" style={{ minHeight: '100vh', padding: 24 }}>
        <Card style={{ maxWidth: 520 }}>
          <Flex direction="column" gap="3">
            <Heading size="4">Algo correu mal</Heading>
            <Text size="2" color="gray" style={{ whiteSpace: 'pre-wrap' }}>{msg}</Text>
            <Flex gap="2">
              <Button onClick={this.reset}>Limpar seleção</Button>
              <Link to="/projects"><Button variant="soft" onClick={this.reset}>Voltar à lista de projetos</Button></Link>
            </Flex>
          </Flex>
        </Card>
      </Flex>
    )
  }
}
```

Then in `frontend/src/App.tsx`, wrap the `<ProjectDetail />` route element (and optionally the whole `<Routes>` for safety — but minimum is ProjectDetail since that's where the crash happens):

```tsx
<Route path="/projects/:id" element={<ErrorBoundary><ProjectDetail /></ErrorBoundary>} />
```

Import `ErrorBoundary` from `./components/ErrorBoundary`. Do NOT wrap the dev-only `CanvasRadixOverlaySmoke` route. Do NOT persist error state; a fresh navigate away from the page naturally clears it, and the "Limpar seleção" button resets state.

The `Link` + onClick combo is intentional — clicking the link navigates AND resets boundary state so the user can immediately re-enter a project.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit 2>&1 | tail -20</automated>
  </verify>
  <done>
    - `ErrorBoundary.tsx` exists with `getDerivedStateFromError` + `componentDidCatch`.
    - App.tsx wraps ProjectDetail route with ErrorBoundary.
    - TypeScript compiles cleanly.
    - Manual smoke (later): forcing a throw inside ProjectDetail shows the fallback card with both buttons functional.
  </done>
</task>

<task type="auto">
  <name>Task 3: Rename LayerName (terrain→condados, add baronies) and update consumers + tests</name>
  <files>frontend/src/stores/uiStore.ts, frontend/src/stores/uiStore.test.ts, frontend/src/components/canvas/LayerTogglePanel.tsx, frontend/src/components/canvas/CanvasViewer.tsx</files>
  <action>
Pre-release rename — no backwards-compat shim. Every occurrence of `'terrain'`/`'territories'` in layer-visibility contexts must move to `'condados'`, and `'baronies'` is added as a new layer key.

1. `frontend/src/stores/uiStore.ts`:
   - Change `LayerName` to `'condados' | 'baronies' | 'borders' | 'capitals' | 'labels'`.
   - Update `DEFAULT_LAYER_VISIBILITY` to `{ condados: true, baronies: false, borders: true, capitals: true, labels: false }`.
   - Remove the `D-09` comment referencing terrain/territories since that spec is now updated in practice (keep a short comment noting the rename rationale: "terrain layer belongs to Phase 05; removed here. baronies added to expose barony subdivisions.").

2. `frontend/src/stores/uiStore.test.ts`:
   - Replace every `layerVisibility.terrain` with `layerVisibility.condados` and every `layerVisibility.territories` with `layerVisibility.condados` as well (both collapsed into a single `condados` key). If the test asserts two separate layers toggled independently, split the assertion so one uses `condados` and the other uses `baronies` (new default=false).
   - Update `toggleLayer('terrain')` → `toggleLayer('condados')` and `toggleLayer('territories')` → `toggleLayer('baronies')` (or `condados` — pick based on what the test is verifying). Read the existing test carefully to preserve intent; if a test asserts a toggled-off state, choose the key whose default matches.

3. `frontend/src/components/canvas/LayerTogglePanel.tsx`:
   - Replace `LAYERS` with:
     ```typescript
     const LAYERS: { key: LayerName; label: string }[] = [
       { key: 'condados',  label: 'Condados' },
       { key: 'baronies',  label: 'Baronias' },
       { key: 'borders',   label: 'Fronteiras' },
       { key: 'capitals',  label: 'Capitais' },
       { key: 'labels',    label: 'Nomes' },
     ]
     ```

4. `frontend/src/components/canvas/CanvasViewer.tsx`:
   - Line 342: `visible={layerVisibility.terrain}` → `visible={layerVisibility.condados}` (BackgroundLayer — terrain PNG becomes gated by the condados toggle; acceptable for Phase 2 since terrain is just the background of the condados view).
   - Line 347: `visible={layerVisibility.territories}` → `visible={layerVisibility.condados}` (TerritoryLayer renders the condado polygons).
   - Line 349: `<BaronyLayer baronies={baroniesQ.data} visible={layerVisibility.borders} />` → `visible={layerVisibility.baronies}`. This is a semantic fix: barony rendering should NOT be gated on the "borders" toggle.

5. Grep the frontend for any other references to `'terrain'` or `'territories'` as layer keys (not as PNG filenames — `territories.png` in ProjectDetail is a preview image path and must NOT be renamed). Use exact string literal matching within layer-visibility contexts. If a stray consumer exists in `__tests__` directories or other components (`BackgroundLayer.tsx`, `TerritoryLayer.tsx`, `BaronyLayer.tsx`, `DecorationsLayer.tsx`), update accordingly. Most of those components accept `visible` as a prop, so they are not directly affected — only the prop wiring in CanvasViewer.tsx needs updating.

Leave `condado_colors.json`, `territories.geojson`, `terrain.png` URLs untouched — these are on-disk artifact names and are decoupled from the UI layer-toggle vocabulary.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit 2>&1 | tail -20 && npx vitest run src/stores src/components/canvas --reporter=basic 2>&1 | tail -30</automated>
  </verify>
  <done>
    - `LayerName` is `'condados' | 'baronies' | 'borders' | 'capitals' | 'labels'`.
    - LayerTogglePanel shows 5 Portuguese labels in the specified order.
    - BaronyLayer visibility toggles independently of borders.
    - `npx tsc --noEmit` passes cleanly.
    - uiStore tests pass with renamed keys.
  </done>
</task>

<task type="auto">
  <name>Task 4: Create LegendCard and mount it in ProjectDetail</name>
  <files>frontend/src/components/canvas/LegendCard.tsx, frontend/src/pages/ProjectDetail.tsx</files>
  <action>
Create a small static floating card explaining the three-level hierarchy badge colors used by InspectorSidebar.

1. `frontend/src/components/canvas/LegendCard.tsx`:
   ```tsx
   import { Card, Flex, Text } from '@radix-ui/themes'

   const ITEMS: { color: 'amber' | 'blue' | 'grass'; label: string }[] = [
     { color: 'amber', label: 'Reino' },
     { color: 'blue',  label: 'Duquia' },
     { color: 'grass', label: 'Condado' },
   ]

   /**
    * Static legend card explaining the hierarchy badge colors used by
    * InspectorSidebar. Positioned bottom-left of the canvas so it does not
    * collide with LayerTogglePanel (top-left) or FitToViewButton (top-right).
    */
   export function LegendCard() {
     return (
       <Card
         variant="surface"
         style={{ position: 'absolute', bottom: 12, left: 12, zIndex: 10, width: 160 }}
       >
         <Flex direction="column" gap="2">
           <Text size="2" weight="bold">Legenda</Text>
           {ITEMS.map(({ color, label }) => (
             <Flex key={label} align="center" gap="2">
               <span
                 aria-hidden
                 style={{
                   display: 'inline-block',
                   width: 10,
                   height: 10,
                   borderRadius: '50%',
                   background: `var(--${color}-9)`,
                 }}
               />
               <Text size="2">{label}</Text>
             </Flex>
           ))}
         </Flex>
       </Card>
     )
   }
   ```

2. Mount in `frontend/src/pages/ProjectDetail.tsx`: add `<LegendCard />` as a sibling inside the `<Box className="canvas-region">` (the same region that contains `<CanvasViewer />`), so it absolute-positions relative to that already-`position: relative` container. Import it at the top.

   ```tsx
   <Box className="canvas-region" style={{ flex: 1, background: '#1a1a2e', overflow: 'hidden', position: 'relative' }}>
     <CanvasViewer projectId={project.id} cacheVersion={project.updated_at} />
     <LegendCard />
   </Box>
   ```

Place LegendCard AFTER `<CanvasViewer />` in DOM order so it stacks above the Konva canvas without needing an explicit z-index bump (its zIndex: 10 is sufficient).

Do not wire any dynamic data; this is a static key. Portuguese strings match the existing `InspectorSidebar` copy (which uses "Condado" — matching here).
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit 2>&1 | tail -20</automated>
  </verify>
  <done>
    - `LegendCard.tsx` exists, exports `LegendCard`.
    - ProjectDetail imports and mounts LegendCard inside `canvas-region` Box.
    - Swatches use `var(--amber-9)`, `var(--blue-9)`, `var(--grass-9)` matching the Radix badge palette.
    - TypeScript compiles cleanly.
    - Manual smoke (later): legend card visible at bottom-left of the canvas, not overlapping LayerTogglePanel.
  </done>
</task>

</tasks>

<verification>
- `cd frontend && npx tsc --noEmit` exits 0.
- `cd frontend && npx vitest run` passes all tests (specifically `src/stores/uiStore.test.ts`).
- Manual smoke: navigate to a generated project, click a territory in the canvas — inspector shows neighbor chips instead of blanking the page. Toggle "Baronias" — barony polygons appear/disappear independently of the "Fronteiras" toggle. Legend card visible at bottom-left. Force an error inside ProjectDetail → ErrorBoundary fallback renders with two working buttons.
</verification>

<success_criteria>
- No blank-page crash when clicking a territory.
- InspectorSidebar neighbor chips work (hoisted neighbors reach the sidebar).
- ErrorBoundary catches rendering errors and shows a recoverable fallback UI.
- LayerTogglePanel uses the `condados / baronies / borders / capitals / labels` vocabulary with Portuguese labels.
- BaronyLayer visibility is now independent of the borders toggle.
- LegendCard explains the Reino/Duquia/Condado color convention.
- All existing tests pass with updated layer-name keys.
</success_criteria>

<output>
After completion, create `.planning/quick/260420-hkr-fix-blank-page-on-territory-click-hoist-/260420-hkr-SUMMARY.md`
</output>
