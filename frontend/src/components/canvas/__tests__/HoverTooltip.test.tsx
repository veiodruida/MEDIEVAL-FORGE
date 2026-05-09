import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { HoverTooltip } from '../HoverTooltip'

function wrap(node: React.ReactNode) {
  return <Theme>{node}</Theme>
}

describe('HoverTooltip', () => {
  it('renders the condado name when name is provided', () => {
    render(wrap(<HoverTooltip name="Coimbra" x={100} y={200} />))
    expect(screen.getByText('Coimbra')).toBeInTheDocument()
  })

  it('positions itself at x+8 / y+8 (offset away from cursor)', () => {
    const { container } = render(wrap(<HoverTooltip name="Coimbra" x={100} y={200} />))
    const overlay = container.querySelector('div[style]') as HTMLElement
    expect(overlay).not.toBeNull()
    expect(overlay.style.left).toBe('108px')
    expect(overlay.style.top).toBe('208px')
    expect(overlay.style.position).toBe('absolute')
    expect(overlay.style.pointerEvents).toBe('none')
    expect(Number(overlay.style.zIndex)).toBe(50)
  })

  it('renders nothing when name is null', () => {
    const { container } = render(wrap(<HoverTooltip name={null} x={100} y={200} />))
    // No "Coimbra"-style content; the tooltip itself returns null
    expect(container.querySelector('.rt-Card')).toBeNull()
    // Lookup by role or tag absence — div should not exist as tooltip overlay.
    // We just assert no Card descendant rendered.
  })

  it('renders nothing when name is empty string', () => {
    const { container } = render(wrap(<HoverTooltip name="" x={0} y={0} />))
    expect(container.querySelector('.rt-Card')).toBeNull()
  })
})
