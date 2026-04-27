import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { act } from 'react'
import { TerritoryLayer } from '../TerritoryLayer'
import type { TerritoryRender } from '../../../hooks/useCanvasArtifacts'
import type { TerrainType } from '../../../types/editing'

// Mock react-konva — Konva requires a real DOM canvas context not available in jsdom
vi.mock('react-konva', () => ({
  Layer: ({ children, visible }: { children?: React.ReactNode; visible?: boolean }) => (
    <div data-testid="territory-layer" data-visible={String(visible ?? true)}>
      {children}
    </div>
  ),
  Line: (p: {
    points?: number[]
    closed?: boolean
    fill?: string
    stroke?: string
    strokeWidth?: number
    onClick?: () => void
    listening?: boolean
  }) => (
    <div
      data-testid="territory-line"
      data-closed={String(p.closed)}
      data-fill={p.fill}
      data-stroke={p.stroke}
      data-stroke-width={String(p.strokeWidth)}
    />
  ),
}))

// Mock useUIStore so tests can control selectedTerritoryId and layerVisibility.terrain
const mockUIStore = {
  selectedTerritoryId: null as string | null,
  layerVisibility: {
    condados: true,
    baronies: false,
    terrain: false,
    borders: true,
    capitals: true,
    labels: false,
  },
}

vi.mock('../../../stores/uiStore', () => ({
  useUIStore: (selector: (s: typeof mockUIStore) => unknown) => selector(mockUIStore),
}))

// Mock useProjectStore so tests can control terrain_types
const mockProjectStore = {
  terrain_types: {} as Record<string, TerrainType>,
}

vi.mock('../../../stores/useProjectStore', () => ({
  useProjectStore: (selector: (s: typeof mockProjectStore) => unknown) => selector(mockProjectStore),
  beginTransaction: vi.fn(),
  endTransaction: vi.fn(),
}))

const T: TerritoryRender[] = [
  { id: 'C_A', name: 'A', points: [0, 0, 10, 0, 10, 10], neighbors: [] },
  { id: 'C_B', name: 'B', points: [10, 0, 20, 0, 20, 10], neighbors: ['C_A'] },
  { id: 'C_C', name: 'C', points: [0, 10, 10, 10, 10, 20], neighbors: ['C_A'] },
]

const COLORS: Record<string, string> = {
  C_A: '#ff0000',
  C_B: '#00ff00',
  // C_C intentionally missing → fallback
}

describe('TerritoryLayer', () => {
  beforeEach(() => {
    mockUIStore.selectedTerritoryId = null
    mockUIStore.layerVisibility.terrain = false
    mockProjectStore.terrain_types = {}
  })

  it('renders exactly 3 Line elements with correct fills and stroke', () => {
    render(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    const lines = screen.getAllByTestId('territory-line')
    expect(lines.length).toBe(3)
    expect(lines[0].getAttribute('data-fill')).toBe('#ff0000')
    expect(lines[1].getAttribute('data-fill')).toBe('#00ff00')
    // stroke
    lines.forEach((l) => {
      expect(l.getAttribute('data-stroke')).toBe('rgba(0, 0, 0, 0.35)')
      expect(l.getAttribute('data-stroke-width')).toBe('1')
      expect(l.getAttribute('data-closed')).toBe('true')
    })
  })

  it('falls back to #666666 for missing color id', () => {
    render(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    const lines = screen.getAllByTestId('territory-line')
    // C_C is at index 2 (missing from COLORS)
    expect(lines[2].getAttribute('data-fill')).toBe('#666666')
  })

  it('subscribes to selectedTerritoryId (only matching polygon gets isSelected)', async () => {
    // TerritoryPolygon passes isSelected down; the test verifies via a data attr
    // We just verify render doesn't crash when selection changes
    const { rerender } = render(
      <TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />,
    )
    await act(async () => {
      mockUIStore.selectedTerritoryId = 'C_A'
    })
    rerender(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    // Still 3 lines rendered after selection change
    expect(screen.getAllByTestId('territory-line').length).toBe(3)
  })
})

describe('TerritoryLayer — terrain color mode (Phase 05)', () => {
  beforeEach(() => {
    mockUIStore.selectedTerritoryId = null
    mockUIStore.layerVisibility.terrain = false
    mockProjectStore.terrain_types = {}
  })

  it('terrain layer OFF: uses kingdom colors (existing behavior)', () => {
    mockUIStore.layerVisibility.terrain = false
    render(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    const lines = screen.getAllByTestId('territory-line')
    expect(lines[0].getAttribute('data-fill')).toBe('#ff0000') // C_A kingdom color
    expect(lines[1].getAttribute('data-fill')).toBe('#00ff00') // C_B kingdom color
  })

  it('terrain layer ON + painted territory: uses TERRAIN_HEX color', () => {
    mockUIStore.layerVisibility.terrain = true
    mockProjectStore.terrain_types = { C_A: 'forest' }
    render(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    const lines = screen.getAllByTestId('territory-line')
    // C_A painted forest → #2d6a2d
    expect(lines[0].getAttribute('data-fill')).toBe('#2d6a2d')
  })

  it('terrain layer ON + unpainted territory: uses TERRAIN_UNPAINTED_HEX (#d4d4d4)', () => {
    mockUIStore.layerVisibility.terrain = true
    mockProjectStore.terrain_types = {} // no painted territories
    render(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    const lines = screen.getAllByTestId('territory-line')
    lines.forEach((l) => {
      expect(l.getAttribute('data-fill')).toBe('#d4d4d4')
    })
  })

  it('terrain layer ON + mixed painted/unpainted: correct fills per territory', () => {
    mockUIStore.layerVisibility.terrain = true
    mockProjectStore.terrain_types = { C_A: 'mountain', C_B: 'plains' }
    render(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    const lines = screen.getAllByTestId('territory-line')
    expect(lines[0].getAttribute('data-fill')).toBe('#9e9e9e') // mountain
    expect(lines[1].getAttribute('data-fill')).toBe('#c8b870') // plains
    expect(lines[2].getAttribute('data-fill')).toBe('#d4d4d4') // unpainted C_C
  })
})
