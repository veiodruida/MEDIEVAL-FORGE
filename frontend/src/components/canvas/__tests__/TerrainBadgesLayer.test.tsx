import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TerrainBadgesLayer } from '../TerrainBadgesLayer'
import { ProjectionProvider } from '../../../context/ProjectionContext'
import { buildProjectionConfig, geoToCanvas } from '../../../lib/projection'
import { useProjectStore } from '../../../stores/useProjectStore'
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
  Text: (p: {
    text?: string
    x?: number
    y?: number
    fontSize?: number
    listening?: boolean
    align?: string
    verticalAlign?: string
    offsetX?: number
    offsetY?: number
  }) => (
    <div
      data-testid="terrain-badge"
      data-text={p.text ?? ''}
      data-x={String(p.x ?? '')}
      data-y={String(p.y ?? '')}
      data-font-size={String(p.fontSize ?? '')}
      data-listening={String(p.listening ?? true)}
      data-align={p.align ?? ''}
      data-vertical-align={p.verticalAlign ?? ''}
      data-offset-x={String(p.offsetX ?? '')}
      data-offset-y={String(p.offsetY ?? '')}
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
    id: 'c1',
    name: 'Condado 1',
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
    id: 'c2',
    name: 'Condado 2',
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

function wrap(node: React.ReactNode) {
  return <ProjectionProvider value={PROJECTION}>{node}</ProjectionProvider>
}

describe('TerrainBadgesLayer — emoji badge rendering', () => {
  beforeEach(() => {
    // Reset store terrain_types before each test
    useProjectStore.setState({ terrain_types: {} })
    useProjectStore.temporal.getState().clear()
  })

  it('test_renders_one_badge_per_painted_territory: renders two badges for c1=forest c2=mountain', () => {
    useProjectStore.setState({ terrain_types: { c1: 'forest', c2: 'mountain' } })

    render(wrap(<TerrainBadgesLayer condados={CONDADOS} projection={PROJECTION} />))

    const badges = screen.getAllByTestId('terrain-badge')
    expect(badges.length).toBe(2)

    const texts = badges.map((b) => b.getAttribute('data-text'))
    expect(texts).toContain('🌲')
    expect(texts).toContain('⛰️')
  })

  it('test_skips_territories_without_terrain: only one badge when c1=forest, c2 unpainted', () => {
    useProjectStore.setState({ terrain_types: { c1: 'forest' } })

    render(wrap(<TerrainBadgesLayer condados={CONDADOS} projection={PROJECTION} />))

    const badges = screen.queryAllByTestId('terrain-badge')
    expect(badges.length).toBe(1)
    expect(badges[0].getAttribute('data-text')).toBe('🌲')
  })

  it('test_text_props_match_spec: fontSize=14, listening=false, offsetX=7, offsetY=7', () => {
    useProjectStore.setState({ terrain_types: { c1: 'plains' } })

    render(wrap(<TerrainBadgesLayer condados={CONDADOS} projection={PROJECTION} />))

    const badge = screen.getByTestId('terrain-badge')
    expect(badge.getAttribute('data-font-size')).toBe('14')
    expect(badge.getAttribute('data-listening')).toBe('false')
    expect(badge.getAttribute('data-offset-x')).toBe('7')
    expect(badge.getAttribute('data-offset-y')).toBe('7')
    expect(badge.getAttribute('data-align')).toBe('center')
    expect(badge.getAttribute('data-vertical-align')).toBe('middle')
  })

  it('test_position_uses_geoToCanvas: x/y match projected coordinates of the condado centroid', () => {
    useProjectStore.setState({ terrain_types: { c1: 'river' } })

    render(wrap(<TerrainBadgesLayer condados={CONDADOS} projection={PROJECTION} />))

    const badge = screen.getByTestId('terrain-badge')
    const [expectedX, expectedY] = geoToCanvas(CONDADOS[0].lon, CONDADOS[0].lat, PROJECTION)

    expect(badge.getAttribute('data-x')).toBe(String(expectedX))
    expect(badge.getAttribute('data-y')).toBe(String(expectedY))
  })

  it('renders nothing when terrain_types is empty', () => {
    useProjectStore.setState({ terrain_types: {} })

    render(wrap(<TerrainBadgesLayer condados={CONDADOS} projection={PROJECTION} />))

    expect(screen.queryAllByTestId('terrain-badge').length).toBe(0)
  })
})
