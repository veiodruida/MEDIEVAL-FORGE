import { describe, it, expect, beforeEach } from 'vitest'
import { useEditorStore } from '../useEditorStore'  // will fail RED until P03

beforeEach(() => {
  // Reset to initial state before each test
  useEditorStore.setState({
    editMode: false,
    activeTool: 'none',
    splitSubMode: 'snap',
    vertexEditCondadoId: null,
    rubberBandSelectionIds: [],
    undoLabels: [],
    redoLabels: [],
  })
})

describe('useEditorStore — initial state', () => {
  it('starts with editMode=false, activeTool=none', () => {
    const state = useEditorStore.getState()
    expect(state.editMode).toBe(false)
    expect(state.activeTool).toBe('none')
  })

  it('toggleEditMode flips editMode', () => {
    useEditorStore.getState().toggleEditMode()
    expect(useEditorStore.getState().editMode).toBe(true)
    useEditorStore.getState().toggleEditMode()
    expect(useEditorStore.getState().editMode).toBe(false)
  })

  it('rubberBandSelectionIds starts empty and can be set', () => {
    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual([])
    useEditorStore.getState().setRubberBandSelectionIds(['leon', 'castela'])
    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual(['leon', 'castela'])
  })

  it('pushUndoLabel appends to undoLabels and clears redoLabels', () => {
    // Pitfall 7: parallel label stack is NOT in temporal history
    useEditorStore.setState({ redoLabels: ['Redo: split Castela'] })
    useEditorStore.getState().pushUndoLabel('Mover capital de León')
    const state = useEditorStore.getState()
    expect(state.undoLabels).toContain('Mover capital de León')
    // Pushing a new undo label should clear the redo stack
    expect(state.redoLabels).toEqual([])
  })
})
