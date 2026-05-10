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
  // Text stub added so BaronyLayer's D-12 label render doesn't crash.
  // Props are intentionally minimal — BaronyLayer.test.tsx does not assert label content.
  Text: (p: { 'data-testid'?: string; text?: string; listening?: boolean }) => (
    <div data-testid={p['data-testid']} data-text={p.text} data-listening={String(p.listening)} />
  ),
}))

const B: BaronyRender[] = [
  { id: 'B_A1', name: 'B_A1', condado_id: 'C_A', fill: '#ff0000', points: [0, 0, 10, 0, 10, 10, 0, 10] },
  { id: 'B_B1', name: 'B_B1', condado_id: 'C_B', fill: '#00ff00', points: [20, 0, 30, 0, 30, 10, 20, 10] },
]

const COLORS: Record<string, string> = {
  B_A1: '#ff0000',
  B_B1: '#00ff00',
}

describe('BaronyLayer', () => {
  it('renders one Line per barony with fill resolved via baronyColors lookup', () => {
    render(<BaronyLayer baronies={B} baronyColors={COLORS} visible />)
    const lines = screen.getAllByTestId('line')
    expect(lines.length).toBe(2)
    expect(lines[0].getAttribute('data-fill')).toBe('#ff0000')
    expect(lines[1].getAttribute('data-fill')).toBe('#00ff00')
    lines.forEach((l) => {
      expect(l.getAttribute('data-closed')).toBe('true')
      // Listening is gated on `visible`. When the layer is on, individual
      // Lines are click-targets so the user can pick a barony for the
      // Phase 03 follow-up barony detail mode.
      expect(l.getAttribute('data-listening')).toBe('true')
    })
  })

  it('Layer is interactive (listening=true) when visible and opacity stays 0.85', () => {
    render(<BaronyLayer baronies={B} baronyColors={COLORS} visible />)
    const layer = screen.getByTestId('layer')
    expect(layer.getAttribute('data-listening')).toBe('true')
    expect(layer.getAttribute('data-opacity')).toBe('0.85')
  })

  it('Layer becomes inert (listening=false) when visible=false', () => {
    render(<BaronyLayer baronies={B} baronyColors={COLORS} visible={false} />)
    const layer = screen.getByTestId('layer')
    expect(layer.getAttribute('data-listening')).toBe('false')
  })

  it('respects visible prop', () => {
    const { rerender } = render(<BaronyLayer baronies={B} baronyColors={COLORS} visible />)
    expect(screen.getByTestId('layer').getAttribute('data-visible')).toBe('true')
    rerender(<BaronyLayer baronies={B} baronyColors={COLORS} visible={false} />)
    expect(screen.getByTestId('layer').getAttribute('data-visible')).toBe('false')
  })

  it('falls back to BaronyRender.fill when the colors map is missing the id', () => {
    render(<BaronyLayer baronies={B} baronyColors={{}} visible />)
    const lines = screen.getAllByTestId('line')
    // Falls back to the fill field that the geojson select carried (Plan 03-01
    // wrote no `fill` property at the backend, so this path is also tolerant
    // of `undefined`, ending at the gray FALLBACK_FILL).
    expect(lines[0].getAttribute('data-fill')).toBe('#ff0000')
    expect(lines[1].getAttribute('data-fill')).toBe('#00ff00')
  })

  it('renders an empty Layer when baronies list is empty', () => {
    render(<BaronyLayer baronies={[]} baronyColors={COLORS} visible />)
    expect(screen.queryAllByTestId('line').length).toBe(0)
  })
})
