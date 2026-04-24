---
phase: 04-canvas-editing-basic
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 30
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-04-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 30
**Status:** issues_found

## Summary

Phase 4 introduces six backend edit endpoints (recalc, merge, split, reshape, vertex-handles, snapshot) and the full frontend canvas editor (rubber-band multi-select, merge toolbar, split tool, vertex-handle drag). The implementation is structurally sound and well-organized: atomic GeoJSON writes, proper transaction wrapping in most paths, zundo temporal middleware correctly integrated, and TypeScript strict mode enforced throughout.

One critical bug was found in the split endpoint: the new second territory inherits the original's capital coordinates, which is incorrect after the polygon is divided. Four warnings cover missing `finally` guards that can leave the temporal store permanently paused, a stale-closure read on freehand drawing completion, a fire-and-forget PATCH that pushes an undo label before confirming backend success, and a bare-click handler that silently clobbers existing rubber-band selections. Four info items cover dead code, a deprecated browser API, a fragile dynamic import, and a missing geometry validation.

---

## Critical Issues

### CR-01: Split territory inherits original capital coordinates for new_b

**File:** `backend/medieval_forge/api/edit.py:158-163`

**Issue:** After a territory is split into two halves, `new_b` is constructed using `**territories[condado_id]`, which copies `lon` and `lat` (the original territory's capital position) verbatim. The capital can only be geometrically inside one of the two resulting polygons. The other half immediately fails the `capital_outside` validation rule with no way to recover without a manual capital move. This means every split operation is guaranteed to produce a validation error on one of the two output territories.

**Fix:**
```python
# Compute a safe interior point for new_b using Shapely's representative_point()
new_b_shape = shape(new_b["geometry"])
rep = new_b_shape.representative_point()

territories[new_b_id] = {
    **territories[condado_id],
    "geometry": new_b["geometry"],
    "id": new_b_id,
    "name": territories[condado_id].get("name", "") + " (split)",
    "lon": rep.x,   # override with a point guaranteed inside new_b
    "lat": rep.y,
}
```

Apply the same fix symmetrically to `new_a` to be safe:
```python
new_a_shape = shape(new_a["geometry"])
rep_a = new_a_shape.representative_point()
territories[condado_id] = {
    **territories[condado_id],
    "geometry": new_a["geometry"],
    "lon": rep_a.x,
    "lat": rep_a.y,
}
```

---

## Warnings

### WR-01: Missing `finally` in merge handler leaves temporal store paused on exception

**File:** `frontend/src/components/canvas/SelectionFloatingToolbar.tsx`

**Issue:** `handleMerge` calls `beginTransaction()` (which pauses zundo temporal recording) but uses separate `endTransaction()` calls in the `catch` block and at the end of the success path rather than in `finally`. If any statement after the `try` block throws, `endTransaction()` is never called. The temporal store remains paused indefinitely, making undo completely non-functional for the rest of the session.

**Fix:**
```tsx
beginTransaction()
try {
  // ... merge logic ...
  pushUndoLabel(label)
  onOperationFinalized()
  clearSelection()
} catch (err) {
  console.error('mergeTerritories failed', err)
  return
} finally {
  endTransaction()   // always runs, whether success or failure
}
```

---

### WR-02: Freehand `onStageMouseUp` reads stale `points` closure

**File:** `frontend/src/components/canvas/SplitTool.tsx:169-179`

**Issue:** `onStageMouseUp` captures `points` from the render-time closure. During freehand drawing, `setPoints` uses functional updates that do not synchronously update the closed-over `points` value. When `mouseup` fires, `points` may be missing the final batched state updates, causing spurious 422 "cut does not bisect" errors.

**Fix:** Use a `ref` to track the live point list in parallel with state:
```tsx
const pointsRef = useRef<Array<[number, number]>>([])

// In onStageMouseMove, update both:
setPoints((prev) => {
  const next = [...prev, [pos.x, pos.y]]
  pointsRef.current = next
  return next
})

// In onStageMouseUp, read from ref (always current):
const sampled = pointsRef.current.filter((_, i) => i % 4 === 0)
void commit(sampled)
pointsRef.current = []
```

---

### WR-03: Vertex-edit PATCH is fire-and-forget; undo label pushed before backend confirms

**File:** `frontend/src/components/canvas/CanvasViewer.tsx:406-431`

**Issue:** `reshapeGeometry` is called without `await` — `endTransaction()` and `pushUndoLabel(...)` execute synchronously unconditional on the PATCH outcome. If the backend errors, the undo stack contains a label for an operation the server never accepted, creating persistent client/server geometry drift.

**Fix:** Move `endTransaction` and `pushUndoLabel` into the `.then()` callback, with rollback in `.catch()`.

---

### WR-04: Bare click on empty canvas clobbers existing rubber-band selection

**File:** `frontend/src/hooks/useRubberBandSelection.ts:65-79`

**Issue:** `onMouseUp` calls `setRubberBandSelectionIds([])` unconditionally whenever `dragStartPos` is set, regardless of whether the mouse moved enough to form a selection. A single click anywhere discards any existing multi-territory selection before the user can act on it (e.g. click Fundir).

**Fix:** Only update selection if drag exceeded a threshold:
```tsx
const didDrag =
  pos &&
  (Math.abs(pos.x - dragStartPos.x) > 4 || Math.abs(pos.y - dragStartPos.y) > 4)

if (didDrag) {
  // ... existing selection logic ...
}
// If no drag, leave existing selection intact
```

---

## Info

### IN-01: Dead code branch in VertexHandlesLayer ring-closure sync

**File:** `frontend/src/components/canvas/VertexHandlesLayer.tsx:79`

**Issue:** Branch `if (sourceIndex === newRing.length - 1) newRing[0] = [lon, lat]` is unreachable — the backend strips the closing duplicate (`ring[:-1]`) before generating handles, so no handle will ever have `source_index` equal to `newRing.length - 1`.

---

### IN-02: Deprecated `navigator.platform` for macOS detection

**File:** `frontend/src/hooks/useUndoShortcut.ts:21`

**Issue:** `navigator.platform` deprecated since Chrome 118. **Fix:** Use `navigator.userAgentData?.platform` with fallback.

---

### IN-03: Fragile dynamic icon lookup in EditToolbar

**File:** `frontend/src/components/canvas/EditToolbar.tsx:11-14`

**Issue:** Icons resolved via `(Icons as Record<string, React.ComponentType>)[iconName]` — silently returns `undefined` if Radix renames an icon. Add a dev-mode `console.warn` guard.

---

### IN-04: Missing ring-closure check in `ReshapeGeometryRequest` validator

**File:** `backend/medieval_forge/schemas.py:157-168`

**Issue:** Validator doesn't verify `coordinates[0][0] === coordinates[0][-1]`. Shapely silently auto-closes open rings, so malformed GeoJSON can be stored and later break strict consumers (Unity importers, QGIS). **Fix:** Add explicit ring-closure assertion.

---

_Reviewed: 2026-04-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
