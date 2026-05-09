import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
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
      data-stroke={p.stroke ?? ''}
      data-stroke-width={String(p.strokeWidth ?? '')}
      data-listening={String(p.listening ?? true)}
    />
  ),
}))

const TERRITORIES: TerritoryRender[] = [
  { id: 'a', name: 'A', points: [0, 0, 10, 0, 10, 10], neighbors: [] },
  { id: 'b', name: 'B', points: [10, 0, 20, 0, 20, 10], neighbors: [] },
  { id: 'c', name: 'C', points: [20, 0, 30, 0, 30, 10], neighbors: [] },
]

describe('InteractionLayer — multi-select (D-17)', () => {
  beforeEach(() => {
    useUIStore.setState({ selectedTerritoryIds: [], selectedTerritoryId: null })
  })

  it('renders 0 Lines when selectedTerritoryIds is empty', () => {
    render(<InteractionLayer territories={TERRITORIES} />)
    expect(screen.queryAllByTestId('interaction-line').length).toBe(0)
  })

  it('renders 2 gold #f0c040 strokeWidth=3 Lines when 2 ids are selected', () => {
    useUIStore.setState({ selectedTerritoryIds: ['a', 'c'], selectedTerritoryId: 'a' })
    render(<InteractionLayer territories={TERRITORIES} />)
    const lines = screen.getAllByTestId('interaction-line')
    expect(lines.length).toBe(2)
    for (const line of lines) {
      expect(line.getAttribute('data-stroke')).toBe('#f0c040')
      expect(line.getAttribute('data-stroke-width')).toBe('3')
      expect(line.getAttribute('data-listening')).toBe('false')
    }
  })

  it('renders only Lines for ids that exist in territories array (unknown id is skipped)', () => {
    useUIStore.setState({ selectedTerritoryIds: ['a', 'unknown'], selectedTerritoryId: 'a' })
    render(<InteractionLayer territories={TERRITORIES} />)
    expect(screen.getAllByTestId('interaction-line').length).toBe(1)
  })

  it('renders 1 Line for single-id selection (single-select still flows through ids[])', () => {
    useUIStore.setState({ selectedTerritoryIds: ['b'], selectedTerritoryId: 'b' })
    render(<InteractionLayer territories={TERRITORIES} />)
    expect(screen.getAllByTestId('interaction-line').length).toBe(1)
  })

  it('Layer is non-listening (visual-only — hit testing stays on TerritoryLayer)', () => {
    useUIStore.setState({ selectedTerritoryIds: ['a'], selectedTerritoryId: 'a' })
    render(<InteractionLayer territories={TERRITORIES} />)
    expect(screen.getByTestId('konva-layer').getAttribute('data-listening')).toBe('false')
  })
})
