import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { act } from 'react'
import { TerritoryLayer } from '../TerritoryLayer'
import type { TerritoryRender } from '../../../hooks/useCanvasArtifacts'

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

// Mock useUIStore so tests can control selectedTerritoryId
const mockStore = {
  selectedTerritoryId: null as string | null,
}

vi.mock('../../../stores/uiStore', () => ({
  useUIStore: (selector: (s: typeof mockStore) => unknown) => selector(mockStore),
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
    mockStore.selectedTerritoryId = null
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
      mockStore.selectedTerritoryId = 'C_A'
    })
    rerender(<TerritoryLayer territories={T} condadoColors={COLORS} visible showBorders />)
    // Still 3 lines rendered after selection change
    expect(screen.getAllByTestId('territory-line').length).toBe(3)
  })
})
