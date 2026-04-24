---
phase: 04-canvas-editing-basic
reviewed: 2026-04-24T12:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - frontend/src/api/edit.ts
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/InspectorSidebar.tsx
  - frontend/src/components/canvas/SaveStatusIndicator.tsx
  - frontend/src/components/canvas/SelectionFloatingToolbar.tsx
  - frontend/src/components/canvas/SettingsPanel.tsx
  - frontend/src/components/canvas/SplitTool.tsx
  - frontend/src/components/canvas/ValidationBadgesLayer.tsx
  - frontend/src/hooks/useBeforeUnloadGuard.ts
  - frontend/src/hooks/useUndoShortcut.ts
  - frontend/src/main.tsx
  - frontend/src/pages/ProjectDetail.tsx
  - frontend/src/services/persistence.ts
  - frontend/src/services/validation.ts
  - frontend/src/stores/useValidationStore.ts
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-04-24T12:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 04 delivers the canvas editing pipeline: capital drag with Voronoi recalc, border vertex editing, territory merge and split, configurable persistence (auto/per_op/explicit), real-time validation badges, and 50-step named undo/redo. The overall structure is solid — the compound-transaction pattern, the zundo integration, the API layer, and the persistence store are all well-implemented. No security vulnerabilities or hardcoded secrets were found.

The VERIFICATION.md (dated 2026-04-24T11:15) identified a BLOCKER gap where TerritoryLayer/DecorationsLayer was disconnected from edit mutations. That gap was closed within Phase 08 via `invalidateCanvasArtifacts()` (CanvasViewer.tsx:171) and a `temporal.subscribe` handler (CanvasViewer.tsx:461). The canvas render path now re-fetches updated geometry after each edit.

Four warnings and three info items were identified. The most significant are: a double-invocation of `endTransaction()` on every vertex-edit session exit (WR-01), and `pushUndoLabel` firing synchronously before API success is confirmed during vertex-edit commit (WR-02). Both cause undo label/history desync in normal editing flows.

---

## Warnings

### WR-01: Double `endTransaction()` on every vertex-edit session exit

**File:** `frontend/src/components/canvas/CanvasViewer.tsx:413-454`

**Issue:** The `useEffect` cleanup function (lines 448–451) fires on every dependency change, not only on component unmount. When `vertexEditId` transitions from `"X"` to `null` during normal editing, React executes the cleanup from the prior render before running the new effect body. At cleanup time `prevVertexEditIdRef.current` is still `"X"`, so `endTransaction()` (i.e., `temporal.resume()`) fires once. Then the new effect body runs, hits the commit branch, and calls `endTransaction()` again at line 443.

The patched `resume()` in `useProjectStore.ts` nulls `prePauseSnapshot` on the first call, so the second call does not produce a duplicate undo history entry. However, it does re-enable `isTracking` after it was already re-enabled. Any state mutation occurring between the two `resume()` calls falls inside an unintended open-tracking window and gets recorded as a standalone undo entry outside the transaction boundary.

**Fix:** Guard the cleanup so it fires only when the component is unmounting or when the session began but was never closed:

```typescript
const didBeginRef = useRef(false)

useEffect(() => {
  const prev = prevVertexEditIdRef.current
  const curr = vertexEditId

  if (!prev && curr) {
    beginTransaction()
    didBeginRef.current = true
  }

  if (prev && !curr && projectId) {
    // ... commit logic unchanged ...
    endTransaction()   // single call — cleanup below will not duplicate this
    didBeginRef.current = false
    pushUndoLabel(`Editar vértice — ${condado?.name ?? prev}`)
  }

  prevVertexEditIdRef.current = curr

  return () => {
    // Only runs if the session was opened and never closed (e.g. unmount mid-drag)
    if (didBeginRef.current) {
      endTransaction()
      didBeginRef.current = false
    }
  }
}, [vertexEditId, ...])
```

---

### WR-02: `pushUndoLabel` fires before `reshapeGeometry` API success is confirmed

**File:** `frontend/src/components/canvas/CanvasViewer.tsx:425-444`

**Issue:** `reshapeGeometry()` is launched as a floating promise with `.then/.catch` attached. `endTransaction()` (line 443) and `pushUndoLabel()` (line 444) execute synchronously after the promise is launched, before the PATCH completes. If the backend returns an error, the undo label is pushed into the editor store anyway, but no matching geometry change was committed to zundo history (the pre-pause snapshot captured by `beginTransaction()` and the post-op state are equal — the PATCH failed, so no net change). This leaves the label stack one entry ahead of the temporal history, causing mismatched labels on all subsequent Ctrl+Z presses.

Compare with `handleCapitalDragEnd` (lines 360–376) which correctly `await`s the API call and pushes the label only on success.

**Fix:** Move label push into the `.then()` callback:

```typescript
if (geom && geom.type === 'Polygon') {
  reshapeGeometry(projectId, prev, { geometry: geom }, { persist })
    .then(() => {
      onOperationFinalized()
      invalidateCanvasArtifacts()
      const storeState = {
        territories: useProjectStore.getState().territories,
        capitals: useProjectStore.getState().capitals,
      }
      setIssuesForIds([prev], validateTerritories([prev], storeState))
      pushUndoLabel(`Editar vértice — ${condado?.name ?? prev}`)  // moved here
    })
    .catch((err) => {
      console.error('reshapeGeometry failed', err)
      // label not pushed on failure — no history entry to name
    })
}
endTransaction()
// pushUndoLabel removed from synchronous path
```

---

### WR-03: Merge revalidation omits neighbors of removed territories

**File:** `frontend/src/components/canvas/SelectionFloatingToolbar.tsx:100-116`

**Issue:** After a successful merge, `validateTerritories` is called with `[response.merged_id]` only (line 101). D-06 specifies: "re-validate only the affected territories and their immediate neighbors." The merged-away territories were previously adjacency neighbors of other condados. After merge their border topology changes, so their former neighbors can acquire new `capital_outside` or `polygon_invalid` conditions that are never caught until the next operation touches those condados. The validation badge layer then shows stale state for those neighbors.

**Fix:** Extend the affected set to include neighbors of the removed territories:

```typescript
const removedNeighbors = response.removed_ids.flatMap(id =>
  condados.find(c => c.id === id)?.neighbors ?? []
).filter(nId => nId !== response.merged_id)

const mergedAffected = [response.merged_id, ...new Set(removedNeighbors)]
const mergeIssues: ValidationIssue[] = validateTerritories(mergedAffected, storeState)
```

---

### WR-04: `MultiPolygon` capital validation ignores inner ring holes

**File:** `frontend/src/services/validation.ts:82-109`

**Issue:** In the `MultiPolygon` branch, `pointInPolygon` is called only with `polygon[0]` (the exterior ring). Inner rings (`polygon[1..n]`, representing holes) are not checked. A capital positioned geometrically inside a hole — a subtracted region — passes the exterior-ring test and does not trigger `capital_outside`. This is a correctness gap that would allow invalid states to be exported.

**Fix:** After confirming the capital is inside the exterior ring, verify it is not inside any hole:

```typescript
const inExterior = capital && pointInPolygon(capital, exterior)
const inHole = inExterior && polygon.slice(1).some(
  (hole) => pointInPolygon(capital, hole)
)
if (inExterior && !inHole) {
  capitalFound = true
}
```

---

## Info

### IN-01: `Ctrl+S` silently consumes the keystroke in `auto`/`per_op` strategies

**File:** `frontend/src/hooks/useUndoShortcut.ts:37-42`

**Issue:** `e.preventDefault()` is called unconditionally for Ctrl+S/Cmd+S regardless of save strategy. `manualSave()` immediately returns without side-effects when strategy is not `explicit`. The browser's native save dialog is suppressed, but the user gets no feedback. A user pressing Ctrl+S in auto or per_op mode will see nothing happen.

**Fix:** Gate `preventDefault` on the strategy being `explicit`, or show a brief informational toast in other modes. Accepting the silent no-op is also valid but warrants a code comment explaining the intent.

---

### IN-02: `navigator.platform` is deprecated

**File:** `frontend/src/hooks/useUndoShortcut.ts:21`

**Issue:** `navigator.platform` has been deprecated since Chrome 118 and may generate console warnings in future browser versions.

**Fix:**
```typescript
// Replace:
const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform)
// With:
const isMac = typeof navigator !== 'undefined' && navigator.userAgent.includes('Mac')
```

---

### IN-03: Merge primary territory selection is unresolved with no backlog entry

**File:** `frontend/src/components/canvas/SelectionFloatingToolbar.tsx:85-86`

**Issue:** `primary_id = selectionIds[0]` uses the first rubber-band–selected condado as the merge primary. The `TODO(P08)` comment notes this should use the largest-area territory instead. ROADMAP.md does not define a P09 or any later phase that closes this. The correct geometry to compute the largest area is already available in `useProjectStore.getState().territories`.

**Suggestion:** Either compute the primary from polygon area using the shoelace formula at merge time, or create an explicit backlog item so this does not silently remain as a known deviation.

---

_Reviewed: 2026-04-24T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
