/**
 * Phase 08.3 Plan 03 — Task 1 TDD
 * Tests for 'create' EditOp variant + 'P' EditTool + single-zundo-entry contract (D-13).
 *
 * Verifies:
 *   T1: create op commits as a single editLog entry with required fields
 *   T2: create op is ONE zundo entry (D-13) — undo once removes it entirely
 *   T3: allocated_original_idx patch mirrors split precedent (lines 279-289)
 *   T4: barony_meta round-trips through the commit (condado_idx/duchy_id/kingdom_id/country)
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useEditorStore } from './useEditorStore';
import type { EditOp } from './useEditorStore';

// ---- helpers ----------------------------------------------------------------

function resetStore() {
  useEditorStore.setState({
    activeBranchId: null,
    landmaskMode: 'manual',
    editableLayer: 'baronies',
    bezierApplyMode: 'manual',
    activeTool: null,
    activeTerritoryId: null,
    selectedVertexIds: [],
    vertices: {},
    editLog: [],
    editsSinceSnapshot: 0,
    undoLabels: [],
    redoLabels: [],
  });
  useEditorStore.temporal.getState().clear();
}

/** Build a minimal valid create EditOp for test fixtures. */
function makeCreateOp(overrides?: Partial<EditOp>): EditOp {
  return {
    op: 'create',
    ts: 1000,
    ring: [
      { lat: 40.0, lon: -8.0 },
      { lat: 40.5, lon: -8.5 },
      { lat: 41.0, lon: -8.0 },
      { lat: 40.0, lon: -8.0 }, // closed ring: first === last
    ],
    allocated_original_idx: null,
    barony_meta: {
      name: 'Baronato de Test',
      condado_idx: 3,
      duchy_id: 'D1',
      kingdom_id: 'K1',
      country: 'PT',
    },
    ...overrides,
  };
}

// ---- tests ------------------------------------------------------------------

describe('Phase 08.3 — useEditorStore create op + EditTool P (PEN-CREATE-01, PEN-CURVE-01)', () => {
  beforeEach(() => {
    resetStore();
  });

  // ---------------------------------------------------------------------------
  // T1: create op commits as single editLog entry
  // ---------------------------------------------------------------------------
  it('T1: setVerticesAndLog with create op appends exactly ONE entry; op===create, ring present, allocated_original_idx===null', () => {
    const createOp = makeCreateOp();
    const currentVertices = useEditorStore.getState().vertices;

    useEditorStore.getState().setVerticesAndLog(currentVertices, createOp);

    const s = useEditorStore.getState();
    expect(s.editLog).toHaveLength(1);
    expect(s.editLog[0].op).toBe('create');
    expect(s.editLog[0].ring).toBeDefined();
    expect(s.editLog[0].ring).toHaveLength(4); // closed ring
    expect(s.editLog[0].allocated_original_idx).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // T2: create op is ONE zundo entry (D-13)
  // ---------------------------------------------------------------------------
  it('T2: committing one create op creates exactly one pastState; undo() removes it entirely (editLog back to 0)', () => {
    const beforeLen = useEditorStore.temporal.getState().pastStates.length;
    expect(beforeLen).toBe(0);

    const createOp = makeCreateOp();
    const currentVertices = useEditorStore.getState().vertices;
    useEditorStore.getState().setVerticesAndLog(currentVertices, createOp);

    // One zundo entry added
    expect(useEditorStore.temporal.getState().pastStates.length).toBe(1);
    expect(useEditorStore.getState().editLog).toHaveLength(1);

    // Single undo removes it entirely
    useEditorStore.temporal.getState().undo();
    expect(useEditorStore.temporal.getState().pastStates.length).toBe(0);
    expect(useEditorStore.getState().editLog).toHaveLength(0);
  });

  // ---------------------------------------------------------------------------
  // T3: allocated_original_idx patch mirrors split precedent (lines 279-289)
  // ---------------------------------------------------------------------------
  it('T3: after committing create op, patching editLog[-1].allocated_original_idx updates from null to number', () => {
    const createOp = makeCreateOp();
    const currentVertices = useEditorStore.getState().vertices;
    useEditorStore.getState().setVerticesAndLog(currentVertices, createOp);

    // Verify initial state: allocated_original_idx is null
    expect(useEditorStore.getState().editLog[0].allocated_original_idx).toBeNull();

    // Simulate post-Apply patch (mirrors split lines 279-289)
    const state = useEditorStore.getState();
    useEditorStore.setState({
      editLog: [
        ...state.editLog.slice(0, -1),
        {
          ...state.editLog[state.editLog.length - 1],
          allocated_original_idx: 47,
        },
      ],
    });

    // After patch: allocated_original_idx updated; other fields intact
    const patched = useEditorStore.getState().editLog[0];
    expect(patched.allocated_original_idx).toBe(47);
    expect(patched.op).toBe('create');
    expect(patched.ring).toBeDefined();
  });

  // ---------------------------------------------------------------------------
  // T4: barony_meta round-trips through the commit
  // ---------------------------------------------------------------------------
  it('T4: barony_meta fields (condado_idx, duchy_id, kingdom_id, country) survive setVerticesAndLog commit', () => {
    const createOp = makeCreateOp({
      barony_meta: {
        name: 'Baronato de Coimbra',
        condado_idx: 7,
        duchy_id: 'D_COIMBRA',
        kingdom_id: 'K_PT',
        country: 'PT',
      },
    });
    const currentVertices = useEditorStore.getState().vertices;
    useEditorStore.getState().setVerticesAndLog(currentVertices, createOp);

    const logEntry = useEditorStore.getState().editLog[0];
    const meta = logEntry.barony_meta as {
      name: string;
      condado_idx: number;
      duchy_id: string;
      kingdom_id: string;
      country: string;
    };

    expect(meta.name).toBe('Baronato de Coimbra');
    expect(meta.condado_idx).toBe(7);
    expect(meta.duchy_id).toBe('D_COIMBRA');
    expect(meta.kingdom_id).toBe('K_PT');
    expect(meta.country).toBe('PT');
  });
});
