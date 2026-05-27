import { useEffect } from 'react'
import { useUIStore } from '../stores/uiStore'
import { useEditorStore } from '../stores/useEditorStore'
import type { EditTool } from '../stores/useEditorStore'

/**
 * Window-level keyboard shortcuts for the canvas viewer.
 *
 * Phase 03 shortcuts (unchanged):
 *   - Ctrl/Cmd+0 → call onFitToView() and preventDefault()
 *   - Esc (no active editor tool) → clear territory selection
 *
 * Phase 08 Plan 05 additions (UX-01 / D-32):
 *   - V → selectTool('V')  (Vertex move)
 *   - A → selectTool('A')  (Add vertex)
 *   - D → selectTool('D')  (Delete vertex)
 *   - S → selectTool('S')  (Split polygon)
 *   - M → selectTool('M')  (Merge polygon)
 *   - Esc → selectTool(null) (deactivate active editor tool)
 *   - Ctrl+Z → temporal.undo()
 *   - Ctrl+Shift+Z → temporal.redo()
 *   - Delete → deleteVertices(selectedVertexIds) when any selected
 *
 * All Phase 08 shortcuts are guarded: inactive when document.activeElement
 * is an INPUT, TEXTAREA, SELECT, or contentEditable element (UX-01).
 */
export function useKeyboardShortcuts(onFitToView: () => void): void {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ctrl/Cmd+0 — fit to view (Phase 03, always active)
      if (e.key === '0' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        onFitToView()
        return
      }

      // ── editable-element guard (UX-01) ──────────────────────────────────
      // All remaining shortcuts are inactive when focus is in a form element.
      const el = document.activeElement as HTMLElement | null
      if (el) {
        const tag = el.tagName
        const editable =
          el.isContentEditable ||
          el.getAttribute?.('contenteditable') === 'true' ||
          el.getAttribute?.('contenteditable') === ''
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || editable) {
          // Fall through only for Escape (Phase 03 selection clear — unchanged behavior)
          if (e.key !== 'Escape') return
          // For Escape in editable: let browser handle it (don't clear selection)
          return
        }
      }

      // ── Phase 08 undo/redo (D-25, UNDO-01) ─────────────────────────────
      if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        if (e.shiftKey) {
          // Ctrl+Shift+Z → redo
          useEditorStore.temporal.getState().redo()
        } else {
          // Ctrl+Z → undo
          useEditorStore.temporal.getState().undo()
        }
        return
      }

      // ── Phase 08 editor tool shortcuts (D-32) ──────────────────────────
      const TOOL_KEYS: Record<string, EditTool> = {
        v: 'V',
        a: 'A',
        d: 'D',
        s: 'S',
        m: 'M',
      }
      const toolKey = e.key.toLowerCase()
      if (toolKey in TOOL_KEYS && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault()
        useEditorStore.getState().selectTool(TOOL_KEYS[toolKey])
        return
      }

      // ── Delete key — remove selected vertices (D-29) ───────────────────
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const { selectedVertexIds, deleteVertices } = useEditorStore.getState()
        if (selectedVertexIds.length > 0) {
          e.preventDefault()
          deleteVertices(selectedVertexIds)
        }
        return
      }

      // ── Escape — deactivate active editor tool OR clear territory selection
      if (e.key === 'Escape') {
        const { activeTool, selectTool } = useEditorStore.getState()
        if (activeTool !== null) {
          // Phase 08: dismiss active editor tool first
          selectTool(null)
        } else {
          // Phase 03 fallback: clear territory selection
          useUIStore.getState().select(null)
        }
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onFitToView])
}
