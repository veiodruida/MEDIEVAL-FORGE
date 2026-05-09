import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { InteractionLayer } from '../InteractionLayer'
import { useUIStore } from '../../../stores/uiStore'
import type { TerritoryRender } from '../../../hooks/useCanvasArtifacts'

vi.mock('react-konva', () => ({
  Layer: ({ children, listening }: { children?: React.ReactNode; listening?: boolean }) => (
    <div data-testid="konva-layer" data-listening={String(listening ?? true)}>
      {children}
    </div>
  ),
  Line: (p: {
    points?: number[]
    closed?: boolean
    stroke?: string
    strokeWidth?: number
    listening?: boolean
  }) => (
    <div
      data-testid="interaction-line"
      data-closed={String(p.closed)}
      data-stroke={p.stroke ?? ''}
      data-stroke-width={String(p.strokeWidth ?? '')}
      data-listening={String(p.listening ?? true)}
      data-points-length={String(p.points?.length ?? 0)}
    />
  ),
}))

const TERRITORIES: TerritoryRender[] = [
  { id: 'C_A', name: 'A', points: [0, 0, 10, 0, 10, 10], neighbors: [] },
  { id: 'C_B', name: 'B', points: [10, 0, 20, 0, 20, 10], neighbors: ['C_A'] },
]

describe('InteractionLayer — gold selection outline', () => {
  beforeEach(() => {
    useUIStore.setState({ selectedTerritoryIds: [], selectedTerritoryId: null })
  })

  it('renders 0 Line children when selectedTerritoryId is null', () => {
    render(<InteractionLayer territories={TERRITORIES} />)
    expect(screen.queryAllByTestId('interaction-line').length).toBe(0)
  })

  it('renders exactly 1 gold Line (#f0c040, width 3, listening=false) for the selected territory', () => {
    useUIStore.setState({ selectedTerritoryIds: ['C_A'], selectedTerritoryId: 'C_A' })
    render(<InteractionLayer territories={TERRITORIES} />)
    const lines = screen.getAllByTestId('interaction-line')
    expect(lines.length).toBe(1)
    const l = lines[0]
    expect(l.getAttribute('data-stroke')).toBe('#f0c040')
    expect(l.getAttribute('data-stroke-width')).toBe('3')
    expect(l.getAttribute('data-closed')).toBe('true')
    expect(l.getAttribute('data-listening')).toBe('false')
    // points from C_A (6 numbers → 3 vertices)
    expect(l.getAttribute('data-points-length')).toBe('6')
  })

  it('renders nothing when selectedTerritoryId points at an unknown id', () => {
    useUIStore.setState({ selectedTerritoryIds: ['C_NONEXISTENT'], selectedTerritoryId: 'C_NONEXISTENT' })
    render(<InteractionLayer territories={TERRITORIES} />)
    expect(screen.queryAllByTestId('interaction-line').length).toBe(0)
  })

  it('Layer is listening=false (selection visual only, no events)', () => {
    useUIStore.setState({ selectedTerritoryIds: ['C_A'], selectedTerritoryId: 'C_A' })
    render(<InteractionLayer territories={TERRITORIES} />)
    const layer = screen.getByTestId('konva-layer')
    expect(layer.getAttribute('data-listening')).toBe('false')
  })
})

describe('Selection integration — TerritoryLayer click → InteractionLayer outline', () => {
  it('dispatches select(id) through useUIStore.select() when a territory is clicked', async () => {
    // This mirrors TerritoryLayer's integration with the store.
    // TerritoryLayer tests cover the click dispatch; here we just assert the
    // full integration path: store.select → InteractionLayer re-renders with outline.
    useUIStore.setState({ selectedTerritoryIds: [], selectedTerritoryId: null })
    const { rerender } = render(<InteractionLayer territories={TERRITORIES} />)
    expect(screen.queryAllByTestId('interaction-line').length).toBe(0)

    useUIStore.getState().select('C_B')
    rerender(<InteractionLayer territories={TERRITORIES} />)

    const lines = screen.getAllByTestId('interaction-line')
    expect(lines.length).toBe(1)
    expect(lines[0].getAttribute('data-stroke')).toBe('#f0c040')
  })
})
