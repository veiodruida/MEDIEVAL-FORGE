/**
 * Plan 04-03 Task 2 — StageViewToggle unit tests.
 * Tests D-10/D-11: Radix RadioGroup with 5 PT-BR stage view options.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import type { ReactNode } from 'react'
import { StageViewToggle } from '../StageViewToggle'
import { usePipelineParams, PARAM_DEFAULTS } from '../../../stores/usePipelineParams'

function wrap(node: ReactNode) {
  return <Theme>{node}</Theme>
}

describe('StageViewToggle', () => {
  beforeEach(() => {
    usePipelineParams.setState({
      values: { ...PARAM_DEFAULTS },
      lastRendered: { ...PARAM_DEFAULTS },
      stageView: 'render-final',
      sidebarOpen: true,
    })
  })

  it('renders 5 RadioGroup items with PT-BR labels', () => {
    render(wrap(<StageViewToggle />))

    // All 5 PT-BR labels must be present
    expect(screen.getByText('Máscara terrestre')).toBeInTheDocument()
    expect(screen.getByText('Voronoi bruto')).toBeInTheDocument()
    expect(screen.getByText('Limpeza')).toBeInTheDocument()
    expect(screen.getByText('Suavização')).toBeInTheDocument()
    expect(screen.getByText('Mapa final')).toBeInTheDocument()

    // Exactly 5 radio inputs
    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(5)
  })

  it('default selection is render-final', () => {
    render(wrap(<StageViewToggle />))

    const radios = screen.getAllByRole('radio')
    // render-final is last in the OPTIONS array
    const renderFinalRadio = radios[radios.length - 1]
    expect(renderFinalRadio).toBeChecked()

    // The others should not be checked
    expect(radios[0]).not.toBeChecked() // landmask
    expect(radios[1]).not.toBeChecked() // voronoi-raw
  })

  it('onChange fires with new stage_view value', () => {
    render(wrap(<StageViewToggle />))

    // Click the "Limpeza" radio (cleanup)
    const limpezaRadio = screen.getByRole('radio', { name: 'Limpeza' })
    fireEvent.click(limpezaRadio)

    // Store should be updated
    expect(usePipelineParams.getState().stageView).toBe('cleanup')
  })

  it('section heading reads "Vista do estágio"', () => {
    render(wrap(<StageViewToggle />))
    expect(screen.getByText('Vista do estágio')).toBeInTheDocument()
  })
})
