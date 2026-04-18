---
status: gaps_found
phase: 02-read-only-canvas-viewer
source: [02-VERIFICATION.md, human re-test 2026-04-18]
started: 2026-04-18T00:00:00Z
updated: 2026-04-18T18:55:00Z
---

## Current Test

[human re-test against generated Iberia project surfaced 4 new gaps after plan 02-04 — diagnosis below]

## Tests

### 1. Condado fills match lookup_condado_colors.json
expected: Open a generated Iberia project at /projects/:id. Every condado polygon renders with the exact hex color from `lookup_condado_colors.json` — pixel-parity with `terrain.png` (no color drift from the Unity palette).
result: FAILED
evidence: User screenshots show condados render in `#666666` fallback (visible when Borders layer is OFF). When Borders is ON, the colored polygons that appear are from `BaronyLayer` rendering on top — NOT from `TerritoryLayer`. Code path is correct (`useCanvasArtifacts.ts:86-97` returns 5-tuple with condado_colors at index 2; `CanvasViewer.tsx:68` destructures it correctly; `TerritoryLayer.tsx:42` reads `condadoColors[t.id] ?? '#666666'`). Suspected root cause: backend not emitting `condado_colors.json` with matching IDs, OR endpoint returns empty. Verify with `curl http://localhost:8000/api/projects/{id}/preview/condado_colors.json`. Maps to gap GAP-04.

### 2. Barony overlay toggle
expected: Borders layer toggle flips barony overlay on/off. When ON, baronies render at 85% opacity with a subtle internal stroke (rgba(0,0,0,0.25), 0.5px). Baronies are NOT clickable (listening=false).
result: pending
note: Toggle behavior likely works; deferred until Failure #5 (Stage sizing) is fixed so visual verification is possible.

### 3. Drag-pan smoothness + edge clamp
expected: Click-and-drag the Stage pans the canvas. At edges, `dragBoundFunc` clamps so the map cannot be dragged beyond its bounds. Movement feels smooth (no stutter or snap-back).
result: pending
note: Deferred — gated by Failure #5.

### 4. Cursor-anchored wheel zoom + scale clamp
expected: Mouse wheel zooms in/out anchored to cursor position (not canvas center). Min scale = fit-to-view; max scale = 4× min. Wheel stops zooming at the clamps.
result: pending
note: Deferred — minScale calculation depends on Stage dimensions (Failure #5).

### 5. Click-select + neighbor chip pan-on-select
expected: Click any condado → gold selection outline appears. Click a neighbor chip in the InspectorSidebar → selection moves to that condado AND canvas pans to center the new selection.
result: FAILED
evidence: User reports "click on a region opens a blank page". Most likely consequence of Failure #5 (Stage Sizing): Stage occupies only left ~800px of the viewport; clicks on the dead navy area at right hit `e.target === e.target.getStage()` at `CanvasViewer.tsx:186-193` → `select(null)` → InspectorSidebar reverts to project-overview state (which the user perceives as "blank"). Secondary suspect: missing `<ErrorBoundary>` around `InspectorSidebarWrapper` at `ProjectDetail.tsx:142` could silently hide errors. Maps to gap GAP-06 (primary) + GAP-07 (defensive).

### 6. Esc + empty-Stage click deselect
expected: Pressing Esc clears the selection. Clicking empty Stage area also clears selection. InspectorSidebar returns to its empty/default state.
result: pending
note: Deferred — gated by Failure #5.

### 7. Label gate at 2× minScale threshold
expected: Labels layer ON + zoom below 2× minScale → no labels visible. Zoom ≥ 2× minScale → condado labels become visible with the D-04 dual-ring capital markers.
result: FAILED (UX)
evidence: User reports "Labels does nothing." Working as designed — `DecorationsLayer.tsx:13,78-80` gates labels with `currentScale >= LABEL_ZOOM_THRESHOLD_RELATIVE * minScale` where threshold = 2.0. At default zoom (= minScale), labels never appear even with toggle ON. Failure #5 (wrong minScale) compounds this. Decision needed: lower threshold to 1.5× or 1.0×, OR add UI affordance (tooltip "Zoom in 2× to show labels"). Maps to gap GAP-08.

### 8. Fit-to-view button + Ctrl/Cmd+0 shortcut
expected: Clicking FitToViewButton OR pressing Ctrl+0 (Cmd+0 on Mac) resets the view: scale → minScale, position → centered with 5% padding.
result: pending
note: Deferred — `computeFitToView` reads `stage.width()`/`stage.height()`, both broken by Failure #5.

### 9. D-06.3 capital sentinel end-to-end
expected: Select a condado with a defined `capital_name` → InspectorSidebar shows the capital name. Select a condado with empty/whitespace `capital_name` → InspectorSidebar shows the "No capital assigned" sentinel text.
result: pending
note: Deferred — cannot reliably select condados until Failure #5 is fixed.

### 10. G-02 error propagation through FastAPI status machine
expected: Trigger a deliberate emitter failure. Run generation. The FastAPI background task should set project status to `error_generating` with `last_error` populated.
result: pending
note: Plan 02-04 closure path; automated test passes; manual confirmation deferred.

### 11. Stage canvas fills full viewport (NEW — discovered in re-test)
expected: The Konva Stage fills the entire central viewport between the left LayerTogglePanel and the right InspectorSidebar — no dead/empty area.
result: FAILED (CRITICAL)
evidence: User screenshots show map renders only in the LEFT half of the viewport; the right half between map and InspectorSidebar is dead navy color (Stage background visible). Root cause: `CanvasViewer.tsx:58` defaults props to `width = 800, height = 600`. `ProjectDetail.tsx:136` calls `<CanvasViewer projectId={...} />` WITHOUT passing dimensions. No `ResizeObserver` wired in `CanvasViewer`. Stage is hardcoded 800×600 regardless of viewport size. This is the keystone bug — it cascades into Failures #3, #4, #5, #6, #7, #8 (anything depending on correct Stage dimensions or minScale). Maps to gap GAP-05.

## Summary

total: 11
passed: 0
issues: 4
pending: 7 (six deferred behind keystone bug GAP-05)
skipped: 0
blocked: 0

## Gaps

### GAP-04 — TerritoryLayer renders #666666 (cores cinza)
severity: blocker
truth: TerritoryLayer falls back to `#666666` for every condado; Unity palette colors from `condado_colors.json` are not applied.
evidence: User screenshots (Borders OFF → all gray); frontend code is correct end-to-end. Suspected backend defect: `condado_colors.json` not produced, returns empty, or has IDs that don't match `territory_metadata.json`.
affects: [CANVAS-01, CANVAS-04]
fix_hint: First, live-verify endpoint with `curl /api/projects/{id}/preview/condado_colors.json`. If empty or 404 → fix `emit_territories_from_disk` sidecar emission. If populated but mismatched → fix ID join logic. Add a backend integration assertion that `condado_colors.json` keys ⊆ `territory_metadata.json` condado IDs.

### GAP-05 — Stage hardcoded to 800×600 (keystone bug)
severity: blocker
truth: `CanvasViewer.tsx` accepts `width`/`height` props with defaults (800, 600); `ProjectDetail.tsx:136` mounts it without passing dimensions; no `ResizeObserver` measures the actual container. Stage stays 800×600 regardless of viewport.
evidence: `CanvasViewer.tsx:58` (defaults), `CanvasViewer.tsx:219-220` (uses props directly as `viewportW`/`viewportH`), `CanvasViewer.tsx:235-236` (Stage created with `width={viewportW}`), `ProjectDetail.tsx:136` (no dimension props passed).
affects: [CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06]
fix_hint: Wire a `ResizeObserver` (or `useResizeObserver` hook) in `CanvasViewer` to measure its parent container. Update `viewportW`/`viewportH` from measured values. Re-call `setMinScale` and re-fit when dimensions change. Add a `useZoomPan` test for "stage resize triggers minScale recompute".

### GAP-06 — Click-select returns "blank" (likely consequence of GAP-05)
severity: blocker
truth: User clicks a condado → InspectorSidebar shows project-overview/empty state instead of selected condado details.
evidence: `CanvasViewer.tsx:186-193` deselects on `e.target === e.target.getStage()`. Because Stage only fills left ~800px (GAP-05), clicks in the right half (dead area) match this condition and clear the selection.
affects: [CANVAS-03, CANVAS-05]
fix_hint: Fixing GAP-05 should resolve GAP-06 directly (clicks will land on actual polygons). Verify after GAP-05 fix.

### GAP-07 — InspectorSidebar lacks ErrorBoundary (defensive)
severity: warning
truth: `ProjectDetail.tsx:142` mounts `InspectorSidebarWrapper` without a `<Suspense>` or `<ErrorBoundary>`. If `metaQ`/`territoriesQ` throws or suspends, the entire sidebar can vanish silently — appearing "blank" to the user.
evidence: `ProjectDetail.tsx:142` (no boundary), TanStack Query queries can throw on network/parse errors.
affects: [CANVAS-03]
fix_hint: Wrap `InspectorSidebarWrapper` in a `<react-error-boundary>` `<ErrorBoundary>` with a visible fallback ("Sidebar failed to load — see console") so silent failures become visible.

### GAP-08 — Labels zoom-gate UX mismatch
severity: warning
truth: Labels checkbox toggles state correctly, but `DecorationsLayer` only renders labels at `currentScale >= 2.0 * minScale`. At default zoom (= minScale), labels never appear even when toggle is ON. User perceives the toggle as broken.
evidence: `DecorationsLayer.tsx:13` (`LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0`), `:78-80` (gate logic). Working as designed but UX is opaque.
affects: [CANVAS-04]
fix_hint: Two options: (a) add a tooltip on the Labels checkbox: "Zoom in 2× to show labels" (preserves current threshold); (b) lower threshold to `1.5` or `1.0` so labels appear closer to default zoom. Decision: UX preference — recommend (a) plus a slight reduction to 1.5× as a compromise.

## Cross-cutting note

GAP-05 (Stage sizing) is the keystone. Fixing it likely resolves GAP-06 directly and unblocks human re-verification of items #2, #3, #4, #6, #8, #9. Recommended fix order: GAP-05 → GAP-04 → GAP-08 → GAP-07.
