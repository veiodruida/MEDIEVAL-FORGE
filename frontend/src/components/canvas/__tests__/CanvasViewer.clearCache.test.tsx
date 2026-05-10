/**
 * CanvasViewer clearCache discipline tests (Plan 04-04 Task 2).
 *
 * Tests that Konva.Layer.clearCache() fires per layer after:
 *   1. effectiveCacheVersion changes (token bump)
 *   2. stageView changes (stage-view radio switch)
 *   3. Does NOT fire spuriously when neither token nor stageView changes
 *
 * Pitfall 6 compliance: clearCache fires AFTER hydration data is present.
 * The mock for useCanvasArtifacts always returns resolved data so the early-
 * return guards in CanvasViewer are bypassed and the useEffect runs.
 *
 * Mock strategy: react-konva Stage is mocked with React.forwardRef to assign
 * a fake Konva-like object (with getLayers()) to the ref. This lets the
 * production useEffect call stage.getLayers().forEach(layer => layer.clearCache())
 * against spy functions we can assert on.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePipelineParams } from '../../../stores/usePipelineParams'
import { useRunStore } from '../../../stores/useRunStore'

// ---------------------------------------------------------------------------
// Spy infrastructure for clearCache assertions
// ---------------------------------------------------------------------------
const clearCacheSpy = vi.fn()
const batchDrawLayerSpy = vi.fn()

// Fake layer returned by getLayers() — has the clearCache/batchDraw surface
const fakeLayer = {
  clearCache: clearCacheSpy,
  batchDraw: batchDrawLayerSpy,
}

// Fake stage object that will be assigned to stageRef.current via forwardRef
const fakeStage = {
  getLayers: vi.fn(() => [fakeLayer]),
  scale: vi.fn(),
  position: vi.fn(),
  batchDraw: vi.fn(),
  scaleX: vi.fn(() => 1),
  getPointerPosition: vi.fn(() => ({ x: 0, y: 0 })),
}

// ---------------------------------------------------------------------------
// Mock react-konva Stage with forwardRef so the ref gets our fake stage object
// ---------------------------------------------------------------------------
vi.mock('react-konva', () => ({
  Stage: React.forwardRef(
    (
      props: { children?: React.ReactNode; [key: string]: unknown },
      ref: React.Ref<typeof fakeStage>,
    ) => {
      // Assign the fake Konva stage object to the ref so CanvasViewer's
      // stageRef.current.getLayers() works in jsdom.
      React.useImperativeHandle(ref, () => fakeStage, [])
      return <div data-testid="konva-stage">{props.children}</div>
    },
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

// ---------------------------------------------------------------------------
// Fixtures for useCanvasArtifacts mock — fully resolved so early-return guards
// in CanvasViewer are bypassed and clearCache useEffect can run.
// ---------------------------------------------------------------------------
const META_FIXTURE = {
  region: 'iberia',
  map_size: [1920, 1080] as [number, number],
  bounds: { lon_min: -9.5, lon_max: 4.5, lat_min: 35.0, lat_max: 44.0 },
  kingdoms: {},
  duchies: {},
  condados: [],
  baronies: [],
}

// Mutable state — tests update cacheVersion/stageView between renders via
// usePipelineParams and useRunStore (Zustand state), not via hook return.
vi.mock('../../../hooks/useCanvasArtifacts', () => ({
  useCanvasArtifacts: (_pid: string, _proj: unknown, _cv: unknown, _sv: unknown) => {
    const territoriesQ = { data: [], isPending: false, error: null }
    const baroniesQ = { data: [], isPending: false, error: null }
    const condadoColorsQ = { data: {}, isPending: false, error: null }
    const baronyColorsQ = { data: {}, isPending: false, error: null }
    const metaQ = { data: META_FIXTURE, isPending: false, error: null }
    const stageRasterUrl = '/api/v3/projects/p1/artifacts/visual_condado.png'
    return [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ, stageRasterUrl]
  },
}))

// ---------------------------------------------------------------------------
// Mocks for dependencies CanvasViewer imports (mirrors CanvasViewer.test.tsx)
// ---------------------------------------------------------------------------
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
  BaronyLayer: ({ visible }: { visible: boolean }) => (
    <div data-testid="barony-layer" data-visible={String(visible)} />
  ),
}))
vi.mock('../LayerTogglePanel', () => ({
  LayerTogglePanel: () => <div data-testid="layer-toggle-panel" />,
}))
vi.mock('../BackgroundLayer', () => ({
  BackgroundLayer: () => <div data-testid="background-layer" />,
}))
vi.mock('../InspectorSidebar', () => ({
  InspectorSidebar: () => <div data-testid="inspector-sidebar" />,
}))
vi.mock('../LegendCard', () => ({
  LegendCard: () => <div data-testid="legend-card" />,
}))

// Silence ResizeObserver (not relevant to these tests)
class NoopRO {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Import CanvasViewer AFTER all mocks are declared.
// eslint-disable-next-line @typescript-eslint/no-require-imports
import { CanvasViewer } from '../CanvasViewer'

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('CanvasViewer clearCache discipline', () => {
  beforeEach(() => {
    ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
      NoopRO as unknown as typeof ResizeObserver

    // Reset spy call counts between tests
    clearCacheSpy.mockReset()
    batchDrawLayerSpy.mockReset()
    fakeStage.getLayers.mockClear()

    // Reset stores to defaults
    usePipelineParams.setState({ stageView: 'render-final' })
    useRunStore.setState({ priorTokens: {}, state: 'generated' })
  })

  it('test_clearCache_called_on_token_change', async () => {
    // Render with cacheVersion='token-a'
    const { rerender } = renderWithProviders(
      <CanvasViewer projectId="p1" cacheVersion="token-a" />,
    )

    // Record call count after initial mount
    const callsAfterMount = clearCacheSpy.mock.calls.length

    // Rerender with a different cacheVersion — effectiveCacheVersion changes,
    // triggering the [effectiveCacheVersion, stageView] useEffect.
    await act(async () => {
      rerender(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <CanvasViewer projectId="p1" cacheVersion="token-b" />
        </QueryClientProvider>,
      )
    })

    // clearCache must have been called at least once after the token change
    expect(clearCacheSpy.mock.calls.length).toBeGreaterThan(callsAfterMount)
  })

  it('test_clearCache_called_on_stage_view_change', async () => {
    // Render with stageView='render-final' (default)
    usePipelineParams.setState({ stageView: 'render-final' })
    const { rerender } = renderWithProviders(
      <CanvasViewer projectId="p1" cacheVersion="token-x" />,
    )

    // Record call count after initial render
    const callsAfterMount = clearCacheSpy.mock.calls.length

    // Change stageView in the store — CanvasViewer reads usePipelineParams.stageView
    await act(async () => {
      usePipelineParams.setState({ stageView: 'smooth' })
      rerender(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <CanvasViewer projectId="p1" cacheVersion="token-x" />
        </QueryClientProvider>,
      )
    })

    // clearCache must have fired again after stageView changed
    expect(clearCacheSpy.mock.calls.length).toBeGreaterThan(callsAfterMount)
  })

  it('test_clearCache_NOT_called_when_token_unchanged', () => {
    // Render once — clearCache fires on initial mount (effect runs on mount)
    const { rerender } = renderWithProviders(
      <CanvasViewer projectId="p1" cacheVersion="stable-token" />,
    )

    // Record call count after initial mount (effect fires once on mount)
    const callsAfterFirstRender = clearCacheSpy.mock.calls.length

    // Rerender with same cacheVersion and same stageView (default 'render-final')
    // — the effect dependency array [effectiveCacheVersion, stageView] does NOT change,
    // so React skips the effect entirely.
    rerender(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <CanvasViewer projectId="p1" cacheVersion="stable-token" />
      </QueryClientProvider>,
    )

    // clearCache count must be the same — no additional calls from the second render
    expect(clearCacheSpy.mock.calls.length).toBe(callsAfterFirstRender)
  })
})
