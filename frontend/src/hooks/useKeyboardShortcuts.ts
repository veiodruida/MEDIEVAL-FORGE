import { useEffect } from 'react'
import { useUIStore } from '../stores/uiStore'

/**
 * Window-level keyboard shortcuts for the canvas viewer:
 *   - Esc → clear selection (unless an editable element has focus)
 *   - Ctrl+0 / Cmd+0 → call onFitToView() and preventDefault()
 *
 * The editable-focus guard checks INPUT / TEXTAREA / contentEditable so that
 * typing in a form field and pressing Esc doesn't blow away an unrelated
 * territory selection. Matches UI-SPEC §Interaction Contracts (Keyboard).
 */
export function useKeyboardShortcuts(onFitToView: () => void): void {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ctrl+0 / Cmd+0 — fit to view
      if (e.key === '0' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        onFitToView()
        return
      }
      // Escape — clear selection (guarded)
      if (e.key === 'Escape') {
        const el = document.activeElement as HTMLElement | null
        if (el) {
          const tag = el.tagName
          // isContentEditable is the canonical check (true when element is currently editable,
          // considering inherited contenteditable). We also check the attribute explicitly
          // for jsdom (isContentEditable is not implemented there).
          const editable =
            el.isContentEditable ||
            el.getAttribute?.('contenteditable') === 'true' ||
            el.getAttribute?.('contenteditable') === ''
          if (tag === 'INPUT' || tag === 'TEXTAREA' || editable) {
            return
          }
        }
        useUIStore.getState().select(null)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onFitToView])
}
