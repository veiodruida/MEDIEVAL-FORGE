import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { FitToViewButton } from '../FitToViewButton'

function wrap(node: React.ReactNode) {
  return <Theme>{node}</Theme>
}

describe('FitToViewButton', () => {
  it('renders with the exact label "Fit to view"', () => {
    render(wrap(<FitToViewButton onFit={() => {}} />))
    expect(screen.getByText('Fit to view')).toBeInTheDocument()
  })

  it('positions itself bottom-right at 12px inset with a 44px tap target (WCAG AA)', () => {
    // Moved from bottom-left to bottom-right on 2026-04-23 because LegendCard
    // (quick-task 260420-hkr) also sits at bottom-left and covered the button.
    const { container } = render(wrap(<FitToViewButton onFit={() => {}} />))
    const wrapper = container.querySelector('[data-testid="fit-to-view-wrapper"]') as HTMLElement
    expect(wrapper).not.toBeNull()
    const s = wrapper.style
    expect(s.bottom).toBe('12px')
    expect(s.right).toBe('12px')
    expect(s.left).toBe('') // explicitly NOT set — must be right-anchored
    expect(s.position).toBe('absolute')
    // 44px min tap target on the button (WCAG 2.5.5 AA)
    const btn = wrapper.querySelector('button') as HTMLButtonElement
    expect(btn).not.toBeNull()
    const mh = btn.style.minHeight || wrapper.style.minHeight
    expect(mh).toBe('44px')
  })

  it('calls onFit when clicked', () => {
    const onFit = vi.fn()
    render(wrap(<FitToViewButton onFit={onFit} />))
    fireEvent.click(screen.getByText('Fit to view'))
    expect(onFit).toHaveBeenCalledOnce()
  })
})
