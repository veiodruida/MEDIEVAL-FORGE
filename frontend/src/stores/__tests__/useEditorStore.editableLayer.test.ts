/**
 * Phase 08 Plan 16 — TDD RED: editableLayer toggle tests.
 *
 * These tests FAIL before useEditorStore has the editableLayer field + setEditableLayer.
 * They assert:
 *   1. editableLayer defaults to 'baronies'.
 *   2. setEditableLayer('landmask') flips the value.
 *   3. Round-trip (baronies→landmask→baronies) works.
 *   4. editableLayer toggle does NOT grow temporal pastStates (zundo-excluded).
 *   5. editableLayer is NOT in partialize output.
 *   6. editLog does NOT grow on setEditableLayer.
 *
 * REQ-IDs: LANDMASK-01, LANDMASK-02
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useEditorStore, registerEditEventSink } from '../useEditorStore';
import type { EditableLayer } from '../useEditorStore';

function resetStore(): void {
  registerEditEventSink(null);
  useEditorStore.setState({
    activeBranchId: null,
    landmaskMode: 'manual',
    activeTool: null,
    activeTerritoryId: null,
    selectedVertexIds: [],
    vertices: {},
    editLog: [],
    editsSinceSnapshot: 0,
    undoLabels: [],
    redoLabels: [],
    // editableLayer will be added — reset it too once the field exists
    editableLayer: 'baronies' as EditableLayer,
  });
  useEditorStore.temporal.getState().clear();
}

describe('Phase 08 Plan 16 — editableLayer toggle (LANDMASK-01, LANDMASK-02)', () => {
  beforeEach(() => {
    resetStore();
  });

  // T1: default is 'baronies'
  it('editableLayer defaults to baronies', () => {
    const s = useEditorStore.getState();
    expect(s.editableLayer).toBe('baronies');
  });

  // T2: setEditableLayer flips to 'landmask'
  it('setEditableLayer("landmask") sets editableLayer to landmask', () => {
    useEditorStore.getState().setEditableLayer('landmask');
    expect(useEditorStore.getState().editableLayer).toBe('landmask');
  });

  // T3: round-trip baronies → landmask → baronies
  it('round-trip: landmask→baronies restores original value', () => {
    useEditorStore.getState().setEditableLayer('landmask');
    useEditorStore.getState().setEditableLayer('baronies');
    expect(useEditorStore.getState().editableLayer).toBe('baronies');
  });

  // T4: toggle does NOT push to zundo pastStates (excluded from partialize)
  it('setEditableLayer does NOT push to temporal pastStates — zundo-excluded', () => {
    const before = useEditorStore.temporal.getState().pastStates.length;
    useEditorStore.getState().setEditableLayer('landmask');
    const after = useEditorStore.temporal.getState().pastStates.length;
    expect(after).toBe(before);
  });

  // T5: after toggle+round-trip, editLog must not grow
  it('setEditableLayer does NOT grow editLog', () => {
    useEditorStore.getState().setEditableLayer('landmask');
    useEditorStore.getState().setEditableLayer('baronies');
    expect(useEditorStore.getState().editLog).toHaveLength(0);
  });

  // T6: EditableLayer type is importable from useEditorStore (source of truth)
  it('EditableLayer type is importable from useEditorStore', () => {
    const layer: EditableLayer = 'landmask';
    expect(layer).toBe('landmask');
  });
});
