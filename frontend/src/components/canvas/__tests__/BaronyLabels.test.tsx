import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BaronyLayer } from '../BaronyLayer'
import type { BaronyRender } from '../../../hooks/useCanvasArtifacts'

// Mock react-konva — jsdom has no canvas context.
// Text mock exposes all Konva props as data-* attributes so assertions can
// read fontSize, fill, shadowBlur, shadowColor, x, y, text, listening.
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
  Text: (p: {
    'data-testid'?: string
    x?: number
    y?: number
    text?: string
    fontSize?: number
    fill?: string
    fontStyle?: string
    offsetX?: number
    offsetY?: number
    shadowColor?: string
    shadowBlur?: number
    shadowOffset?: { x: number; y: number }
    shadowOpacity?: number
    listening?: boolean
  }) => (
    <div
      data-testid={p['data-testid']}
      data-x={String(p.x)}
      data-y={String(p.y)}
      data-text={p.text}
      data-font-size={String(p.fontSize)}
      data-fill={p.fill}
      data-shadow-color={p.shadowColor}
      data-shadow-blur={String(p.shadowBlur)}
      data-listening={String(p.listening)}
    />
  ),
}))

// Mock useUIStore — BaronyLayer reads selectedBaronyId + selectBarony
vi.mock('../../../stores/uiStore', () => ({
  useUIStore: (selector: (s: { selectedBaronyId: null; selectBarony: () => void }) => unknown) =>
    selector({ selectedBaronyId: null, selectBarony: () => {} }),
}))

const SAMPLE: BaronyRender[] = [
  {
    id: 'b1',
    name: 'Curta',
    condado_id: 'c1',
    fill: '#abc',
    points: [0, 0, 100, 0, 100, 100, 0, 100],
    // centroid = (50, 50); name length 5; no truncation
  },
  {
    id: 'b2',
    name: 'BaroniaDeNomeMuitoLongo',
    condado_id: 'c1',
    fill: '#def',
    points: [200, 200, 300, 200, 300, 300, 200, 300],
    // centroid = (250, 250); name length 22; truncated to 'BaroniaDeNo…' (11 chars + ellipsis = 12)
  },
]

describe('BaronyLabels (D-12)', () => {
  it('renders Konva Text per barony when layerVisibility.baronies is true', () => {
    render(<BaronyLayer baronies={SAMPLE} baronyColors={{}} visible={true} />)
    expect(screen.queryByTestId('barony-label-b1')).toBeTruthy()
    expect(screen.queryByTestId('barony-label-b2')).toBeTruthy()
  })

  it('hides labels when layerVisibility.baronies is false', () => {
    render(<BaronyLayer baronies={SAMPLE} baronyColors={{}} visible={false} />)
    expect(screen.queryByTestId('barony-label-b1')).toBeFalsy()
    expect(screen.queryByTestId('barony-label-b2')).toBeFalsy()
  })

  it('truncates label at 12 chars with ellipsis', () => {
    render(<BaronyLayer baronies={SAMPLE} baronyColors={{}} visible={true} />)
    const labelB2 = screen.queryByTestId('barony-label-b2')
    expect(labelB2).toBeTruthy()
    // 'BaroniaDeNo' (11 chars) + '…' (U+2026) = 12 visible chars
    expect(labelB2!.getAttribute('data-text')).toBe('BaroniaDeNo…')
    // Short name: no truncation
    const labelB1 = screen.queryByTestId('barony-label-b1')
    expect(labelB1!.getAttribute('data-text')).toBe('Curta')
  })

  it('positions text at barony centroid pixel coordinate', () => {
    render(<BaronyLayer baronies={SAMPLE} baronyColors={{}} visible={true} />)
    // b1 centroid: mean([0,100,100,0]) = 50, mean([0,0,100,100]) = 50
    const labelB1 = screen.queryByTestId('barony-label-b1')
    expect(labelB1).toBeTruthy()
    expect(labelB1!.getAttribute('data-x')).toBe('50')
    expect(labelB1!.getAttribute('data-y')).toBe('50')
    // b2 centroid: mean([200,300,300,200]) = 250, mean([200,200,300,300]) = 250
    const labelB2 = screen.queryByTestId('barony-label-b2')
    expect(labelB2!.getAttribute('data-x')).toBe('250')
    expect(labelB2!.getAttribute('data-y')).toBe('250')
  })

  it('font size is 10px, fill is #FFFFFF, shadow blur is 1px black, listening=false', () => {
    render(<BaronyLayer baronies={SAMPLE} baronyColors={{}} visible={true} />)
    const labelB1 = screen.queryByTestId('barony-label-b1')
    expect(labelB1).toBeTruthy()
    expect(labelB1!.getAttribute('data-font-size')).toBe('10')
    expect(labelB1!.getAttribute('data-fill')).toBe('#FFFFFF')
    expect(labelB1!.getAttribute('data-shadow-blur')).toBe('1')
    expect(labelB1!.getAttribute('data-shadow-color')).toBe('black')
    expect(labelB1!.getAttribute('data-listening')).toBe('false')
  })
})
