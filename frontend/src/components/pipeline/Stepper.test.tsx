import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { Stepper } from './Stepper'
import type { StepStatus } from '../../stores/usePipelineStore'

function makeStatuses(overrides: Partial<Record<string, StepStatus>> = {}) {
  return {
    osm: 'pending' as StepStatus,
    baronies: 'pending' as StepStatus,
    research: 'pending' as StepStatus,
    map: 'pending' as StepStatus,
    codex: 'pending' as StepStatus,
    ...overrides,
  }
}

function renderStepper(props?: Partial<React.ComponentProps<typeof Stepper>>) {
  const defaults = {
    currentStep: 1 as const,
    statuses: makeStatuses(),
    onStepClick: vi.fn(),
  }
  return render(
    <Theme>
      <Stepper {...defaults} {...props} />
    </Theme>,
  )
}

describe('Stepper', () => {
  it('renders 5 nodes with labels OSM/Baronies/Pesquisa/Mapa/Codex', () => {
    renderStepper()
    expect(screen.getByText('OSM')).toBeInTheDocument()
    expect(screen.getByText('Baronies')).toBeInTheDocument()
    expect(screen.getByText('Pesquisa')).toBeInTheDocument()
    expect(screen.getByText('Mapa')).toBeInTheDocument()
    expect(screen.getByText('Codex')).toBeInTheDocument()
  })

  it('node with status done shows data-status="done"', () => {
    renderStepper({ statuses: makeStatuses({ osm: 'done' }) })
    // The OSM node button should have data-status="done"
    const osmBtn = screen.getByRole('button', { name: /OSM/i })
    expect(osmBtn.closest('[data-status="done"]') ?? osmBtn).toHaveAttribute('data-status', 'done')
  })

  it('node with status active shows data-status="active"', () => {
    renderStepper({ statuses: makeStatuses({ baronies: 'active' }) })
    const btn = screen.getByRole('button', { name: /Baronies/i })
    expect(btn.closest('[data-status="active"]') ?? btn).toHaveAttribute('data-status', 'active')
  })

  it('node with status error shows data-status="error"', () => {
    renderStepper({ statuses: makeStatuses({ research: 'error' }) })
    const btn = screen.getByRole('button', { name: /Pesquisa/i })
    expect(btn.closest('[data-status="error"]') ?? btn).toHaveAttribute('data-status', 'error')
  })

  it('clicking a node calls onStepClick with that step number', () => {
    const onStepClick = vi.fn()
    renderStepper({ onStepClick })
    fireEvent.click(screen.getByRole('button', { name: /Mapa/i }))
    expect(onStepClick).toHaveBeenCalledWith(4)
  })

  it('currentStep node has aria-current="step"', () => {
    renderStepper({ currentStep: 3 })
    const btn = screen.getByRole('button', { name: /Pesquisa/i })
    // The button or a wrapper should have aria-current="step"
    const node = btn.closest('[aria-current="step"]') ?? btn
    expect(node).toHaveAttribute('aria-current', 'step')
  })
})
