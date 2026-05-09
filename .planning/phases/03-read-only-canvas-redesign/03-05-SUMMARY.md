---
phase: 03-read-only-canvas-redesign
plan: 05
subsystem: frontend
tags: [konva, multi-select, hover-tooltip, inspector-dispatcher, vitest, radix-themes, read-only]

# Dependency graph
requires:
  - phase: 03-read-only-canvas-redesign
    plan: 03
    provides: uiStore.selectedTerritoryIds[] + selectIds() + selectSelectedTerritoryId selector + 'terrain' LayerName already removed
  - phase: 03-read-only-canvas-redesign
    plan: 04
    provides: ProjectDetail workspace shell wiring CanvasViewer with cacheVersion
provides:
  - "CanvasViewer.tsx — read-only stripped (697 -> 361 LOC; zero v1 deleted-module imports)"
  - "InteractionLayer multi-id rendering — gold #f0c040 outline per id in selectedTerritoryIds (D-17)"
  - "TerritoryLayer read-only click handler — plain click selects single, shift+click toggles set"
  - "TerritoryPolygon hover callback opt-in (onMouseEnter/onMouseLeave)"
  - "HoverTooltip — DOM overlay for D-15 hover tooltip"
  - "MultiSelectInspector — D-17 aggregate view (count, total km², union kingdoms/duchies, names)"
  - "InspectorSidebar 3-mode dispatcher (placeholder/single/multi) with English COPY locked"
  - "pixelsToKm2 util in src/lib/ with graceful null fallback"
  - "LayerTogglePanel trimmed to 5 layers (terrain row removed)"
affects:
  - "03-06 / 03-07 (Wave 3 deletion) — CanvasViewer + TerritoryLayer no longer reference SplitTool/VertexHandlesLayer/SelectionFloatingToolbar/ValidationBadgesLayer/TerrainBadgesLayer/SaveStatusIndicator/EditToolbar/SettingsPanel modules; useEditorStore/useProjectStore/useResearchStore/useValidationStore/useRubberBandSelection/useUndoShortcut/useEditKeyboardMap/useBeforeUnloadGuard hooks; api/edit + services/persistence + services/validation. Physical deletion is now mechanical."
  - "03-08 (Playwright UAT) — multi-select + hover + inspector dispatch end-to-end is testable"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only canvas Konva stack: BackgroundLayer + TerritoryLayer + BaronyLayer + DecorationsLayer + InteractionLayer with InteractionLayer listening=false (visual-only) and TerritoryLayer carrying click+hover hit testing"
    - "Empty-stage deselect via canonical Pitfall 5 pattern: e.target === e.target.getStage() race-free under React StrictMode"
    - "DOM overlay tooltip positioned via stage.getPointerPosition() — Radix Tooltip cannot anchor to Konva nodes (no DOM)"
    - "Stable handleClick reference (useCallback with []) reading via useUIStore.getState() — preserves React.memo on TerritoryPolygon at 800-territory scale"
    - "Multi-id Set membership filter in InteractionLayer: idsSet = new Set(selectedIds) → constant-time has(id) per polygon"
    - "Inspector 3-mode dispatcher branches on selectedTerritoryIds.length — placeholder / single (existing) / MultiSelectInspector"

key-files:
  created:
    - frontend/src/components/canvas/HoverTooltip.tsx
    - frontend/src/components/canvas/MultiSelectInspector.tsx
    - frontend/src/lib/pixelsToKm2.ts
    - frontend/src/components/canvas/__tests__/HoverTooltip.test.tsx
    - frontend/src/components/canvas/__tests__/MultiSelectInspector.test.tsx
    - frontend/src/components/canvas/__tests__/InteractionLayer.multiSelect.test.tsx
  modified:
    - frontend/src/components/canvas/CanvasViewer.tsx (697 -> 361 LOC; full read-only strip)
    - frontend/src/components/canvas/TerritoryLayer.tsx (read-only click + hover passthrough; no useEditorStore/useProjectStore/'terrain')
    - frontend/src/components/canvas/InteractionLayer.tsx (multi-id rendering via selectedTerritoryIds Set)
    - frontend/src/components/canvas/LayerTogglePanel.tsx (terrain row removed; 5 layers)
    - frontend/src/components/canvas/TerritoryPolygon.tsx (opt-in onMouseEnter/onMouseLeave)
    - frontend/src/components/canvas/InspectorSidebar.tsx (3-mode dispatcher; English COPY untouched)
    - frontend/src/components/canvas/__tests__/TerritoryLayer.shiftClick.test.tsx (rewritten to uiStore contract)
    - frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx (terrain describe block removed; uiStore mock updated)
    - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx (paint describe block removed; HoverTooltip mock added)
    - frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx (HoverTooltip mock added)
    - frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx (HoverTooltip mock added)
    - frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx (5-layer baseline; terrain assertions dropped)
    - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx (placeholder + multi-select dispatcher; selectedTerritoryIds setState)
    - frontend/src/components/canvas/__tests__/selection.test.tsx (selectedTerritoryIds setState alongside mirror)
  deleted:
    - frontend/src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx (orphan — exclusively tested useProjectStore hydrate effect that the strip removes)

key-decisions:
  - "InspectorSidebar EMPTY-state contract change (Rule 3 deviation): plan acceptance demands PT-BR placeholder when ids=0; existing tests expected 'Project overview'+hierarchy. The project-overview view is no longer reached when no territory is selected — D-16 placeholder takes over. Test file updated to reflect the new contract; English COPY constants left intact in source for the single-select branch (locked per UI-SPEC §Copywriting Contract)."
  - "Single-flight hover-callback prop (Rule 3 deviation from advisor flag): TerritoryLayer accepts optional onHoverEnter/onHoverLeave + passes through to TerritoryPolygon. Memo equality check extended to include both new props — prevents re-render storms when CanvasViewer's hover-state setter re-creates the closure (shouldn't happen because setHover lives outside the layer, but defensive)."
  - "Multi-select reference-stability test relaxed (Rule 1 deviation, by-design): the original test asserted ZERO additional handler pushes after a shift-click + rerender. With the new contract, shift+click writes through selectIds → mirror selectedTerritoryId updates → exactly ONE polygon's isSelected flips → ONE re-render. Test now asserts ≤1 extra push (perf guard intact, not a regression)."
  - "Deleted CanvasViewer.hydrate.test.tsx (Rule 3 — orphan): file exclusively tested the useProjectStore.hydrate effect that this plan strips. Same shape as 03-03's __tests__/uiStore.test.ts deletion. The plan's verify command listed the file but the plan itself stripped the feature — internal inconsistency; advisor confirmed."
  - "Deleted paint describe block in CanvasViewer.test.tsx (Rule 3 — orphan): block tested useEditorStore paint state + paintTerrain api; both stripped. The main describe('CanvasViewer') block survives + carries the read-only smoke + branch coverage."
  - "Deleted terrain describe block in TerritoryLayer.test.tsx (Rule 3 — orphan): tested layerVisibility.terrain branch which the strip removed. The basic-render block survives."
  - "TerritoryLayer.test.tsx getState mock added (Rule 3): existing test mocked useUIStore as a selector function only. The new TerritoryLayer click handler calls useUIStore.getState() → had to add Object.assign({getState}) to the mock so click reads don't throw at runtime."
  - "Plan claim '4 layers exposed: background, territory, barony, decorations' is wrong (advisor flag): current LayerName is condados/baronies/borders/capitals/labels (5 names; never matched the plan's invented 4). Followed the plain-language action 'remove the terrain row' verbatim — kept all other 5 rows."
  - "pixelsToKm2 extracted to shared util at src/lib/pixelsToKm2.ts (Pitfall 7 mitigation): MultiSelectInspector + InspectorSidebar both need the conversion; bounds=null fallback returns 0 so partial-data renders gracefully."
  - "Test selection.test.tsx + integration test updated (Rule 3): InteractionLayer now reads selectedTerritoryIds; tests that wrote only the selectedTerritoryId mirror needed selectedTerritoryIds[] writes too."

requirements-completed: [SC-1, SC-2]

# Metrics
duration: ~10min
completed: 2026-05-09
---

# Phase 03 Plan 05: Refit canvas surface for read-only Phase 03 Summary

**CanvasViewer stripped 697 -> 361 LOC with zero v1-deleted-module imports, plus shift+click multi-select via uiStore, hover tooltip via DOM overlay, and 3-mode InspectorSidebar dispatcher (placeholder / single / aggregate). Two new components (HoverTooltip + MultiSelectInspector), one shared util (pixelsToKm2), 16 new test specs, plus a deviation sweep across 7 existing test files. Full vitest suite 268/268 green; 2 atomic commits delivered.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-09T21:29:32Z
- **Completed:** 2026-05-09T21:39:03Z
- **Tasks:** 2
- **Commits:** 2 atomic
- **Files created:** 6
- **Files modified:** 14
- **Files deleted:** 1

## Accomplishments

- **CanvasViewer surgical strip — 697 -> 361 LOC.** Removed every import and usage of `useEditorStore`, `useProjectStore`, `useResearchStore`, `useValidationStore`, `useRubberBandSelection`, `useUndoShortcut`, `useEditKeyboardMap`, `useBeforeUnloadGuard`, `EditToolbar`, `SplitTool`, `VertexHandlesLayer`, `SelectionFloatingToolbar`, `ValidationBadgesLayer`, `TerrainBadgesLayer`, `SaveStatusIndicator`, `SettingsPanel`, `services/persistence`, `services/validation`, `api/edit`, `EditApiError`. Empty-stage click deselect uses Pitfall 5 verbatim (`e.target === e.target.getStage()`). ResizeObserver callback-ref pattern preserved verbatim.
- **InteractionLayer multi-select rendering (D-17).** `idsSet = new Set(useUIStore((s) => s.selectedTerritoryIds))` → `territories.filter(t => idsSet.has(t.id))` → one gold `#f0c040` strokeWidth=3 closed `<Line>` per polygon. Layer is `listening={false}` so hit-testing stays on TerritoryLayer.
- **TerritoryLayer read-only click handler.** Stable `handleClick` reference (useCallback with `[]`) reads `useUIStore.getState()` inside the body. Plain click → `selectIds([id])`; shift+click → toggle id in/out of `selectedTerritoryIds`. The `evt.evt.shiftKey` Konva event accessor passes the boolean through TerritoryPolygon.
- **HoverTooltip (D-15).** DOM `<div>` overlay sibling to the Stage; `position: absolute`, `pointer-events: none`, `z-index: 50`. Radix Themes `Card variant=surface` + `Text size=1`. Returns `null` when name is empty/null. CanvasViewer wires it via local React state + `stage.getPointerPosition()` reads on mouseover.
- **MultiSelectInspector (D-17 aggregate).** Heading `${count} condados selecionados` (PT-BR). "Área total" + summed pixel_count via shared `pixelsToKm2` util. "Reinos" with amber Badge per unique kingdom; "Ducados" with blue Badge per unique duchy; "Condados" inside ScrollArea (maxHeight=200) listing each name.
- **InspectorSidebar 3-mode dispatcher.** `length === 0` → PT-BR placeholder "Clique num território para ver detalhes" (D-16); `length === 1` → existing single-select detail view UNCHANGED (English COPY constants intact: `PROJECT_OVERVIEW`, `PATH_LABEL`, `CENTROID_LABEL`, `CAPITAL_LABEL`, `ADJACENT_LABEL`, `NO_CAPITAL`, `NO_NEIGHBORS` all 13 grep hits preserved); `length >= 2` → `MultiSelectInspector`.
- **LayerTogglePanel trimmed.** Dropped the `'terrain'` row + handler. The 5 surviving layers: condados, baronies, borders, capitals, labels.
- **Test suite green across 16 new specs + 7 updated specs.** No regressions: 256/256 → 268/268 across 43 → 45 files (12 new specs are net-new).

## Task Commits

| # | Task | Type | Commit |
|---|------|------|--------|
| 1 | Strip CanvasViewer + multi-select InteractionLayer + read-only TerritoryLayer + 5-layer LayerTogglePanel + 8 test files | feat | `e146b23` |
| 2 | HoverTooltip + MultiSelectInspector + InspectorSidebar 3-mode dispatch + pixelsToKm2 util + 3 test files | feat | `730648d` |

## Files Created/Modified

### Created (6)

- `frontend/src/components/canvas/HoverTooltip.tsx` — 30 lines. DOM overlay, returns null when name empty.
- `frontend/src/components/canvas/MultiSelectInspector.tsx` — 75 lines. Aggregate view per UI-SPEC §Multi-select Inspector aggregate.
- `frontend/src/lib/pixelsToKm2.ts` — 26 lines. Shared util with `bounds=null` graceful fallback returning 0 km².
- `frontend/src/components/canvas/__tests__/HoverTooltip.test.tsx` — 4 specs.
- `frontend/src/components/canvas/__tests__/MultiSelectInspector.test.tsx` — 7 specs.
- `frontend/src/components/canvas/__tests__/InteractionLayer.multiSelect.test.tsx` — 5 specs.

### Modified (14)

- `frontend/src/components/canvas/CanvasViewer.tsx` — 697 -> 361 LOC; full read-only strip; HoverTooltip wiring; Pitfall 5 deselect pattern.
- `frontend/src/components/canvas/TerritoryLayer.tsx` — read-only click handler; hover passthrough props; no useEditorStore/useProjectStore/'terrain'.
- `frontend/src/components/canvas/InteractionLayer.tsx` — multi-id rendering via `selectedTerritoryIds` Set membership.
- `frontend/src/components/canvas/LayerTogglePanel.tsx` — `'terrain'` row removed; 5 LAYERS entries.
- `frontend/src/components/canvas/TerritoryPolygon.tsx` — opt-in `onMouseEnter`/`onMouseLeave` props; memo compare extended.
- `frontend/src/components/canvas/InspectorSidebar.tsx` — top-of-render dispatcher (selectedTerritoryIds.length branch); MultiSelectInspector import; pixelsToKm2 util import; PLACEHOLDER_PT const.
- `frontend/src/components/canvas/__tests__/TerritoryLayer.shiftClick.test.tsx` — rewritten to uiStore contract (no useEditorStore.rubberBandSelectionIds).
- `frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx` — terrain describe block removed; uiStore mock extended with getState.
- `frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx` — paint describe block removed; HoverTooltip mock added; layerVisibility.terrain dropped from setState.
- `frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx` — HoverTooltip mock added.
- `frontend/src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx` — HoverTooltip mock added.
- `frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx` — 5-layer baseline; terrain assertions dropped; checkbox count 6 -> 5.
- `frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx` — placeholder describe (no-selection); multi-select dispatcher describe; selectedTerritoryIds setState alongside mirror.
- `frontend/src/components/canvas/__tests__/selection.test.tsx` — selectedTerritoryIds setState alongside selectedTerritoryId mirror.

### Deleted (1)

- `frontend/src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx` — orphan exclusively testing useProjectStore.hydrate effect that this plan strips.

## Decisions Made

See `key-decisions` block in frontmatter. Highlights:

- **Empty-state contract change.** D-16 placeholder takes over the no-selection slot; `Project overview` view no longer reachable. English COPY constants intact in source.
- **`pixelsToKm2` extracted** for shared use by InspectorSidebar + MultiSelectInspector (Pitfall 7 — bounds + map_size dependency); `bounds=null` returns 0 km² so partial data renders gracefully.
- **Multi-select perf guard test relaxed** to `≤baseline+1` because shift-click flips the `selectedTerritoryId` mirror → exactly ONE polygon's isSelected changes → exactly ONE re-render (perf intact).
- **Plan's "4 layers" specification was wrong** (canonical 5 in uiStore). Followed actionable text "remove terrain row" — left other 5 rows untouched.

## Deviations from Plan

**Total deviations:** 8 — all advisor-confirmed before commit; all Rule 1/3 (auto-fix bug or auto-fix blocking).

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Deleted orphaned `CanvasViewer.hydrate.test.tsx`**
- **Found during:** Pre-Task 1 (advisor flagged during conflict-resolution call).
- **Issue:** File exclusively tests `useProjectStore.hydrate` effect that the strip removes. Plan's verify command lists the file → internal plan inconsistency.
- **Fix:** `git rm` the orphan; commit with Task 1.
- **Committed in:** `e146b23` (Task 1).

**2. [Rule 3 — Blocking] Deleted paint describe block in `CanvasViewer.test.tsx`**
- **Found during:** Pre-Task 1.
- **Issue:** 130-LOC block exercises useEditorStore paint state + paintTerrain api/edit — both stripped.
- **Fix:** Remove block (130 LOC) + drop `useEditorStore`/`useProjectStore`/`paintTerrain` imports + drop the `terrain` key from layerVisibility setState.
- **Committed in:** `e146b23` (Task 1).

**3. [Rule 3 — Blocking] Deleted terrain describe block in `TerritoryLayer.test.tsx`**
- **Found during:** Task 1 first test pass.
- **Issue:** Block tested `layerVisibility.terrain` branch in TerritoryLayer that the strip removes; mocked `useProjectStore` for terrain_types which is also gone.
- **Fix:** Drop describe block; replace useUIStore mock with one that exposes `getState()` (new TerritoryLayer click handler reads via getState).
- **Committed in:** `e146b23` (Task 1).

**4. [Rule 3 — Blocking] Updated existing test files to set selectedTerritoryIds + add HoverTooltip mock**
- **Found during:** Task 1 first test pass.
- **Issue:** `selection.test.tsx` set only `selectedTerritoryId` (mirror) — InteractionLayer now reads `selectedTerritoryIds`. `CanvasViewer.{resize,panOnSelect}.test.tsx` did not mock HoverTooltip — Theme provider needed.
- **Fix:** setState writes both fields atomically; HoverTooltip vi.mock added to both Canvas test mocks.
- **Committed in:** `e146b23` (Task 1).

**5. [Rule 3 — Blocking] LayerTogglePanel.test.tsx rebaselined to 5 layers**
- **Found during:** Task 1 first test pass.
- **Issue:** Existing test asserted 6 checkboxes + Terreno text presence; trimming to 5 broke both.
- **Fix:** Dropped Terreno-row assertions; updated `getAllByRole('checkbox').length` to 5; updated default-state index map; added explicit `queryByText('Terreno')` is null assertion.
- **Committed in:** `e146b23` (Task 1).

**6. [Rule 1 — Bug] Multi-select perf guard test failed at expected baseline+0**
- **Found during:** Task 1 second test pass.
- **Issue:** Test asserted exactly `baselineCount` handlers after shift+click rerender. Reality: shift+click via `selectIds` writes the `selectedTerritoryId` mirror → polygon 'a' isSelected flips false→true → exactly ONE polygon re-renders → handler count = baseline+1. The original test ran in edit-mode-multi-select-via-rubberBandSelectionIds where the mirror DIDN'T flip.
- **Fix:** Assert `≤ baseline + 1`. Perf guard intact: if handleClick reference were unstable, count would be baseline+3 (all polygons re-render).
- **Committed in:** `e146b23` (Task 1).

**7. [Rule 3 — Blocking] InspectorSidebar empty-state contract changed; existing tests rewritten**
- **Found during:** Task 2 first test pass.
- **Issue:** Plan acceptance demands PT-BR placeholder when ids=0; existing test asserts "Project overview" + 4 hierarchy stats. The empty-state slot now belongs to D-16. Test file kept its English COPY single-select assertions intact (D-14 contract — locked) but rebaselined the no-selection branch.
- **Fix:** Replaced "project overview (no selection)" describe with two new describes: (a) D-16 placeholder, (b) D-17 multi-select dispatcher. Single-select describes (4 specs) untouched — assert PROJECT_OVERVIEW etc. verbatim.
- **Committed in:** `730648d` (Task 2).

**8. [Adapted to code reality] Plan's "4 layers exposed: background, territory, barony, decorations" was wrong**
- **Found during:** Pre-Task 1 (advisor flagged).
- **Issue:** Plan invented LayerName values that don't exist in uiStore. Canonical LayerName remains `condados | baronies | borders | capitals | labels` (5 keys; 'terrain' was removed in 03-03).
- **Fix:** Followed the actionable plan text "remove the 'terrain' row" — kept the other 5 rows verbatim. Adjusted LayerTogglePanel.test.tsx baseline accordingly.
- **Committed in:** `e146b23` (Task 1).

## Authentication Gates

None. Phase 03 is local-only by D-20.

## Issues Encountered

None outside the 8 deviations above.

## User Setup Required

None.

## Next Phase Readiness

- **Plan 03-06 / 03-07 (Wave 3 deletion) cleared.** CanvasViewer + TerritoryLayer + LayerTogglePanel + InspectorSidebar (sans the still-imported `useResearchStore` + `useValidationStore` for research overlay + validation badges in the single-select branch — those stay until Wave 3 deletion of the modules + the assignment data flow). The v1 SplitTool/VertexHandlesLayer/SelectionFloatingToolbar/ValidationBadgesLayer/TerrainBadgesLayer/SaveStatusIndicator/EditToolbar/SettingsPanel modules are now unimported by the canvas surface — physical deletion is mechanical.
- **Note for Wave 3:** `InspectorSidebar.tsx` still imports `useResearchStore` (research kingdom/duchy badges in single-select view) + `useValidationStore` (red/amber badges for validation issues). Both will be removed by Wave 3 along with the stores themselves. The plan's `<must_haves>` block did not list these as deletion targets for Plan 05 — kept verbatim per "do not modify the locked English single-select view".
- **Plan 03-08 (Playwright UAT) ready.** Multi-select via shift+click → InteractionLayer multi-outline → MultiSelectInspector aggregate is end-to-end testable. Hover tooltip is testable via mouse-event simulation.
- **Phase 03 SC-3 (no console errors) close.** New canvas surface references zero deleted-module imports. Final confirmation will be the Plan 08 Playwright UAT smoke + a full grep sweep after Wave 3.

## Verification

- `cd frontend && npm run test -- --run src/components/canvas/__tests__/InteractionLayer.multiSelect.test.tsx src/components/canvas/__tests__/TerritoryLayer.shiftClick.test.tsx src/components/canvas/__tests__/CanvasViewer.test.tsx src/components/canvas/__tests__/CanvasViewer.resize.test.tsx src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx src/components/canvas/__tests__/LayerTogglePanel.test.tsx src/components/canvas/__tests__/TerritoryLayer.test.tsx src/components/canvas/__tests__/selection.test.tsx` → **44/44 green** (8 files)
- `cd frontend && npm run test -- --run src/components/canvas/__tests__/HoverTooltip.test.tsx src/components/canvas/__tests__/MultiSelectInspector.test.tsx src/components/canvas/__tests__/InspectorSidebar.test.tsx` → **21/21 green** (3 files)
- `cd frontend && npm run test -- --run` (full suite) → **268/268 green across 45 files**
- `wc -l frontend/src/components/canvas/CanvasViewer.tsx` → **361** (≤ 420 budget; vs 697 baseline = 48% reduction)
- `grep -nE "useEditorStore|useProjectStore|useResearchStore|useValidationStore|useRubberBandSelection|useUndoShortcut|useEditKeyboardMap|useBeforeUnloadGuard|EditToolbar|SplitTool|VertexHandlesLayer|SelectionFloatingToolbar|ValidationBadgesLayer|TerrainBadgesLayer|SaveStatusIndicator|SettingsPanel|services/persistence|services/validation|api/edit|EditApiError" frontend/src/components/canvas/CanvasViewer.tsx` → **0 hits**
- `grep -nE "useEditorStore|useProjectStore|'terrain'" frontend/src/components/canvas/TerritoryLayer.tsx` → **0 hits**
- `grep -n "'terrain'" frontend/src/components/canvas/LayerTogglePanel.tsx` → **0 hits**
- `grep -n "e\.target === e\.target\.getStage()" frontend/src/components/canvas/CanvasViewer.tsx` → **3 hits** (canonical Pitfall 5)
- `grep -n "Clique num território para ver detalhes" frontend/src/components/canvas/InspectorSidebar.tsx` → **1 hit** (PT-BR placeholder present)
- `grep -nE "PROJECT_OVERVIEW|PATH_LABEL|CENTROID_LABEL|CAPITAL_LABEL|ADJACENT_LABEL|NO_CAPITAL|NO_NEIGHBORS" frontend/src/components/canvas/InspectorSidebar.tsx` → **13 hits** (English COPY constants untouched — 7 declarations + 6 in-render references)
- `grep -n "getPointerPosition" frontend/src/components/canvas/CanvasViewer.tsx` → **1 hit** (hover wiring)
- `grep -n "condados selecionados" frontend/src/components/canvas/MultiSelectInspector.tsx` → **2 hits** (heading template + comment)

## Self-Check: PASSED

- FOUND: frontend/src/components/canvas/CanvasViewer.tsx (361 LOC; 0 deleted-module imports)
- FOUND: frontend/src/components/canvas/TerritoryLayer.tsx (read-only click; no useEditorStore/useProjectStore)
- FOUND: frontend/src/components/canvas/InteractionLayer.tsx (multi-id Set rendering)
- FOUND: frontend/src/components/canvas/LayerTogglePanel.tsx (5 layers; no terrain)
- FOUND: frontend/src/components/canvas/TerritoryPolygon.tsx (hover passthrough)
- FOUND: frontend/src/components/canvas/HoverTooltip.tsx
- FOUND: frontend/src/components/canvas/MultiSelectInspector.tsx
- FOUND: frontend/src/components/canvas/InspectorSidebar.tsx (3-mode dispatcher; English COPY locked)
- FOUND: frontend/src/lib/pixelsToKm2.ts
- FOUND: frontend/src/components/canvas/__tests__/HoverTooltip.test.tsx (4 specs green)
- FOUND: frontend/src/components/canvas/__tests__/MultiSelectInspector.test.tsx (7 specs green)
- FOUND: frontend/src/components/canvas/__tests__/InteractionLayer.multiSelect.test.tsx (5 specs green)
- DELETED: frontend/src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx (orphan removed)
- FOUND commit: e146b23 (Task 1 — feat strip + multi-select)
- FOUND commit: 730648d (Task 2 — feat HoverTooltip + MultiSelectInspector + dispatcher)
- VITEST: full suite 268/268 green across 45 files; no regressions

---
*Phase: 03-read-only-canvas-redesign*
*Completed: 2026-05-09*
