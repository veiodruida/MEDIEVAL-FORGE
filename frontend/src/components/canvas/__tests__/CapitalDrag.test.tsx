import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { useEditorStore } from '../../../stores/useEditorStore'
import { useProjectStore, beginTransaction, endTransaction } from '../../../stores/useProjectStore'
import { DecorationsLayer } from '../DecorationsLayer'
import { ProjectionProvider } from '../../../context/ProjectionContext'
import { buildProjectionConfig } from '../../../lib/projection'
import type { TerritoryMetadataCondado } from '../../../hooks/useCanvasArtifacts'

// Mock the edit API so tests don't hit network
vi.mock('../../../api/edit', () => ({
  moveCapital: vi.fn(),
  EditApiError: class EditApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'EditApiError'
      this.status = status
    }
  },
}))

// Import after mock so we get the mocked version
import { moveCapital } from '../../../api/edit'

// react-konva mock: Circle fires onDragEnd onClick so we can simulate drag in tests
vi.mock('react-konva', () => ({
  Layer: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-layer">{children}</div>
  ),
  Circle: (p: {
    x?: number
    y?: number
    radius?: number
    fill?: string
    stroke?: string
    strokeWidth?: number
    shadowBlur?: number
    draggable?: boolean
    onDragEnd?: (e: { target: { x: () => number; y: () => number } }) => void
    'data-role'?: string
    'data-id'?: string
  }) => {
    const node = { x: () => p.x ?? 0, y: () => p.y ?? 0 }
    return (
      <div
        data-testid="circle"
        data-x={String(p.x ?? '')}
        data-y={String(p.y ?? '')}
        data-radius={String(p.radius ?? '')}
        data-fill={p.fill ?? ''}
        data-stroke={p.stroke ?? ''}
        data-draggable={String(p.draggable ?? false)}
        data-role={p['data-role'] ?? ''}
        data-id={p['data-id'] ?? ''}
        onClick={() => p.onDragEnd?.({ target: node })}
      />
    )
  },
  Text: (p: { text?: string }) => <div data-testid="text" data-text={p.text ?? ''} />,
}))

const PROJECTION = buildProjectionConfig(
  { lonMin: -10, lonMax: 0, latMin: 40, latMax: 50 },
  2000,
  1600,
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
    neighbors: ['castela'],
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
    neighbors: ['leon'],
  },
]

const COLORS: Record<string, string> = { leon: '#e03030', castela: '#3050e0' }

function wrap(node: React.ReactNode) {
  return <ProjectionProvider value={PROJECTION}>{node}</ProjectionProvider>
}

beforeEach(() => {
  // Clean store state between tests so pastStates don't bleed across
  useProjectStore.setState({ territories: {}, capitals: {}, projectId: 'test-pid', loading: false })
  useProjectStore.temporal.getState().clear()
  useEditorStore.setState({ editMode: false, undoLabels: [], redoLabels: [] })
  vi.clearAllMocks()
})

describe('CapitalDrag — edit mode gating (D-09 + D-01)', () => {
  it('capital Circle is draggable only in edit mode', () => {
    const { rerender } = render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
          isEditMode={true}
        />,
      ),
    )

    const circles = screen.getAllByTestId('circle')
    const capitalInners = circles.filter((c) => c.getAttribute('data-radius') === '6')
    expect(capitalInners.length).toBeGreaterThan(0)
    capitalInners.forEach((c) => {
      expect(c.getAttribute('data-draggable')).toBe('true')
    })

    // Re-render with edit mode off
    rerender(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
          isEditMode={false}
        />,
      ),
    )

    const circlesReadOnly = screen.getAllByTestId('circle')
    const capitalInnersReadOnly = circlesReadOnly.filter((c) => c.getAttribute('data-radius') === '6')
    capitalInnersReadOnly.forEach((c) => {
      expect(c.getAttribute('data-draggable')).toBe('false')
    })
  })

  it('onDragEnd fires handleCapitalDragEnd with converted geo coordinates', () => {
    const handleCapitalDragEnd = vi.fn()

    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
          isEditMode={true}
          onCapitalDragEnd={handleCapitalDragEnd}
        />,
      ),
    )

    // Find the inner capital circle for 'leon' and simulate drag end via onClick
    const circles = screen.getAllByTestId('circle')
    const leonInner = circles.find(
      (c) => c.getAttribute('data-radius') === '6' && c.getAttribute('data-fill') === '#e03030',
    )
    expect(leonInner).toBeDefined()

    // Simulate drag end (onClick → onDragEnd in mock)
    leonInner!.click()

    expect(handleCapitalDragEnd).toHaveBeenCalledOnce()
    const [calledId, calledLon, calledLat] = handleCapitalDragEnd.mock.calls[0] as [string, number, number]
    expect(calledId).toBe('leon')
    // Coordinates should be numbers (geo-space output from canvasToGeo)
    expect(typeof calledLon).toBe('number')
    expect(typeof calledLat).toBe('number')
  })

  it('a capital drag produces exactly one past-state entry (compound op batching)', async () => {
    // Stub moveCapital to return 3 updated territories
    vi.mocked(moveCapital).mockResolvedValue({
      updated_territories: {
        leon: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
        castela: { type: 'Polygon', coordinates: [[[1, 0], [2, 0], [2, 1], [1, 0]]] },
        galiza: { type: 'Polygon', coordinates: [[[0, 1], [1, 1], [1, 2], [0, 1]]] },
      },
      affected_ids: ['leon', 'castela', 'galiza'],
    })

    // Inline handler that replicates CanvasViewer.handleCapitalDragEnd compound-op pattern
    const handleCapitalDragEnd = async (condadoId: string, lon: number, lat: number) => {
      const applyBatchUpdate = useProjectStore.getState().applyBatchUpdate
      beginTransaction()
      try {
        const response = await moveCapital('test-pid', condadoId, { lon, lat })
        applyBatchUpdate(response.updated_territories, { [condadoId]: [lon, lat] })
      } finally {
        endTransaction()
      }
      useEditorStore.getState().pushUndoLabel(`Mover capital de León`)
    }

    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
          isEditMode={true}
          onCapitalDragEnd={handleCapitalDragEnd}
        />,
      ),
    )

    const circles = screen.getAllByTestId('circle')
    const leonInner = circles.find(
      (c) => c.getAttribute('data-radius') === '6' && c.getAttribute('data-fill') === '#e03030',
    )
    expect(leonInner).toBeDefined()

    // Trigger drag end and await the async handler
    await act(async () => {
      leonInner!.click()
    })

    // The compound op (1 capital update + 3 territory updates) must register as ONE undo step
    expect(useProjectStore.temporal.getState().pastStates.length).toBe(1)
  })

  it('pushes "Mover capital de {name}" label to useEditorStore after drag', async () => {
    vi.mocked(moveCapital).mockResolvedValue({
      updated_territories: {
        leon: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
      },
      affected_ids: ['leon'],
    })

    const handleCapitalDragEnd = async (condadoId: string, lon: number, lat: number) => {
      const applyBatchUpdate = useProjectStore.getState().applyBatchUpdate
      beginTransaction()
      try {
        const response = await moveCapital('test-pid', condadoId, { lon, lat })
        applyBatchUpdate(response.updated_territories, { [condadoId]: [lon, lat] })
      } finally {
        endTransaction()
      }
      useEditorStore.getState().pushUndoLabel(`Mover capital de León`)
    }

    render(
      wrap(
        <DecorationsLayer
          condados={CONDADOS}
          condadoColors={COLORS}
          layerVisibility={{ capitals: true, labels: false }}
          currentScale={1}
          minScale={0.34}
          isEditMode={true}
          onCapitalDragEnd={handleCapitalDragEnd}
        />,
      ),
    )

    const circles = screen.getAllByTestId('circle')
    const leonInner = circles.find(
      (c) => c.getAttribute('data-radius') === '6' && c.getAttribute('data-fill') === '#e03030',
    )

    await act(async () => {
      leonInner!.click()
    })

    expect(useEditorStore.getState().undoLabels.at(-1)).toBe('Mover capital de León')
  })
})
