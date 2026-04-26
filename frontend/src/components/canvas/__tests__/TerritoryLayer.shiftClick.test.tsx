import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { useUIStore } from '../../../stores/uiStore'
import { useEditorStore } from '../../../stores/useEditorStore'
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

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const TERRITORIES: TerritoryRender[] = [
  { id: 'a', name: 'A', points: [0, 0, 10, 0, 10, 10], neighbors: [] },
  { id: 'b', name: 'B', points: [20, 0, 30, 0, 30, 10], neighbors: [] },
  { id: 'c', name: 'C', points: [40, 0, 50, 0, 50, 10], neighbors: [] },
]
const COLORS: Record<string, string> = { a: '#f00', b: '#0f0', c: '#00f' }

// Simulate a Konva click on territory at index i with the given shiftKey state.
function click(index: number, shift: boolean) {
  capturedHandlers.items[index]?.({ evt: { shiftKey: shift } })
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  capturedHandlers.items.length = 0
  useUIStore.setState({ selectedTerritoryId: null })
  useEditorStore.setState({
    editMode: false,
    rubberBandSelectionIds: [],
    activeTool: 'none',
  })
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TerritoryLayer — shift-click multi-select (04-12)', () => {
  it('Test 1: plain click sets single selection; rubberBandSelectionIds unchanged', () => {
    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(0, false) // plain click on 'a'

    expect(useUIStore.getState().selectedTerritoryId).toBe('a')
    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual([])
  })

  it('Test 2: shift-click in edit mode adds id to rubberBandSelectionIds', () => {
    useEditorStore.setState({ editMode: true })

    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(0, true) // shift-click on 'a'

    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual(['a'])
  })

  it('Test 3: shift-click accumulates; shift-click same id again toggles it off', () => {
    useEditorStore.setState({ editMode: true })

    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(0, true) // add 'a'
    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual(['a'])

    click(1, true) // add 'b'
    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual(['a', 'b'])

    click(0, true) // toggle 'a' off
    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual(['b'])
  })

  it('Test 4: shift-click outside edit mode falls through to single-select', () => {
    // editMode=false (default from beforeEach)
    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(0, true) // shift-click, but editMode=false

    expect(useUIStore.getState().selectedTerritoryId).toBe('a')
    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual([])
  })

  it('Test 5: plain click clears existing multi-select before setting single selection', () => {
    useEditorStore.setState({ editMode: true, rubberBandSelectionIds: ['a', 'b'] })

    render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    click(2, false) // plain click on 'c'

    expect(useEditorStore.getState().rubberBandSelectionIds).toEqual([])
    expect(useUIStore.getState().selectedTerritoryId).toBe('c')
  })

  it('Test 6: handleClick reference is stable across shift-click mutations (perf guard)', () => {
    useEditorStore.setState({ editMode: true })

    const { rerender } = render(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    // First render pushes one handler per territory (3 total)
    const countAfterFirstRender = capturedHandlers.items.length
    expect(countAfterFirstRender).toBe(TERRITORIES.length)

    // Trigger a shift-click — this mutates rubberBandSelectionIds in the store
    click(0, true) // 'a' added to selection

    // Reset captured count AFTER the first render (don't clear items — just record the baseline)
    const baselineCount = capturedHandlers.items.length // still 3

    // Force TerritoryLayer to re-render (store state changed → parent re-renders)
    rerender(
      <TerritoryLayer
        territories={TERRITORIES}
        condadoColors={COLORS}
        visible
        showBorders
      />,
    )

    // If handleClick reference is STABLE (useCallback with empty deps), React.memo on
    // TerritoryPolygon sees onClick===onClick → skips re-render → Line mock is NOT
    // called again → capturedHandlers.items count stays at the baseline.
    // If reference were unstable, each TerritoryPolygon would re-render and push 3
    // more handlers, making the count 6.
    expect(capturedHandlers.items.length).toBe(baselineCount)
  })
})
