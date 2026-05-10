/**
 * Plan 04-03 Task 3/4 — WorkspaceToolbar cancel button tests.
 * Tests D-16: status badge → red Cancelar button when state === 'rendering'.
 * Per UI-SPEC §State Machine: cancel only shows during 'rendering', not 'generating'.
 * Task 4 migration: cancel state now read from runState prop ('rendering' added to RunState union).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { WorkspaceToolbar } from '../WorkspaceToolbar'
import type { Project } from '../../../api/client'
import { usePipelineParams, PARAM_DEFAULTS } from '../../../stores/usePipelineParams'
import { useRunStore } from '../../../stores/useRunStore'

// Mock postRenderCancel so tests don't hit network
vi.mock('../../../api/render', () => ({
  postRender: vi.fn().mockResolvedValue({ run_id: 'r-1', status: 'scheduled', kind: 'render' }),
  postRenderCancel: vi.fn().mockResolvedValue(undefined),
  getStageRasterUrl: vi.fn(),
}))

import { postRenderCancel } from '../../../api/render'

const PROJECT: Project = {
  id: 'p1',
  name: 'Iberia 868',
  country_qid: 'Q29',
  period_start: 868,
  period_end: 900,
  bbox_lon_min: null,
  bbox_lon_max: null,
  bbox_lat_min: null,
  bbox_lat_max: null,
  generator_config: null,
  status: 'created',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function wrap(node: ReactNode) {
  return (
    <MemoryRouter>
      <Theme>{node}</Theme>
    </MemoryRouter>
  )
}

function renderToolbar(runState: Parameters<typeof WorkspaceToolbar>[0]['runState']) {
  return render(
    wrap(
      <WorkspaceToolbar
        project={PROJECT}
        runState={runState}
        currentStage={null}
        hasArtifacts={false}
        onGenerate={() => {}}
        onExport={() => {}}
        statusBadgeOpen={false}
        onToggleStatusBadge={() => {}}
      />,
    ),
  )
}

describe('WorkspaceToolbar cancel', () => {
  beforeEach(() => {
    usePipelineParams.setState({
      values: { ...PARAM_DEFAULTS },
      lastRendered: { ...PARAM_DEFAULTS },
      stageView: 'render-final',
      sidebarOpen: true,
    })
    useRunStore.getState().reset()
    vi.mocked(postRenderCancel).mockReset()
    vi.mocked(postRenderCancel).mockResolvedValue(undefined)
  })

  it('renders status badge when state in {idle, generated}', () => {
    // idle: badge shown, no cancel
    renderToolbar('idle')
    expect(screen.queryByTestId('cancel-render-button')).toBeNull()
    expect(screen.getByTestId('generate-status-badge')).toBeInTheDocument()
  })

  it('replaces status badge with red Cancelar button when state in {rendering}', () => {
    // Per UI-SPEC §State Machine: cancel only visible during 'rendering' (not 'generating').
    // During 'generating' the status badge stays visible showing "Gerando: {stage}".
    renderToolbar('rendering')
    expect(screen.getByTestId('cancel-render-button')).toBeInTheDocument()
    expect(screen.getByTestId('cancel-render-button')).toHaveTextContent('Cancelar')
    expect(screen.queryByTestId('generate-status-badge')).toBeNull()
  })

  it('Cancelar onClick fires postRenderCancel(projectId)', async () => {
    // Trigger cancel button via runState='rendering'
    renderToolbar('rendering')

    const cancelBtn = screen.getByTestId('cancel-render-button')
    fireEvent.click(cancelBtn)

    // Allow the async handler to run
    await vi.waitFor(() => {
      expect(postRenderCancel).toHaveBeenCalledTimes(1)
      expect(postRenderCancel).toHaveBeenCalledWith('p1')
    })
  })

  it('badge restores when state flips back to generated', () => {
    // Start in rendering state — cancel button visible
    const { rerender } = renderToolbar('rendering')
    expect(screen.getByTestId('cancel-render-button')).toBeInTheDocument()

    // Re-render with generated state — badge restored
    rerender(
      wrap(
        <WorkspaceToolbar
          project={PROJECT}
          runState="generated"
          currentStage={null}
          hasArtifacts={false}
          onGenerate={() => {}}
          onExport={() => {}}
          statusBadgeOpen={false}
          onToggleStatusBadge={() => {}}
        />,
      ),
    )

    // Badge restored, cancel button gone
    expect(screen.queryByTestId('cancel-render-button')).toBeNull()
    expect(screen.getByTestId('generate-status-badge')).toBeInTheDocument()
  })
})
