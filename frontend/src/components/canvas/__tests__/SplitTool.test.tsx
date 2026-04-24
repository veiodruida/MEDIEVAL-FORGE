import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSplitTool } from '../SplitTool'
import type { TerritoryMetadataCondado } from '../../../hooks/useCanvasArtifacts'
import type { ProjectionConfig } from '../../../lib/projection'

// --------------------------------------------------------------------------
// Mocks
// --------------------------------------------------------------------------

// Mutable mock state — tests can mutate fields before renderHook
const mockEditorState = {
  activeTool: 'split' as string,
  splitSubMode: 'snap' as string,
  setActiveTool: vi.fn(),
  pushUndoLabel: vi.fn(),
}

vi.mock('../../../stores/useEditorStore', () => ({
  useEditorStore: (selector: (s: typeof mockEditorState) => unknown) =>
    selector(mockEditorState),
}))

vi.mock('../../../stores/uiStore', () => ({
  useUIStore: (selector: (s: { selectedTerritoryId: string | null }) => unknown) =>
    selector({ selectedTerritoryId: 'cond-1' }),
}))

vi.mock('../../../stores/useProjectStore', () => ({
  useProjectStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ projectId: 'proj-1', territories: {} }),
  beginTransaction: vi.fn(),
  endTransaction: vi.fn(),
}))

vi.mock('../../../api/edit', () => ({
  splitTerritory: vi.fn(),
  EditApiError: class EditApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
      this.name = 'EditApiError'
    }
  },
}))

const mockCondados: TerritoryMetadataCondado[] = [
  {
    id: 'cond-1',
    name: 'León',
    lon: 0,
    lat: 40,
    duchy: 'Leon',
    kingdom: 'Asturias',
    pixel_center: [500, 250],
    pixel_count: 1000,
    baronies: [],
    neighbors: [],
  },
]

const mockProjection: ProjectionConfig = {
  lonMin: -10,
  lonMax: 10,
  latMin: 35,
  latMax: 45,
  mapW: 1000,
  mapH: 500,
  lonScale: 0.8,
}

const mockStageRef = {
  current: {
    getRelativePointerPosition: () => ({ x: 100, y: 200 }),
  },
} as unknown as React.RefObject<import('konva/lib/Stage').default>

// --------------------------------------------------------------------------
// Tests
// --------------------------------------------------------------------------

describe('useSplitTool', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset mutable state to defaults
    mockEditorState.activeTool = 'split'
    mockEditorState.splitSubMode = 'snap'
  })

  it('exports useSplitTool hook', () => {
    expect(typeof useSplitTool).toBe('function')
  })

  it('returns required interface: previewLayer, toastEl, and event handlers', () => {
    const { result } = renderHook(() =>
      useSplitTool({ condados: mockCondados, stageRef: mockStageRef, projection: mockProjection }),
    )
    expect(result.current).toHaveProperty('previewLayer')
    expect(result.current).toHaveProperty('toastEl')
    expect(result.current).toHaveProperty('onStageMouseDown')
    expect(result.current).toHaveProperty('onStageMouseMove')
    expect(result.current).toHaveProperty('onStageMouseUp')
    expect(result.current).toHaveProperty('onStageDblClick')
  })

  it('snap mode: second click triggers splitTerritory API', async () => {
    const { splitTerritory } = await import('../../../api/edit')
    const splitSpy = vi.mocked(splitTerritory)
    splitSpy.mockResolvedValue({
      original_id: 'cond-1',
      new_territory_a: { id: 'cond-1a', geometry: { type: 'Polygon', coordinates: [] } },
      new_territory_b: { id: 'cond-1b', geometry: { type: 'Polygon', coordinates: [] } },
    })

    mockEditorState.splitSubMode = 'snap'
    const { result } = renderHook(() =>
      useSplitTool({ condados: mockCondados, stageRef: mockStageRef, projection: mockProjection }),
    )

    // First click — sets first point
    act(() => {
      result.current.onStageMouseDown(
        {} as unknown as import('konva/lib/Node').KonvaEventObject<MouseEvent>,
      )
    })

    // Second click — should commit and call splitTerritory
    await act(async () => {
      result.current.onStageMouseDown(
        {} as unknown as import('konva/lib/Node').KonvaEventObject<MouseEvent>,
      )
    })

    expect(splitSpy).toHaveBeenCalledTimes(1)
  })

  it('polyline mode: dblClick triggers splitTerritory with accumulated points', async () => {
    const { splitTerritory: st } = await import('../../../api/edit')
    const splitSpy = vi.mocked(st)
    splitSpy.mockResolvedValue({
      original_id: 'cond-1',
      new_territory_a: { id: 'cond-1a', geometry: { type: 'Polygon', coordinates: [] } },
      new_territory_b: { id: 'cond-1b', geometry: { type: 'Polygon', coordinates: [] } },
    })

    // Override subMode to polyline via mutable state
    mockEditorState.splitSubMode = 'polyline'

    const { result } = renderHook(() =>
      useSplitTool({ condados: mockCondados, stageRef: mockStageRef, projection: mockProjection }),
    )

    // Add two points
    act(() => {
      result.current.onStageMouseDown(
        {} as unknown as import('konva/lib/Node').KonvaEventObject<MouseEvent>,
      )
    })
    act(() => {
      result.current.onStageMouseDown(
        {} as unknown as import('konva/lib/Node').KonvaEventObject<MouseEvent>,
      )
    })

    // dblClick finishes polyline
    await act(async () => {
      result.current.onStageDblClick()
    })

    expect(splitSpy).toHaveBeenCalledTimes(1)
  })
})
