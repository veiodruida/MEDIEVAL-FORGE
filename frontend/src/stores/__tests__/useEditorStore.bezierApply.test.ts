/**
 * Phase 08.2 Plan 03 — Task 1 TDD
 * Tests for bezierApplyMode field + setBezierApplyMode action.
 * Verifies default value, mode toggle, and partialize exclusion (undo must NOT revert mode).
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useEditorStore } from '../useEditorStore'

function resetStore() {
  useEditorStore.setState({
    vertices: {},
    editLog: [],
    activeBranchId: null,
    activeTool: null,
    activeTerritoryId: null,
    selectedVertexIds: [],
    landmaskMode: 'manual',
    editableLayer: 'baronies',
    editsSinceSnapshot: 0,
    undoLabels: [],
    redoLabels: [],
    bezierApplyMode: 'manual',
  })
  useEditorStore.temporal.getState().clear()
}

describe('useEditorStore bezierApplyMode', () => {
  beforeEach(() => {
    resetStore()
  })

  it('defaults to manual', () => {
    const state = useEditorStore.getState()
    expect(state.bezierApplyMode).toBe('manual')
  })

  it('setBezierApplyMode updates the field to auto-immediate', () => {
    useEditorStore.getState().setBezierApplyMode('auto-immediate')
    expect(useEditorStore.getState().bezierApplyMode).toBe('auto-immediate')
  })

  it('setBezierApplyMode can toggle back to manual', () => {
    useEditorStore.getState().setBezierApplyMode('auto-immediate')
    useEditorStore.getState().setBezierApplyMode('manual')
    expect(useEditorStore.getState().bezierApplyMode).toBe('manual')
  })

  it('bezierApplyMode is NOT reverted by undo (excluded from zundo partialize)', () => {
    // Make a real vertex edit to create a past state in zundo
    useEditorStore.getState().setVerticesAndLog(
      { v1: { lat: 10, lon: 20 } },
      { op: 'move', ts: Date.now(), vertexIds: ['v1'], lat: 10, lon: 20 },
    )
    // Verify the edit was recorded
    expect(useEditorStore.getState().vertices).toEqual({ v1: { lat: 10, lon: 20 } })
    expect(useEditorStore.temporal.getState().pastStates.length).toBeGreaterThan(0)

    // Toggle mode to auto-immediate
    useEditorStore.getState().setBezierApplyMode('auto-immediate')
    expect(useEditorStore.getState().bezierApplyMode).toBe('auto-immediate')

    // Undo should revert vertices but NOT the mode toggle
    useEditorStore.temporal.getState().undo()

    // Vertices should be reverted (proof undo actually fired)
    expect(useEditorStore.getState().vertices).toEqual({})

    // Mode must still be auto-immediate (excluded from partialize)
    expect(useEditorStore.getState().bezierApplyMode).toBe('auto-immediate')
  })
})
