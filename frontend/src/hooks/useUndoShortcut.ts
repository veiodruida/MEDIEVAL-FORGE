import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useProjectStore } from '../stores/useProjectStore'
import { useEditorStore } from '../stores/useEditorStore'
import { manualSave } from '../services/persistence'

/**
 * Binds Ctrl+Z / Ctrl+Y (Cmd+Z / Cmd+Y on macOS) to zundo temporal.undo/redo.
 *
 * Pitfall 7 (Research): zundo does NOT store metadata. We maintain a parallel
 * label stack in useEditorStore. Undo pops from undoLabels → pushes to redoLabels;
 * Redo inverts. Both operations must be kept in sync with temporal.undo/redo.
 *
 * Also handles Cmd+Shift+Z (macOS alternate redo binding).
 * Also handles Ctrl+S / Cmd+S → manualSave() flush (D-07 explicit strategy).
 *
 * Input guard: no-ops when focus is in INPUT / TEXTAREA / contentEditable.
 */
export function useUndoShortcut() {
  const queryClient = useQueryClient()
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform)
      const mod = isMac ? e.metaKey : e.ctrlKey

      if (!mod) return

      // Ignore when typing in form fields
      const target = e.target as HTMLElement | null
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return
      }

      if (e.key === 's' || e.key === 'S') {
        // Ctrl+S / Cmd+S: flush explicit-mode snapshot (D-07).
        // GAP-10: After successful flush, invalidate TanStack Query cache so
        // canvas re-renders with post-edit geometry. Mirrors CanvasViewer's
        // invalidateCanvasArtifacts pattern but runs ONLY in the explicit path
        // (CanvasViewer skips invalidation for explicit mode by design).
        e.preventDefault()
        void (async () => {
          try {
            await manualSave()
            const { projectId } = useProjectStore.getState()
            if (!projectId) return
            queryClient.invalidateQueries({ queryKey: ['territories-geojson', projectId] })
            queryClient.invalidateQueries({ queryKey: ['territory-metadata', projectId] })
          } catch (err) {
            // manualSave currently does not throw (catches internally and calls
            // markUnsaved), but guard defensively so a future throw does not
            // trigger invalidation of a stale/unsaved cache.
            // eslint-disable-next-line no-console
            console.error('Ctrl+S flush failed', err)
          }
        })()
        return
      }

      if (e.key === 'z' || e.key === 'Z') {
        if (e.shiftKey) {
          // Cmd+Shift+Z on Mac = redo (alternate binding)
          e.preventDefault()
          useProjectStore.temporal.getState().redo()
          useEditorStore.getState().popRedoLabel()
        } else {
          e.preventDefault()
          useProjectStore.temporal.getState().undo()
          useEditorStore.getState().popUndoLabel()
        }
      } else if (e.key === 'y' || e.key === 'Y') {
        e.preventDefault()
        useProjectStore.temporal.getState().redo()
        useEditorStore.getState().popRedoLabel()
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [queryClient])
}
