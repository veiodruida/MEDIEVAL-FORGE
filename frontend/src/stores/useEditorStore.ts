import { create } from 'zustand'
import type { EditorState, ToolMode, SplitSubMode, UndoLabel } from '../types/editing'

interface EditorStore extends EditorState {
  // --- actions ---
  toggleEditMode: () => void
  setEditMode: (on: boolean) => void
  setActiveTool: (tool: ToolMode) => void
  setSplitSubMode: (mode: SplitSubMode) => void
  setVertexEditCondadoId: (id: string | null) => void
  setRubberBandSelectionIds: (ids: string[]) => void
  clearRubberBandSelection: () => void

  // --- Named undo/redo label stack (Pitfall 7) ---
  // zundo does NOT store metadata. We maintain a parallel array synchronized
  // with the temporal history. Call pushUndoLabel AFTER endTransaction (in the
  // wiring layer). Undo pops from undoLabels → pushes to redoLabels; Redo inverts.
  pushUndoLabel: (label: UndoLabel) => void
  popUndoLabel: () => UndoLabel | undefined         // called on undo()
  popRedoLabel: () => UndoLabel | undefined         // called on redo()
  clearLabels: () => void
}

/**
 * useEditorStore — tool/edit state + named undo labels.
 *
 * MUST NOT be wrapped with `temporal`. These fields are transient UI state that
 * the user should never undo (Research §Architecture Patterns: "Only useProjectStore
 * gets the temporal wrapper"). Partialize in useProjectStore excludes all of these
 * by virtue of them living in a separate store.
 */
export const useEditorStore = create<EditorStore>()((set) => ({
  editMode: false,
  activeTool: 'none',
  splitSubMode: 'snap',
  vertexEditCondadoId: null,
  rubberBandSelectionIds: [],
  undoLabels: [],
  redoLabels: [],

  toggleEditMode: () => set((s) => ({ editMode: !s.editMode })),
  setEditMode: (on) => set({ editMode: on }),
  setActiveTool: (tool) => set({ activeTool: tool }),
  setSplitSubMode: (mode) => set({ splitSubMode: mode }),
  setVertexEditCondadoId: (id) => set({ vertexEditCondadoId: id }),
  setRubberBandSelectionIds: (ids) => set({ rubberBandSelectionIds: ids }),
  clearRubberBandSelection: () => set({ rubberBandSelectionIds: [] }),

  // Any new recorded action clears the redo stack — matches zundo behavior
  pushUndoLabel: (label) =>
    set((s) => ({ undoLabels: [...s.undoLabels, label], redoLabels: [] })),

  popUndoLabel: () => {
    let popped: UndoLabel | undefined
    set((s) => {
      if (s.undoLabels.length === 0) return {}
      popped = s.undoLabels[s.undoLabels.length - 1]
      return {
        undoLabels: s.undoLabels.slice(0, -1),
        redoLabels: [...s.redoLabels, popped],
      }
    })
    return popped
  },

  popRedoLabel: () => {
    let popped: UndoLabel | undefined
    set((s) => {
      if (s.redoLabels.length === 0) return {}
      popped = s.redoLabels[s.redoLabels.length - 1]
      return {
        redoLabels: s.redoLabels.slice(0, -1),
        undoLabels: [...s.undoLabels, popped],
      }
    })
    return popped
  },

  clearLabels: () => set({ undoLabels: [], redoLabels: [] }),
}))
