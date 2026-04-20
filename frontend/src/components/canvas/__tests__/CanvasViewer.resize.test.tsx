import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useUIStore } from '../../../stores/uiStore'

// Mock lib/projection so we can spy on computeFitToView (ESM named imports
// used directly in CanvasViewer — vi.spyOn won't intercept, so we replace
// the module with spyable impls that delegate to the real functions).
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

// ---------------------------------------------------------------------------
// Hoisted mutable state for useCanvasArtifacts mock (R4 transition test)
// ---------------------------------------------------------------------------
const mockState = vi.hoisted(() => ({
  // Each call to useCanvasArtifacts reads from this state object.
  // R4 flips `ready` from false → true between renders.
  ready: false,
}))

const META_FIXTURE = {
  region: 'iberia',
  map_size: [1920, 1080] as [number, number],
  bounds: { lon_min: -9.5, lon_max: 4.5, lat_min: 35.0, lat_max: 44.0 },
  kingdoms: {},
  duchies: {},
  condados: [],
  baronies: [],
}

vi.mock('../../../hooks/useCanvasArtifacts', () => {
  return {
    useCanvasArtifacts: () => {
      const ready = mockState.ready
      const territoriesQ = ready
        ? { data: [], isPending: false, error: null }
        : { data: undefined, isPending: true, error: null }
      const baroniesQ = ready
        ? { data: [], isPending: false, error: null }
        : { data: undefined, isPending: true, error: null }
      const condadoColorsQ = ready
        ? { data: {}, isPending: false, error: null }
        : { data: undefined, isPending: true, error: null }
      const baronyColorsQ = ready
        ? { data: {}, isPending: false, error: null }
        : { data: undefined, isPending: true, error: null }
      const metaQ = ready
        ? { data: META_FIXTURE, isPending: false, error: null }
        : { data: undefined, isPending: true, error: null }
      return [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ]
    },
  }
})

// Capture Stage props across re-renders (R1/R2/R4)
const stagePropsRef: { current: Record<string, unknown> | null } = { current: null }

vi.mock('react-konva', () => ({
  Stage: (p: Record<string, unknown>) => {
    stagePropsRef.current = p
    return <div data-testid="konva-stage">{p.children as React.ReactNode}</div>
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
  LABEL_ZOOM_THRESHOLD_RELATIVE: 1.5,
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

// ---------------------------------------------------------------------------
// Capturing ResizeObserver fake — retains history across mount/unmount cycles
// ---------------------------------------------------------------------------
let roCallback: ResizeObserverCallback | null = null
const observedElements: Element[] = []
class CapturingRO {
  constructor(cb: ResizeObserverCallback) {
    roCallback = cb
  }
  observe(el: Element) {
    observedElements.push(el)
  }
  unobserve() {}
  disconnect() {
    // Keep callback reference alive so tests can invoke it even after disconnect.
  }
}

// ---------------------------------------------------------------------------
// Silent ResizeObserver — used for R5 (sync-measure belt-and-suspenders test).
// Never fires the callback; simulates a browser that delivers no initial entry.
// ---------------------------------------------------------------------------
class SilentRO {
  constructor(_cb: ResizeObserverCallback) {
    // deliberately does not store cb — callback is never fired
  }
  observe(_el: Element) {}
  unobserve() {}
  disconnect() {}
}

// Import CanvasViewer AFTER mocks are declared.
// eslint-disable-next-line @typescript-eslint/no-require-imports
import { CanvasViewer } from '../CanvasViewer'

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
    CapturingRO as unknown as typeof ResizeObserver
  stagePropsRef.current = null
  roCallback = null
  observedElements.length = 0
  mockState.ready = true // default: artifacts resolved (loading-transition test flips this)
  useUIStore.setState({
    selectedTerritoryId: null,
    layerVisibility: {
      condados: true,
      baronies: false,
      borders: true,
      capitals: true,
      labels: false,
    },
  })
})

describe('CanvasViewer — ResizeObserver wiring (GAP-05)', () => {
  it('R1: updates Stage width/height when container resizes', () => {
    renderWithProviders(<CanvasViewer projectId="p1" />)

    // Initial: fallback 800/600 from props defaults
    expect(stagePropsRef.current?.width).toBe(800)
    expect(stagePropsRef.current?.height).toBe(600)

    // Trigger resize via captured observer callback (wrapped in act so
    // React state updates flush before we assert Stage props).
    act(() => {
      roCallback!(
        [{ contentRect: { width: 1600, height: 900 } } as unknown as ResizeObserverEntry],
        {} as ResizeObserver,
      )
    })

    expect(stagePropsRef.current?.width).toBe(1600)
    expect(stagePropsRef.current?.height).toBe(900)
  })

  it('R2: recomputes minScale after resize — computeFitToView called with new dims', () => {
    computeFitToViewSpy.mockClear()
    renderWithProviders(<CanvasViewer projectId="p1" />)

    const mountCallCount = computeFitToViewSpy.mock.calls.length
    expect(mountCallCount).toBeGreaterThanOrEqual(1) // initial auto-fit

    // Fire resize callback with a new viewport
    act(() => {
      roCallback!(
        [{ contentRect: { width: 1600, height: 900 } } as unknown as ResizeObserverEntry],
        {} as ResizeObserver,
      )
    })

    const calls = computeFitToViewSpy.mock.calls
    expect(calls.length).toBeGreaterThan(mountCallCount) // re-fit triggered by resize
    const lastCall = calls[calls.length - 1]
    expect(lastCall).toBeDefined()
    expect(lastCall![2]).toBe(1600) // stage width arg
    expect(lastCall![3]).toBe(900) // stage height arg
  })

  it('R3: ignores 0x0 transient measurements without regression', () => {
    renderWithProviders(<CanvasViewer projectId="p1" />)
    const initialW = stagePropsRef.current?.width
    act(() => {
      roCallback!(
        [{ contentRect: { width: 0, height: 0 } } as unknown as ResizeObserverEntry],
        {} as ResizeObserver,
      )
    })
    // Stage stays at prior dimensions (no 0x0 write-through)
    expect(stagePropsRef.current?.width).toBe(initialW)
    expect(stagePropsRef.current?.width).not.toBe(0)
  })

  it('R5: sync-measures container via getBoundingClientRect when RO never fires (belt-and-suspenders)', () => {
    // Switch to a silent RO that never fires the callback — simulates browsers
    // that don't deliver an initial ResizeObserver entry for already-laid-out elements.
    ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
      SilentRO as unknown as typeof ResizeObserver

    // Stub getBoundingClientRect on HTMLElement so the sync-measure path sees
    // real non-zero dims rather than jsdom's default 0×0.
    const realGetBCR = HTMLElement.prototype.getBoundingClientRect
    HTMLElement.prototype.getBoundingClientRect = function () {
      return {
        width: 1440, height: 810,
        top: 0, left: 0, right: 1440, bottom: 810,
        x: 0, y: 0,
        toJSON() { return {} },
      } as DOMRect
    }

    try {
      renderWithProviders(<CanvasViewer projectId="p1" />)

      // The RO callback is never fired — Stage dimensions must come from getBCR.
      expect(stagePropsRef.current?.width).toBe(1440)
      expect(stagePropsRef.current?.height).toBe(810)
    } finally {
      HTMLElement.prototype.getBoundingClientRect = realGetBCR
    }
  })

  it('R4: attaches observer to the content container after metaQ resolves (B-1 fix)', () => {
    // Start with loading branch
    mockState.ready = false
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" />
      </QueryClientProvider>,
    )

    // At this point the observer should be attached to the loading div
    const loadingObservedCount = observedElements.length
    expect(loadingObservedCount).toBeGreaterThanOrEqual(1)

    // Flip the mock so artifacts resolve, then re-render with the SAME
    // QueryClient — otherwise the entire tree re-mounts and state is lost.
    mockState.ready = true
    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" />
      </QueryClientProvider>,
    )

    // The observer must have migrated to the new content div
    expect(observedElements.length).toBeGreaterThanOrEqual(2)
    expect(observedElements[0]).not.toBe(
      observedElements[observedElements.length - 1],
    )

    // The LIVE observer (attached to the content div) MUST still drive Stage props
    // when fired with new dimensions.
    act(() => {
      roCallback!(
        [{ contentRect: { width: 1280, height: 720 } } as unknown as ResizeObserverEntry],
        {} as ResizeObserver,
      )
    })
    expect(stagePropsRef.current?.width).toBe(1280)
    expect(stagePropsRef.current?.height).toBe(720)
  })
})
