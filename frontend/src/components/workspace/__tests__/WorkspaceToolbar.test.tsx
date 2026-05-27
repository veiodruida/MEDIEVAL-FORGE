import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { WorkspaceToolbar } from '../WorkspaceToolbar'
import type { Project } from '../../../api/client'

// Mock BranchPicker + EditorSyncBridge so WorkspaceToolbar tests don't need
// QueryClientProvider (BranchPicker uses useBranches which requires TanStack context)
vi.mock('../../../components/editor/BranchPicker', () => ({
  BranchPicker: () => null,
}))
vi.mock('../../../components/editor/EditorSyncBridge', () => ({
  EditorSyncBridge: () => null,
}))

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

describe('WorkspaceToolbar', () => {
  it('renders project name and ← Projetos back link to /projects', () => {
    render(
      wrap(
        <WorkspaceToolbar
          project={PROJECT}
          runState="idle"
          currentStage={null}
          onGenerate={() => {}}
          onExport={() => {}}
          statusBadgeOpen={false}
          onToggleStatusBadge={() => {}}
        />,
      ),
    )
    expect(screen.getByText('Iberia 868')).toBeInTheDocument()
    const back = screen.getByRole('link', { name: /Projetos/ })
    expect(back).toHaveAttribute('href', '/projects')
  })

  it('renders "Gerar Mapa" button when runState=idle', () => {
    const onGenerate = vi.fn()
    render(
      wrap(
        <WorkspaceToolbar
          project={PROJECT}
          runState="idle"
          currentStage={null}
          onGenerate={onGenerate}
          onExport={() => {}}
          statusBadgeOpen={false}
          onToggleStatusBadge={() => {}}
        />,
      ),
    )
    const btn = screen.getByRole('button', { name: 'Gerar Mapa' })
    expect(btn).toBeEnabled()
    fireEvent.click(btn)
    expect(onGenerate).toHaveBeenCalledTimes(1)
  })

  it('renders disabled "Regenerar" button when runState=generating', () => {
    render(
      wrap(
        <WorkspaceToolbar
          project={PROJECT}
          runState="generating"
          currentStage="voronoi"
          onGenerate={() => {}}
          onExport={() => {}}
          statusBadgeOpen={false}
          onToggleStatusBadge={() => {}}
        />,
      ),
    )
    const btn = screen.getByRole('button', { name: 'Regenerar' })
    expect(btn).toBeDisabled()
  })

  it('renders Exportar ZIP button always', () => {
    const onExport = vi.fn()
    render(
      wrap(
        <WorkspaceToolbar
          project={PROJECT}
          runState="idle"
          currentStage={null}
          onGenerate={() => {}}
          onExport={onExport}
          statusBadgeOpen={false}
          onToggleStatusBadge={() => {}}
        />,
      ),
    )
    const btn = screen.getByRole('button', { name: 'Exportar ZIP' })
    fireEvent.click(btn)
    expect(onExport).toHaveBeenCalledTimes(1)
  })

  it('renders toolbar at 48px height', () => {
    const { container } = render(
      wrap(
        <WorkspaceToolbar
          project={PROJECT}
          runState="idle"
          currentStage={null}
          onGenerate={() => {}}
          onExport={() => {}}
          statusBadgeOpen={false}
          onToggleStatusBadge={() => {}}
        />,
      ),
    )
    const root = container.querySelector('[data-testid="workspace-toolbar"]') as HTMLElement
    expect(root).toBeTruthy()
    expect(root.style.height).toBe('48px')
  })
})
