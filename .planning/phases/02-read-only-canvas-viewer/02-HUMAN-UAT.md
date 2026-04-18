---
status: partial
phase: 02-read-only-canvas-viewer
source: [02-VERIFICATION.md]
started: 2026-04-18T00:00:00Z
updated: 2026-04-18T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Condado fills match lookup_condado_colors.json
expected: Open a generated Iberia project at /projects/:id. Every condado polygon renders with the exact hex color from `lookup_condado_colors.json` — pixel-parity with `terrain.png` (no color drift from the Unity palette).
result: [pending]

### 2. Barony overlay toggle
expected: Borders layer toggle flips barony overlay on/off. When ON, baronies render at 85% opacity with a subtle internal stroke (rgba(0,0,0,0.25), 0.5px). Baronies are NOT clickable (listening=false).
result: [pending]

### 3. Drag-pan smoothness + edge clamp
expected: Click-and-drag the Stage pans the canvas. At edges, `dragBoundFunc` clamps so the map cannot be dragged beyond its bounds. Movement feels smooth (no stutter or snap-back).
result: [pending]

### 4. Cursor-anchored wheel zoom + scale clamp
expected: Mouse wheel zooms in/out anchored to cursor position (not canvas center). Min scale = fit-to-view; max scale = 4× min. Wheel stops zooming at the clamps.
result: [pending]

### 5. Click-select + neighbor chip pan-on-select
expected: Click any condado → gold selection outline appears. Click a neighbor chip in the InspectorSidebar → selection moves to that condado AND canvas pans to center the new selection. Zoom level is preserved during pan-on-select (does not reset).
result: [pending]

### 6. Esc + empty-Stage click deselect
expected: Pressing Esc clears the selection. Clicking empty Stage area (not on any territory) also clears selection. InspectorSidebar returns to its empty/default state.
result: [pending]

### 7. Label gate at 2× minScale threshold
expected: Labels layer ON + zoom below 2× minScale → no labels visible. Zoom ≥ 2× minScale → condado labels become visible with the D-04 dual-ring capital markers. Labels remain legible (no overlap with capital dots).
result: [pending]

### 8. Fit-to-view button + Ctrl/Cmd+0 shortcut
expected: Clicking FitToViewButton OR pressing Ctrl+0 (Cmd+0 on Mac) resets the view: scale → minScale, position → centered with 5% padding. Works from any zoomed/panned state.
result: [pending]

### 9. D-06.3 capital sentinel end-to-end
expected: Select a condado with a defined `capital_name` → InspectorSidebar shows the capital name. Select a condado with undefined/empty/whitespace `capital_name` → InspectorSidebar shows the "No capital assigned" sentinel text.
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps
