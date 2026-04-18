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

  it('positions itself bottom-left with minHeight >= 44', () => {
    const { container } = render(wrap(<FitToViewButton onFit={() => {}} />))
    const wrapper = container.querySelector('[data-testid="fit-to-view-wrapper"]') as HTMLElement
    expect(wrapper).not.toBeNull()
    const s = wrapper.style
    expect(s.bottom).toBe('12px')
    expect(s.left).toBe('12px')
    expect(s.position).toBe('absolute')
    // min-height on the button target (wrapper or button)
    const btn = wrapper.querySelector('button') as HTMLButtonElement
    expect(btn).not.toBeNull()
    const mh = btn.style.minHeight || wrapper.style.minHeight
    // Accept "44px" literal
    expect(mh).toBe('44px')
  })

  it('calls onFit when clicked', () => {
    const onFit = vi.fn()
    render(wrap(<FitToViewButton onFit={onFit} />))
    fireEvent.click(screen.getByText('Fit to view'))
    expect(onFit).toHaveBeenCalledOnce()
  })
})
