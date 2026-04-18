import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CanvasViewer } from '../CanvasViewer'
import { useUIStore } from '../../../stores/uiStore'

// Mock the zoom-pan hook so we can spy on panToGeoCenter + control scale updates.
// The plan's acceptance criteria require `panToGeoCenter` to appear in CanvasViewer
// source AND be called from a selectedId effect — both are enforced here.
const panToGeoCenterMock = vi.fn()
const makeWheelHandlerMock = vi.fn(() => () => {})
const makeDragBoundFuncMock = vi.fn(() => (pos: { x: number; y: number }) => pos)

vi.mock('../../../hooks/useZoomPan', () => ({
  SCALE_BY: 1.05,
  MAX_SCALE_MULTIPLIER: 4,
  panToGeoCenter: panToGeoCenterMock,
  makeWheelHandler: makeWheelHandlerMock,
  makeDragBoundFunc: makeDragBoundFuncMock,
  applyPanClamp: vi.fn(),
}))

vi.mock('../../../hooks/useKeyboardShortcuts', () => ({
  useKeyboardShortcuts: vi.fn(),
}))

// Record the latest select() dispatcher + capture Stage onClick handler
let lastStageProps: Record<string, unknown> | null = null
vi.mock('react-konva', () => ({
  Stage: ({
    children,
    ...rest
  }: { children?: React.ReactNode } & Record<string, unknown>) => {
    lastStageProps = rest
    return <div data-testid="konva-stage">{children}</div>
  },
  Layer: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-layer">{children}</div>
  ),
  Image: () => <div data-testid="konva-image" />,
  Rect: () => <div data-testid="konva-rect" />,
  Circle: () => <div data-testid="konva-circle" />,
  Text: () => <div data-testid="konva-text" />,
  Line: () => <div data-testid="konva-line" />,
}))

vi.mock('use-image', () => ({
  default: () => [undefined, 'loading'],
  useImage: () => [undefined, 'loading'],
}))

// Stub children to keep the test focused on selection-driven pan behavior
vi.mock('../TerritoryLayer', () => ({
  TerritoryLayer: () => <div data-testid="territory-layer" />,
}))
vi.mock('../BaronyLayer', () => ({
  BaronyLayer: () => <div data-testid="barony-layer" />,
}))
vi.mock('../LayerTogglePanel', () => ({
  LayerTogglePanel: () => <div data-testid="layer-toggle-panel" />,
}))
vi.mock('../DecorationsLayer', () => ({
  DecorationsLayer: () => <div data-testid="decorations-layer" />,
  LABEL_ZOOM_THRESHOLD_RELATIVE: 2.0,
}))
vi.mock('../InteractionLayer', () => ({
  InteractionLayer: () => <div data-testid="interaction-layer" />,
}))
vi.mock('../FitToViewButton', () => ({
  FitToViewButton: ({ onFit }: { onFit: () => void }) => (
    <button data-testid="fit-to-view" onClick={onFit}>fit</button>
  ),
}))

const META = {
  region: 'iberia',
  map_size: [2000, 1600],
  bounds: { lon_min: -10, lon_max: 0, lat_min: 40, lat_max: 50 },
  kingdoms: { K_LEON: 'León' },
  duchies: { D_G: { kingdom: 'K_LEON', name: 'Galicia' } },
  condados: [
    {
      id: 'C_CORUNA',
      name: 'Coruña',
      lon: -8.41,
      lat: 43.37,
      duchy: 'D_G',
      kingdom: 'K_LEON',
      pixel_center: [100, 100],
      pixel_count: 1000,
      baronies: [],
      neighbors: ['C_LUGO'],
    },
    {
      id: 'C_LUGO',
      name: 'Lugo',
      lon: -7.55,
      lat: 43.01,
      duchy: 'D_G',
      kingdom: 'K_LEON',
      pixel_center: [200, 100],
      pixel_count: 800,
      baronies: [],
      neighbors: ['C_CORUNA'],
    },
  ],
  baronies: [],
}

const EMPTY_FC = { type: 'FeatureCollection', features: [] }

function setupFetchMock() {
  global.fetch = vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('territory_metadata')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(META) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(EMPTY_FC) })
  }) as unknown as typeof fetch
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('CanvasViewer — Pitfall 5 pan-on-select', () => {
  beforeEach(() => {
    panToGeoCenterMock.mockClear()
    lastStageProps = null
    useUIStore.setState({
      selectedTerritoryId: null,
      layerVisibility: {
        terrain: true,
        territories: true,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
    setupFetchMock()
  })

  it('calls panToGeoCenter when selectedTerritoryId transitions from null to a known id', async () => {
    render(<CanvasViewer projectId="p1" />, { wrapper })
    await screen.findByTestId('konva-stage')

    panToGeoCenterMock.mockClear()

    await act(async () => {
      useUIStore.getState().select('C_LUGO')
      // Flush timers for any pending useEffects
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(panToGeoCenterMock).toHaveBeenCalled()
    const call = panToGeoCenterMock.mock.calls.at(-1)!
    // signature: (stage, lon, lat, projection, scale, cfg)
    expect(call[1]).toBeCloseTo(-7.55, 6)  // Lugo lon
    expect(call[2]).toBeCloseTo(43.01, 6)  // Lugo lat
    // cfg should carry mapW/mapH
    expect(call[5]).toMatchObject({ mapW: 2000, mapH: 1600 })
  })

  it('does NOT call panToGeoCenter when selection clears (id = null)', async () => {
    useUIStore.setState({ selectedTerritoryId: 'C_LUGO' })
    render(<CanvasViewer projectId="p1" />, { wrapper })
    await screen.findByTestId('konva-stage')
    panToGeoCenterMock.mockClear()

    await act(async () => {
      useUIStore.getState().select(null)
      await new Promise((r) => setTimeout(r, 0))
    })
    expect(panToGeoCenterMock).not.toHaveBeenCalled()
  })
})

describe('CanvasViewer — Pitfall 6 empty-Stage click deselect', () => {
  beforeEach(() => {
    panToGeoCenterMock.mockClear()
    lastStageProps = null
    useUIStore.setState({
      selectedTerritoryId: 'C_LUGO',
      layerVisibility: {
        terrain: true,
        territories: true,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
    setupFetchMock()
  })

  it('clears selection when clicking the Stage background (e.target === e.target.getStage())', async () => {
    render(<CanvasViewer projectId="p1" />, { wrapper })
    await screen.findByTestId('konva-stage')

    expect(lastStageProps).not.toBeNull()
    const onClick = (lastStageProps as { onClick?: (e: unknown) => void }).onClick
    expect(typeof onClick).toBe('function')

    // Fake Konva click event where e.target is the stage (e.target.getStage() === e.target)
    const stageLike = {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any
    stageLike.getStage = () => stageLike
    onClick!({ target: stageLike })

    expect(useUIStore.getState().selectedTerritoryId).toBeNull()
  })

  it('does NOT clear selection when click target is a child shape', async () => {
    render(<CanvasViewer projectId="p1" />, { wrapper })
    await screen.findByTestId('konva-stage')

    const onClick = (lastStageProps as { onClick?: (e: unknown) => void }).onClick
    const stageLike = { getStage() { return this } }
    const shapeLike = { getStage: () => stageLike }
    onClick!({ target: shapeLike })

    expect(useUIStore.getState().selectedTerritoryId).toBe('C_LUGO')
  })
})

describe('CanvasViewer — Stage wiring for zoom/pan/fit', () => {
  beforeEach(() => {
    panToGeoCenterMock.mockClear()
    lastStageProps = null
    useUIStore.setState({
      selectedTerritoryId: null,
      layerVisibility: {
        terrain: true,
        territories: true,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
    setupFetchMock()
  })

  it('passes draggable, onWheel, dragBoundFunc, onClick, onTap to the Stage', async () => {
    render(<CanvasViewer projectId="p1" />, { wrapper })
    await screen.findByTestId('konva-stage')
    const p = lastStageProps as Record<string, unknown>
    expect(p.draggable).toBe(true)
    expect(typeof p.onWheel).toBe('function')
    expect(typeof p.dragBoundFunc).toBe('function')
    expect(typeof p.onClick).toBe('function')
    expect(typeof p.onTap).toBe('function')
  })

  it('does NOT pass scaleX/scaleY props to Stage (imperative scale only)', async () => {
    // Advisor note: Stage scaleX/scaleY props fight with imperative stage.scale()
    // and snap the view back on every React re-render. Initial scale is set by
    // fitToView() on mount via the stage ref.
    render(<CanvasViewer projectId="p1" />, { wrapper })
    await screen.findByTestId('konva-stage')
    const p = lastStageProps as Record<string, unknown>
    expect(p.scaleX).toBeUndefined()
    expect(p.scaleY).toBeUndefined()
  })

  it('renders FitToViewButton and InteractionLayer as part of the canvas tree', async () => {
    render(<CanvasViewer projectId="p1" />, { wrapper })
    await screen.findByTestId('konva-stage')
    expect(screen.getByTestId('fit-to-view')).toBeInTheDocument()
    expect(screen.getByTestId('interaction-layer')).toBeInTheDocument()
    expect(screen.getByTestId('decorations-layer')).toBeInTheDocument()
  })
})
