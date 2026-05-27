/* Phase 08 D-25 + D-37 + WARNING-6: useEditorStore tests.
 * Covers REQ-IDs: UNDO-01, EDIT-VERTEX-03, PERSIST-02
 *
 * Design notes:
 *   - beforeEach resets module-level mutable state by calling registerEditEventSink(null)
 *     then setState + temporal.clear() so tests are isolated without vi.resetModules().
 *   - Sink fires via Promise.resolve(...).then(...) — tests that assert on sink calls
 *     must flush the microtask queue (await vi.waitFor or explicit flushes).
 *   - undoLabels/redoLabels are mutated in lockstep via temporal.subscribe subscription;
 *     that subscription fires synchronously when undo()/redo() changes pastStates length.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  useEditorStore,
  registerEditEventSink,
  switchBranch,
  type EditEventSink,
} from '../useEditorStore';

// ---- helpers ----------------------------------------------------------------

/** Flush microtasks so Promise.resolve().then() callbacks run. */
async function flushMicrotasks(): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
}

/** Reset all store state and temporal history between tests. */
function resetStore(): void {
  // 1. Clear any registered sink
  registerEditEventSink(null);
  // 2. Reset store to initial state
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
  });
  // 3. Clear temporal history — fires subscription which resets undoLabels/redoLabels
  useEditorStore.temporal.getState().clear();
}

// ---- tests ------------------------------------------------------------------

describe('Phase 08 — useEditorStore (UNDO-01, EDIT-VERTEX-03, PERSIST-02)', () => {

  beforeEach(() => {
    resetStore();
  });

  // ---------------------------------------------------------------------------
  // T1: initial state
  // ---------------------------------------------------------------------------
  it('initial state has activeTool=null, selectedVertexIds=[], vertices={}, editLog=[]', () => {
    const s = useEditorStore.getState();
    expect(s.activeTool).toBeNull();
    expect(s.selectedVertexIds).toEqual([]);
    expect(s.vertices).toEqual({});
    expect(s.editLog).toEqual([]);
    expect(s.undoLabels).toEqual([]);
    expect(s.redoLabels).toEqual([]);
  });

  // ---------------------------------------------------------------------------
  // T2: moveVertex is undoable — pastStates grows
  // ---------------------------------------------------------------------------
  it('moveVertex mutates vertices and editLog; pastStates length grows by 1', () => {
    const before = useEditorStore.temporal.getState().pastStates.length;
    useEditorStore.getState().moveVertex('v1', 40.5, -8.2);
    const s = useEditorStore.getState();
    expect(s.vertices['v1']).toEqual({ lat: 40.5, lon: -8.2 });
    expect(s.editLog).toHaveLength(1);
    expect(s.editLog[0].op).toBe('move');
    const after = useEditorStore.temporal.getState().pastStates.length;
    expect(after).toBe(before + 1);
  });

  // ---------------------------------------------------------------------------
  // T3: selectTool does NOT push to pastStates (excluded from partialize)
  // ---------------------------------------------------------------------------
  it('selectTool does NOT push to pastStates — excluded per D-25', () => {
    const before = useEditorStore.temporal.getState().pastStates.length;
    useEditorStore.getState().selectTool('V');
    const after = useEditorStore.temporal.getState().pastStates.length;
    expect(after).toBe(before);
    expect(useEditorStore.getState().activeTool).toBe('V');
  });

  // ---------------------------------------------------------------------------
  // T4: history cap = 100; oldest evicted on push past cap
  // ---------------------------------------------------------------------------
  it('101 sequential moveVertex calls cap pastStates at 100 — oldest entry evicted', () => {
    for (let i = 0; i < 101; i++) {
      useEditorStore.getState().moveVertex(`v${i}`, i * 0.001, i * 0.001);
    }
    const pastLen = useEditorStore.temporal.getState().pastStates.length;
    expect(pastLen).toBe(100);
  });

  // ---------------------------------------------------------------------------
  // T5: switchBranch rehydrates state + clears temporal history
  // ---------------------------------------------------------------------------
  it('switchBranch replaces state, clears temporal history and resets editsSinceSnapshot', () => {
    // Add some history first
    useEditorStore.getState().moveVertex('v1', 1.0, 2.0);
    useEditorStore.getState().moveVertex('v2', 3.0, 4.0);
    expect(useEditorStore.temporal.getState().pastStates.length).toBe(2);

    const newVertices = { vA: { lat: 10.0, lon: 20.0 } };
    const newEditLog = [{ op: 'move' as const, ts: 0, vertexIds: ['vA'], lat: 10.0, lon: 20.0 }];
    switchBranch('branch-42', { vertices: newVertices, editLog: newEditLog });

    const s = useEditorStore.getState();
    expect(s.activeBranchId).toBe('branch-42');
    expect(s.vertices).toEqual(newVertices);
    expect(s.editLog).toEqual(newEditLog);
    expect(s.editsSinceSnapshot).toBe(0);
    expect(s.selectedVertexIds).toEqual([]);
    expect(s.activeTool).toBeNull();
    // temporal cleared
    expect(useEditorStore.temporal.getState().pastStates.length).toBe(0);
  });

  // ---------------------------------------------------------------------------
  // T6: undo() / redo() round-trip
  // ---------------------------------------------------------------------------
  it('undo() reverts last moveVertex; redo() re-applies it', () => {
    useEditorStore.getState().moveVertex('v1', 40.0, -8.0);
    expect(useEditorStore.getState().vertices['v1']).toEqual({ lat: 40.0, lon: -8.0 });

    useEditorStore.temporal.getState().undo();
    expect(useEditorStore.getState().vertices['v1']).toBeUndefined();

    useEditorStore.temporal.getState().redo();
    expect(useEditorStore.getState().vertices['v1']).toEqual({ lat: 40.0, lon: -8.0 });
  });

  // ---------------------------------------------------------------------------
  // T7: marquee delete = single undoable op for N vertices
  // ---------------------------------------------------------------------------
  it('deleteVertices with 3 ids is ONE undoable op — pastStates grows by exactly 1', () => {
    // Seed vertices
    useEditorStore.getState().addVertex('va', 1.0, 1.0);
    useEditorStore.getState().addVertex('vb', 2.0, 2.0);
    useEditorStore.getState().addVertex('vc', 3.0, 3.0);
    const before = useEditorStore.temporal.getState().pastStates.length;

    // Delete all 3 in one op
    useEditorStore.getState().deleteVertices(['va', 'vb', 'vc']);
    const after = useEditorStore.temporal.getState().pastStates.length;
    expect(after).toBe(before + 1);
    expect(useEditorStore.getState().vertices['va']).toBeUndefined();
    expect(useEditorStore.getState().vertices['vb']).toBeUndefined();
    expect(useEditorStore.getState().vertices['vc']).toBeUndefined();
  });

  // ---------------------------------------------------------------------------
  // T8 (WARNING-6): every undoable action invokes the registered sink exactly once
  // ---------------------------------------------------------------------------
  it('WARNING-6: move/add/deleteVertices each invoke the edit-event sink exactly once; selectTool does not', async () => {
    const sink = vi.fn<Parameters<EditEventSink>, ReturnType<EditEventSink>>()
      .mockResolvedValue(undefined);
    registerEditEventSink(sink);

    useEditorStore.getState().moveVertex('v1', 1.0, 1.0);
    useEditorStore.getState().addVertex('v2', 2.0, 2.0);
    useEditorStore.getState().deleteVertices(['v1']);
    useEditorStore.getState().selectTool('V');  // NOT undoable — must NOT trigger sink

    // Flush microtasks so Promise.resolve().then() runs
    await flushMicrotasks();

    expect(sink).toHaveBeenCalledTimes(3);
    // Verify op types in order
    expect(sink.mock.calls[0][0].op.op).toBe('move');
    expect(sink.mock.calls[1][0].op.op).toBe('add');
    expect(sink.mock.calls[2][0].op.op).toBe('multi_delete');
  });

  // ---------------------------------------------------------------------------
  // T9 (D-37 auto-snapshot): 25th call receives snapshot_payload_if_due
  // ---------------------------------------------------------------------------
  it('D-37 auto-snapshot: 25th edit sink call includes snapshot_payload_if_due; others do not', async () => {
    const sink = vi.fn<Parameters<EditEventSink>, ReturnType<EditEventSink>>()
      .mockResolvedValue({ snapshot_persisted: true });
    registerEditEventSink(sink);

    for (let i = 0; i < 25; i++) {
      useEditorStore.getState().moveVertex(`v${i}`, i * 0.1, i * 0.1);
    }

    await flushMicrotasks();

    expect(sink).toHaveBeenCalledTimes(25);
    // All except the 25th should have undefined snapshot_payload_if_due
    for (let i = 0; i < 24; i++) {
      expect(sink.mock.calls[i][0].snapshot_payload_if_due).toBeUndefined();
    }
    // 25th call: snapshot_payload_if_due must be present (vertices + editLog)
    const call25 = sink.mock.calls[24][0];
    expect(call25.snapshot_payload_if_due).toBeDefined();
    expect(call25.snapshot_payload_if_due?.vertices).toBeDefined();
    expect(call25.snapshot_payload_if_due?.editLog).toBeDefined();
  });

  // ---------------------------------------------------------------------------
  // T10: switchBranch resets editsSinceSnapshot to 0
  // ---------------------------------------------------------------------------
  it('switchBranch resets editsSinceSnapshot to 0', () => {
    // Make some edits
    useEditorStore.getState().moveVertex('v1', 1.0, 1.0);
    useEditorStore.getState().moveVertex('v2', 2.0, 2.0);
    expect(useEditorStore.getState().editsSinceSnapshot).toBeGreaterThan(0);

    switchBranch('other-branch', { vertices: {}, editLog: [] });
    expect(useEditorStore.getState().editsSinceSnapshot).toBe(0);
  });

  // ---------------------------------------------------------------------------
  // T11 (Gemini review: undoLabels/redoLabels UX): label stacks mirror pastStates
  // ---------------------------------------------------------------------------
  it('Gemini UX: undoLabels grows with moveVertex; undo/redo moves labels between stacks; switchBranch resets both', () => {
    useEditorStore.getState().moveVertex('v1', 1.0, 1.0);
    useEditorStore.getState().moveVertex('v2', 2.0, 2.0);
    useEditorStore.getState().moveVertex('v3', 3.0, 3.0);

    // After 3 moves: pastStates.length === 3 AND undoLabels has 3 'move' entries
    expect(useEditorStore.temporal.getState().pastStates.length).toBe(3);
    expect(useEditorStore.getState().undoLabels).toEqual(['move', 'move', 'move']);
    expect(useEditorStore.getState().redoLabels).toEqual([]);

    // After undo(): undoLabels shrinks by 1, redoLabels gains 1
    useEditorStore.temporal.getState().undo();
    expect(useEditorStore.getState().undoLabels).toHaveLength(2);
    expect(useEditorStore.getState().redoLabels).toHaveLength(1);
    expect(useEditorStore.getState().redoLabels[0]).toBe('move');

    // After another undo(): undoLabels.length === 1, redoLabels.length === 2
    useEditorStore.temporal.getState().undo();
    expect(useEditorStore.getState().undoLabels).toHaveLength(1);
    expect(useEditorStore.getState().redoLabels).toHaveLength(2);

    // After redo(): pop from redoLabels to undoLabels
    useEditorStore.temporal.getState().redo();
    expect(useEditorStore.getState().undoLabels).toHaveLength(2);
    expect(useEditorStore.getState().redoLabels).toHaveLength(1);

    // After switchBranch: both stacks reset to []
    switchBranch('fresh-branch', { vertices: {}, editLog: [] });
    expect(useEditorStore.getState().undoLabels).toEqual([]);
    expect(useEditorStore.getState().redoLabels).toEqual([]);
  });

});
