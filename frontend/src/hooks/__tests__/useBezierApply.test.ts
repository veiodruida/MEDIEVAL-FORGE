/**
 * Phase 08.2 Plan 03 — Task 2 TDD
 * Tests for useBezierApply hook.
 *
 * Covers:
 *   - handleApplyEdits posts snapshot with correct payload (edit_log snake_case, vertices)
 *   - NO barony_name_to_idx in payload (constraint #5)
 *   - calls postRender directly (Pitfall 3 — no dispatch/flush/diffOverrides)
 *   - on render success: editLog cleared via temporal.pause → setState → resume
 *   - auto-immediate path posts fresh snapshot on each call
 *   - MAX_VERTEX_KEYS cap guard aborts Apply when exceeded
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useEditorStore } from '../../stores/useEditorStore'
import { useRunStore } from '../../stores/useRunStore'
import type { EditOp, VertexCoord } from '../../stores/useEditorStore'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock postRender from api/render
vi.mock('../../api/render', () => ({
  postRender: vi.fn().mockResolvedValue({ run_id: 'run-abc', status: 'scheduled', kind: 'render' }),
  postRenderCancel: vi.fn().mockResolvedValue(undefined),
}))

import { postRender } from '../../api/render'
import { useBezierApply, MAX_VERTEX_KEYS_FALLBACK } from '../useBezierApply'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeVertices(n: number): Record<string, VertexCoord> {
  const v: Record<string, VertexCoord> = {}
  for (let i = 0; i < n; i++) {
    v[`v${i}`] = { lat: i, lon: i }
  }
  return v
}

function makeEditLog(n: number): EditOp[] {
  return Array.from({ length: n }, (_, i) => ({
    op: 'move' as const,
    ts: 1000 + i,
    vertexIds: [`v${i}`],
    lat: i,
    lon: i,
  }))
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
  useRunStore.setState({ state: 'idle', runId: null, currentStage: null, completedStages: [], logLines: [], errorMessage: null, errorStage: null, priorTokens: {}, affectedStages: [] })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useBezierApply', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
    // Restore postRender mock return value after clearAllMocks clears it
    vi.mocked(postRender).mockResolvedValue({ run_id: 'run-abc', status: 'scheduled', kind: 'render' })
    // Default fetch mock — success snapshot POST
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ snapshot_id: 'snap-1', seq: 1, created_at: '2026-01-01T00:00:00Z' }),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('handleApplyEdits POSTs snapshot with edit_log (snake_case) and vertices', async () => {
    const vertices = makeVertices(3)
    const editLog = makeEditLog(2)
    useEditorStore.setState({ vertices, editLog })

    const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))

    await act(async () => {
      await result.current.handleApplyEdits('render-final')
    })

    // fetch called for snapshot POST
    expect(global.fetch).toHaveBeenCalled()
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('/snapshots')
    const body = JSON.parse(init.body)
    // edit_log must be snake_case
    expect(body.payload.edit_log).toEqual(editLog)
    // vertices must be present
    expect(body.payload.vertices).toEqual(vertices)
  })

  it('handleApplyEdits does NOT include barony_name_to_idx in payload', async () => {
    useEditorStore.setState({ vertices: makeVertices(2), editLog: makeEditLog(1) })

    const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))

    await act(async () => {
      await result.current.handleApplyEdits('render-final')
    })

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const body = JSON.parse(init.body)
    expect(body.payload.barony_name_to_idx).toBeUndefined()
    expect(Object.keys(body.payload)).not.toContain('barony_name_to_idx')
  })

  it('handleApplyEdits calls postRender directly (not dispatch/flush)', async () => {
    useEditorStore.setState({ vertices: makeVertices(2), editLog: makeEditLog(1) })

    const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))

    await act(async () => {
      await result.current.handleApplyEdits('render-final')
    })

    // Branch id ('branch-1') is now passed as 4th arg so _render_producer can load snapshot_loader
    expect(postRender).toHaveBeenCalledWith('proj-1', {}, 'render-final', 'branch-1')
  })

  it('on render success, editLog is cleared via temporal.pause → setState → resume', async () => {
    const vertices = makeVertices(3)
    const editLog = makeEditLog(3)
    useEditorStore.setState({ vertices, editLog })

    // Spy BEFORE mounting the hook so useEffect captures the spy
    const temporalState = useEditorStore.temporal.getState()
    const pauseSpy = vi.spyOn(temporalState, 'pause')
    const resumeSpy = vi.spyOn(temporalState, 'resume')

    // Mount hook (useEffect registers subscription)
    const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))

    // Step 1: call handleApplyEdits → sets pendingApplyRef = true, calls postRender
    await act(async () => {
      await result.current.handleApplyEdits('render-final')
    })

    // Step 2: simulate RunStore transition rendering → generated
    // (the subscription in the hook listens for this exact transition)
    act(() => {
      useRunStore.getState().startRender('run-abc')
    })
    act(() => {
      useRunStore.getState().finish('generated')
    })

    // Allow microtasks/subscription callback to settle
    await act(async () => { await new Promise(r => setTimeout(r, 0)) })

    expect(pauseSpy).toHaveBeenCalled()
    expect(resumeSpy).toHaveBeenCalled()
    expect(useEditorStore.getState().editLog).toEqual([])
  })

  it('MAX_VERTEX_KEYS cap guard aborts Apply when vertices exceed limit', async () => {
    // Create more vertices than allowed
    const oversized = makeVertices(MAX_VERTEX_KEYS_FALLBACK + 1)
    useEditorStore.setState({ vertices: oversized, editLog: makeEditLog(1) })

    const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))

    await act(async () => {
      await result.current.handleApplyEdits('render-final')
    })

    // fetch should NOT have been called (aborted before POST)
    expect(global.fetch).not.toHaveBeenCalled()
    expect(postRender).not.toHaveBeenCalled()
  })

  it('auto-immediate triggerAutoApply posts fresh snapshot before postRender', async () => {
    useEditorStore.setState({
      vertices: makeVertices(2),
      editLog: makeEditLog(1),
      bezierApplyMode: 'auto-immediate',
    })

    const { result } = renderHook(() => useBezierApply('proj-1', 'branch-1'))

    await act(async () => {
      await result.current.triggerAutoApply('render-final')
    })

    // Snapshot POST should have been called
    expect(global.fetch).toHaveBeenCalled()
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('/snapshots')
    // postRender also called — branchId now passed as 4th arg
    expect(postRender).toHaveBeenCalledWith('proj-1', {}, 'render-final', 'branch-1')
  })
})
