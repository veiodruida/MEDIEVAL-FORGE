import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CanvasViewer } from '../CanvasViewer'
import { useUIStore } from '../../../stores/uiStore'

vi.mock('react-konva', () => ({
  Stage: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-stage">{children}</div>
  ),
  Layer: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-layer">{children}</div>
  ),
  Image: () => <div data-testid="konva-image" />,
  Rect: () => <div data-testid="konva-rect" />,
  // plan 2.3 adds DecorationsLayer (Circle + Text) + InteractionLayer (Line)
  Circle: () => <div data-testid="konva-circle" />,
  Text: () => <div data-testid="konva-text" />,
  Line: () => <div data-testid="konva-line" />,
}))

// plan 2.3 hooks — pass-through stubs for integration tests that don't exercise
// zoom/pan logic directly (covered by dedicated useZoomPan + panOnSelect tests)
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
  BaronyLayer: ({ visible }: { visible: boolean }) => (
    <div data-testid="barony-layer" data-visible={String(visible)} />
  ),
}))

vi.mock('../LayerTogglePanel', () => ({
  LayerTogglePanel: () => <div data-testid="layer-toggle-panel" />,
}))

const META_FIXTURE = {
  region: 'iberia',
  map_size: [1920, 1080],
  bounds: { lon_min: -9.5, lon_max: 4.5, lat_min: 35.0, lat_max: 44.0 },
  kingdoms: {},
  duchies: {},
  condados: [],
  baronies: [],
}

const TERRITORIES_FIXTURE = { type: 'FeatureCollection', features: [] }
const BARONIES_FIXTURE = { type: 'FeatureCollection', features: [] }

function setupFetchMock(
  meta: unknown = META_FIXTURE,
  error: { status: number } | null = null,
) {
  global.fetch = vi.fn((url: string) => {
    const urlStr = String(url)
    if (error && urlStr.includes('territory_metadata')) {
      return Promise.resolve({
        ok: false,
        status: error.status,
        statusText: error.status === 404 ? 'Not Found' : 'Server Error',
        text: () => Promise.resolve('error'),
        json: () => Promise.resolve(null),
      })
    }
    if (urlStr.includes('territory_metadata')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(meta) })
    }
    if (urlStr.includes('territories.geojson')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(TERRITORIES_FIXTURE) })
    }
    if (urlStr.includes('baronies.geojson')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(BARONIES_FIXTURE) })
    }
    if (urlStr.includes('condado_colors')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    if (urlStr.includes('barony_colors')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  }) as unknown as typeof fetch
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('CanvasViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useUIStore.setState({
      selectedTerritoryId: null,
      layerVisibility: { terrain: true, territories: true, borders: true, capitals: true, labels: false },
    })
  })

  it('shows loading state while fetching metadata', async () => {
    global.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch
    render(<CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />, { wrapper })
    expect(screen.getByText('Loading map…')).toBeTruthy()
  })

  it('renders Stage when metadata loads successfully', async () => {
    setupFetchMock()
    const { findByTestId } = render(
      <CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />,
      { wrapper },
    )
    const stage = await findByTestId('konva-stage')
    expect(stage).toBeTruthy()
  })

  it('shows not-generated message on 404', async () => {
    setupFetchMock(null, { status: 404 })
    const { findByText } = render(
      <CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />,
      { wrapper },
    )
    expect(await findByText(/No map generated yet/)).toBeTruthy()
  })

  it('shows error message on server error', async () => {
    setupFetchMock(null, { status: 500 })
    const { findByText } = render(
      <CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />,
      { wrapper },
    )
    expect(await findByText(/Failed to load territory data/)).toBeTruthy()
  })

  it('Stage contains TerritoryLayer and BaronyLayer after all data loads', async () => {
    setupFetchMock()
    render(<CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />, { wrapper })
    const stage = await screen.findByTestId('konva-stage')
    expect(stage.querySelector('[data-testid="territory-layer"]')).not.toBeNull()
    expect(stage.querySelector('[data-testid="barony-layer"]')).not.toBeNull()
  })

  it('LayerTogglePanel is sibling of Stage (not inside Stage)', async () => {
    setupFetchMock()
    render(<CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />, { wrapper })
    const panel = await screen.findByTestId('layer-toggle-panel')
    const stage = screen.getByTestId('konva-stage')
    expect(panel).toBeTruthy()
    expect(stage.contains(panel)).toBe(false)
  })

  it('BaronyLayer visible prop tracks layerVisibility.borders', async () => {
    useUIStore.setState({
      layerVisibility: { terrain: true, territories: true, borders: false, capitals: true, labels: false },
    })
    setupFetchMock()
    render(<CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />, { wrapper })
    const barony = await screen.findByTestId('barony-layer')
    expect(barony.getAttribute('data-visible')).toBe('false')
  })
})
