---
plan: 04-10
phase: 04-canvas-editing-basic
status: complete
gap_closure: true
requirements: [EDIT-01]
completed: 2026-04-24
---

## Summary

Closed the final SC1 explicit-mode gap: `useUndoShortcut.ts` Ctrl+S handler now awaits `manualSave()` and invalidates TanStack Query cache on success, so the canvas re-renders with post-edit geometry after a Ctrl+S flush — no manual page reload required.

## What Was Built

Single surgical change to `frontend/src/hooks/useUndoShortcut.ts`:

1. Added `import { useQueryClient } from '@tanstack/react-query'`
2. Called `useQueryClient()` inside the hook body to obtain `queryClient`
3. Replaced fire-and-forget `void manualSave()` with an async IIFE that:
   - `await manualSave()` inside a try block
   - On success: reads `projectId` from `useProjectStore.getState()` and calls `queryClient.invalidateQueries()` for both `['territories-geojson', projectId]` and `['territory-metadata', projectId]`
   - On failure (defensive): logs error, skips invalidation
4. Added `queryClient` to the `useEffect` dependency array

## Diff Summary

```diff
+ import { useQueryClient } from '@tanstack/react-query'
  import { useProjectStore } from '../stores/useProjectStore'
  ...
  export function useUndoShortcut() {
+   const queryClient = useQueryClient()
    useEffect(() => {
      ...
-       void manualSave()
+       void (async () => {
+         try {
+           await manualSave()
+           const { projectId } = useProjectStore.getState()
+           if (!projectId) return
+           queryClient.invalidateQueries({ queryKey: ['territories-geojson', projectId] })
+           queryClient.invalidateQueries({ queryKey: ['territory-metadata', projectId] })
+         } catch (err) {
+           console.error('Ctrl+S flush failed', err)
+         }
+       })()
-   }, [])
+   }, [queryClient])
```

## Confirmations

- `persistence.ts` NOT modified — zero react-query imports there (verified by grep)
- TypeScript: `cd frontend && npx tsc --noEmit` exited 0 — zero new errors
- `invalidateQueries` appears 2 times, both AFTER `await manualSave()` in source order
- `void manualSave()` bare pattern absent

## SC1 Closure Status

SC1 (explicit save mode) is now fully closed across all three save strategies:
- `auto` / `per_op`: already wired by Plan 09 via `invalidateCanvasArtifacts` in CanvasViewer
- `explicit`: wired by Plan 10 via Ctrl+S handler in useUndoShortcut

## Self-Check: PASSED
