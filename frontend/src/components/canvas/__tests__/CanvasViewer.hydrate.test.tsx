import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useProjectStore } from '../../../stores/useProjectStore'

// ---------------------------------------------------------------------------
// Mocks — must match the pattern in CanvasViewer.resize.test.tsx so that
// CanvasViewer can render without Konva/network dependencies.
// ---------------------------------------------------------------------------

// Mutable state read by the useCanvasArtifacts mock below.
// Tests call mockArtifacts() to install fresh query results before each render.
let currentTerritories: unknown = []
let currentMeta: unknown = undefined

vi.mock('../../../hooks/useCanvasArtifacts', () => ({
  useCanvasArtifacts: () => {
    return [
      { data: currentTerritories, isPending: currentTerritories === undefined, error: null },
      { data: [], isPending: false, error: null },
      { data: {}, isPending: false, error: null },
      { data: {}, isPending: false, error: null },
      { data: currentMeta, isPending: currentMeta === undefined, error: null },
    ]
  },
}))

vi.mock('react-konva', () => ({
  Stage: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-stage">{children}</div>
  ),
  Layer: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-layer">{children}</div>
  ),
  Image: () => <div data-testid="konva-image" />,
  Rect: () => <div data-testid="konva-rect" />,
  Circle: () => <div data-testid="konva-circle" />,
  Text: () => <div data-testid="konva-text" />,
  Line: () => <div data-testid="konva-line" />,
}))

vi.mock('../../../hooks/useZoomPan', () => ({
  SCALE_BY: 1.05,
  MAX_SCALE_MULTIPLIER: 4,
  panToGeoCenter: vi.fn(),
  makeWheelHandler: vi.fn(() => () => {}),
  makeDragBoundFunc: vi.fn(() => (pos: { x: number; y: number }) => pos),
  applyPanClamp: vi.fn(),
}))

vi.mock('../../../hooks/useKeyboardShortcuts', () => ({
  useKeyboardShortcuts: vi.fn(),
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

vi.mock('use-image', () => ({
  default: () => [undefined, 'loading'],
  useImage: () => [undefined, 'loading'],
}))

vi.mock('../TerritoryLayer', () => ({
  TerritoryLayer: () => <div data-testid="territory-layer" />,
}))

vi.mock('../BaronyLayer', () => ({
  BaronyLayer: () => <div data-testid="barony-layer" />,
}))

vi.mock('../LayerTogglePanel', () => ({
  LayerTogglePanel: () => <div data-testid="layer-toggle-panel" />,
}))

vi.mock('../BackgroundLayer', () => ({
  BackgroundLayer: () => <div data-testid="background-layer" />,
}))

// Import CanvasViewer AFTER mocks are declared.
import { CanvasViewer } from '../CanvasViewer'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeMeta = (condados: Array<{ id: string; lon: number; lat: number }>) => ({
  region: 'test',
  map_size: [1000, 800] as [number, number],
  bounds: { lon_min: -10, lon_max: 0, lat_min: 40, lat_max: 45 },
  kingdoms: {},
  duchies: {},
  condados: condados.map((c) => ({
    id: c.id,
    name: c.id,
    lon: c.lon,
    lat: c.lat,
    duchy: 'D',
    kingdom: 'K',
    pixel_center: [0, 0] as [number, number],
    pixel_count: 1,
    baronies: [],
    neighbors: [],
  })),
  baronies: [],
})

const makeTerritoryRenderList = (ids: string[]) =>
  ids.map((id) => ({
    id,
    name: id,
    points: [0, 0, 10, 0, 10, 10],
    neighbors: [],
  }))

const makeRawFC = (ids: string[]) => ({
  type: 'FeatureCollection',
  features: ids.map((id) => ({
    type: 'Feature',
    id,
    properties: { id, name: id, neighbors: [] },
    geometry: {
      type: 'Polygon',
      coordinates: [[[-5, 42], [-4, 42], [-4, 43], [-5, 42]]],
    },
  })),
})

// Install a global fetch mock that returns makeRawFC bodies keyed by projectId.
const installFetchMock = (byProjectId: Record<string, ReturnType<typeof makeRawFC>>) => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const m = url.match(/\/api\/projects\/([^/?]+)\/preview\/territories\.geojson/)
      if (!m) return new Response('not found', { status: 404 })
      const id = decodeURIComponent(m[1])
      const body = byProjectId[id]
      if (!body) return new Response('not found', { status: 404 })
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
}

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

// ---------------------------------------------------------------------------
// Test setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  useProjectStore.setState({ projectId: null, territories: {}, capitals: {}, loading: false })
  useProjectStore.temporal.getState().clear()
  currentTerritories = []
  currentMeta = undefined
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CanvasViewer — useProjectStore.hydrate() wiring', () => {
  it('Test 1: hydrates useProjectStore on mount once queries resolve', async () => {
    installFetchMock({ p1: makeRawFC(['a', 'b']) })
    currentTerritories = makeTerritoryRenderList(['a', 'b'])
    currentMeta = makeMeta([
      { id: 'a', lon: -5, lat: 42 },
      { id: 'b', lon: -4, lat: 43 },
    ])

    const qc = makeQC()
    render(<CanvasViewer projectId="p1" />, { wrapper: makeWrapper(qc) })

    await waitFor(() =>
      expect(useProjectStore.getState().projectId).toBe('p1'),
    )
    expect(useProjectStore.getState().territories['a']).toBeDefined()
    expect(useProjectStore.getState().territories['b']).toBeDefined()
    expect(useProjectStore.getState().capitals['a']).toEqual([-5, 42])
    expect(useProjectStore.getState().capitals['b']).toEqual([-4, 43])
  })

  it('Test 2: re-hydrates when projectId prop changes AND fully replaces prior territories', async () => {
    installFetchMock({
      p1: makeRawFC(['a', 'b']),
      p2: makeRawFC(['c']),
    })
    currentTerritories = makeTerritoryRenderList(['a', 'b'])
    currentMeta = makeMeta([
      { id: 'a', lon: -5, lat: 42 },
      { id: 'b', lon: -4, lat: 43 },
    ])

    const qc = makeQC()
    const { rerender } = render(<CanvasViewer projectId="p1" />, { wrapper: makeWrapper(qc) })

    // Wait for initial hydrate
    await waitFor(() =>
      expect(useProjectStore.getState().projectId).toBe('p1'),
    )

    // Switch to p2
    currentTerritories = makeTerritoryRenderList(['c'])
    currentMeta = makeMeta([{ id: 'c', lon: -6, lat: 41 }])
    rerender(<CanvasViewer projectId="p2" />)

    await waitFor(() =>
      expect(useProjectStore.getState().projectId).toBe('p2'),
    )
    expect(useProjectStore.getState().territories['c']).toBeDefined()
    // Absence checks (checker WARNING 5): old territories must be gone
    expect(useProjectStore.getState().territories['a']).toBeUndefined()
    expect(useProjectStore.getState().territories['b']).toBeUndefined()
  })

  it('Test 3: re-hydrates when cacheVersion changes', async () => {
    installFetchMock({ p1: makeRawFC(['a', 'b']) })
    currentTerritories = makeTerritoryRenderList(['a', 'b'])
    currentMeta = makeMeta([
      { id: 'a', lon: -5, lat: 42 },
      { id: 'b', lon: -4, lat: 43 },
    ])

    const qc = makeQC()
    const { rerender } = render(<CanvasViewer projectId="p1" cacheVersion="v1" />, { wrapper: makeWrapper(qc) })

    await waitFor(() =>
      expect(useProjectStore.getState().territories['a']).toBeDefined(),
    )

    // Change cacheVersion with new data
    installFetchMock({ p1: makeRawFC(['a', 'c']) })
    currentTerritories = makeTerritoryRenderList(['a', 'c'])
    currentMeta = makeMeta([
      { id: 'a', lon: -5, lat: 42 },
      { id: 'c', lon: -6, lat: 41 },
    ])
    rerender(<CanvasViewer projectId="p1" cacheVersion="v2" />)

    await waitFor(() =>
      expect(useProjectStore.getState().territories['c']).toBeDefined(),
    )
    expect(useProjectStore.getState().territories['b']).toBeUndefined()
  })

  it('Test 4: does nothing when metaQ is still pending', async () => {
    installFetchMock({ p1: makeRawFC(['a']) })
    currentTerritories = undefined
    currentMeta = undefined

    const qc = makeQC()
    render(<CanvasViewer projectId="p1" />, { wrapper: makeWrapper(qc) })

    // Give it time to fire if it was going to
    await new Promise((r) => setTimeout(r, 30))
    expect(useProjectStore.getState().projectId).toBeNull()
  })

  it('Test 5 (BLOCKER 1): hydrate does NOT push an undo entry', async () => {
    installFetchMock({ p1: makeRawFC(['a', 'b']) })
    currentTerritories = makeTerritoryRenderList(['a', 'b'])
    currentMeta = makeMeta([
      { id: 'a', lon: -5, lat: 42 },
      { id: 'b', lon: -4, lat: 43 },
    ])

    const before = useProjectStore.temporal.getState().pastStates.length // 0 after beforeEach.clear()

    const qc = makeQC()
    render(<CanvasViewer projectId="p1" />, { wrapper: makeWrapper(qc) })

    await waitFor(() =>
      expect(useProjectStore.getState().projectId).toBe('p1'),
    )

    expect(useProjectStore.temporal.getState().pastStates.length).toBe(before)
  })

  it('Test 6 (BLOCKER 1): user edit after hydrate pushes exactly one undo entry; Ctrl+Z restores edit not hydration', async () => {
    installFetchMock({ p1: makeRawFC(['a', 'b']) })
    currentTerritories = makeTerritoryRenderList(['a', 'b'])
    currentMeta = makeMeta([
      { id: 'a', lon: -5, lat: 42 },
      { id: 'b', lon: -4, lat: 43 },
    ])

    const qc = makeQC()
    render(<CanvasViewer projectId="p1" />, { wrapper: makeWrapper(qc) })

    await waitFor(() =>
      expect(useProjectStore.getState().projectId).toBe('p1'),
    )

    const hydratedLon = useProjectStore.getState().capitals['a'][0] // -5

    // Simulate user edit
    useProjectStore.getState().setCapital('a', [99, 99])
    expect(useProjectStore.temporal.getState().pastStates.length).toBe(1)

    // Undo should restore the hydrated capital, not an empty state
    useProjectStore.temporal.getState().undo()
    expect(useProjectStore.getState().capitals['a'][0]).toBe(hydratedLon)
    expect(useProjectStore.temporal.getState().pastStates.length).toBe(0)
    expect(useProjectStore.temporal.getState().futureStates.length).toBe(1)
  })

  it('Test 7 (BLOCKER 2): auto-save-style query invalidation does NOT re-hydrate', async () => {
    installFetchMock({ p1: makeRawFC(['a', 'b']) })
    currentTerritories = makeTerritoryRenderList(['a', 'b'])
    currentMeta = makeMeta([
      { id: 'a', lon: -5, lat: 42 },
      { id: 'b', lon: -4, lat: 43 },
    ])

    const qc = makeQC()
    const { rerender } = render(
      <CanvasViewer projectId="p1" cacheVersion="v1" />,
      { wrapper: makeWrapper(qc) },
    )

    await waitFor(() =>
      expect(useProjectStore.getState().projectId).toBe('p1'),
    )

    // Simulate an in-memory edit that should survive auto-save invalidation
    const editedGeom = {
      type: 'Polygon' as const,
      coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] as [number, number][][],
    }
    useProjectStore.getState().setTerritory('a', editedGeom)
    const editedRef = useProjectStore.getState().territories['a']

    // Simulate post-auto-save refetch: same projectId + cacheVersion,
    // but a new territoriesQ.data reference (different array identity)
    currentTerritories = [...makeTerritoryRenderList(['a', 'b'])] // new reference
    rerender(<CanvasViewer projectId="p1" cacheVersion="v1" />)

    // Give time for any accidental re-hydrate to fire
    await new Promise((r) => setTimeout(r, 50))

    // The in-memory edit must survive — hydrate must NOT have re-run
    expect(useProjectStore.getState().territories['a']).toBe(editedRef)
  })
})
