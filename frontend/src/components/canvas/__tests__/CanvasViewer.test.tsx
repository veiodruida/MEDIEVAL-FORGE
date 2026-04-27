import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CanvasViewer } from '../CanvasViewer'
import { useUIStore } from '../../../stores/uiStore'
import { useEditorStore } from '../../../stores/useEditorStore'
import { useProjectStore, beginTransaction, endTransaction } from '../../../stores/useProjectStore'

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

vi.mock('../../../api/edit', () => ({
  paintTerrain: vi.fn(),
  moveCapital: vi.fn(),
  reshapeGeometry: vi.fn(),
  EditApiError: class EditApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'EditApiError'
      this.status = status
    }
  },
}))

// Import paintTerrain after mock so we get the mocked version
import { paintTerrain } from '../../../api/edit'

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
      layerVisibility: { condados: true, baronies: false, terrain: false, borders: true, capitals: true, labels: false },
    })
    useEditorStore.setState({ editMode: false, activeTool: 'none', activeTerrain: null, brushRadius: 30, undoLabels: [], redoLabels: [] })
    useProjectStore.setState({ territories: {}, capitals: {}, terrain_types: {}, projectId: 'test-pid' })
    useProjectStore.temporal.getState().clear()
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

  it('BaronyLayer visible prop tracks layerVisibility.baronies (260420-hkr)', async () => {
    // After 260420-hkr BaronyLayer is gated by its own `baronies` key,
    // independent of the `borders` toggle. Default baronies=false → hidden.
    useUIStore.setState({
      layerVisibility: { condados: true, baronies: false, terrain: false, borders: true, capitals: true, labels: false },
    })
    setupFetchMock()
    render(<CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />, { wrapper })
    const barony = await screen.findByTestId('barony-layer')
    expect(barony.getAttribute('data-visible')).toBe('false')
  })
})

// ---------------------------------------------------------------------------
// Phase 05 — paint tool tests
// ---------------------------------------------------------------------------

const META_WITH_CONDADOS = {
  region: 'iberia',
  map_size: [1920, 1080],
  bounds: { lon_min: -9.5, lon_max: 4.5, lat_min: 35.0, lat_max: 44.0 },
  kingdoms: {},
  duchies: {},
  condados: [
    { id: 'c1', name: 'C1', lon: -5, lat: 40, duchy: 'D', kingdom: 'K', pixel_center: [0, 0], pixel_count: 1, baronies: [], neighbors: [] },
    { id: 'c2', name: 'C2', lon: -4, lat: 41, duchy: 'D', kingdom: 'K', pixel_center: [0, 0], pixel_count: 1, baronies: [], neighbors: [] },
  ],
  baronies: [],
}

const RAW_FC_WITH_CONDADOS = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { id: 'c1' }, geometry: { type: 'Polygon', coordinates: [[[-5, 40], [-4, 40], [-4, 41], [-5, 40]]] } },
    { type: 'Feature', properties: { id: 'c2' }, geometry: { type: 'Polygon', coordinates: [[[-4, 41], [-3, 41], [-3, 42], [-4, 41]]] } },
  ],
}

function setupFetchMockWithCondados() {
  global.fetch = vi.fn((url: string) => {
    const urlStr = String(url)
    if (urlStr.includes('territory_metadata')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(META_WITH_CONDADOS) })
    }
    if (urlStr.includes('territories.geojson')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(RAW_FC_WITH_CONDADOS) })
    }
    if (urlStr.includes('baronies.geojson')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ type: 'FeatureCollection', features: [] }) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  }) as unknown as typeof fetch
}

describe('CanvasViewer — paint tool (Phase 05)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useUIStore.setState({
      selectedTerritoryId: null,
      layerVisibility: { condados: true, baronies: false, terrain: false, borders: true, capitals: true, labels: false },
    })
    useEditorStore.setState({ editMode: true, activeTool: 'none', activeTerrain: null, brushRadius: 30, undoLabels: [], redoLabels: [] })
    useProjectStore.setState({ territories: {}, capitals: {}, terrain_types: {}, projectId: 'test-pid' })
    useProjectStore.temporal.getState().clear()
  })

  it('test_paint_p_shortcut_sets_active_tool: pressing P in editMode sets activeTool=paint', async () => {
    setupFetchMockWithCondados()
    render(<CanvasViewer projectId="test-pid" />, { wrapper })
    // Wait for render
    await screen.findByTestId('konva-stage')

    act(() => {
      fireEvent.keyDown(window, { key: 'p' })
    })

    expect(useEditorStore.getState().activeTool).toBe('paint')
  })

  it('test_paint_p_shortcut_noop_when_not_editMode: P does nothing when editMode=false', async () => {
    useEditorStore.setState({ editMode: false, activeTool: 'none', activeTerrain: null, brushRadius: 30, undoLabels: [], redoLabels: [] })
    setupFetchMockWithCondados()
    render(<CanvasViewer projectId="test-pid" />, { wrapper })
    await screen.findByTestId('konva-stage')

    act(() => {
      fireEvent.keyDown(window, { key: 'p' })
    })

    expect(useEditorStore.getState().activeTool).toBe('none')
  })

  it('test_paint_stroke_optimistic_then_skipped_revert: painted_ids keep terrain, skipped_ids revert', async () => {
    vi.mocked(paintTerrain).mockResolvedValue({ painted_ids: ['c1'], skipped_ids: ['c2'] })
    setupFetchMockWithCondados()

    // Directly test the store behavior (paint handler logic)
    useEditorStore.setState({ editMode: true, activeTool: 'paint', activeTerrain: 'forest', brushRadius: 30, undoLabels: [], redoLabels: [] })

    // Capture pre-stroke snapshot BEFORE optimistic paint (mirrors CanvasViewer handlePaintMouseDown)
    const snapshot = { ...useProjectStore.getState().terrain_types }

    // Simulate optimistic paint: set both c1 and c2
    beginTransaction()
    useProjectStore.getState().setTerrainType('c1', 'forest')
    useProjectStore.getState().setTerrainType('c2', 'forest')

    // Simulate mouseup: call paintTerrain, revert skipped
    const resp = await paintTerrain('test-pid', { territory_ids: ['c1', 'c2'], terrain_type: 'forest' })
    for (const id of resp.skipped_ids) {
      const prior = snapshot[id]
      if (prior !== undefined) {
        useProjectStore.getState().setTerrainType(id, prior)
      } else {
        useProjectStore.getState().clearTerrainType(id)
      }
    }
    endTransaction()
    if (resp.painted_ids.length > 0) {
      useEditorStore.getState().pushUndoLabel(`Pintar Floresta — ${resp.painted_ids.length} condado(s)`)
    }

    expect(useProjectStore.getState().terrain_types['c1']).toBe('forest')
    expect(useProjectStore.getState().terrain_types['c2']).toBeUndefined()
  })

  it('test_paint_network_error_full_rollback: on paintTerrain reject, terrain_types reverts to snapshot', async () => {
    vi.mocked(paintTerrain).mockRejectedValue(new Error('network error'))

    useEditorStore.setState({ editMode: true, activeTool: 'paint', activeTerrain: 'mountain', brushRadius: 30, undoLabels: [], redoLabels: [] })

    // Snapshot before stroke
    const snapshot = { ...useProjectStore.getState().terrain_types }

    // Simulate optimistic paint
    beginTransaction()
    useProjectStore.getState().setTerrainType('c1', 'mountain')
    useProjectStore.getState().setTerrainType('c2', 'mountain')

    // Simulate error rollback
    try {
      await paintTerrain('test-pid', { territory_ids: ['c1', 'c2'], terrain_type: 'mountain' })
    } catch {
      useProjectStore.getState().restoreTerrainTypes(snapshot)
    } finally {
      endTransaction()
    }

    expect(useProjectStore.getState().terrain_types['c1']).toBeUndefined()
    expect(useProjectStore.getState().terrain_types['c2']).toBeUndefined()
  })

  it('test_paint_records_one_undo_step: successful stroke pushes exactly one past state', async () => {
    vi.mocked(paintTerrain).mockResolvedValue({ painted_ids: ['c1', 'c2', 'c3'], skipped_ids: [] })

    const before = useProjectStore.temporal.getState().pastStates.length

    // Simulate paint stroke compound op
    beginTransaction()
    useProjectStore.getState().setTerrainType('c1', 'plains')
    useProjectStore.getState().setTerrainType('c2', 'plains')
    useProjectStore.getState().setTerrainType('c3', 'plains')
    endTransaction()

    const after = useProjectStore.temporal.getState().pastStates.length
    expect(after).toBe(before + 1)
  })

  it('test_paint_undo_label_pushed: after success, last undoLabel matches Portuguese paint pattern', async () => {
    vi.mocked(paintTerrain).mockResolvedValue({ painted_ids: ['c1', 'c2', 'c3'], skipped_ids: [] })

    useEditorStore.setState({ editMode: true, activeTool: 'paint', activeTerrain: 'mountain', brushRadius: 30, undoLabels: [], redoLabels: [] })

    // Simulate successful stroke
    beginTransaction()
    useProjectStore.getState().setTerrainType('c1', 'mountain')
    useProjectStore.getState().setTerrainType('c2', 'mountain')
    useProjectStore.getState().setTerrainType('c3', 'mountain')
    endTransaction()
    useEditorStore.getState().pushUndoLabel('Pintar Montanha — 3 condado(s)')

    const lastLabel = useEditorStore.getState().undoLabels.at(-1)
    expect(lastLabel).toMatch(/^Pintar Montanha — 3 condado/)
  })
})
