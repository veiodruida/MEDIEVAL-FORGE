/**
 * Plan 04-03 Task 2 — ParameterSidebar unit tests.
 * Tests D-05/D-06: 320px collapsible sidebar with StageViewToggle + 4 SliderCards.
 * Plan 04.1-02 Task 2 — D-06 consolidation: ParameterSidebar consumes
 * useParameterStudioDispatch (no inlined dispatch logic).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import type { ReactNode } from 'react'
import { ParameterSidebar } from '../ParameterSidebar'
import { usePipelineParams, PARAM_DEFAULTS } from '../../../stores/usePipelineParams'
import { useRunStore } from '../../../stores/useRunStore'
import { useParameterStudioDispatch } from '../../../hooks/useParameterStudioDispatch'
import { useRenderStream } from '../../../api/useRenderStream'

// Mock the render API and useRenderStream so ParameterSidebar tests don't hit network
vi.mock('../../../api/render', () => ({
  postRender: vi.fn().mockResolvedValue({ run_id: 'r-1', status: 'scheduled', kind: 'render' }),
  postRenderCancel: vi.fn().mockResolvedValue(undefined),
  getStageRasterUrl: vi.fn(),
}))

const mockSubscribe = vi.fn()
const mockClose = vi.fn()
vi.mock('../../../api/useRenderStream', () => ({
  useRenderStream: vi.fn(() => ({
    subscribe: mockSubscribe,
    close: mockClose,
  })),
}))

// Mock the canonical dispatch hook so Task 2 can assert that ParameterSidebar
// invokes it with (projectId, onRenderStarted). The mocked dispatcher exposes
// .flush() so the onResetCommit path still works in pre-existing tests.
vi.mock('../../../hooks/useParameterStudioDispatch', () => ({
  useParameterStudioDispatch: vi.fn(() => Object.assign(vi.fn(), { flush: vi.fn() })),
}))

function wrap(node: ReactNode) {
  return <Theme>{node}</Theme>
}

describe('ParameterSidebar', () => {
  beforeEach(() => {
    usePipelineParams.setState({
      values: { ...PARAM_DEFAULTS },
      lastRendered: { ...PARAM_DEFAULTS },
      stageView: 'render-final',
      sidebarOpen: true,
    })
    useRunStore.getState().reset()
    mockSubscribe.mockClear()
    mockClose.mockClear()
    vi.mocked(useParameterStudioDispatch).mockClear()
    vi.mocked(useRenderStream).mockClear()
    // Re-prime the renderStream mock after clear so each test gets a fresh handle.
    vi.mocked(useRenderStream).mockReturnValue({
      subscribe: mockSubscribe,
      close: mockClose,
    })
    // Re-prime the dispatch hook mock so each test gets a fresh dispatcher.
    vi.mocked(useParameterStudioDispatch).mockReturnValue(
      Object.assign(vi.fn(), { flush: vi.fn() }) as unknown as ReturnType<
        typeof useParameterStudioDispatch
      >,
    )
  })

  it('renders 320px collapsible left sidebar', () => {
    const { container } = render(
      wrap(<ParameterSidebar projectId="proj-1" />),
    )
    const sidebar = container.querySelector('[data-testid="parameter-sidebar"]') as HTMLElement
    expect(sidebar).toBeTruthy()
    expect(sidebar.style.width).toBe('320px')
  })

  it('renders StageViewToggle at top + 4 SliderCards stacked', () => {
    render(wrap(<ParameterSidebar projectId="proj-1" />))

    // StageViewToggle must be present
    expect(screen.getByTestId('stage-view-toggle')).toBeInTheDocument()

    // All 4 slider cards must be present
    expect(screen.getByTestId('slider-card-smooth_sigma')).toBeInTheDocument()
    expect(screen.getByTestId('slider-card-median_passes')).toBeInTheDocument()
    expect(screen.getByTestId('slider-card-fragment_min_px')).toBeInTheDocument()
    expect(screen.getByTestId('slider-card-blob_merge_px')).toBeInTheDocument()
  })

  it('collapses to width 0 when toggle closed', () => {
    usePipelineParams.setState({ sidebarOpen: false })
    const { container } = render(
      wrap(<ParameterSidebar projectId="proj-1" />),
    )
    // When collapsed, the component returns null — sidebar is not in DOM
    const sidebar = container.querySelector('[data-testid="parameter-sidebar"]')
    expect(sidebar).toBeNull()
  })

  it('mirrors InspectorSidebar borderRight: 1px solid var(--gray-6)', () => {
    const { container } = render(
      wrap(<ParameterSidebar projectId="proj-1" />),
    )
    const sidebar = container.querySelector('[data-testid="parameter-sidebar"]') as HTMLElement
    expect(sidebar).toBeTruthy()
    expect(sidebar.style.borderRight).toBe('1px solid var(--gray-6)')
  })

  // Plan 04.1-02 Task 2 / D-06 — single canonical dispatch path.
  // Asserts ParameterSidebar.tsx delegates to useParameterStudioDispatch
  // (instead of inlining the latest-wins sequence) and wires
  // renderStream.subscribe via the onRenderStarted callback.
  it('test_parameter_sidebar_invokes_use_parameter_studio_dispatch', () => {
    render(wrap(<ParameterSidebar projectId="proj-1" />))

    // The hook was called with (projectId, onRenderStarted callback).
    expect(useParameterStudioDispatch).toHaveBeenCalledWith(
      'proj-1',
      expect.any(Function),
    )

    // Extract the onRenderStarted callback from the most recent invocation
    // and verify it wires through to renderStream.subscribe.
    const calls = vi.mocked(useParameterStudioDispatch).mock.calls
    const lastCall = calls[calls.length - 1]
    const onRenderStarted = lastCall[1]
    expect(onRenderStarted).toBeTypeOf('function')
    // Invoke it (simulates the hook's success path calling back into the sidebar).
    onRenderStarted?.('r-99')
    expect(mockSubscribe).toHaveBeenCalledWith('proj-1')
  })
})
