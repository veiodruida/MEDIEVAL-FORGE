import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BaronyLayer } from '../BaronyLayer'
import type { BaronyRender } from '../../../hooks/useCanvasArtifacts'

vi.mock('react-konva', () => ({
  Layer: ({ children, listening, visible, opacity }: {
    children?: React.ReactNode
    listening?: boolean
    visible?: boolean
    opacity?: number
  }) => (
    <div
      data-testid="layer"
      data-listening={String(listening)}
      data-visible={String(visible)}
      data-opacity={String(opacity)}
    >
      {children}
    </div>
  ),
  Line: (p: {
    fill?: string
    closed?: boolean
    listening?: boolean
    stroke?: string
    strokeWidth?: number
    points?: number[]
  }) => (
    <div
      data-testid="line"
      data-fill={p.fill}
      data-closed={String(p.closed)}
      data-listening={String(p.listening)}
    />
  ),
}))

const B: BaronyRender[] = [
  { id: 'B_A1', name: 'B_A1', condado_id: 'C_A', fill: '#ff0000', points: [0, 0, 10, 0, 10, 10, 0, 10] },
  { id: 'B_B1', name: 'B_B1', condado_id: 'C_B', fill: '#00ff00', points: [20, 0, 30, 0, 30, 10, 20, 10] },
]

describe('BaronyLayer', () => {
  it('renders one Line per barony with fill from the BaronyRender.fill field', () => {
    render(<BaronyLayer baronies={B} visible />)
    const lines = screen.getAllByTestId('line')
    expect(lines.length).toBe(2)
    expect(lines[0].getAttribute('data-fill')).toBe('#ff0000')
    expect(lines[1].getAttribute('data-fill')).toBe('#00ff00')
    lines.forEach((l) => {
      expect(l.getAttribute('data-closed')).toBe('true')
      expect(l.getAttribute('data-listening')).toBe('false')
    })
  })

  it('Layer has listening=false and opacity=0.85', () => {
    render(<BaronyLayer baronies={B} visible />)
    const layer = screen.getByTestId('layer')
    expect(layer.getAttribute('data-listening')).toBe('false')
    expect(layer.getAttribute('data-opacity')).toBe('0.85')
  })

  it('respects visible prop', () => {
    const { rerender } = render(<BaronyLayer baronies={B} visible />)
    expect(screen.getByTestId('layer').getAttribute('data-visible')).toBe('true')
    rerender(<BaronyLayer baronies={B} visible={false} />)
    expect(screen.getByTestId('layer').getAttribute('data-visible')).toBe('false')
  })

  it('renders an empty Layer when baronies list is empty', () => {
    render(<BaronyLayer baronies={[]} visible />)
    expect(screen.queryAllByTestId('line').length).toBe(0)
  })
})
