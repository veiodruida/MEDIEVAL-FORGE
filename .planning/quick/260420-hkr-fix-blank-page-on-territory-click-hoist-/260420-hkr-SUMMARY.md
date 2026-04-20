---
phase: 260420-hkr
plan: 01
subsystem: canvas-viewer
tags: [bug-fix, frontend, canvas, inspector, error-boundary]
dependency_graph:
  requires: [02-03 canvas viewer + InspectorSidebar wired]
  provides: [neighbors-on-metadata, ErrorBoundary primitive, Portuguese layer vocabulary, hierarchy legend]
  affects:
    - frontend/src/hooks/useCanvasArtifacts.ts
    - frontend/src/components/ErrorBoundary.tsx
    - frontend/src/App.tsx
    - frontend/src/stores/uiStore.ts
    - frontend/src/stores/uiStore.test.ts
    - frontend/src/components/canvas/LayerTogglePanel.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/components/canvas/LegendCard.tsx
    - frontend/src/pages/ProjectDetail.tsx
    - frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx
    - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
tech_stack:
  added: []
  patterns: [react-class-error-boundary, client-side-hoist-merge]
key_files:
  created:
    - frontend/src/components/ErrorBoundary.tsx
    - frontend/src/components/canvas/LegendCard.tsx
  modified:
    - frontend/src/hooks/useCanvasArtifacts.ts
    - frontend/src/App.tsx
    - frontend/src/stores/uiStore.ts
    - frontend/src/stores/uiStore.test.ts
    - frontend/src/components/canvas/LayerTogglePanel.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/pages/ProjectDetail.tsx
    - frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx
    - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
decisions:
  - Hoist neighbors client-side (not in backend metadata) — smallest blast radius, no regen required.
  - Pre-release rename of LayerName without backwards-compat shim (project is pre-release).
  - BaronyLayer visibility decoupled from borders toggle (semantic bug fix).
  - LegendCard is purely static — no live data bindings.
metrics:
  duration_min: 8
  tasks_completed: 4
  files_touched: 13
  completed_date: 2026-04-20
---

# Quick Task 260420-hkr: Fix Blank Page on Territory Click + Hoist Neighbors Summary

Fixed the blank-page crash triggered by clicking any territory (neighbors array was undefined on `TerritoryMetadataCondado`), hardened the canvas subtree with a recoverable React ErrorBoundary, renamed the layer-toggle vocabulary to the real Reino/Duquia/Condado/Baronia hierarchy, and added a static legend card explaining the hierarchy badge colors.

## What Shipped

1. **Neighbors hoist (Task 1, `useCanvasArtifacts.ts`)** — After the `useQueries` call, a `useMemo` merges `territories.geojson .properties.neighbors` into every `metadata.condados[i]`, producing a fully populated `TerritoryMetadata` for consumers. Fallback empty array while territories.geojson is in flight so InspectorSidebar never sees `undefined.length`. The 5-tuple shape returned by the hook is preserved so `CanvasViewer` and `ProjectDetail` keep destructuring by index.
2. **ErrorBoundary (Task 2, `ErrorBoundary.tsx` + `App.tsx`)** — React class component with `getDerivedStateFromError` and `componentDidCatch`. Fallback renders a Radix Card with two recovery actions: "Limpar seleção" (clears `selectedTerritoryId` via `useUIStore.getState().select(null)` and resets boundary) and a `<Link to="/projects">` with the same reset-on-click so the user can re-enter a project immediately. Wraps only `/projects/:id` in `App.tsx`; dev-only canvas-smoke route remains unwrapped.
3. **LayerName rename (Task 3)** — `LayerName` is now `'condados' | 'baronies' | 'borders' | 'capitals' | 'labels'`. Defaults: `condados/borders/capitals=true`, `baronies/labels=false`. LayerTogglePanel shows Portuguese labels (Condados / Baronias / Fronteiras / Capitais / Nomes) under the header "Camadas". CanvasViewer: `BackgroundLayer` and `TerritoryLayer` are both gated by `layerVisibility.condados`; `BaronyLayer` now tracks `layerVisibility.baronies` independently of borders (semantic fix — previously hiding borders also hid the barony polygons). All fixture objects in the five touched test files were updated in lock-step; `uiStore.test.ts` and `LayerTogglePanel.test.tsx` were rewritten around the new vocabulary. One existing CanvasViewer test was retargeted from the old `borders → BaronyLayer` coupling to the new `baronies → BaronyLayer` coupling.
4. **LegendCard (Task 4, `LegendCard.tsx` + `ProjectDetail.tsx`)** — Static Radix Card at `position: absolute; bottom: 12; left: 12; zIndex: 10; width: 160`, mounted as a sibling of `<CanvasViewer />` inside the `canvas-region` Box. Three rows with `var(--amber-9) / var(--blue-9) / var(--grass-9)` swatches and labels Reino / Duquia / Condado, matching the `InspectorSidebar` `Badge` palette.

## Verification

- `npx tsc --noEmit` — passes (0 errors) after each of the four tasks.
- `npm test -- --run` — 91/91 tests pass after each task.
- `npm run build` — succeeds (vite v6, 444 modules, new bundle `index-o3sfdJnA.js` emitted to `backend/medieval_forge/static/`).
- Manual smoke pending: verify in the running Unity-asset-serving dev session that clicking a territory shows neighbor chips; toggling Baronias hides/shows BaronyLayer independently of Fronteiras; LegendCard visible at bottom-left; forcing a throw inside ProjectDetail shows the ErrorBoundary fallback with both buttons functional.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Fixture types in five test files referenced the old LayerName keys**
- **Found during:** Task 3 `npx tsc --noEmit`.
- **Issue:** `Record<LayerName, boolean>` became strictly typed after the rename, so every `beforeEach` fixture that wrote `{ terrain: true, territories: true, ... }` produced a TS2353 error. Plan only explicitly mentioned `uiStore.test.ts`; the plan's grep-step caught the rest.
- **Fix:** Replaced the five fixtures to `{ condados: true, baronies: false, borders: true, capitals: true, labels: false }`. Updated the `LayerTogglePanel.test.tsx` assertions to match the new Portuguese labels and the "Camadas" header. Retargeted the `BaronyLayer visible prop tracks layerVisibility.borders` test at the new `baronies` key (and renamed the `it()` accordingly) since the plan intentionally decouples that wiring.
- **Files modified:** CanvasViewer.test.tsx, CanvasViewer.panOnSelect.test.tsx, CanvasViewer.resize.test.tsx, InspectorSidebar.test.tsx, LayerTogglePanel.test.tsx.
- **Commit:** 49b97ce.

No other deviations — each of the four tasks executed exactly as written.

## Commits

| Task | Commit  | Message |
|------|---------|---------|
| 1    | 3dc5333 | fix(260420-hkr): hoist territories.geojson neighbors into metadata.condados |
| 2    | 098acaa | feat(260420-hkr): add ErrorBoundary wrapping ProjectDetail route |
| 3    | 49b97ce | refactor(260420-hkr): rename LayerName to condados/baronies hierarchy |
| 4    | 6d8b9e9 | feat(260420-hkr): add LegendCard explaining hierarchy badge colors |

## Known Stubs

None. Every change is wired to live data (hoist uses real territories.geojson; LegendCard is intentionally a static key, which is documented in its JSDoc and matches the plan spec).

## Self-Check: PASSED

- FOUND: frontend/src/components/ErrorBoundary.tsx
- FOUND: frontend/src/components/canvas/LegendCard.tsx
- FOUND: commit 3dc5333
- FOUND: commit 098acaa
- FOUND: commit 49b97ce
- FOUND: commit 6d8b9e9
- TS: `npx tsc --noEmit` clean
- Tests: 91/91 pass
- Build: vite build succeeded (new minified bundle emitted)
