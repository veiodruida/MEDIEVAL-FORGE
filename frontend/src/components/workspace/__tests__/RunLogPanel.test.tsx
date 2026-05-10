import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import type { ReactNode } from 'react'
import { RunLogPanel } from '../RunLogPanel'
import { PIPELINE_STAGES } from '../../../stores/useRunStore'

function wrap(node: ReactNode) {
  return <Theme>{node}</Theme>
}

describe('RunLogPanel', () => {
  it('renders all 12 PIPELINE_STAGES in canonical order', () => {
    render(
      wrap(
        <RunLogPanel
          completedStages={[]}
          currentStage={null}
          errorStage={null}
        />,
      ),
    )
    const rows = screen.getAllByTestId(/stage-row-/)
    expect(rows).toHaveLength(12)
    PIPELINE_STAGES.forEach((stage, idx) => {
      expect(rows[idx]).toHaveTextContent(stage)
    })
  })

  it('marks completed stages with done state and current stage with active state', () => {
    render(
      wrap(
        <RunLogPanel
          completedStages={['landmask', 'border']}
          currentStage="voronoi"
          errorStage={null}
        />,
      ),
    )
    const done = screen.getAllByTestId('stage-row-done')
    expect(done).toHaveLength(2)
    expect(done[0]).toHaveTextContent('landmask')
    expect(done[1]).toHaveTextContent('border')

    const active = screen.getAllByTestId('stage-row-active')
    expect(active).toHaveLength(1)
    expect(active[0]).toHaveTextContent('voronoi')

    const pending = screen.getAllByTestId('stage-row-pending')
    expect(pending).toHaveLength(9)
  })

  it('marks error stage with error state (overrides other states)', () => {
    render(
      wrap(
        <RunLogPanel
          completedStages={['landmask', 'border']}
          currentStage={null}
          errorStage="voronoi"
        />,
      ),
    )
    const errors = screen.getAllByTestId('stage-row-error')
    expect(errors).toHaveLength(1)
    expect(errors[0]).toHaveTextContent('voronoi')
  })
})
