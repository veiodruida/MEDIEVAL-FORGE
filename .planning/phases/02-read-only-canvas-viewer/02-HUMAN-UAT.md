---
status: partial
phase: 02-read-only-canvas-viewer
source: [02-VERIFICATION.md]
started: 2026-04-18T00:00:00Z
updated: 2026-04-18T18:29:24Z
---

## Current Test

[awaiting human re-test against a freshly generated Iberia project after plan 02-04 gap closure (G-01/G-02/G-03 closed)]

## Tests

### 1. Condado fills match lookup_condado_colors.json
expected: Open a generated Iberia project at /projects/:id. Every condado polygon renders with the exact hex color from `lookup_condado_colors.json` — pixel-parity with `terrain.png` (no color drift from the Unity palette).
result: pending
note: Previously FAILED (G-01 format mismatch). Plan 02-04 rewrote `emit_territories_from_disk` to parse the real `{"r,g,b": idx}` format and emit `condado_colors.json` sidecar. Frontend now consumes `condado_colors.json` (Record<id, "#hex">). Re-run against a freshly generated project.

### 2. Barony overlay toggle
expected: Borders layer toggle flips barony overlay on/off. When ON, baronies render at 85% opacity with a subtle internal stroke (rgba(0,0,0,0.25), 0.5px). Baronies are NOT clickable (listening=false).
result: pending
note: Previously BLOCKED (depended on G-01). `emit_baronies_from_disk` is fixed and emits `barony_colors.json` sidecar. Re-run after fresh generation.

### 3. Drag-pan smoothness + edge clamp
expected: Click-and-drag the Stage pans the canvas. At edges, `dragBoundFunc` clamps so the map cannot be dragged beyond its bounds. Movement feels smooth (no stutter or snap-back).
result: pending

### 4. Cursor-anchored wheel zoom + scale clamp
expected: Mouse wheel zooms in/out anchored to cursor position (not canvas center). Min scale = fit-to-view; max scale = 4× min. Wheel stops zooming at the clamps.
result: pending

### 5. Click-select + neighbor chip pan-on-select
expected: Click any condado → gold selection outline appears. Click a neighbor chip in the InspectorSidebar → selection moves to that condado AND canvas pans to center the new selection. Zoom level is preserved during pan-on-select (does not reset).
result: pending
note: Previously BLOCKED (no polygons rendered). Now unblocked.

### 6. Esc + empty-Stage click deselect
expected: Pressing Esc clears the selection. Clicking empty Stage area (not on any territory) also clears selection. InspectorSidebar returns to its empty/default state.
result: pending

### 7. Label gate at 2× minScale threshold
expected: Labels layer ON + zoom below 2× minScale → no labels visible. Zoom ≥ 2× minScale → condado labels become visible with the D-04 dual-ring capital markers. Labels remain legible (no overlap with capital dots).
result: pending
note: Previously BLOCKED. Now unblocked.

### 8. Fit-to-view button + Ctrl/Cmd+0 shortcut
expected: Clicking FitToViewButton OR pressing Ctrl+0 (Cmd+0 on Mac) resets the view: scale → minScale, position → centered with 5% padding. Works from any zoomed/panned state.
result: pending

### 9. D-06.3 capital sentinel end-to-end
expected: Select a condado with a defined `capital_name` → InspectorSidebar shows the capital name. Select a condado with undefined/empty/whitespace `capital_name` → InspectorSidebar shows the "No capital assigned" sentinel text.
result: pending
note: Previously BLOCKED. Now unblocked.

### 10. G-02 error propagation through FastAPI status machine
expected: Trigger a deliberate emitter failure (e.g., corrupt `lookup_condado_colors.json` to invalid format). Run generation. The FastAPI background task in `api/generate.py` should set project status to `error_generating` with `last_error` populated — the failure must be observable, not silently swallowed.
result: pending
note: Closure path for G-02 (silent swallow). Automated test `test_emitter_error_propagates_to_caller` proves the ValueError bubbles to `_run_pipeline_sync` callers; this UAT confirms the FastAPI background-task layer surfaces it to the user-facing project status.

## Summary

total: 10
passed: 0
issues: 0
pending: 10
skipped: 0
blocked: 0

## Gaps

(All prior gaps closed by plan 02-04.)
- G-01: RESOLVED — adapter rewrite at `territories_geojson.py:160-177` and `baronies_geojson.py:93-113` parses real `{"r,g,b": idx}` format. 5 new unit tests cover happy path / malformed-key ValueError / out-of-range idx skip.
- G-02: RESOLVED — try/except removed from `generator.py:349-356`; emitters propagate errors. `test_emitter_error_propagates_to_caller` PASSES.
- G-03: RESOLVED — `backend/tests/test_generator_e2e.py` (164 lines, 2 tests, 4 [BLOCKING] assertions) exercises real `run_generation → lookup_*_colors.json → emit_*_from_disk → territories.geojson + baronies.geojson + sidecars` path. PASSES.
