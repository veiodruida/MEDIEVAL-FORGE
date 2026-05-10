/**
 * Plan 04-03 Task 2 — SliderCard unit tests.
 * Tests D-08: Radix Slider.Root + numeric input + reset + default-tick.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import type { ReactNode } from 'react'
import { SliderCard } from '../SliderCard'
import { usePipelineParams, PARAM_DEFAULTS } from '../../../stores/usePipelineParams'

function wrap(node: ReactNode) {
  return <Theme>{node}</Theme>
}

describe('SliderCard', () => {
  beforeEach(() => {
    usePipelineParams.setState({
      values: { ...PARAM_DEFAULTS },
      lastRendered: { ...PARAM_DEFAULTS },
      stageView: 'render-final',
      sidebarOpen: true,
    })
  })

  it('renders Radix Slider.Root with min, max, step from prop', () => {
    render(
      wrap(
        <SliderCard
          paramKey="smooth_sigma"
          label="Suavização (σ)"
          onCommit={() => {}}
          onResetCommit={() => {}}
        />,
      ),
    )
    // Radix Slider.Root renders aria-valuemin / aria-valuemax on the thumb element
    const thumb = screen.getByRole('slider')
    expect(thumb).toHaveAttribute('aria-valuemin', '3')
    expect(thumb).toHaveAttribute('aria-valuemax', '4.5')
    expect(thumb).toHaveAttribute('aria-valuenow', '3')
  })

  it('renders adjacent numeric input with type=number', () => {
    render(
      wrap(
        <SliderCard
          paramKey="smooth_sigma"
          label="Suavização (σ)"
          onCommit={() => {}}
          onResetCommit={() => {}}
        />,
      ),
    )
    const input = screen.getByLabelText(/Suavização.*value/i)
    expect(input).toHaveAttribute('type', 'number')
  })

  it('clamps numeric input out-of-bounds and flashes red 600ms', async () => {
    vi.useFakeTimers()
    render(
      wrap(
        <SliderCard
          paramKey="smooth_sigma"
          label="Suavização (σ)"
          onCommit={() => {}}
          onResetCommit={() => {}}
        />,
      ),
    )
    const input = screen.getByLabelText(/Suavização.*value/i)

    // Type an out-of-bounds value and blur
    fireEvent.change(input, { target: { value: '9999' } })
    fireEvent.blur(input)

    // data-flash should be true immediately
    expect(input).toHaveAttribute('data-flash', 'true')

    // Advance 600ms — flash should clear
    act(() => {
      vi.advanceTimersByTime(600)
    })
    expect(input).toHaveAttribute('data-flash', 'false')

    vi.useRealTimers()
  })

  it('reset IconButton reverts to default and fires onResetCommit immediately', () => {
    const onResetCommit = vi.fn()
    render(
      wrap(
        <SliderCard
          paramKey="smooth_sigma"
          label="Suavização (σ)"
          onCommit={() => {}}
          onResetCommit={onResetCommit}
        />,
      ),
    )

    // First change the value
    act(() => {
      usePipelineParams.getState().setValue('smooth_sigma', 4.0)
    })

    // Click the reset button
    const resetBtn = screen.getByRole('button', { name: /Redefinir Suavização/i })
    fireEvent.click(resetBtn)

    // Value should be reverted to default
    expect(usePipelineParams.getState().values.smooth_sigma).toBe(PARAM_DEFAULTS.smooth_sigma)
    // onResetCommit should fire immediately (not debounced)
    expect(onResetCommit).toHaveBeenCalledTimes(1)
  })

  it('default-tick mark renders at percentage matching default value', () => {
    const { container } = render(
      wrap(
        <SliderCard
          paramKey="smooth_sigma"
          label="Suavização (σ)"
          onCommit={() => {}}
          onResetCommit={() => {}}
        />,
      ),
    )
    const tick = container.querySelector('[data-testid="tick-smooth_sigma"]') as HTMLElement
    expect(tick).toBeTruthy()
    // smooth_sigma default=3.0, min=3.0, max=4.5 → (3.0-3.0)/(4.5-3.0)*100 = 0%
    expect(tick.style.left).toBe('0%')
  })
})
