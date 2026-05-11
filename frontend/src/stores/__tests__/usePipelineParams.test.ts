/**
 * Plan 04-03 Task 1 — usePipelineParams + useParameterStudioDispatch unit tests.
 * Tests slider state, debounce behavior, latest-wins sequence, and diffOverrides.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePipelineParams, PARAM_DEFAULTS, diffOverrides } from '../usePipelineParams'
import { useParameterStudioDispatch } from '../../hooks/useParameterStudioDispatch'
import { useRunStore } from '../useRunStore'

// ---------------------------------------------------------------------------
// Mock api/render.ts so tests don't hit network
// ---------------------------------------------------------------------------
const mockPostRender = vi.fn()
const mockPostRenderCancel = vi.fn()
const mockGetStageRasterUrl = vi.fn()

vi.mock('../../api/render', () => ({
  postRender: (...args: unknown[]) => mockPostRender(...args),
  postRenderCancel: (...args: unknown[]) => mockPostRenderCancel(...args),
  getStageRasterUrl: (...args: unknown[]) => mockGetStageRasterUrl(...args),
}))

describe('usePipelineParams', () => {
  beforeEach(() => {
    usePipelineParams.setState({
      values: { ...PARAM_DEFAULTS },
      lastRendered: { ...PARAM_DEFAULTS },
      stageView: 'render-final',
      sidebarOpen: true,
    })
    useRunStore.getState().reset()
    // Reset and re-configure mocks each test
    mockPostRender.mockReset()
    mockPostRenderCancel.mockReset()
    mockGetStageRasterUrl.mockReset()
    mockPostRender.mockResolvedValue({ run_id: 'r-1', status: 'scheduled', kind: 'render' })
    mockPostRenderCancel.mockResolvedValue(undefined)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('test_slider_change_debounces_250ms', async () => {
    vi.useFakeTimers()

    const { result } = renderHook(() =>
      useParameterStudioDispatch('proj-1'),
    )

    // Change a slider value
    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 3.5)
    })

    // Trigger dispatch (simulates slider onChange calling dispatch)
    act(() => {
      result.current()
    })

    // At 200ms — postRender NOT called yet
    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(mockPostRender).not.toHaveBeenCalled()

    // Advance past the 250ms debounce threshold
    await act(async () => {
      vi.advanceTimersByTime(100)
      // Flush microtasks for async dispatch
      await Promise.resolve()
      await Promise.resolve()
    })

    // postRender should have been called once
    expect(mockPostRender).toHaveBeenCalledTimes(1)
    expect(mockPostRender).toHaveBeenCalledWith(
      'proj-1',
      { smooth_sigma: 3.5 },
      'render-final',
    )
  })

  it('latest-wins: new debounce cancels in-flight render via cancel endpoint', async () => {
    vi.useFakeTimers()

    // Track call order manually using a shared sequence array
    const callOrder: string[] = []
    mockPostRenderCancel.mockImplementation(async () => {
      callOrder.push('cancel')
    })
    mockPostRender.mockImplementation(async () => {
      callOrder.push('render')
      return { run_id: 'r-1', status: 'scheduled', kind: 'render' }
    })

    const { result } = renderHook(() =>
      useParameterStudioDispatch('proj-1'),
    )

    // First slider change + dispatch call
    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 3.5)
      result.current()
    })

    // Wait 100ms (debounce not yet expired for first call)
    act(() => {
      vi.advanceTimersByTime(100)
    })

    // Second slider change + dispatch call — resets the debounce timer
    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 4.0)
      result.current()
    })

    // Advance past 250ms from the SECOND call
    await act(async () => {
      vi.advanceTimersByTime(300)
      await Promise.resolve()
      await Promise.resolve()
    })

    // cancel must be called before render (latest-wins sequence)
    expect(callOrder).toEqual(['cancel', 'render'])

    // postRender called exactly once (for the second value)
    expect(mockPostRender).toHaveBeenCalledTimes(1)
    expect(mockPostRender).toHaveBeenCalledWith(
      'proj-1',
      { smooth_sigma: 4.0 },
      'render-final',
    )

    // postRenderCancel called once
    expect(mockPostRenderCancel).toHaveBeenCalledTimes(1)
  })

  it('reset action skips debounce and fires immediately', async () => {
    vi.useFakeTimers()

    const { result } = renderHook(() =>
      useParameterStudioDispatch('proj-1'),
    )

    // Setup: mark lastRendered at a different value so diff is non-empty on reset
    act(() => {
      usePipelineParams.getState().markRendered({ ...PARAM_DEFAULTS, smooth_sigma: 4.2 })
      // Reset the slider (values.smooth_sigma goes back to 3.0, lastRendered stays 4.2)
      usePipelineParams.getState().resetSlider('smooth_sigma')
    })

    // Trigger debounce
    act(() => {
      result.current()
    })

    // flush() bypasses the 250ms delay — fires synchronously
    await act(async () => {
      result.current.flush()
      await Promise.resolve()
      await Promise.resolve()
    })

    // No timer advancement needed — flush bypasses the delay
    // Now smooth_sigma = 3.0 (reset) vs lastRendered = 4.2 — diff has smooth_sigma: 3.0
    expect(mockPostRender).toHaveBeenCalledWith(
      'proj-1',
      { smooth_sigma: 3.0 },
      'render-final',
    )
  })

  it('exposes stage_view as client-only state (not in cfg overrides on /generate)', () => {
    // stageView is NOT a slider key — verify diffOverrides never includes it.
    const customValues = {
      smooth_sigma: 3.5,
      median_passes: 8,
      fragment_min_px: 600,
      blob_merge_px: 200,
    }
    const diff = diffOverrides(customValues, { ...PARAM_DEFAULTS })

    // Only smooth_sigma differs → diff should only contain that key
    expect(diff).toEqual({ smooth_sigma: 3.5 })
    // stageView is NOT in the diff (it's a separate store field, not in values)
    expect('stageView' in diff).toBe(false)
    expect('stage_view' in diff).toBe(false)
  })
})

// =============================================================================
// Plan 04.1-02 Task 1 — D-04 bounded RENDER_BUSY retry contract.
//
// Contract: after a cancel→POST race, postRender returns 409 (Error 'RENDER_BUSY').
// The dispatch hook re-queues up to 3 times within a 1.5s window; on the 4th
// consecutive 409 it surfaces useRunStore.finish('error', 'RENDER_BUSY').
// A successful postRender (run_id returned) resets the retry counter.
// =============================================================================
describe('useParameterStudioDispatch RENDER_BUSY retry (D-04)', () => {
  beforeEach(() => {
    usePipelineParams.setState({
      values: { ...PARAM_DEFAULTS },
      lastRendered: { ...PARAM_DEFAULTS },
      stageView: 'render-final',
      sidebarOpen: true,
    })
    useRunStore.getState().reset()
    mockPostRender.mockReset()
    mockPostRenderCancel.mockReset()
    mockGetStageRasterUrl.mockReset()
    mockPostRenderCancel.mockResolvedValue(undefined)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // Helper — advance the 250ms debounce + flush microtasks so async dispatch
  // resolves (postRenderCancel → postRender → catch → re-queue) before the
  // next iteration. Mirrors the pattern from the 'latest-wins' test above.
  async function advanceOneDebounceCycle() {
    await act(async () => {
      vi.advanceTimersByTime(250)
      // Multiple microtask flushes — postRenderCancel.then → postRender.then → catch.
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
    })
  }

  it('test_render_busy_three_times_then_success_does_not_error', async () => {
    vi.useFakeTimers()
    // Two 409s then a success — should NOT transition to error.
    mockPostRender
      .mockRejectedValueOnce(new Error('RENDER_BUSY'))
      .mockRejectedValueOnce(new Error('RENDER_BUSY'))
      .mockResolvedValueOnce({ run_id: 'r-ok', status: 'scheduled', kind: 'render' })

    const { result } = renderHook(() =>
      useParameterStudioDispatch('proj-1'),
    )

    // Trigger initial dispatch (non-empty diff).
    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 3.5)
      result.current()
    })

    // Cycle 1: 250ms → 409 → re-queue.
    await advanceOneDebounceCycle()
    // Cycle 2: 250ms → 409 → re-queue.
    await advanceOneDebounceCycle()
    // Cycle 3: 250ms → 200 success.
    await advanceOneDebounceCycle()

    expect(mockPostRender).toHaveBeenCalledTimes(3)
    expect(useRunStore.getState().state).not.toBe('error')
    expect(useRunStore.getState().runId).toBe('r-ok')
  })

  it('test_render_busy_four_times_surfaces_error_on_fourth_attempt', async () => {
    vi.useFakeTimers()
    // Always 409 — on the 4th attempt the bounded retry surfaces 'error'.
    mockPostRender.mockRejectedValue(new Error('RENDER_BUSY'))

    const { result } = renderHook(() =>
      useParameterStudioDispatch('proj-1'),
    )

    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 3.5)
      result.current()
    })

    // Cycles 1, 2, 3 — re-queue.
    await advanceOneDebounceCycle()
    await advanceOneDebounceCycle()
    await advanceOneDebounceCycle()
    // Cycle 4 — exhausts retries, finish('error', 'RENDER_BUSY').
    await advanceOneDebounceCycle()

    expect(mockPostRender).toHaveBeenCalledTimes(4)
    expect(useRunStore.getState().state).toBe('error')
    expect(useRunStore.getState().errorMessage).toBe('RENDER_BUSY')
  })

  it('test_render_busy_counter_resets_on_success', async () => {
    vi.useFakeTimers()
    // 2× 409 → success → 1× 409 → success. After the first success the
    // counter resets; the next 409 starts at attempt 1, not 3, so no error.
    mockPostRender
      .mockRejectedValueOnce(new Error('RENDER_BUSY'))
      .mockRejectedValueOnce(new Error('RENDER_BUSY'))
      .mockResolvedValueOnce({ run_id: 'r-ok-1', status: 'scheduled', kind: 'render' })
      .mockRejectedValueOnce(new Error('RENDER_BUSY'))
      .mockResolvedValueOnce({ run_id: 'r-ok-2', status: 'scheduled', kind: 'render' })

    const { result } = renderHook(() =>
      useParameterStudioDispatch('proj-1'),
    )

    // First slider edit dispatches the first cycle.
    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 3.5)
      result.current()
    })

    // 409, 409, then success — counter should be cleared.
    await advanceOneDebounceCycle()
    await advanceOneDebounceCycle()
    await advanceOneDebounceCycle()
    expect(useRunStore.getState().runId).toBe('r-ok-1')
    expect(useRunStore.getState().state).not.toBe('error')

    // Trigger a new diff to start a fresh dispatch (markRendered set
    // lastRendered=3.5; setValue(3.6) creates a new diff).
    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 3.6)
      result.current()
    })

    // 409 once → re-queue → success.
    await advanceOneDebounceCycle()
    await advanceOneDebounceCycle()
    expect(mockPostRender).toHaveBeenCalledTimes(5)
    expect(useRunStore.getState().state).not.toBe('error')
    expect(useRunStore.getState().runId).toBe('r-ok-2')
  })

  it('test_non_render_busy_error_surfaces_immediately_without_retry', async () => {
    vi.useFakeTimers()
    mockPostRender.mockRejectedValue(new Error('OTHER_FAILURE'))

    const { result } = renderHook(() =>
      useParameterStudioDispatch('proj-1'),
    )

    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 3.5)
      result.current()
    })

    await advanceOneDebounceCycle()

    // postRender called exactly once — no retry for non-RENDER_BUSY errors.
    expect(mockPostRender).toHaveBeenCalledTimes(1)
    expect(useRunStore.getState().state).toBe('error')
    expect(useRunStore.getState().errorMessage).toBe('OTHER_FAILURE')
  })
})
