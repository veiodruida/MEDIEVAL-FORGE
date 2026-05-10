/**
 * Plan 04-03 Task 2 — ParameterSidebar unit tests.
 * Tests D-05/D-06: 320px collapsible sidebar with StageViewToggle + 4 SliderCards.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import type { ReactNode } from 'react'
import { ParameterSidebar } from '../ParameterSidebar'
import { usePipelineParams, PARAM_DEFAULTS } from '../../../stores/usePipelineParams'
import { useRunStore } from '../../../stores/useRunStore'

// Mock the render API and useRenderStream so ParameterSidebar tests don't hit network
vi.mock('../../../api/render', () => ({
  postRender: vi.fn().mockResolvedValue({ run_id: 'r-1', status: 'scheduled', kind: 'render' }),
  postRenderCancel: vi.fn().mockResolvedValue(undefined),
  getStageRasterUrl: vi.fn(),
}))

vi.mock('../../../api/useRenderStream', () => ({
  useRenderStream: vi.fn(() => ({
    subscribe: vi.fn(),
    close: vi.fn(),
  })),
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
})
