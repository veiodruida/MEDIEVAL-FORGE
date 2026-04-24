import { useEffect } from 'react'
import { useEditorStore } from '../stores/useEditorStore'
import { useUIStore } from '../stores/uiStore'

/**
 * useEditKeyboardMap — Phase 4 keyboard shortcut map.
 *
 * Key bindings (UI-SPEC §"Keyboard Shortcut Map"):
 *   E         → toggleEditMode (any context; turns ON → activeTool='select', turns OFF → activeTool='none')
 *   V         → toggle vertex-edit mode (only if editMode && selectedTerritoryId)
 *   S         → toggle split tool (only if editMode && selectedTerritoryId)
 *   Escape    → exit sub-mode priority: vertex-edit > split > rubber-band > fall through
 *
 * Guards:
 *   - No-ops when focus is in INPUT / TEXTAREA / contentEditable (T-04-07-04)
 *   - Ctrl/Cmd/Alt modifier keys return early (delegate to useUndoShortcut + browser defaults)
 *   - V/S/Escape only active in editMode (except E which toggles editMode globally)
 *
 * Coexistence:
 *   - useKeyboardShortcuts (Phase 2) handles Ctrl+0 and Phase-2 Esc (deselect). Both are
 *     registered on window. This hook handles Esc for sub-mode exit; when none of the
 *     sub-mode conditions apply, stopImmediatePropagation is NOT called so the Phase-2
 *     Esc (deselect) fires as fallback.
 *   - useUndoShortcut handles Ctrl+Z / Ctrl+Y — the modifier guard here ensures no conflict.
 *   - The inline Esc handler in CanvasViewer (vertex-edit exit) is superseded by this hook;
 *     it can be removed as a cleanup task (dead code only — no behavioral regression).
 */
export function useEditKeyboardMap() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // T-04-07-04: don't intercept while typing in a form field
      const target = e.target as HTMLElement | null
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return
      }

      // Delegate Ctrl/Cmd/Alt combinations to their respective hooks (useUndoShortcut etc.)
      if (e.ctrlKey || e.metaKey || e.altKey) return

      const editor = useEditorStore.getState()
      const selectedId = useUIStore.getState().selectedTerritoryId

      // E — toggle edit mode (works in any context)
      if (e.key === 'e' || e.key === 'E') {
        e.preventDefault()
        editor.toggleEditMode()
        // When turning ON, set tool to 'select'; when turning OFF, reset to 'none'.
        // Read fresh state after toggle to get the updated editMode.
        const nowEdit = useEditorStore.getState().editMode
        editor.setActiveTool(nowEdit ? 'select' : 'none')
        return
      }

      // V / S / Escape require editMode to be active
      if (!editor.editMode) return

      // V — toggle vertex-edit mode for selected territory
      if ((e.key === 'v' || e.key === 'V') && selectedId) {
        e.preventDefault()
        editor.setVertexEditCondadoId(
          editor.vertexEditCondadoId ? null : selectedId,
        )
        return
      }

      // S — toggle split tool
      if ((e.key === 's' || e.key === 'S') && selectedId) {
        e.preventDefault()
        editor.setActiveTool(editor.activeTool === 'split' ? 'select' : 'split')
        return
      }

      // Escape — priority: vertex-edit > split > rubber-band > fall through to Phase-2 Esc
      if (e.key === 'Escape') {
        if (editor.vertexEditCondadoId) {
          e.preventDefault()
          editor.setVertexEditCondadoId(null)
          return
        }
        if (editor.activeTool === 'split') {
          e.preventDefault()
          editor.setActiveTool('select')
          return
        }
        if (editor.rubberBandSelectionIds.length > 0) {
          e.preventDefault()
          editor.clearRubberBandSelection()
          return
        }
        // Fall through: Phase-2 useKeyboardShortcuts Esc (deselect) handles remaining case
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
}
