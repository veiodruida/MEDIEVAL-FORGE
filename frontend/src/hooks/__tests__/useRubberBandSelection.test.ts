import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useRubberBandSelection } from '../useRubberBandSelection'
import { useEditorStore } from '../../stores/useEditorStore'
import { buildProjectionConfig } from '../../lib/projection'
import type { TerritoryMetadataCondado } from '../useCanvasArtifacts'
import type Konva from 'konva'

// Projection: lonMin=-10, lonMax=0, latMin=36, latMax=48, mapW=2000, mapH=2000
// Pre-computed canvas positions (via geoToCanvas with this projection):
//   León (-5.57, 42.6):    canvas ~ [886, 900]
//   Castela (-3.7, 40.4):  canvas ~ [1260, 1267]
//   Toledo (-4.02, 39.86): canvas ~ [1196, 1357]
const PROJECTION = buildProjectionConfig(
  { lonMin: -10, lonMax: 0, latMin: 36, latMax: 48 },
  2000,
  2000,
)

const CONDADOS: TerritoryMetadataCondado[] = [
  {
    id: 'leon',
    name: 'León',
    lon: -5.57,
    lat: 42.6,
    duchy: 'D_LEON',
    kingdom: 'K_LEON',
    pixel_center: [0, 0],
    pixel_count: 100,
    baronies: [],
    neighbors: [],
  },
  {
    id: 'castela',
    name: 'Castela',
    lon: -3.7,
    lat: 40.4,
    duchy: 'D_CASTELA',
    kingdom: 'K_CASTELA',
    pixel_center: [0, 0],
    pixel_count: 100,
    baronies: [],
    neighbors: [],
  },
  {
    id: 'toledo',
    name: 'Toledo',
    lon: -4.02,
    lat: 39.86,
    duchy: 'D_TOLEDO',
    kingdom: 'K_CASTELA',
    pixel_center: [0, 0],
    pixel_count: 100,
    baronies: [],
    neighbors: [],
  },
]

/**
 * Creates a mock Konva Stage that self-references via getStage().
 * The hook checks: if (e.target !== stage) return  — to detect empty-Stage clicks.
 * For that check to pass, e.target must be === e.target.getStage().
 * This factory makes an object where getStage() returns itself.
 */
function makeMockStage(positions: { x: number; y: number }[]) {
  let callIdx = 0
  const stage = {
    getRelativePointerPosition: vi.fn().mockImplementation(() => {
      const pos = positions[callIdx] ?? positions[positions.length - 1]
      callIdx++
      return pos
    }),
    // Self-reference: e.target === e.target.getStage() -> passes the empty-area gate
    getStage: (): typeof stage => stage,
  }
  return stage
}

beforeEach(() => {
  useEditorStore.setState({
    editMode: false,
    activeTool: 'none',
    rubberBandSelectionIds: [],
  })
})

describe('useRubberBandSelection', () => {
  it('returns selectionRect=null and no handlers fire when editMode is off', () => {
    const mockStage = makeMockStage([{ x: 100, y: 200 }])
    const stageRef = { current: mockStage as unknown as Konva.Stage }

    const { result } = renderHook(() =>
      useRubberBandSelection({ condados: CONDADOS, projection: PROJECTION, stageRef }),
    )

    expect(result.current.selectionRect).toBeNull()
    expect(result.current.isActive).toBe(false)

    // onMouseDown should be a no-op when editMode is off
    act(() => {
      result.current.onMouseDown({
        target: mockStage,
      } as unknown as Parameters<typeof result.current.onMouseDown>[0])
    })

    // selectionRect stays null — no drag initiated
    expect(result.current.selectionRect).toBeNull()
    expect(mockStage.getRelativePointerPosition).not.toHaveBeenCalled()
  })

  it('onMouseDown on empty Stage area initializes selectionRect', () => {
    useEditorStore.setState({ editMode: true, activeTool: 'select' })

    const mockStage = makeMockStage([{ x: 100, y: 200 }])
    const stageRef = { current: mockStage as unknown as Konva.Stage }

    const { result } = renderHook(() =>
      useRubberBandSelection({ condados: CONDADOS, projection: PROJECTION, stageRef }),
    )

    // e.target === e.target.getStage() because mockStage.getStage() returns itself
    act(() => {
      result.current.onMouseDown({
        target: mockStage,
      } as unknown as Parameters<typeof result.current.onMouseDown>[0])
    })

    expect(result.current.selectionRect).toEqual({ x: 100, y: 200, w: 0, h: 0 })
  })

  it('onMouseMove updates selectionRect width/height', () => {
    useEditorStore.setState({ editMode: true, activeTool: 'select' })

    const mockStage = makeMockStage([
      { x: 100, y: 200 }, // mouseDown
      { x: 250, y: 350 }, // mouseMove
    ])
    const stageRef = { current: mockStage as unknown as Konva.Stage }

    const { result } = renderHook(() =>
      useRubberBandSelection({ condados: CONDADOS, projection: PROJECTION, stageRef }),
    )

    // Start drag
    act(() => {
      result.current.onMouseDown({
        target: mockStage,
      } as unknown as Parameters<typeof result.current.onMouseDown>[0])
    })

    // Move mouse
    act(() => {
      result.current.onMouseMove({
        target: { getStage: () => mockStage },
      } as unknown as Parameters<typeof result.current.onMouseMove>[0])
    })

    expect(result.current.selectionRect).toEqual({
      x: 100,
      y: 200,
      w: 150, // |250 - 100|
      h: 150, // |350 - 200|
    })
  })

  it('onMouseUp populates rubberBandSelectionIds with condados whose centroid falls inside', () => {
    useEditorStore.setState({ editMode: true, activeTool: 'select' })

    // Rect: x=[700, 1400], y=[800, 1300]
    // León canvas ≈ [886, 900]      — inside  ✓
    // Castela canvas ≈ [1260, 1267] — inside  ✓
    // Toledo canvas ≈ [1196, 1357]  — OUTSIDE (y=1357 > 1300) ✗
    const startPos = { x: 700, y: 800 }
    const endPos = { x: 1400, y: 1300 }

    const mockStage = makeMockStage([startPos, endPos])
    const stageRef = { current: mockStage as unknown as Konva.Stage }

    const { result } = renderHook(() =>
      useRubberBandSelection({ condados: CONDADOS, projection: PROJECTION, stageRef }),
    )

    // mouseDown on empty Stage area
    act(() => {
      result.current.onMouseDown({
        target: mockStage,
      } as unknown as Parameters<typeof result.current.onMouseDown>[0])
    })

    // mouseMove to expand rect
    act(() => {
      result.current.onMouseMove({
        target: { getStage: () => mockStage },
      } as unknown as Parameters<typeof result.current.onMouseMove>[0])
    })

    // mouseUp — triggers centroid containment test and store update
    act(() => {
      result.current.onMouseUp()
    })

    // After mouseUp the visual rect is cleared
    expect(result.current.selectionRect).toBeNull()

    // Store must contain exactly León and Castela (Toledo excluded by y bound)
    const ids = useEditorStore.getState().rubberBandSelectionIds
    expect(ids).toHaveLength(2)
    expect(ids).toContain('leon')
    expect(ids).toContain('castela')
    expect(ids).not.toContain('toledo')
  })

  it('Stage draggable is disabled when activeTool === "select"', () => {
    // Pitfall 2 mitigation: isActive=true signals CanvasViewer to set Stage draggable=false.
    // CanvasViewer implements: draggable={activeTool !== 'select'}
    // This test verifies the hook exposes isActive correctly so that gate works.
    useEditorStore.setState({ editMode: true, activeTool: 'select' })

    const stageRef = { current: null as unknown as Konva.Stage }
    const { result } = renderHook(() =>
      useRubberBandSelection({ condados: CONDADOS, projection: PROJECTION, stageRef }),
    )

    // isActive=true → CanvasViewer sets draggable=false
    expect(result.current.isActive).toBe(true)

    // Switching to a non-select tool re-enables Stage draggable
    act(() => {
      useEditorStore.setState({ activeTool: 'capital' })
    })

    expect(result.current.isActive).toBe(false)
  })
})
