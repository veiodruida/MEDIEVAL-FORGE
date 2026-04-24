---
status: partial
phase: 04-canvas-editing-basic
source: [04-VERIFICATION.md]
started: 2026-04-24T15:45:00Z
updated: 2026-04-24T15:45:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Capital drag re-renders in under 500ms (auto/per_op mode)
expected: Dragging a capital marker causes the affected neighbor Voronoi polygons to visually update on the Konva canvas within 500ms — no page reload required
result: [pending]

### 2. Vertex drag immediately reflected on canvas (auto/per_op mode)
expected: Dragging a border vertex reshapes the polygon outline on canvas without reload
result: [pending]

### 3. Merge result immediately visible (auto/per_op mode)
expected: After clicking Fundir on 2+ selected territories, a single merged polygon replaces the selected set on canvas without reload
result: [pending]

### 4. Ctrl+Z undoes capital drag as single compound step (visual)
expected: Pressing Ctrl+Z after a capital drag restores both the capital marker position and all affected neighbor polygon shapes in one step — no partial revert
result: [pending]

### 5. Ctrl+S in explicit save mode flushes and visually updates canvas (no reload)
expected: Pressing Ctrl+S with unsaved edits in explicit mode flips SaveStatusIndicator to 'Salvo' AND the canvas re-renders with post-edit geometry within 500ms
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
