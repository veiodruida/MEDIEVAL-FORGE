import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { useUIStore } from '../../../stores/uiStore'
import type { TerritoryRender } from '../../../hooks/useCanvasArtifacts'

// ---------------------------------------------------------------------------
// Capture onClick props from Line renders so tests can simulate Konva clicks
// without needing a real canvas context.
// ---------------------------------------------------------------------------
type KonvaClickEvent = { evt: { shiftKey: boolean } }
const capturedHandlers = vi.hoisted(
  () => ({ items: [] as Array<(e: KonvaClickEvent) => void> }),
)

vi.mock('react-konva', () => ({
  Layer: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  Line: (p: { onClick?: (e: KonvaClickEvent) => void }) => {
    if (p.onClick) capturedHandlers.items.push(p.onClick)
    return null
  },
}))

// Import after mocks
import { TerritoryLayer } from '../TerritoryLayer'

const TERRITORIES: TerritoryRender[] = [
  { id: 'a', name: 'A', points: [0, 0, 10, 0, 10, 10], neighbors: [] },
  { id: 'b', name: 'B', points: [20, 0, 30, 0, 30, 10], neighbors: [] },
  { id: 'c', name: 'C', points: [40, 0, 50, 0, 50, 10], neighbors: [] },
]
const COLORS: Record<string, string> = { a: '#f00', b: '#0f0', c: '#00f' }

function click(index: number, shift: boolean) {
  capturedHandlers.items[index]?.({ evt: { shiftKey: shift } })
}

beforeEach(() => {
  capturedHandlers.items.length = 0
  useUIStore.setState({ selectedTerritoryIds: [], selectedTerritoryId: null })
})

describe('TerritoryLayer — shift-click multi-select (Phase 03 D-17)', () => {
  it('plain click on territory "x" sets selectedTerritoryIds to [x]', () => {
    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(0, false) // plain click on 'a'

    expect(useUIStore.getState().selectedTerritoryIds).toEqual(['a'])
    expect(useUIStore.getState().selectedTerritoryId).toBe('a')
  })

  it('plain click replaces existing multi-select with single id', () => {
    useUIStore.setState({ selectedTerritoryIds: ['a', 'b'], selectedTerritoryId: 'a' })

    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(2, false) // plain click on 'c'

    expect(useUIStore.getState().selectedTerritoryIds).toEqual(['c'])
  })

  it('shift+click on "x" with prior ids ["a"] yields ["a","x"]', () => {
    useUIStore.setState({ selectedTerritoryIds: ['a'], selectedTerritoryId: 'a' })

    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(1, true) // shift-click on 'b'

    expect(useUIStore.getState().selectedTerritoryIds).toEqual(['a', 'b'])
  })

  it('shift+click on "a" when ids was ["a","b"] toggles "a" off → ["b"]', () => {
    useUIStore.setState({ selectedTerritoryIds: ['a', 'b'], selectedTerritoryId: 'a' })

    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(0, true) // shift-click on 'a' (already selected)

    expect(useUIStore.getState().selectedTerritoryIds).toEqual(['b'])
  })

  it('shift+click on "a" with empty selection yields ["a"]', () => {
    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(0, true) // shift-click on 'a' from empty selection

    expect(useUIStore.getState().selectedTerritoryIds).toEqual(['a'])
  })

  it('handleClick reference is stable across shift-click mutations (perf guard)', () => {
    const { rerender } = render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    const countAfterFirstRender = capturedHandlers.items.length
    expect(countAfterFirstRender).toBe(TERRITORIES.length)

    click(0, true) // shift-click → mutates store

    const baselineCount = capturedHandlers.items.length

    rerender(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    // handleClick is stable (useCallback with []), so React.memo on
    // TerritoryPolygon skips re-render for sibling polygons. Only the polygon
    // whose isSelected flipped (because selectedTerritoryId mirror updated)
    // re-renders. We expect at most 1 extra handler push, never N.
    expect(capturedHandlers.items.length).toBeLessThanOrEqual(baselineCount + 1)
  })
})
