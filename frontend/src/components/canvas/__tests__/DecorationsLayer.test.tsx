import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DecorationsLayer, LABEL_ZOOM_THRESHOLD_RELATIVE } from '../DecorationsLayer'
import { ProjectionProvider } from '../../../context/ProjectionContext'
import { buildProjectionConfig } from '../../../lib/projection'
import type { TerritoryMetadataCondado } from '../../../hooks/useCanvasArtifacts'

// Minimal react-konva mock exposing data-* attrs the tests need
vi.mock('react-konva', () => ({
  Layer: ({
    children,
    listening,
  }: {
    children?: React.ReactNode
    listening?: boolean
  }) => (
    <div data-testid="konva-layer" data-listening={String(listening ?? true)}>
      {children}
    </div>
  ),
  Circle: (p: {
    x?: number
    y?: number
    radius?: number
    fill?: string
    stroke?: string
    strokeWidth?: number
    shadowBlur?: number
    'data-role'?: string
  }) => (
    <div
      data-testid="circle"
      data-x={String(p.x ?? '')}
      data-y={String(p.y ?? '')}
      data-radius={String(p.radius ?? '')}
      data-fill={p.fill ?? ''}
      data-stroke={p.stroke ?? ''}
      data-stroke-width={String(p.strokeWidth ?? '')}
      data-shadow-blur={p.shadowBlur === undefined ? null : String(p.shadowBlur)}
      data-role={p['data-role'] ?? ''}
    />
  ),
  Text: (p: {
    text?: string
    x?: number
    y?: number
    fontFamily?: string
    fontSize?: number
    fill?: string
    stroke?: string
    strokeWidth?: number
    listening?: boolean
  }) => (
    <div
      data-testid="text"
      data-text={p.text ?? ''}
      data-font-family={p.fontFamily ?? ''}
      data-font-size={String(p.fontSize ?? '')}
      data-fill={p.fill ?? ''}
      data-stroke={p.stroke ?? ''}
      data-stroke-width={String(p.strokeWidth ?? '')}
      data-listening={String(p.listening ?? true)}
    />
  ),
}))

const PROJECTION = buildProjectionConfig(
  { lonMin: -10, lonMax: 0, latMin: 40, latMax: 50 },
  2000,
  1600,
)

const CONDADOS: TerritoryMetadataCondado[] = [
  {
    id: 'C_A',
    name: 'Condado A',
    lon: -8,
    lat: 43,
    duchy: 'D_1',
    kingdom: 'K_1',
    pixel_center: [0, 0],
    pixel_count: 100,
    baronies: [],
    neighbors: [],
  },
  {
    id: 'C_B',
    name: 'Condado B',
    lon: -5,
    lat: 45,
    duchy: 'D_1',
    kingdom: 'K_1',
    pixel_center: [0, 0],
    pixel_count: 100,
    baronies: [],
    neighbors: [],
  },
]

const COLORS: Record<string, string> = { C_A: '#ff0000', C_B: '#00ff00' }

function wrap(node: React.ReactNode) {
  return <ProjectionProvider value={PROJECTION}>{node}</ProjectionProvider>
}

describe('DecorationsLayer — D-04 dual-ring capitals', () => {
  it('exposes LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0', () => {
    expect(LABEL_ZOOM_THRESHOLD_RELATIVE).toBe(2.0)
  })

  it('renders D-04 dual-ring capitals when layerVisibility.capitals=true', () => {
    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
        />,
      ),
    )
    const circles = screen.getAllByTestId('circle')
    // 2 condados × 2 circles each = 4
    expect(circles.length).toBe(4)

    const darkRings = circles.filter((c) => c.getAttribute('data-radius') === '6.75')
    const inners = circles.filter((c) => c.getAttribute('data-radius') === '6')
    expect(darkRings.length).toBe(2)
    expect(inners.length).toBe(2)

    darkRings.forEach((r) => {
      expect(r.getAttribute('data-fill')).toBe('rgba(0, 0, 0, 0.6)')
    })
    inners.forEach((i) => {
      expect(i.getAttribute('data-stroke')).toBe('#ffffff')
      expect(i.getAttribute('data-stroke-width')).toBe('1.5')
    })

    // No shadow-based ring — D-04 specifies a real circle, not a shadow.
    // shadowBlur is undefined on both circles → React omits the attribute → getAttribute returns null
    circles.forEach((c) => {
      expect(c.getAttribute('data-shadow-blur')).toBeNull()
    })
  })

  it('inner disk fills match the per-condado color map', () => {
    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
        />,
      ),
    )
    const inners = screen
      .getAllByTestId('circle')
      .filter((c) => c.getAttribute('data-radius') === '6')
    const fills = inners.map((i) => i.getAttribute('data-fill'))
    expect(fills).toContain('#ff0000')
    expect(fills).toContain('#00ff00')
  })

  it('hides capitals when layerVisibility.capitals=false', () => {
    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: false, labels: false }}
          currentScale={1}
          minScale={0.34}
        />,
      ),
    )
    expect(screen.queryAllByTestId('circle').length).toBe(0)
  })
})

describe('DecorationsLayer — label gating (D-04 + zoom threshold)', () => {
  it('does NOT render labels when currentScale < LABEL_ZOOM_THRESHOLD_RELATIVE * minScale', () => {
    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: true }}
          currentScale={0.5}
          minScale={0.34}
        />,
      ),
    )
    expect(screen.queryAllByTestId('text').length).toBe(0)
  })

  it('renders labels when layerVisibility.labels && currentScale >= 2*minScale', () => {
    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: true }}
          currentScale={0.68}
          minScale={0.34}
        />,
      ),
    )
    const texts = screen.getAllByTestId('text')
    expect(texts.length).toBe(2)
    texts.forEach((t) => {
      expect(t.getAttribute('data-font-family')).toBe('system-ui, sans-serif')
      expect(t.getAttribute('data-font-size')).toBe('12')
      expect(t.getAttribute('data-fill')).toBe('#1a1a1a')
      expect(t.getAttribute('data-stroke')).toBe('rgba(255,255,255,0.7)')
      expect(t.getAttribute('data-stroke-width')).toBe('1')
      expect(t.getAttribute('data-listening')).toBe('false')
    })
  })

  it('does NOT render labels when layerVisibility.labels=false even above threshold', () => {
    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={5}
          minScale={0.34}
        />,
      ),
    )
    expect(screen.queryAllByTestId('text').length).toBe(0)
  })
})

describe('DecorationsLayer — layer props', () => {
  it('Layer has listening=false (decorative, not interactive)', () => {
    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
        />,
      ),
    )
    const layer = screen.getByTestId('konva-layer')
    expect(layer.getAttribute('data-listening')).toBe('false')
  })
})
