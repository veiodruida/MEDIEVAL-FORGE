/**
 * Regression tests for bug "carve-enclave-edit-leaves-hole" (2026-06-01).
 *
 * Two bugs are tested here:
 *
 * BUG A — Persistence loss on selection change:
 *   After committing a carve op + move ops for the new enclave N, clicking
 *   a neighbouring barony causes SelectionBridge to overwrite store.vertices
 *   with the neighbour's ring. When "Aplicar edições" is then called, runApply
 *   reads the CURRENT store.vertices (neighbour's ring) — N's edited ring is
 *   gone. The snapshot sent to the backend contains the wrong vertices.
 *
 *   Fix direction: useBezierApply.runApply should capture the snapshot at the
 *   time the Apply is triggered, OR the editLog should carry a self-contained
 *   vertex snapshot for ops that reference a freshly-carved enclave.
 *
 * BUG B — N's edited ring lost because auto-select never fires before Apply:
 *   The post-close auto-select watcher (CanvasViewer) calls resolveAutoSelect
 *   which looks up N in effectiveBaronies (baroniesQ data). N is only present
 *   in baroniesQ AFTER a full pipeline Apply+re-run. Therefore auto-select
 *   never fires, SelectionBridge never loads N's vertices, BezierEditLayer
 *   is inactive, and any user gesture is a Stage drag (no move op written).
 *   When Apply is called, editLog = [carve only] + vertices = {} or neighbour.
 *
 * These tests pin the frontend contract so fixes can be verified.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useEditorStore } from '../../stores/useEditorStore'
import { useRunStore } from '../../stores/useRunStore'
import type { EditOp, VertexCoord } from '../../stores/useEditorStore'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../api/render', () => ({
  postRender: vi.fn().mockResolvedValue({ run_id: 'run-xyz', status: 'scheduled', kind: 'render' }),
  postRenderCancel: vi.fn().mockResolvedValue(undefined),
}))

import { postRender } from '../../api/render'
import { useBezierApply } from '../useBezierApply'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ENCLAVE_NAME = 'Baronato-1748700000000'
const PARENT_NAME = 'Cuenca'
const NEIGHBOUR_NAME = 'Albarracin'

/** Carve op as committed by PenDrawLayer.commitCreate */
function makeCarveOp(allocatedIdx: number | null = 42): EditOp {
  return {
    op: 'carve',
    ts: 1748700000000,
    parent_id: 5,   // raster index of Cuenca
    ring: [
      { lat: 39.5, lon: -5.5 },
      { lat: 39.5, lon: -5.0 },
      { lat: 39.0, lon: -5.0 },
      { lat: 39.0, lon: -5.5 },
    ],
    allocated_original_idx: allocatedIdx,
    barony_meta: {
      name: ENCLAVE_NAME,
      condado_idx: 3,
      duchy_id: 'castile',
      kingdom_id: 'leon',
      country: 'ES',
    },
  }
}

/** Move op on the freshly-carved enclave N — as BezierEditLayer would write */
function makeMoveOpOnEnclave(): EditOp {
  return {
    op: 'move',
    ts: 1748700001000,
    vertexIds: [
      `${ENCLAVE_NAME}#0`,
      `${ENCLAVE_NAME}#1`,
      `${ENCLAVE_NAME}#2`,
      `${ENCLAVE_NAME}#3`,
    ],
  }
}

/** Vertices for enclave N as loaded by SelectionBridge (if N were in baroniesQ) */
function makeEnclaveVertices(): Record<string, VertexCoord> {
  return {
    [`${ENCLAVE_NAME}#0`]: { lat: 39.5, lon: -5.5 },
    [`${ENCLAVE_NAME}#1`]: { lat: 39.5, lon: -5.0 },
    [`${ENCLAVE_NAME}#2`]: { lat: 39.0, lon: -5.0 },  // edited position
    [`${ENCLAVE_NAME}#3`]: { lat: 39.0, lon: -5.5 },
  }
}

/** Vertices for a neighbouring barony — written by SelectionBridge when user clicks neighbour */
function makeNeighbourVertices(): Record<string, VertexCoord> {
  return {
    [`${NEIGHBOUR_NAME}#0`]: { lat: 38.5, lon: -4.5 },
    [`${NEIGHBOUR_NAME}#1`]: { lat: 38.5, lon: -4.0 },
    [`${NEIGHBOUR_NAME}#2`]: { lat: 38.0, lon: -4.0 },
    [`${NEIGHBOUR_NAME}#3`]: { lat: 38.0, lon: -4.5 },
  }
}

function resetStores() {
  useEditorStore.setState({
    vertices: {},
    editLog: [],
    activeBranchId: 'branch-1',
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
  useRunStore.setState({
    state: 'idle',
    runId: null,
    currentStage: null,
    completedStages: [],
    logLines: [],
    errorMessage: null,
    errorStage: null,
    priorTokens: {},
    affectedStages: [],
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useBezierApply — carve+enclave-edit persistence (regression 2026-06-01)', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
    vi.mocked(postRender).mockResolvedValue({ run_id: 'run-xyz', status: 'scheduled', kind: 'render' })
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ snapshot_id: 'snap-1', seq: 1, created_at: '2026-01-01T00:00:00Z' }),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it(
    'BUG A — snapshot sent by Apply contains enclave N vertices even after clicking a neighbour barony',
    /**
     * Reproduction of BUG A:
     *   1. User carves enclave N inside Cuenca.
     *   2. editLog = [carve op (allocated_original_idx=42)]
     *   3. User somehow gets BezierEditLayer active and drags a handle → move op written.
     *      (In the ideal fixed flow, SelectionBridge would load N's vertices from
     *      the carve op's ring before the refetch, giving BezierEditLayer the vertices it needs.)
     *   4. editLog = [carve op, move op on N's vertices]
     *      store.vertices = N's edited ring (Baronato-…#0…#3)
     *   5. User clicks Albarracin (neighbour) → SelectionBridge overwrites store.vertices
     *      with Albarracin's ring. store.vertices NO LONGER contains N's keys.
     *   6. User clicks "Aplicar edições" → runApply reads store.vertices = Albarracin's ring.
     *
     * EXPECTED after fix: the snapshot payload's vertices field must contain N's edited ring
     * (Baronato-…#* keys), not Albarracin's ring.
     * CURRENTLY (RED): vertices = Albarracin's ring → N's edited shape lost on backend replay.
     */
    async () => {
      // Step 1-4: Commit carve op + move op on N's vertices.
      // Directly set the store to the state it would be in after both ops.
      const carveOp = makeCarveOp(42)
      const moveOp = makeMoveOpOnEnclave()
      const enclaveVertices = makeEnclaveVertices()

      useEditorStore.setState({
        editLog: [carveOp, moveOp],
        vertices: enclaveVertices,  // N's edited ring is in the store
        activeTerritoryId: ENCLAVE_NAME,
      })

      // Step 5: Simulate SelectionBridge overwriting vertices when user clicks neighbour.
      // This is exactly what SelectionBridge does: useEditorStore.setState({ vertices })
      // (bypasses zundo, no undo entry).
      const temporal = useEditorStore.temporal.getState()
      temporal.pause()
      useEditorStore.setState({
        vertices: makeNeighbourVertices(),   // neighbour's ring wipes N's ring
        activeTerritoryId: NEIGHBOUR_NAME,
      })
      temporal.resume()

      // Verify the store no longer has N's vertices (this is the current broken state)
      const storeAfterNavigation = useEditorStore.getState()
      const hasEnclaveKeys = Object.keys(storeAfterNavigation.vertices).some(k =>
        k.startsWith(ENCLAVE_NAME)
      )
      // This assertion PASSES currently — confirms the store state is broken
      expect(hasEnclaveKeys).toBe(false)  // N's vertices are gone from store

      // Step 6: Call Apply
      const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))
      await act(async () => {
        await result.current.handleApplyEdits('render-final')
      })

      // FAILING ASSERTION (RED): the snapshot must contain N's edited vertices, not the neighbour's.
      // After fix, the snapshot payload should contain N's ring for proper backend replay.
      const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
      const body = JSON.parse(init.body as string)
      const sentVertices: Record<string, VertexCoord> = body.payload.vertices

      // This is the RED assertion: currently sentVertices = Albarracin's ring (no N keys).
      // After the fix, the Apply snapshot must capture N's vertices even after navigation away.
      const sentEnclaveKeys = Object.keys(sentVertices).filter(k => k.startsWith(ENCLAVE_NAME))
      expect(sentEnclaveKeys.length).toBeGreaterThan(0)  // RED: currently 0
    },
  )

  it(
    'BUG A — snapshot edit_log still contains the carve op after clicking a neighbour barony',
    /**
     * The editLog must NOT be wiped when the user navigates to a neighbour.
     * This sub-test pins that editLog is preserved (it IS in the current codebase,
     * since only SelectionBridge wipes vertices, not editLog — this should stay GREEN
     * and serves as a regression guard that the fix does not break editLog persistence).
     */
    async () => {
      const carveOp = makeCarveOp(42)
      const moveOp = makeMoveOpOnEnclave()

      useEditorStore.setState({
        editLog: [carveOp, moveOp],
        vertices: makeEnclaveVertices(),
        activeTerritoryId: ENCLAVE_NAME,
      })

      // Simulate SelectionBridge navigation to neighbour
      const temporal = useEditorStore.temporal.getState()
      temporal.pause()
      useEditorStore.setState({
        vertices: makeNeighbourVertices(),
        activeTerritoryId: NEIGHBOUR_NAME,
      })
      temporal.resume()

      const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))
      await act(async () => {
        await result.current.handleApplyEdits('render-final')
      })

      const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
      const body = JSON.parse(init.body as string)

      // editLog must still contain both ops (carve + move)
      expect(body.payload.edit_log).toHaveLength(2)
      expect(body.payload.edit_log[0].op).toBe('carve')
      expect(body.payload.edit_log[1].op).toBe('move')
    },
  )
})
