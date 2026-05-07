---
phase: 02-read-only-canvas-viewer
plan: 03
subsystem: canvas-interaction-inspector
tags: [canvas, konva, zustand, radix, tdd, pitfall-5, pitfall-6, d-04, d-06.3]
dependency_graph:
  requires:
    - plan 02-01 (projection, Zustand slice, useCanvasArtifacts 5-tuple, ProjectionProvider, CanvasViewer scaffold)
    - plan 02-02 (TerritoryLayer, BaronyLayer, LayerTogglePanel, two-region layout)
  provides:
    - frontend/src/hooks/useZoomPan.ts (SCALE_BY, MAX_SCALE_MULTIPLIER, applyPanClamp, makeWheelHandler, makeDragBoundFunc, panToGeoCenter)
    - frontend/src/hooks/useKeyboardShortcuts.ts (useKeyboardShortcuts — Esc + Ctrl/Cmd+0)
    - frontend/src/components/canvas/FitToViewButton.tsx (bottom-left Radix button)
    - frontend/src/components/canvas/DecorationsLayer.tsx (D-04 dual-ring capitals + zoom-gated labels, LABEL_ZOOM_THRESHOLD_RELATIVE)
    - frontend/src/components/canvas/InteractionLayer.tsx (#f0c040 gold selection outline)
    - frontend/src/components/canvas/InspectorSidebar.tsx (project-summary + territory-detail states, D-06.3 capital sentinel)
    - frontend/e2e/perf-panzoom.spec.ts (A5 FPS probe, env-gated)
  affects:
    - Phase 4 canvas editing — reuses makeWheelHandler, makeDragBoundFunc, panToGeoCenter, useKeyboardShortcuts verbatim
    - Phase 4 barony-level selection — extends InteractionLayer + InspectorSidebar shape
tech_stack:
  added: []
  patterns:
    - Selection-pan coupling via useEffect([selectedId, projection, metaQ.data]) that reads scale live from stage.scaleX() (advisor bug #1)
    - Imperative-only Stage scale — no scaleX/scaleY props on <Stage> (advisor bug #2)
    - Empty-Stage click deselect via e.target === e.target.getStage() (Pitfall 6 canonical)
    - Post-mount getTextWidth() for pixel-accurate label centering
    - vi.hoisted() + React.forwardRef in react-konva mocks to inject stub Konva.Stage into stageRef for effect tests
key_files:
  created:
    - frontend/src/hooks/useZoomPan.ts
    - frontend/src/hooks/useZoomPan.test.ts
    - frontend/src/hooks/useKeyboardShortcuts.ts
    - frontend/src/hooks/useKeyboardShortcuts.test.ts
    - frontend/src/components/canvas/FitToViewButton.tsx
    - frontend/src/components/canvas/__tests__/FitToViewButton.test.tsx
    - frontend/src/components/canvas/DecorationsLayer.tsx
    - frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx
    - frontend/src/components/canvas/InteractionLayer.tsx
    - frontend/src/components/canvas/__tests__/selection.test.tsx
    - frontend/src/components/canvas/InspectorSidebar.tsx
    - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx
    - frontend/e2e/perf-panzoom.spec.ts
  modified:
    - frontend/src/components/canvas/CanvasViewer.tsx (full rewrite — zoom/pan/fit/selection-pan/empty-click/DecorationsLayer/InteractionLayer/FitToViewButton)
    - frontend/src/pages/ProjectDetail.tsx (replaced inspector-sidebar-placeholder with InspectorSidebarWrapper)
    - frontend/src/hooks/useCanvasArtifacts.ts (added optional capital_name to TerritoryMetadataCondado per D-06.3)
    - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx (mock Circle/Text/Line + new layer stubs + zoom-hook stubs)
    - frontend/src/test-setup.ts (ResizeObserver polyfill for Radix ScrollArea in jsdom)
    - .gitignore (frontend/test-results/ + playwright-report/ — Playwright runtime output)
decisions:
  - Konva dragBoundFunc correct signature is `(this: Node, pos: Vector2d) => Vector2d` — no extra args (caught by tsc during Task 3b build)
  - Imperative-only Stage scale — scaleX/scaleY props removed; fitToView() sets initial scale via stage.scale()
  - Selection-pan effect reads currentScale live from stage.scaleX(), NOT from state deps, so wheel zoom does not snap view back
  - D-04 dual-ring capital is two overlaid <Circle> nodes (outer rgba(0,0,0,0.6) r=6.75 + inner colored r=6 with white 1.5 stroke) — NO shadowBlur
  - D-06.3 "No capital assigned" sentinel is rendered when capital_name is undefined OR empty OR whitespace-only
  - Empty-Stage click deselect uses e.target === e.target.getStage() (race-free under React StrictMode; Pitfall 6)
  - jsdom does not implement isContentEditable or ResizeObserver — handler and test-setup fall back / polyfill
metrics:
  duration_minutes: 20
  completed_date: "2026-04-18"
  tasks_completed: 4
  tasks_total: 4
  files_created: 14
  files_modified: 6
---

# Phase 2 Plan 3: Interaction + Inspector Summary

**One-liner:** Wired pan/zoom (cursor-anchored, clamped), fit-to-view (button + Ctrl+0), D-04 dual-ring capitals + zoom-gated labels, gold InteractionLayer outline, 4-group InspectorSidebar with D-06.3 capital sentinel, selection-driven pan-to-center (Pitfall 5), and empty-Stage click deselect (Pitfall 6) — all TDD.

## Final Konva Stage Composition (5 layers)

```
<Stage draggable dragBoundFunc onWheel onClick onTap>
  BackgroundLayer   — terrain PNG, listening=false     (D-01)
  TerritoryLayer    — condado polygons, clickable       (D-01/D-02 colors)
  BaronyLayer       — barony polygons @ 85%, listening=false  (D-02)
  DecorationsLayer  — dual-ring capitals + labels, listening=false  (D-04 + D-10/11)
  InteractionLayer  — #f0c040 selection outline, listening=false  (D-03)
</Stage>
<LayerTogglePanel />    /* absolute top-left Radix card */
<FitToViewButton />     /* absolute bottom-left Radix button */
```

Every decorative layer is `listening=false` so hit-testing goes through TerritoryLayer only — D-03 read-only contract preserved (no geometry mutation on selection).

## Interaction Hooks API (reusable for Phase 4)

All four primitives are plain functions/hooks with no Konva type bleed into consumer code — Phase 4 editing plans can import them directly.

| Symbol | Module | Purpose |
|---|---|---|
| `SCALE_BY = 1.05` | `useZoomPan.ts` | Wheel zoom factor per tick |
| `MAX_SCALE_MULTIPLIER = 4` | `useZoomPan.ts` | Max zoom = 4× fit-scale |
| `applyPanClamp(stage, scale, cfg)` | `useZoomPan.ts` | Centers-or-clamps stage position in-place |
| `makeWheelHandler(min, max, cfg)` | `useZoomPan.ts` | Cursor-anchored wheel zoom with clamps |
| `makeDragBoundFunc(cfg, getScale, getStage?)` | `useZoomPan.ts` | Konva dragBoundFunc — correct `(this: Node, pos) => Vector2d` signature |
| `panToGeoCenter(stage, lon, lat, proj, scale, cfg)` | `useZoomPan.ts` | Center viewport on a geo point (Pitfall 5 helper) |
| `useKeyboardShortcuts(onFitToView)` | `useKeyboardShortcuts.ts` | Esc-deselect + Ctrl/Cmd+0-fit, guards INPUT/TEXTAREA/contentEditable |

## InspectorSidebar Consumer Contract

```ts
<InspectorSidebar
  metadata={TerritoryMetadata}     // from /preview/territory_metadata.json
  territories={TerritoryRender[]}  // from /preview/territories.geojson
  project={{ name, country_qid, period_start, period_end }}
/>
```

Two UI states, switched by `useUIStore.selectedTerritoryId`:

- **`null` (project overview)** — heading `"Project overview"` + 4 hierarchy stat rows (Kingdoms amber, Duchies blue, Condados grass, Baronies gray) + project name/country/period.
- **`id` (territory detail)** — heading = condado name; 4 groups:
  1. Hierarchy badges — amber kingdom / blue duchy / grass Condado / gray baronies count
  2. Path / Area / **Centroid** (its own row)
  3. **Capital** (D-06.3): real `capital_name` when present, otherwise literal `"No capital assigned"`
  4. Adjacent territories as chips; clicking a chip dispatches `useUIStore.select(neighborId)` → the CanvasViewer selection-change effect pans the canvas to center the newly selected territory.

All UI copy is pinned in a `COPY` const at the top of `InspectorSidebar.tsx` and enforced verbatim by `grep` acceptance criteria.

## D-04 Dual-Ring Capital Implementation

Two overlaid `<Circle>` nodes per capital (NOT a shadow). Order matters — dark ring first, colored disk on top:

```tsx
<Circle data-role="capital-dark-ring"  radius={6.75} fill="rgba(0, 0, 0, 0.6)" />
<Circle data-role="capital"            radius={6}    fill={condadoColor} stroke="#ffffff" strokeWidth={1.5} />
```

`grep "shadowBlur" DecorationsLayer.tsx` returns 0 matches — enforced by test + plan acceptance criterion. The dark ring is a real geometric circle, never a Canvas shadow filter.

## D-06.3 Capital Name Fallback Policy

```ts
const hasCapital =
  typeof condado.capital_name === 'string' &&
  condado.capital_name.trim().length > 0
```

- `capital_name` present and non-blank → render as large Text, then centroid lat/lng as small gray Text below it.
- absent / undefined / empty / whitespace-only → render the **exact** literal string `"No capital assigned"`.

Centroid is **always** its own `<Box>` row (separate from Capital) — no duplication with the capital's lat/lng; the two rows can carry different values (capital city coordinates vs condado centroid) once a capitals dataset is wired in Phase 3+.

## Pitfall 5 — Pan-to-Selected Implementation

```tsx
useEffect(() => {
  const stage = stageRef.current
  if (!stage || !projection || !selectedId || !metaQ.data) return
  const condado = metaQ.data.condados.find((c) => c.id === selectedId)
  if (!condado) return
  panToGeoCenter(stage, condado.lon, condado.lat, projection,
    stage.scaleX(),  // read live, NOT from deps
    { mapW: projection.mapW, mapH: projection.mapH },
  )
  stage.batchDraw()
}, [selectedId, projection, metaQ.data])
```

The effect runs once per selection change (initial click OR neighbor-chip navigation — both flow through `useUIStore.select(id)`, so the effect subsumes both). Scale is read live from `stage.scaleX()` so wheel zoom doesn't retrigger the effect and snap the viewport back. Verified in `CanvasViewer.panOnSelect.test.tsx`.

## Pitfall 6 — Empty-Stage Click Deselect

```tsx
const handleStageClick = useCallback(
  (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (e.target === e.target.getStage()) {
      select(null)
    }
  },
  [select],
)
```

Uses `e.target.getStage()` — race-free under React StrictMode double-invocation. Does NOT compare against `stageRef.current` (that pattern fails when the stage is remounted between StrictMode passes). Konva 10.2.5 `DragAndDrop.js` confirmed to set `_mouseListenClick = false` on drag start, which gates click firing in `Stage._pointerup` — so an empty-Stage click fires only on a true click with no intervening drag. Verified by grep scan of `node_modules/konva/lib/DragAndDrop.js:74`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pan-on-select effect deps included `currentScale`**
- **Found during:** Task 3b planning (advisor review)
- **Issue:** Plan listed `currentScale` in the useEffect dep array. Wheel zoom calls `setCurrentScale(stage.scaleX())`, which would re-trigger the effect and snap the viewport back to the selected territory on every wheel tick.
- **Fix:** Dropped `currentScale` from deps. Scale is read live from `stage.scaleX()` inside the effect.
- **Files modified:** frontend/src/components/canvas/CanvasViewer.tsx
- **Commit:** d45645e

**2. [Rule 1 - Bug] `<Stage scaleX scaleY>` props conflict with imperative zoom**
- **Found during:** Task 3b planning (advisor review)
- **Issue:** Prior CanvasViewer passed `<Stage scaleX={scale} scaleY={scale}>`. Wheel handler calls `stage.scale({...})`, but the next React render would reset scale back to the prop value.
- **Fix:** Removed `scaleX`/`scaleY` props. Initial scale is set imperatively by `fitToView()` on mount via the stage ref; thereafter only `stage.scale()` touches it.
- **Files modified:** frontend/src/components/canvas/CanvasViewer.tsx
- **Commit:** d45645e

**3. [Rule 1 - Bug] `makeDragBoundFunc` signature mismatch**
- **Found during:** Task 3b TypeScript build (`tsc -b`)
- **Issue:** Plan text prescribed `(pos, _e, stage?) => {...}` — 3-arg signature. Konva's actual `dragBoundFunc` type is `(this: Node, pos: Vector2d) => Vector2d` — no extra args; the Node is bound via `this`.
- **Fix:** Rewrote as `function(this: Konva.Node | void, pos) { ... }` with an optional `getStage` resolver. Tests now invoke via `bound.call(stubStage, pos)`.
- **Files modified:** frontend/src/hooks/useZoomPan.ts, frontend/src/hooks/useZoomPan.test.ts
- **Commit:** d45645e

**4. [Rule 3 - Blocking] Radix ScrollArea crashes in jsdom without ResizeObserver**
- **Found during:** Task 3a (first InspectorSidebar test run — ResizeObserver is not defined)
- **Issue:** jsdom does not implement ResizeObserver. Radix ScrollArea mounts it unconditionally and the tests crashed before any assertion ran.
- **Fix:** Added a minimal ResizeObserverStub to `src/test-setup.ts`. Real behavior is covered by Playwright e2e.
- **Files modified:** frontend/src/test-setup.ts
- **Commit:** 5ade5b4

**5. [Rule 2 - Missing] `TerritoryMetadataCondado.capital_name` not in type**
- **Found during:** Task 3a (writing InspectorSidebar tests)
- **Issue:** Plan's D-06.3 depends on `condado.capital_name` being a typed optional, but `useCanvasArtifacts.ts` didn't declare it.
- **Fix:** Added `capital_name?: string` to `TerritoryMetadataCondado` with a comment documenting D-06.3.
- **Files modified:** frontend/src/hooks/useCanvasArtifacts.ts
- **Commit:** 6f4eb33

**6. [Rule 1 - Bug] jsdom isContentEditable returns undefined**
- **Found during:** Task 1 (useKeyboardShortcuts contenteditable test)
- **Issue:** jsdom doesn't implement `HTMLElement.isContentEditable`. Handler only checked `el.isContentEditable`, so the test passed Esc through and cleared selection inside a contenteditable element.
- **Fix:** Handler also checks `el.getAttribute('contenteditable') === 'true' | ''`. Test uses `tabIndex = 0` + `div.dispatchEvent(...)` so jsdom focus + attribute lookup both work.
- **Files modified:** frontend/src/hooks/useKeyboardShortcuts.ts, frontend/src/hooks/useKeyboardShortcuts.test.ts
- **Commit:** d383882

**7. [Rule 3 - Blocking] existing CanvasViewer.test.tsx mock too narrow**
- **Found during:** Task 3b (new layers mounted)
- **Issue:** Existing react-konva mock declared only Stage/Layer/Image/Rect. DecorationsLayer renders Circle+Text; InteractionLayer renders Line — missing mocks would cause the test to render real Konva, which needs a real canvas context not available in jsdom.
- **Fix:** Added Circle/Text/Line to the mock + `vi.mock` pass-through stubs for DecorationsLayer / InteractionLayer / FitToViewButton / useZoomPan / useKeyboardShortcuts.
- **Files modified:** frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
- **Commit:** ed72153

**8. [Rule 3 - Gitignore] Playwright test-results untracked after test runs**
- **Found during:** Pre-summary status check
- **Issue:** `frontend/test-results/` left untracked files after running smoke-tailwind-radix.
- **Fix:** Added `frontend/test-results/` + `frontend/playwright-report/` to `.gitignore`.
- **Files modified:** .gitignore
- **Commit:** (bundled with this SUMMARY commit)

No deviations required Rule 4 (architectural approval).

## Authentication Gates

None — plan 2.3 is purely frontend interaction wiring. No network secrets or external credentials involved.

## Known Stubs

None. All components render real data from the plan 2.1 backend artifacts. The `territories` prop on InspectorSidebar is currently accepted but intentionally unused in Phase 2 — it's a seam for Phase 4+ to derive geometry-based area (Shoelace formula on projected `points`) rather than relying on `pixel_count`. This is documented in an inline `void territories` comment in the source.

## Known Open Items for Phase 4+

- **Barony-level selection** — InteractionLayer currently renders one gold outline per condado. Phase 4 editing will add barony hit-testing + a secondary InteractionLayer (or a shape-type discriminator) once the edit workflow needs barony selection.
- **Dynamic label anti-collision** — labels render when `scale >= 2*minScale` with no collision avoidance. If UAT flags label clutter at 2×–3× zoom, a simple rtree-based label suppression pass can be added to DecorationsLayer.
- **InspectorSidebarWrapper 2× useCanvasArtifacts call** — the wrapper subscribes to all 5 query objects twice (once with `projection=null` to read metadata first, then again with `projection` set). TanStack dedups the network requests but not the hook subscriptions. A Phase 4 refactor can consolidate into one call via a dedicated `useInspectorData` hook.
- **Capital coordinate data** — D-06.3 renders the capital city name when present, but the centroid lat/lng is also shown as the capital's coords because the backend does not yet emit a separate `capital_lat / capital_lon` pair. When capital geocoding lands, flip the capital row's coords to the real capital city location.

## Read-Only Contract (D-03)

Confirmed preserved:
- Selection dispatches through `useUIStore.select(id)` — pure state mutation, no geometry touched.
- InteractionLayer paints a standalone `<Line>` from the already-projected `territory.points` — does not mutate TerritoryPolygon's points or any backing metadata.
- TerritoryPolygon's `memo(areEqual)` from plan 2.2 remains intact: sibling polygons do not re-render when selection changes.
- No mutation paths to metadata, territories, or baronies arrays anywhere in the Phase 2 tree.

## Verification Results

| Check | Result |
|-------|--------|
| `vitest run` (full suite) | 86/86 pass across 13 test files |
| `tsc -b` | 0 errors |
| `vite build` | success (442 modules transformed, 2.42s) |
| `playwright test smoke-tailwind-radix` | 1/1 pass (Pitfall 2 visual regression) |
| `grep SCALE_BY = 1.05 useZoomPan.ts` | match |
| `grep MAX_SCALE_MULTIPLIER = 4 useZoomPan.ts` | match |
| `grep panToGeoCenter useZoomPan.ts` | match (export) |
| `grep panToGeoCenter CanvasViewer.tsx` | match (inside useEffect) |
| `grep "[selectedId" CanvasViewer.tsx` | match (effect dep array) |
| `grep "e.target === e.target.getStage()" CanvasViewer.tsx` | match |
| `grep "e.target === stageRef" CanvasViewer.tsx` | 0 matches (old Pitfall 6 pattern absent) |
| `grep "isContentEditable\|TEXTAREA\|INPUT" useKeyboardShortcuts.ts` | all 3 match |
| `grep "Fit to view" FitToViewButton.tsx` | match |
| `grep "minHeight: '44px'" FitToViewButton.tsx` | match |
| `grep "LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0" DecorationsLayer.tsx` | match |
| `grep "radius={6}" DecorationsLayer.tsx` | match (inner disk) |
| `grep "radius={6.75}" DecorationsLayer.tsx` | match (outer dark ring) |
| `grep "rgba(0, 0, 0, 0.6)" DecorationsLayer.tsx` | match |
| `grep "getTextWidth" DecorationsLayer.tsx` | match |
| `grep "shadowBlur" DecorationsLayer.tsx` | 0 matches (D-04 real ring) |
| `grep "#f0c040\|strokeWidth={3}\|listening={false}" InteractionLayer.tsx` | all 3 match |
| `grep "'No capital assigned'" InspectorSidebar.tsx` | match (literal string) |
| `grep "'Project overview'\|'Path:'\|'Centroid'\|'Capital'\|'Adjacent territories'" InspectorSidebar.tsx` | all 5 match |
| `grep "color=\"amber\"\|color=\"blue\"\|color=\"grass\"\|color=\"gray\"" InspectorSidebar.tsx` | all 4 match |
| `grep "capital_name" InspectorSidebar.tsx` | match (reads optional field) |
| `grep "<InspectorSidebar" ProjectDetail.tsx` | match |
| `grep "inspector-sidebar-placeholder" ProjectDetail.tsx` | 0 matches (placeholder removed) |
| `grep "draggable\|onWheel\|dragBoundFunc\|useKeyboardShortcuts" CanvasViewer.tsx` | all 4 match |

## Commits

RED/GREEN TDD pairs per task (all with `--no-verify` per parallel-agent protocol):

| Task | RED (tests) | GREEN (impl) |
|---|---|---|
| 1. useZoomPan + useKeyboardShortcuts + FitToViewButton | `3415b16` | `d383882` |
| 2. DecorationsLayer + InteractionLayer | `edaf0c5` | `54337f4` |
| 3a. InspectorSidebar | `6f4eb33` | `5ade5b4` |
| 3b. CanvasViewer wiring + ProjectDetail InspectorSidebarWrapper | `ed72153` | `d45645e` |

## Threat Flags

None new. The plan's `<threat_model>` mitigations (T-02-03-01 through T-02-03-07) are all honored:
- T-02-03-01 (XSS via capital_name): React auto-escapes. `grep dangerouslySetInnerHTML frontend/src/components/canvas/` returns 0.
- T-02-03-03 (wheel DoS): makeWheelHandler is O(1), short-circuits at clamp.
- T-02-03-04 (Esc inside input): guarded by INPUT/TEXTAREA/contentEditable check.
- T-02-03-05 (Radix/Tailwind config): Plan 2.1 visual-regression smoke remains green.
- T-02-03-06 (re-render amplification): narrow Zustand selectors, memo'd TerritoryPolygon from plan 2.2.
- T-02-03-07 (pan-on-select overrides user pan): accepted behavior per UI-SPEC.

## Self-Check: PASSED

- All 14 created files exist on disk (verified via ls in working tree).
- All 4 modified files verified via `grep` acceptance checks above.
- All 8 commits (4 RED + 4 GREEN) reachable via `git log`.
- `vitest run` full-suite: 86/86 pass.
- `tsc -b` + `vite build`: 0 errors.
- Playwright Pitfall 2 smoke: 1/1 pass.
