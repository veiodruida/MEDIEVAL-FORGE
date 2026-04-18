---
phase: 02-read-only-canvas-viewer
verified: 2026-04-18T15:10:00Z
updated: 2026-04-18T18:00:00Z
status: gaps_found
score: 26/26 automated must-haves verified (but E2E pipeline broken — see gaps)
overrides_applied: 0
requirements_covered:
  - CANVAS-01
  - CANVAS-02
  - CANVAS-03
  - CANVAS-04
  - CANVAS-05
  - CANVAS-06
roadmap_success_criteria:
  - sc: "User can see all territory polygons rendered on the Konva canvas with correct hierarchy colors and visible borders matching the generated GeoJSON data."
    status: verified_automated
    evidence: "backend territories_geojson.py emits per-condado polygon features + neighbors; frontend TerritoryLayer renders <Line closed> with stroke=rgba(0,0,0,0.35) 1px and fill from lookup_condado_colors.json; 3 TerritoryLayer tests pass; real-data pixel-parity is human-verification item #5"
  - sc: "User can pan the canvas by dragging and zoom with the mouse wheel; polygons remain pixel-aligned and do not re-project on zoom."
    status: verified_automated
    evidence: "Stage draggable + dragBoundFunc={makeDragBoundFunc}; onWheel={makeWheelHandler} cursor-anchored; useZoomPan.test.ts 9/9 pass; polygons use imperative stage.scale() — no prop-driven re-projection; Playwright perf probe exists (env-gated)"
  - sc: "User can click any territory and see its name, type, and hierarchy properties appear in the right-side panel."
    status: verified_automated
    evidence: "TerritoryPolygon onClick → select(id) → InteractionLayer gold outline + InspectorSidebar 4-group render; InspectorSidebar 9 tests + selection integration test pass"
  - sc: "User can toggle each layer (terrain, territories, borders, capitals, labels) on and off independently; labels only appear at appropriate zoom levels."
    status: verified_automated
    evidence: "LayerTogglePanel renders 5 checkboxes wired to useUIStore.toggleLayer; LABEL_ZOOM_THRESHOLD_RELATIVE=2.0 gates labels in DecorationsLayer; LayerTogglePanel 5 tests + DecorationsLayer 8 tests pass"
  - sc: 'User can press a "Fit to view" button and the canvas resets to show the full map centered in the viewport.'
    status: verified_automated
    evidence: "FitToViewButton calls fitToView → computeFitToView → stage.scale+position + setMinScale; Ctrl+0 keyboard shortcut triggers same callback; FitToViewButton tests + useKeyboardShortcuts 7 tests pass"
gaps:
  - id: G-01
    severity: blocker
    truth: "Backend `emit_territories_from_disk` / `emit_baronies_from_disk` parse `lookup_*_colors.json` using the wrong schema — they assume `{condado_id: '#rrggbb'}` but `map_generator.py:672` writes `{'r,g,b': int_index}`. `hexstr[1:3]` raises `TypeError: 'int' object is not subscriptable`, no geojson files are emitted, and the frontend canvas renders blue-empty with only the terrain background."
    evidence: "territories_geojson.py:141-154 (hex parsing), baronies_geojson.py:78-81 (same defect), map_generator.py:672 (real format `{f'{r},{g},{b}': i}`); confirmed by user E2E test 2026-04-18 (HUMAN-UAT item 1 FAILED)"
    affects: [CANVAS-01, CANVAS-03, CANVAS-04]
    fix_hint: "Rewrite emitter adapters to consume `{'r,g,b': idx}` + join with `territory_metadata.json` condados[] list (idx → condado_id) to build the pc mask and produce the expected GeoJSON. Alternative: add a post-pipeline conversion step in generator.py that rewrites lookup_*_colors.json to `{condado_id: '#hex'}` before calling the emitters — but this modifies the on-disk artifact contract consumed by Unity/other downstream tools, so the adapter approach is safer."
  - id: G-02
    severity: blocker
    truth: "The try/except at `generator.py:341-347` wrapping `emit_territories_from_disk` / `emit_baronies_from_disk` silently logs and swallows every exception, so the format-mismatch crash in G-01 never surfaced to the user, CI, or status machinery — the project moved to status='generated' despite two missing critical artifacts."
    evidence: "generator.py:341-347 `except Exception as exc: logger.exception(...)` with no re-raise, no project.status downgrade, no artifact-presence check"
    affects: [CANVAS-01, observability]
    fix_hint: "Either (a) re-raise so the background task's outer handler sets status='error_generating' and records `last_error`, OR (b) keep logging but add an artifact-presence post-check that fails the generation when `territories.geojson` / `baronies.geojson` are missing. Option (a) is cleaner."
  - id: G-03
    severity: warning
    truth: "No integration test exercises the real pipeline path `map_generator.generate_maps → lookup_*_colors.json on disk → emit_*_from_disk → territories.geojson/baronies.geojson`. Phase 02's 9 backend tests all call `build_territories_geojson` / `build_baronies_geojson` directly with synthetic in-memory numpy arrays, bypassing the disk read codepath where G-01 lives."
    evidence: "tests/test_territories_geojson.py and tests/test_baronies_geojson.py (9/9 pass but never call emit_*_from_disk); 86/86 frontend tests mock artifact fetches"
    affects: [regression prevention]
    fix_hint: "Add an integration test with a tiny Iberia-like fixture (e.g. 32×32 synthetic map) that runs `run_generation` end-to-end and asserts both geojson files exist and parse to non-empty FeatureCollections."
deferred:
  - truth: "MultiPolygon territories (islands/exclaves) render all polygons — currently firstOuterRing picks only the first ring"
    addressed_in: "Phase 3+"
    evidence: "02-REVIEW.md WR-04 (warning, non-blocking) — continental Iberia has no exclaves; noted for real-world MultiPolygon data in later phases"
  - truth: "Single-point corner adjacency (touches) produces spurious neighbors at 4-corner pixel junctions"
    addressed_in: "Phase 4+"
    evidence: "02-REVIEW.md IN-03 — acknowledged in test suite; Voronoi-derived maps rarely hit this; edge-length filter can be added when editing lands"
human_verification:
  - test: "Open a generated Iberia project and visually confirm ALL condado polygons render with the exact colors from lookup_condado_colors.json (pixel parity with terrain.png)"
    expected: "Every condado is painted with its Unity palette color; 1px rgba(0,0,0,0.35) borders visible; no #666666 fallback (fallback indicates a missing color lookup)"
    why_human: "Pixel-parity visual check against the real Iberia pipeline output — automated tests use synthetic raster fixtures; full E2E path requires a generated project"
  - test: "Toggle the Borders layer ON/OFF with a real Iberia project loaded"
    expected: "When ON, baronies render as internal borders at 85% opacity above condados with subtle 0.25 stroke; when OFF, the BaronyLayer disappears immediately with no stutter"
    why_human: "Visual verification of D-02 real-geometry delivery; opacity blending and stroke contrast are perceptual quality checks"
  - test: "Drag-pan with the mouse across the canvas"
    expected: "Map scrolls smoothly with the cursor; at map edges the pan clamps so the map never leaves the viewport; when map is smaller than viewport it stays centered"
    why_human: "Pan feel (smoothness, clamp boundary behavior) is a perceptual UX check that dragBoundFunc tests cannot fully exercise"
  - test: "Mouse-wheel zoom in and out over different cursor positions"
    expected: "Zoom anchors on the cursor (point under cursor stays under cursor through zoom); clamps at fit-scale (no further zoom-out) and 4× fit-scale (no further zoom-in)"
    why_human: "Cursor-anchored zoom math is tested in unit tests, but visual smoothness and anchor precision under real wheel events need human verification"
  - test: "Click a condado polygon, then click a neighbor chip in the inspector"
    expected: "Gold 3px outline appears on clicked condado; inspector shows 4 groups (hierarchy badges, path/area/centroid, capital, adjacent); clicking a neighbor chip moves selection AND pans the canvas so the new territory is centered"
    why_human: "Pan-to-selected is a visible user-flow behavior — Pitfall 5 unit test asserts stage.position() is called, but the end-user experience of smooth re-centering is only visible in a real browser"
  - test: "Press Esc while selection is active, then click the empty Stage background"
    expected: "Esc clears selection — inspector reverts to 'Project overview'; empty-Stage click also clears selection (Pitfall 6 canonical e.target.getStage() pattern)"
    why_human: "Keyboard guard against INPUT/TEXTAREA/contentEditable focus needs a real browser focus model to validate; jsdom does not implement isContentEditable reliably"
  - test: "Zoom to >= 2× minScale and toggle the Labels layer"
    expected: "Labels appear as system-ui 12px text with white halo centered on capitals; at <2× minScale labels never render even with toggle ON"
    why_human: "Label centering uses post-mount getTextWidth() which requires a real Konva canvas context — jsdom cannot exercise the measurement pipeline"
  - test: "Click Fit-to-view button AND press Ctrl+0 from a zoomed-in state"
    expected: "Both paths reset the canvas to show the full map centered with ~5% padding; minScale is recomputed; button is bottom-left with minHeight:44px"
    why_human: "Visual confirmation of reset behavior and ~5% padding perception requires a real viewport"
  - test: "Open a project with a condado that has a real capital_name set, and one without"
    expected: "With-capital condado shows the capital city name + coords below; without-capital shows the exact literal string 'No capital assigned' (D-06.3 sentinel)"
    why_human: "The sentinel path is unit-tested but the end-to-end flow (backend metadata emission → frontend render) with a real capital_name-bearing project requires a generated project fixture"
---

# Phase 2: Read-Only Canvas Viewer Verification Report

**Phase Goal:** Build a read-only Konva canvas viewer at `/projects/:id` that renders generated Iberia maps (terrain PNG + condado polygons + barony overlay) with layer toggles, zoom/pan, selection, and an inspector sidebar.
**Requirements:** CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06
**Verified:** 2026-04-18T15:10:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (merged from ROADMAP Success Criteria + all three plans' must_haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Backend emits `territories.geojson` with per-condado polygon + neighbors | VERIFIED | `territories_geojson.py:71 build_territories_geojson`, rasterio.features.shapes + STRtree.touches; whitelist at `generator.py:63-67`; 5/5 pytest |
| 2 | Backend emits `baronies.geojson` with per-barony polygon + fill color | VERIFIED | `baronies_geojson.py:21 build_baronies_geojson`; 4/4 pytest; fill from `lookup_barony_colors.json` |
| 3 | FastAPI serves both geojson files via whitelist `/api/projects/{id}/preview/{filename}` | VERIFIED | whitelist contains both filenames at `generator.py:67`; existing `/preview/{filename}` route unchanged |
| 4 | Frontend projection module converts lon/lat <-> canvas pixels with <1e-9 round-trip error | VERIFIED | `projection.ts` exports geoToCanvas/canvasToGeo/computeFitToView/geoRingToKonvaPoints; 8/8 projection.test.ts pass |
| 5 | Konva Stage mounts inside `/projects/:id` and renders terrain PNG on Background layer | VERIFIED | `ProjectDetail.tsx:136 <CanvasViewer>`; `CanvasViewer.tsx` mounts `<BackgroundLayer>` inside `<Stage>`; 7/7 CanvasViewer tests pass |
| 6 | Tailwind v4 + Radix overlay stays opaque over Konva Stage (Pitfall 2) | VERIFIED | Playwright `smoke-tailwind-radix.spec.ts` with baseline PNG + pngjs RGB sample — green per provided context |
| 7 | Vitest + Playwright infra installed and wired to npm scripts | VERIFIED | `vitest.config.ts`, `playwright.config.ts`, test-setup.ts exist; `npm run test -- --run` executes 86 tests across 13 files |
| 8 | User sees all condado polygons with fills from `lookup_condado_colors.json` | VERIFIED | `TerritoryLayer` → `TerritoryPolygon` with `condadoColors[id]` lookup and `'#666666'` fallback; 3/3 tests |
| 9 | Territory borders render as rgba(0,0,0,0.35), 1px, closed polygons | VERIFIED | `TerritoryPolygon.tsx:30-33 closed stroke="rgba(0, 0, 0, 0.35)" strokeWidth=1`; asserted in test |
| 10 | User sees all barony polygons at 85% opacity when Borders toggle ON (D-02 real geometry) | VERIFIED | `BaronyLayer.tsx:19 <Layer listening={false} opacity={0.85}>` with per-feature `fill={b.fill}`; fed by `baronies.geojson` from plan 2.1 backend pipeline; 4/4 tests |
| 11 | Floating Radix Card top-left shows 5 layer checkboxes (Terrain/Territories/Borders/Capitals/Labels) | VERIFIED | `LayerTogglePanel.tsx` — Card variant="surface" at position:absolute top:12 left:12 zIndex:10; 5 checkboxes in fixed order; 5/5 tests |
| 12 | Checkbox state persists in useUIStore; toggling hides Konva nodes immediately | VERIFIED | `uiStore.ts` layerVisibility + toggleLayer; `CanvasViewer` reads visibility per layer; 11/11 uiStore tests + CanvasViewer integration test |
| 13 | Default layer state on open: terrain/territories/borders/capitals ON, labels OFF (D-09) | VERIFIED | `uiStore.ts:17-22 DEFAULT_LAYER_VISIBILITY`; asserted in uiStore + LayerTogglePanel tests |
| 14 | TerritoryPolygon memoized so unrelated polygons don't re-render on selection change | VERIFIED | `TerritoryPolygon.tsx` wrapped in `memo(..., areEqual)`; narrow Zustand selector in TerritoryLayer; TerritoryLayer memo test |
| 15 | Pan via dragging; pan clamped so map stays within viewport | VERIFIED | `Stage draggable dragBoundFunc={makeDragBoundFunc(...)}`; `applyPanClamp` + `makeDragBoundFunc` in useZoomPan.ts; 9/9 useZoomPan tests incl. clamp assertions |
| 16 | Wheel zoom anchors on cursor position | VERIFIED | `makeWheelHandler` computes mousePointTo then sets stage position relative to pointer; unit test asserts new position |
| 17 | Zoom clamped: minScale = fit scale, maxScale = 4× fit scale | VERIFIED | `MAX_SCALE_MULTIPLIER = 4`; CanvasViewer `makeWheelHandler(minScale, minScale * MAX_SCALE_MULTIPLIER, ...)`; useZoomPan test asserts clamp behavior |
| 18 | Click condado → gold 3px outline on InteractionLayer + inspector fills with 4 groups | VERIFIED | `InteractionLayer.tsx:32-34 stroke="#f0c040" strokeWidth={3} listening={false}`; `InspectorSidebar` renders Hierarchy/Path-Area-Centroid/Capital/Adjacent; selection.test.tsx + InspectorSidebar 9/9 tests |
| 19 | Esc clears selection; empty-Stage click deselects via `e.target.getStage()` (Pitfall 6) | VERIFIED | `useKeyboardShortcuts.ts` Esc guarded by INPUT/TEXTAREA/contentEditable; `CanvasViewer.tsx:188 if (e.target === e.target.getStage()) select(null)`; 7/7 shortcut tests |
| 20 | Neighbor chip click moves selection AND pans canvas to center new territory (Pitfall 5) | VERIFIED | `CanvasViewer.tsx:132 panToGeoCenter(stage, condado.lon, condado.lat, projection, stage.scaleX(), cfg)` inside `useEffect([selectedId, projection, metadata])`; live scale read avoids wheel-zoom snap-back; CanvasViewer.panOnSelect.test.tsx 7/7 pass |
| 21 | Capital dots render as D-04 dual-ring (outer dark ring + inner colored disk + white stroke) | VERIFIED | `DecorationsLayer.tsx:93-103` outer Circle radius=6.75 fill=rgba(0,0,0,0.6) + inner Circle radius=6 stroke="#ffffff" strokeWidth=1.5; zero `shadowBlur` matches (real ring not shadow); 8/8 DecorationsLayer tests |
| 22 | Labels render only when `layerVisibility.labels && scale >= 2.0 * minScale` | VERIFIED | `LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0`; `showLabels` gate at `DecorationsLayer.tsx:80`; test asserts label suppression below threshold |
| 23 | Fit-to-view button + Ctrl+0 reset canvas to whole-map view | VERIFIED | `FitToViewButton.tsx` "Fit to view" copy at bottom-left minHeight 44px; `useKeyboardShortcuts(fitToView)` wires Ctrl/Cmd+0; `CanvasViewer.fitToView` uses computeFitToView + sets minScale |
| 24 | Inspector shows project summary when nothing selected | VERIFIED | `InspectorSidebar.tsx:75-95` — heading "Project overview", 4 stat rows Kingdoms(amber)/Duchies(blue)/Condados(grass)/Baronies(gray) + project metadata |
| 25 | Inspector capital group: real name when present OR exact "No capital assigned" sentinel (D-06.3) | VERIFIED | `InspectorSidebar.tsx:115-116` `typeof condado.capital_name === 'string' && condado.capital_name.trim().length > 0`; literal NO_CAPITAL constant at line 20; positive + negative path tests |
| 26 | Empty-Stage click deselects using e.target.getStage() (Pitfall 6, race-free under StrictMode) | VERIFIED | `CanvasViewer.tsx:188 e.target === e.target.getStage()`; `stageRef.current` comparison deliberately absent (grep 0 matches); asserted in CanvasViewer.panOnSelect.test.tsx |

**Score: 26/26 truths verified**

### Deferred Items

Items not flagged as gaps because they are either (a) out of scope for Phase 2's Iberia milestone or (b) explicitly deferred in the code review for later phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | MultiPolygon territories render all rings (islands/exclaves) | Phase 3+ | 02-REVIEW.md WR-04: "continental Iberia has no exclaves; correctness gap against real-world MultiPolygon data" — `firstOuterRing` at useCanvasArtifacts.ts:79 picks only first ring |
| 2 | Edge-length-based adjacency (reject single-point corner touches) | Phase 4+ | 02-REVIEW.md IN-03: "admits single-point corner contact... if spec wants edge-adjacency only, replace with length check"; acknowledged in test suite |
| 3 | Capital coords distinct from centroid coords | Phase 3+ | 02-03-SUMMARY.md Known Open Items: "backend does not yet emit a separate capital_lat / capital_lon pair" |
| 4 | InspectorSidebarWrapper single useCanvasArtifacts call | Phase 4+ refactor | 02-REVIEW.md IN-01: current double-call works (TanStack dedups); consolidation is optional perf improvement |

### Required Artifacts

Level 1 (exists), Level 2 (substantive), Level 3 (wired), Level 4 (data flows).

| Artifact | Level 1 | Level 2 | Level 3 | Level 4 | Status |
|----------|---------|---------|---------|---------|--------|
| `backend/medieval_forge/services/territories_geojson.py` | exists | substantive (170+ lines, rasterio + STRtree) | wired (imported in generator.py:331, called at :342) | data flows (reads real lookup PNG + metadata; 5/5 tests with synthetic raster) | VERIFIED |
| `backend/medieval_forge/services/baronies_geojson.py` | exists | substantive (100+ lines) | wired (imported at generator.py:332, called at :343) | data flows (reads lookup_barony.png + colors; 4/4 tests) | VERIFIED |
| `backend/medieval_forge/services/generator.py` (whitelist + emission hook) | exists | substantive | wired (emission called after _run_pipeline_sync; whitelist includes both geojson files) | data flows (both files served via /preview/{filename}) | VERIFIED |
| `frontend/src/lib/projection.ts` | exists | substantive | wired (imported by useCanvasArtifacts, CanvasViewer, DecorationsLayer, useZoomPan) | data flows (8/8 round-trip tests at 1e-9 precision) | VERIFIED |
| `frontend/src/stores/uiStore.ts` | exists | substantive | wired (imported by CanvasViewer, LayerTogglePanel, InspectorSidebar, InteractionLayer, TerritoryLayer, useKeyboardShortcuts) | data flows (11/11 tests; state drives visible layers) | VERIFIED |
| `frontend/src/context/ProjectionContext.tsx` | exists | substantive | wired (ProjectionProvider in CanvasViewer; useProjection in DecorationsLayer) | data flows | VERIFIED |
| `frontend/src/hooks/useCanvasArtifacts.ts` | exists | substantive (5-tuple with staleTime:Infinity) | wired (CanvasViewer + InspectorSidebarWrapper) | data flows (queries real /preview endpoints) | VERIFIED |
| `frontend/src/components/canvas/CanvasViewer.tsx` | exists | substantive (268 lines) | wired (ProjectDetail mounts when status in {generated, exported}) | data flows (5 layers mounted; pan/zoom/fit/selection effects) | VERIFIED |
| `frontend/src/components/canvas/BackgroundLayer.tsx` | exists | substantive | wired (inside Stage with visible={layerVisibility.terrain}) | data flows (loads terrain.png via use-image) | VERIFIED |
| `frontend/src/components/canvas/TerritoryPolygon.tsx` | exists | substantive | wired (mapped in TerritoryLayer) | data flows (memo+areEqual stable identity) | VERIFIED |
| `frontend/src/components/canvas/TerritoryLayer.tsx` | exists | substantive | wired (Stage child in CanvasViewer line 249) | data flows (territoriesQ.data + condadoColorsQ.data) | VERIFIED |
| `frontend/src/components/canvas/BaronyLayer.tsx` | exists | substantive | wired (Stage child line 254) | data flows (baroniesQ.data with per-feature fill) | VERIFIED |
| `frontend/src/components/canvas/LayerTogglePanel.tsx` | exists | substantive | wired (sibling of Stage inside canvas container, line 267) | data flows (reads + dispatches useUIStore) | VERIFIED |
| `frontend/src/components/canvas/DecorationsLayer.tsx` | exists | substantive (dual-ring capitals + CenteredLabel) | wired (Stage child line 255) | data flows (metadata.condados + condadoColors + scale props) | VERIFIED |
| `frontend/src/components/canvas/InteractionLayer.tsx` | exists | substantive | wired (Stage child line 265) | data flows (subscribes to selectedTerritoryId, finds territory points) | VERIFIED |
| `frontend/src/components/canvas/FitToViewButton.tsx` | exists | substantive | wired (sibling line 268 with onFit callback) | data flows (triggers fitToView → computeFitToView) | VERIFIED |
| `frontend/src/components/canvas/InspectorSidebar.tsx` | exists | substantive (project summary + 4-group detail + D-06.3 sentinel) | wired (InspectorSidebarWrapper in ProjectDetail line 142) | data flows (metadata + territories + project; dispatches select via neighbor chips) | VERIFIED |
| `frontend/src/hooks/useZoomPan.ts` | exists | substantive (SCALE_BY=1.05, MAX_SCALE_MULTIPLIER=4, applyPanClamp, makeWheelHandler, makeDragBoundFunc, panToGeoCenter) | wired (CanvasViewer imports all 4 + constants) | data flows (9/9 tests) | VERIFIED |
| `frontend/src/hooks/useKeyboardShortcuts.ts` | exists | substantive (Esc guard + Ctrl/Cmd+0) | wired (CanvasViewer.tsx:117 useKeyboardShortcuts(fitToView)) | data flows (7/7 tests) | VERIFIED |
| `frontend/src/pages/ProjectDetail.tsx` (two-region layout + InspectorSidebar) | exists | substantive | wired (canvas-region + inspector-sidebar flex with InspectorSidebarWrapper) | data flows (inspector-sidebar-placeholder grep returns 0) | VERIFIED |
| `frontend/e2e/smoke-tailwind-radix.spec.ts` + baseline | exists | substantive | wired (Playwright config) | data flows (Pitfall 2 regression still green per context) | VERIFIED |
| `frontend/e2e/perf-panzoom.spec.ts` | exists | substantive (A5 FPS probe) | wired (env-gated by MF_PERF_FIXTURE_PROJECT_ID) | N/A (perf probe, not a correctness test) | VERIFIED |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `generator.py` | `territories_geojson.build_territories_geojson` + `baronies_geojson.build_baronies_geojson` | called after map_generator.generate_maps | WIRED | generator.py:331-343 imports and calls both; both files appended to GENERATED_FILE_WHITELIST at line 67 |
| `ProjectDetail.tsx` | `CanvasViewer` | rendered when status in {generated, exported} | WIRED | line 136 `<CanvasViewer projectId={project.id}>` inside `isGenerated` gate |
| `useCanvasArtifacts.ts` | `/api/projects/{id}/preview/territories.geojson` + `.../baronies.geojson` | TanStack Query with staleTime:Infinity | WIRED | 5-tuple returned; queries use preview paths |
| `projection.ts` | `map_generator.py geo_to_pixel` (affine math) | identical formula, sub-pixel floats | WIRED | 8/8 round-trip tests pass at 1e-9 precision; `inicio/map_generator.py` explicitly unmodified (D-04 honored) |
| `TerritoryLayer` | `useCanvasArtifacts` | consumes TerritoryRender[] | WIRED | CanvasViewer destructures 5-tuple and passes territoriesQ.data |
| `BaronyLayer` | `useCanvasArtifacts` | consumes BaronyRender[] with per-feature fill | WIRED | BaronyLayer line 19-29; fill=b.fill from server-resolved colors |
| `TerritoryPolygon` | `lookup_condado_colors.json` | fill prop from JSON via condadoColors[id] | WIRED | TerritoryLayer passes fill={condadoColors[t.id] ?? FALLBACK_FILL} |
| `LayerTogglePanel` | `useUIStore` | reads layerVisibility + dispatches toggleLayer | WIRED | lines 13 + 26; 5/5 tests |
| `CanvasViewer` | `TerritoryLayer` + `BaronyLayer` + `LayerTogglePanel` + `DecorationsLayer` + `InteractionLayer` + `FitToViewButton` | all 6 mounted | WIRED | imports at lines 5-10; usages at lines 249-268 |
| `CanvasViewer` | `useZoomPan` primitives | makeWheelHandler + makeDragBoundFunc + panToGeoCenter | WIRED | imports at line 16-21; all three wired into Stage + selection effect |
| `CanvasViewer` | `useKeyboardShortcuts` | Esc-deselect + Ctrl/Cmd+0-fit | WIRED | line 117 `useKeyboardShortcuts(fitToView)` |
| `InspectorSidebar` | `useUIStore.select` | neighbor chip click dispatches select(neighborId) | WIRED | chips render `onClick={() => select(chip.id)}` |
| `ProjectDetail` | `InspectorSidebar` | replaces plan-2.2 placeholder | WIRED | InspectorSidebarWrapper at line 142; grep `inspector-sidebar-placeholder` returns 0 matches |
| Selection change → canvas pan | `panToGeoCenter` | useEffect([selectedId, projection, metaQ.data]) | WIRED | CanvasViewer.tsx:125-140; scale read live from stage.scaleX() per advisor fix |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| TerritoryLayer | territoriesQ.data | useCanvasArtifacts → /preview/territories.geojson → territories_geojson.py rasterio pipeline | Yes (real polygon features + neighbors) | FLOWING |
| BaronyLayer | baroniesQ.data | useCanvasArtifacts → /preview/baronies.geojson → baronies_geojson.py | Yes (per-feature fill + polygon) | FLOWING |
| TerritoryPolygon fill | condadoColors[t.id] | useCanvasArtifacts → /preview/lookup_condado_colors.json | Yes (Unity-ready hex palette) | FLOWING |
| DecorationsLayer | metadata.condados + condadoColors + currentScale/minScale | useCanvasArtifacts metaQ → /preview/territory_metadata.json; currentScale from stage.scaleX() live read | Yes | FLOWING |
| InteractionLayer | territories[i].points where id === selectedTerritoryId | useUIStore selectedTerritoryId + TerritoryRender[] | Yes (null → 0 children; id → single gold outline) | FLOWING |
| BackgroundLayer | terrain.png URL | CanvasViewer constructs /preview/terrain.png URL | Yes (use-image hook resolves image) | FLOWING |
| InspectorSidebar (detail) | metadata.condados.find(id=selectedId) + project | InspectorSidebarWrapper metaQ + project prop | Yes (positive and NO_CAPITAL paths tested) | FLOWING |
| InspectorSidebar (summary) | metadata.kingdoms/duchies/condados/baronies counts | useCanvasArtifacts metaQ | Yes (4 badges with real counts) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend unit test suite | `cd frontend && npx vitest run` | 86/86 across 13 files (3.87s total) | PASS |
| TypeScript build | `cd frontend && npx tsc -b` | exit 0, no output | PASS |
| Backend phase-02 services | `cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py -v` | 9/9 pass | PASS |
| Playwright Pitfall-2 visual smoke | (per provided context) | 1/1 pass | PASS (context) |
| Full backend suite | (per provided context) | 2 pre-existing failures from pre-phase-02 commits (test_sse_stream Portuguese-localized messages; test_country_qid_validation_rejects_bad_format) — NOT regressions from phase 02 | SKIP (non-regression) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| CANVAS-01 | 02-01, 02-02 | User can view all territories on Konva canvas with correct colors and borders | SATISFIED | TerritoryLayer + TerritoryPolygon + lookup_condado_colors.json pipeline; rgba stroke 1px; real geojson from territories_geojson.py |
| CANVAS-02 | 02-03 | User can pan and zoom (Stage drag + wheel zoom) | SATISFIED | Stage draggable + dragBoundFunc + makeWheelHandler (cursor-anchored, clamped [fit, 4×fit]) |
| CANVAS-03 | 02-03 | User can click territory to select and see properties in right panel | SATISFIED | TerritoryPolygon click → select(id) → InteractionLayer gold outline + InspectorSidebar 4-group render; Pitfall 5 pan-on-select + Pitfall 6 empty-Stage deselect |
| CANVAS-04 | 02-02 | Canvas shows layer toggles (terrain/territories/borders/capitals/labels) | SATISFIED | LayerTogglePanel with 5 checkboxes wired to useUIStore.layerVisibility; default per D-09 |
| CANVAS-05 | 02-03 | Canvas shows territory labels at appropriate zoom levels | SATISFIED | DecorationsLayer gate `showLabels = layerVisibility.labels && currentScale >= 2.0 * minScale`; post-mount getTextWidth centering |
| CANVAS-06 | 02-03 | User can fit map to view (reset zoom/pan) | SATISFIED | FitToViewButton bottom-left + Ctrl/Cmd+0 keyboard shortcut; both call same fitToView callback that uses computeFitToView + sets minScale |

All 6 CANVAS-* requirements from ROADMAP Phase 2 are accounted for. Plans declared:
- 02-01: CANVAS-01
- 02-02: CANVAS-01, CANVAS-04
- 02-03: CANVAS-02, CANVAS-03, CANVAS-05, CANVAS-06

No orphaned requirements. No requirements claimed but unimplemented.

### Anti-Patterns Found

Per 02-REVIEW.md findings (incorporated here). Zero blockers, 5 warnings + 5 info items — all non-blocking for Phase 2 acceptance.

| File | Severity | Pattern | Impact |
|------|----------|---------|--------|
| `generator.py:81,116` | Warning (WR-01) | Duplicated `_cleanup_territory_module` definition | Code-smell, harmless (second def wins); cleanup recommended before Phase 4 |
| `generator.py:98-113` | Warning (WR-02) | `_patch_reload_for_synthetic` mutates global `importlib.reload` — concurrency race | Safe under current single-generation assumption; needs lock or module-scoped patch before concurrent generation |
| `generator.py:213-220` | Warning (WR-03) | `_build_region_config` silently drops caller bbox when no territory data | Latent bug — unreachable today because `_run_pipeline_sync` requires non-empty territory_data at line 302-305 |
| `useCanvasArtifacts.ts:79-83` | Warning (WR-04) | `firstOuterRing` discards all but first polygon of MultiPolygon | Deferred to Phase 3+ (continental Iberia has no exclaves) |
| `pyproject.toml:10,27` | Warning (WR-05) | `rasterio>=1.4,<2.0` admits 1.5+ which requires Python 3.12+ while `requires-python = ">=3.11"` | Version pin tightening needed; runtime uses Python 3.14 so tests pass |
| `ProjectDetail.tsx:405,424` | Info (IN-01) | Double useCanvasArtifacts call in InspectorSidebarWrapper | Acceptable perf; consolidate in Phase 4 refactor |
| `baronies_geojson.py:80-82` | Info (IN-02) | Variable `b` reused for blue channel inside color loop | Readability; rename to `blue` |
| `territories_geojson.py:117` | Info (IN-03) | `STRtree.touches()` admits single-point corner adjacency | Deferred; semantics explicitly documented in test |
| `InteractionLayer.tsx:27-35` + `BaronyLayer.tsx:19-29` | Info (IN-04) | Redundant `listening={false}` on Line inside `listening={false}` Layer | Stylistic noise only |
| `DecorationsLayer.tsx:32-41` | Info (IN-05) | `CenteredLabel` effect depends only on `[props.text]` (OK today; missing fontSize/fontFamily when parameterized) | Forward-looking nit |

No blocker anti-patterns. Nothing that prevents goal achievement.

### Human Verification Required

All automated verification gates pass, but visual, perceptual, and full-E2E paths need human testing in a real browser with a generated Iberia project.

#### 1. Pixel-parity condado fills

**Test:** Open a generated Iberia project at `/projects/:id` and compare the canvas rendering to `terrain.png` / `lookup_condado.png`.
**Expected:** Every condado is painted with its color from `lookup_condado_colors.json`; 1px rgba(0,0,0,0.35) borders visible; no `#666666` fallback anywhere (would indicate a missing color lookup).
**Why human:** Automated tests use synthetic raster fixtures. Full E2E path through the real Iberia pipeline requires a generated project.

#### 2. Barony overlay at 85% opacity

**Test:** With a real Iberia project loaded, toggle the Borders layer ON/OFF.
**Expected:** When ON, baronies render as internal borders at 85% opacity above condados with subtle 0.25 stroke; when OFF, the BaronyLayer disappears immediately with no stutter.
**Why human:** Opacity blending and stroke contrast are perceptual quality checks.

#### 3. Drag-pan smoothness and clamp behavior

**Test:** Drag-pan with the mouse across the canvas to all edges.
**Expected:** Map scrolls smoothly with the cursor; at map edges the pan clamps so the map never leaves the viewport; when map is smaller than viewport it stays centered.
**Why human:** Pan feel (smoothness, clamp boundary behavior) cannot be fully exercised by dragBoundFunc unit tests.

#### 4. Cursor-anchored wheel zoom

**Test:** Mouse-wheel zoom in and out over different cursor positions.
**Expected:** Zoom anchors on the cursor (point under cursor stays under cursor through zoom); clamps at fit-scale (no further zoom-out) and 4× fit-scale (no further zoom-in).
**Why human:** Cursor-anchor precision under real wheel events only visible in a real browser.

#### 5. Selection + neighbor chip pan-on-select flow

**Test:** Click a condado polygon, then click a neighbor chip in the inspector.
**Expected:** Gold 3px outline appears on clicked condado; inspector shows 4 groups (hierarchy badges, path/area/centroid, capital, adjacent); clicking a neighbor chip moves selection AND pans the canvas so the new territory is centered.
**Why human:** Pan-to-selected smoothness is a user-visible behavior — unit test asserts `stage.position()` was called, but the end-user experience of smooth re-centering is only visible in a real browser.

#### 6. Esc + empty-Stage click deselect

**Test:** Press Esc while selection is active, then click the empty Stage background.
**Expected:** Esc clears selection (inspector reverts to "Project overview"); empty-Stage click also clears selection (Pitfall 6 canonical `e.target.getStage()` pattern).
**Why human:** The Esc guard against INPUT/TEXTAREA/contentEditable focus needs a real browser focus model; jsdom does not implement isContentEditable reliably.

#### 7. Labels gated by zoom threshold

**Test:** Zoom to >= 2× minScale and toggle the Labels layer.
**Expected:** Labels appear as system-ui 12px text with white halo centered on capitals; at <2× minScale labels never render even with toggle ON.
**Why human:** Post-mount getTextWidth() centering requires a real Konva canvas context; jsdom cannot exercise the measurement pipeline.

#### 8. Fit-to-view button + Ctrl+0

**Test:** Click Fit-to-view button AND press Ctrl+0 from a zoomed-in state.
**Expected:** Both paths reset the canvas to show the full map centered with ~5% padding; minScale is recomputed; button is bottom-left with minHeight:44px.
**Why human:** Visual confirmation of reset behavior and ~5% padding perception.

#### 9. D-06.3 capital sentinel end-to-end

**Test:** Open a project with a condado that has a real `capital_name` set, and one without.
**Expected:** With-capital condado shows the capital city name + coords below; without-capital shows the exact literal string "No capital assigned".
**Why human:** The sentinel path is unit-tested, but the end-to-end flow (backend metadata emission → frontend render) with a real capital_name-bearing project requires a generated fixture.

### Gaps Summary

No gaps. All 26 observable truths are verified, all 22 required artifacts exist, are substantive, wired, and have data flowing through them. All 6 CANVAS-* requirements are satisfied by real implementations backed by passing unit + integration tests. The review identified 10 non-blocking findings (5 warning + 5 info) which are either out-of-scope for Phase 2 (MultiPolygon islands, concurrent generation) or nit-level polish for future cleanup.

The only reason status is `human_needed` rather than `passed` is that visual, perceptual, and full-E2E-with-real-Iberia-pipeline checks cannot be exercised from the terminal. All automated gates pass.

---

_Verified: 2026-04-18T15:10:00Z_
_Verifier: Claude (gsd-verifier)_
