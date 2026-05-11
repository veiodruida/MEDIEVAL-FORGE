/**
 * CanvasViewer hold-spacebar before/after preview tests (Plan 04.1-03
 * Task 2 / D-02 / UAT gap #2).
 *
 * D-02: hold spacebar swaps the canvas raster to `previousCacheVersion`
 * (the cacheVersion that was current right before the latest slider-driven
 * render replaced it). Release restores the current cacheVersion.
 *
 * Precedence chain for effectiveCacheVersion (top wins):
 *   1. Spacebar gesture (previewPrior && previousCacheVersion) → previousCacheVersion
 *   2. D-13 cancel revert (priorTokens.render) → priorTokens.render
 *   3. Default → cacheVersion (prop)
 *
 * Test strategy:
 *   - vi.mock useCanvasArtifacts with a spy so we can read the 3rd arg
 *     (effective cacheVersion) per render
 *   - useCacheVersionsRef captures cacheVersion values flowing into the hook
 *   - fireEvent on window for keydown/keyup/blur (jsdom supports these)
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, screen, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useUIStore } from '../../../stores/uiStore'
import { useRunStore } from '../../../stores/useRunStore'

// Hoisted spy capturing every call to useCanvasArtifacts.
// The 3rd arg is `effectiveCacheVersion`.
const useCanvasArtifactsSpy = vi.hoisted(() => vi.fn())

const META_FIXTURE = {
  region: 'iberia',
  map_size: [1920, 1080] as [number, number],
  bounds: { lon_min: -9.5, lon_max: 4.5, lat_min: 35.0, lat_max: 44.0 },
  kingdoms: {},
  duchies: {},
  condados: [],
  baronies: [],
}

vi.mock('../../../hooks/useCanvasArtifacts', () => ({
  useCanvasArtifacts: (
    projectId: string | undefined,
    projection: unknown,
    cacheVersion: string | undefined,
    stageView: unknown,
  ) => {
    useCanvasArtifactsSpy(projectId, projection, cacheVersion, stageView)
    const territoriesQ = { data: [], isPending: false, error: null }
    const baroniesQ = { data: [], isPending: false, error: null }
    const condadoColorsQ = { data: {}, isPending: false, error: null }
    const baronyColorsQ = { data: {}, isPending: false, error: null }
    const metaQ = { data: META_FIXTURE, isPending: false, error: null }
    const stageRasterUrl = `/api/v3/projects/p1/artifacts/visual_condado.png?v=${cacheVersion ?? ''}`
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

// Silent ResizeObserver — not relevant to gesture tests.
class NoopRO {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Import CanvasViewer AFTER all mocks declared.
import { CanvasViewer } from '../CanvasViewer'

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return { qc, ...render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>) }
}

/** Returns the cacheVersion (3rd arg) passed to the most recent call. */
function lastEffectiveCacheVersion(): string | undefined {
  const calls = useCanvasArtifactsSpy.mock.calls
  if (calls.length === 0) return undefined
  return calls[calls.length - 1][2] as string | undefined
}

describe('CanvasViewer hold-spacebar before/after preview (D-02 / UAT gap #2)', () => {
  beforeEach(() => {
    ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
      NoopRO as unknown as typeof ResizeObserver
    useCanvasArtifactsSpy.mockClear()
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
  })

  it('test_spacebar_hold_sets_preview_prior_when_previous_cache_version_exists', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    // Slider-driven render completed → cacheVersion transitions v1 → v2.
    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v2" />
      </QueryClientProvider>,
    )

    // After transition, effective cacheVersion is the new value (v2).
    expect(lastEffectiveCacheVersion()).toBe('v2')

    // Hold spacebar → effective cacheVersion swaps to v1 (the previous).
    fireEvent.keyDown(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('v1')

    // Release → restore v2.
    fireEvent.keyUp(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('v2')
  })

  it('test_spacebar_hold_is_noop_when_no_cache_version_transition_has_occurred', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    expect(lastEffectiveCacheVersion()).toBe('v1')

    // No transition has occurred — gesture must be no-op.
    fireEvent.keyDown(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('v1')

    // Badge MUST NOT be in DOM.
    expect(screen.queryByTestId('preview-prior-badge')).toBeNull()
  })

  it('test_anterior_badge_visible_only_while_preview_prior_true', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v2" />
      </QueryClientProvider>,
    )

    // Before hold — badge absent.
    expect(screen.queryByTestId('preview-prior-badge')).toBeNull()

    fireEvent.keyDown(window, { code: 'Space' })

    // During hold — badge present with PT-BR text.
    const badge = screen.getByTestId('preview-prior-badge')
    expect(badge).toBeTruthy()
    expect(badge.textContent).toBe('Anterior')

    fireEvent.keyUp(window, { code: 'Space' })

    // After release — badge gone.
    expect(screen.queryByTestId('preview-prior-badge')).toBeNull()
  })

  it('test_window_blur_resets_preview_prior', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v2" />
      </QueryClientProvider>,
    )

    fireEvent.keyDown(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('v1')

    // Window blur should reset previewPrior even though keyup never fired.
    fireEvent.blur(window)
    expect(lastEffectiveCacheVersion()).toBe('v2')
    expect(screen.queryByTestId('preview-prior-badge')).toBeNull()
  })

  it('test_keyboard_repeat_does_not_re_toggle_preview_prior', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    rerender(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v2" />
      </QueryClientProvider>,
    )

    // Initial keydown → previewPrior true.
    fireEvent.keyDown(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('v1')

    // OS key-repeat fires keydown again with repeat=true.
    // Behavior: state stays true (no toggle); cacheVersion stays at v1.
    fireEvent.keyDown(window, { code: 'Space', repeat: true })
    fireEvent.keyDown(window, { code: 'Space', repeat: true })
    fireEvent.keyDown(window, { code: 'Space', repeat: true })
    expect(lastEffectiveCacheVersion()).toBe('v1')
    expect(screen.queryByTestId('preview-prior-badge')).toBeTruthy()

    // Release → previewPrior false.
    fireEvent.keyUp(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('v2')
  })

  it('test_effective_cache_version_uses_previous_cache_version_during_preview', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    // Three transitions: v1 → v2 → v3. previousCacheVersion should hold v2
    // (the value that was current BEFORE v3 replaced it).
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

    expect(lastEffectiveCacheVersion()).toBe('v3')

    fireEvent.keyDown(window, { code: 'Space' })
    // Gesture surfaces the SETTLED PRIOR — i.e. v2, not v1.
    expect(lastEffectiveCacheVersion()).toBe('v2')

    // Critical: gesture must NOT fall back to priorTokens.render — that path
    // is D-13's territory. Here priorTokens.render is empty.
    expect(lastEffectiveCacheVersion()).not.toBe(undefined)

    fireEvent.keyUp(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('v3')
  })

  it('test_d13_cancel_revert_still_uses_prior_tokens_render_when_no_gesture', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <CanvasViewer projectId="p1" cacheVersion="v1" />
      </QueryClientProvider>,
    )

    // No cacheVersion transition has occurred. previousCacheVersion is
    // undefined → gesture is disabled. Now simulate the D-13 cancel revert
    // by populating priorTokens.render directly (revertStage action does
    // the same).
    expect(lastEffectiveCacheVersion()).toBe('v1')

    // Wrap the Zustand setState in act() so React commits the resulting
    // re-render before we assert. Without act, the spy reads the call list
    // before the new render cycle propagates effective=tok-prev.
    act(() => {
      useRunStore.setState({ priorTokens: { render: 'tok-prev' } })
    })
    expect(lastEffectiveCacheVersion()).toBe('tok-prev')

    // Spacebar hold: previewEnabled = false (no transition), so no-op.
    fireEvent.keyDown(window, { code: 'Space' })
    expect(lastEffectiveCacheVersion()).toBe('tok-prev')
    expect(screen.queryByTestId('preview-prior-badge')).toBeNull()
  })
})
