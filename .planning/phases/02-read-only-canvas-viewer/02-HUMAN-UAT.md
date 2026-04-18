---
status: gaps_found
phase: 02-read-only-canvas-viewer
source: [02-VERIFICATION.md]
started: 2026-04-18T00:00:00Z
updated: 2026-04-18T18:00:00Z
---

## Current Test

[gap-closure planned — blocked on G-01 format mismatch fix]

## Tests

### 1. Condado fills match lookup_condado_colors.json
expected: Open a generated Iberia project at /projects/:id. Every condado polygon renders with the exact hex color from `lookup_condado_colors.json` — pixel-parity with `terrain.png` (no color drift from the Unity palette).
result: FAILED
evidence: User reports "imagem azul sem nada dentro" (blue empty canvas). Root cause: `territories_geojson.emit_territories_from_disk` (line 141–154) parses `lookup_condado_colors.json` assuming `{condado_id: "#rrggbb"}` schema, but the real `map_generator.py:672` writes `{"r,g,b": int_index}`. `hexstr[1:3]` then raises `TypeError: 'int' object is not subscriptable`. The exception is silently swallowed by the broad try/except at `generator.py:344`, so `territories.geojson` is never emitted and the frontend renders only the terrain background. Same defect in `baronies_geojson.py:78–81`. Tests pass because they exercise `build_territories_geojson` directly with an in-memory `pc` numpy array, never the disk-reading `emit_*_from_disk` codepath.

### 2. Barony overlay toggle
expected: Borders layer toggle flips barony overlay on/off. When ON, baronies render at 85% opacity with a subtle internal stroke (rgba(0,0,0,0.25), 0.5px). Baronies are NOT clickable (listening=false).
result: BLOCKED (depends on G-01 fix — `baronies.geojson` not emitted for same reason as #1)

### 3. Drag-pan smoothness + edge clamp
expected: Click-and-drag the Stage pans the canvas. At edges, `dragBoundFunc` clamps so the map cannot be dragged beyond its bounds. Movement feels smooth (no stutter or snap-back).
result: [pending — retest after G-01 fix; behavior doesn't require geojson but best tested against a populated canvas]

### 4. Cursor-anchored wheel zoom + scale clamp
expected: Mouse wheel zooms in/out anchored to cursor position (not canvas center). Min scale = fit-to-view; max scale = 4× min. Wheel stops zooming at the clamps.
result: [pending — retest after G-01 fix]

### 5. Click-select + neighbor chip pan-on-select
expected: Click any condado → gold selection outline appears. Click a neighbor chip in the InspectorSidebar → selection moves to that condado AND canvas pans to center the new selection. Zoom level is preserved during pan-on-select (does not reset).
result: BLOCKED (no polygons rendered — nothing to click on until G-01 is fixed)

### 6. Esc + empty-Stage click deselect
expected: Pressing Esc clears the selection. Clicking empty Stage area (not on any territory) also clears selection. InspectorSidebar returns to its empty/default state.
result: [pending — partially exercisable via empty-Stage click but not Esc-after-selection until G-01 is fixed]

### 7. Label gate at 2× minScale threshold
expected: Labels layer ON + zoom below 2× minScale → no labels visible. Zoom ≥ 2× minScale → condado labels become visible with the D-04 dual-ring capital markers. Labels remain legible (no overlap with capital dots).
result: BLOCKED (capitals rendered from `territory_metadata.json` may work but labels are visually tied to condado colors; retest with full pipeline after G-01)

### 8. Fit-to-view button + Ctrl/Cmd+0 shortcut
expected: Clicking FitToViewButton OR pressing Ctrl+0 (Cmd+0 on Mac) resets the view: scale → minScale, position → centered with 5% padding. Works from any zoomed/panned state.
result: [pending — independent of G-01; retest after gap-closure]

### 9. D-06.3 capital sentinel end-to-end
expected: Select a condado with a defined `capital_name` → InspectorSidebar shows the capital name. Select a condado with undefined/empty/whitespace `capital_name` → InspectorSidebar shows the "No capital assigned" sentinel text.
result: BLOCKED (cannot select a condado without territories.geojson — depends on G-01 fix)

## Summary

total: 9
passed: 0
issues: 1
pending: 4
skipped: 0
blocked: 4

## Gaps

- G-01: `emit_territories_from_disk` / `emit_baronies_from_disk` format mismatch with real `map_generator.py` output — see 02-VERIFICATION.md gaps[0]
- G-02: Broad try/except at `generator.py:344` silently swallows emitter errors — see 02-VERIFICATION.md gaps[1]
- G-03: No integration test exercises real generator → real emitter pipeline — see 02-VERIFICATION.md gaps[2]
