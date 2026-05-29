/**
 * CanvasViewer fitToView gating tests (Plan 04.1-03 Task 1 / D-01 / UAT gap #1).
 *
 * D-01: stable projection-bounds key gates fitToView. A slider re-render that
 * produces a NEW projection object reference with IDENTICAL bounds must NOT
 * reset Stage zoom/pan. fitToView only fires on:
 *   - First mount (initial fit)
 *   - Real bounds change (project switch, region load → new mapW/mapH/bounds)
 *   - Viewport resize (separate effect — bounds-stable resize must still fit)
 *
 * Mock strategy mirrors CanvasViewer.resize.test.tsx:
 *   - vi.hoisted spy on computeFitToView (real impl delegated, calls tracked)
 *   - vi.mock useCanvasArtifacts to return resolved data (bypass early-return)
 *   - CapturingRO for ResizeObserver — invoke callback manually in act()
 *   - mockState.bounds drives metaQ.bounds so we can simulate "new object ref,
 *     same bounds" by re-rendering without flipping bounds, OR "real bounds
 *     change" by flipping mapW/lonMin between renders
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useUIStore } from '../../../stores/uiStore'
import { useRunStore } from '../../../stores/useRunStore'

// Hoisted spy on computeFitToView — replaces the named export with a vi.fn
// that delegates to the real implementation. Lets us count calls across
// re-renders without changing fit-to-view math.
const computeFitToViewSpy = vi.hoisted(() => vi.fn())
vi.mock('../../../lib/projection', async () => {
  const actual = await vi.importActual<typeof import('../../../lib/projection')>(
    '../../../lib/projection',
  )
  computeFitToViewSpy.mockImplementation(actual.computeFitToView)
  return {
    ...actual,
    computeFitToView: computeFitToViewSpy,
  }
})

// Mutable bounds — tests flip this between renders to simulate real bounds
// changes vs. identical-bounds re-renders.
const mockState = vi.hoisted(() => ({
  mapW: 1920,
  mapH: 1080,
  lonMin: -9.5,
  lonMax: 4.5,
  latMin: 35.0,
  latMax: 44.0,
}))

vi.mock('../../../hooks/useCanvasArtifacts', () => ({
  useCanvasArtifacts: () => {
    // Build a fresh META object every call so the consumer pattern of "new
    // ref every render" is realistic. The `bounds` and `map_size` values are
    // read from mockState, which tests mutate between renders.
    const meta = {
      region: 'iberia',
      map_size: [mockState.mapW, mockState.mapH] as [number, number],
      bounds: {
        lon_min: mockState.lonMin,
        lon_max: mockState.lonMax,
        lat_min: mockState.latMin,
        lat_max: mockState.latMax,
      },
      kingdoms: {},
      duchies: {},
      condados: [],
      baronies: [],
    }
    const territoriesQ = { data: [], isPending: false, error: null }
    const baroniesQ = { data: [], isPending: false, error: null }
    const condadoColorsQ = { data: {}, isPending: false, error: null }
    const baronyColorsQ = { data: {}, isPending: false, error: null }
    const metaQ = { data: meta, isPending: false, error: null }
    const stageRasterUrl = '/api/v3/projects/p1/artifacts/visual_condado.png'
    return [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ, stageRasterUrl]
  },
}))

vi.mock('react-konva', () => ({
  Stage: (p: Record<string, unknown>) => (
    <div data-testid="konva-stage">{p.children as React.ReactNode}</div>
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
  MAX_SCALE_MULTIPLIER: 16,
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
vi.mock('../HoverTooltip', () => ({
  HoverTooltip: () => <div data-testid="hover-tooltip" />,
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
vi.mock('../LegendCard', () => ({
  LegendCard: () => <div data-testid="legend-card" />,
}))
vi.mock('../InspectorSidebar', () => ({
  InspectorSidebar: () => <div data-testid="inspector-sidebar" />,
}))

// CapturingRO retains callback so tests can fire resize events manually.
let roCallback: ResizeObserverCallback | null = null
class CapturingRO {
  constructor(cb: ResizeObserverCallback) {
    roCallback = cb
  }
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Import CanvasViewer AFTER all mocks are declared.
import { CanvasViewer } from '../CanvasViewer'

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return { qc, ...render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>) }
}

describe('CanvasViewer fitToView gating (D-01 / UAT gap #1)', () => {
  beforeEach(() => {
    ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
      CapturingRO as unknown as typeof ResizeObserver
    roCallback = null
    computeFitToViewSpy.mockClear()

    // Reset stores so prior tests don't leak state (priorTokens leaks could
    // mask D-13 fallback resolution; selectedTerritoryId leaks could fire
    // panToGeoCenter unexpectedly).
    useUIStore.setState({
      selectedTerritoryIds: [],
      selectedTerritoryId: null,
      layerVisibility: {
        condados: true,
        baronies: false,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
    useRunStore.setState({ priorTokens: {}, state: 'generated' })

    // Reset bounds to canonical Iberia values.
    mockState.mapW = 1920
    mockState.mapH = 1080
    mockState.lonMin = -9.5
    mockState.lonMax = 4.5
    mockState.latMin = 35.0
    mockState.latMax = 44.0
  })

  it('test_fitToView_called_once_across_three_projection_ref_changes_with_identical_bounds', () => {
    // Initial mount — fitToView should fire once
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    const callsAfterMount = computeFitToViewSpy.mock.calls.length
    expect(callsAfterMount).toBeGreaterThanOrEqual(1)

    // Three re-renders with NEW projection object references but IDENTICAL
    // bounds (mockState unchanged). The useCanvasArtifacts mock builds a
    // fresh META object every call, so the meta useEffect that derives
    // `projection` SHOULD see a "new" meta — but bounds key stays stable,
    // so fitToView must NOT fire again.
    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v2" />
      </QueryClientProvider>,
    )
    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v3" />
      </QueryClientProvider>,
    )
    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v4" />
      </QueryClientProvider>,
    )

    // fitToView count must be the same — no additional fits after three
    // identical-bounds re-renders.
    expect(computeFitToViewSpy.mock.calls.length).toBe(callsAfterMount)
  })

  it('test_fitToView_fires_on_real_bounds_change_mapW', () => {
    // Mount with default Iberia bounds (mapW=1920)
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    const callsAfterMount = computeFitToViewSpy.mock.calls.length

    // Flip mapW to a different value to simulate region/project switch
    act(() => {
      mockState.mapW = 3840
    })
    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v2" />
      </QueryClientProvider>,
    )

    // The change in mapW must propagate through the bounds key and trigger
    // a new fitToView call.
    expect(computeFitToViewSpy.mock.calls.length).toBeGreaterThan(callsAfterMount)
  })

  it('test_fitToView_fires_on_viewport_resize', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    const callsAfterMount = computeFitToViewSpy.mock.calls.length
    expect(callsAfterMount).toBeGreaterThanOrEqual(1)

    // Fire ResizeObserver callback with new viewport dims — fit must fire
    // again (existing GAP-05 behavior preserved by viewport-key effect).
    act(() => {
      roCallback!(
        [{ contentRect: { width: 1600, height: 900 } } as unknown as ResizeObserverEntry],
        {} as ResizeObserver,
      )
    })

    expect(computeFitToViewSpy.mock.calls.length).toBeGreaterThan(callsAfterMount)
  })
})
