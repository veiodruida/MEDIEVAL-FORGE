/**
 * Phase 08.1 Plan 02 — BezierEditLayer render tests (Task 1).
 * Covers BEZ-RENDER-01 (curve + few anchors, NOT hundreds of raw vertices),
 * BEZ-RENDER-02 (activeTerritoryId=null → zero nodes), and the active-anchor-only
 * handle behavior (handles appear ONLY after an anchor is clicked).
 *
 * react-konva is mocked (jsdom has no canvas — Plan 01 didn't add the `canvas` dep),
 * following the VertexEditLayer.test.tsx pattern, extended with Path + Rect so anchors
 * and the curve outline are countable. useEditorStore is mocked so each test can drive
 * a deterministic store state. The store-identity guard against the REAL store lives in
 * the separate useEditorStore.bezierIdentity.test.ts (Task 2).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import React from 'react'
import { IBERIA_BARONY_RING } from '../__fixtures__/iberiaBaronyRing'
import type { ProjectionConfig } from '../../../lib/projection'

// ── mock react-konva ──────────────────────────────────────────────────────────
vi.mock('react-konva', () => {
  const React = require('react')
  const Layer: React.FC<{ children?: React.ReactNode; onClick?: (e: unknown) => void }> = ({
    children,
  }) => React.createElement('div', { 'data-testid': 'konva-layer' }, children)
  const Path: React.FC<{ data?: string; 'data-testid'?: string }> = (props) =>
    React.createElement('div', {
      'data-testid': props['data-testid'] ?? 'konva-path',
      'data-d': props.data,
    })
  const Rect: React.FC<{
    fill?: string
    width?: number
    height?: number
    onClick?: () => void
    onMouseEnter?: () => void
    onMouseLeave?: () => void
    'data-testid'?: string
    'data-anchor-idx'?: number
  }> = (props) =>
    React.createElement('div', {
      'data-testid': props['data-testid'] ?? 'konva-rect',
      'data-fill': props.fill,
      'data-width': props.width,
      'data-anchor-idx': props['data-anchor-idx'],
      onClick: props.onClick,
      onMouseEnter: props.onMouseEnter,
      onMouseLeave: props.onMouseLeave,
    })
  const Circle: React.FC<{ fill?: string; 'data-testid'?: string }> = (props) =>
    React.createElement('div', {
      'data-testid': props['data-testid'] ?? 'konva-circle',
      'data-fill': props.fill,
    })
  const Line: React.FC<{ 'data-testid'?: string; points?: number[] }> = (props) =>
    React.createElement('div', {
      'data-testid': props['data-testid'] ?? 'konva-line',
      // Forward points length as data-point-count so tests can assert the overlay geometry
      // without parsing a serialised number[] string. The plan unit test for the overlay
      // asserts points.length === 2 × vertexCount (explicit numeric fixture).
      'data-point-count': props.points !== undefined ? String(props.points.length) : undefined,
    })
  return { Layer, Path, Rect, Circle, Line }
})

// ── mock useEditorStore ───────────────────────────────────────────────────────
interface MockState {
  editableLayer: 'baronies' | 'landmask'
  activeTerritoryId: string | null
  activeTool: 'V' | 'A' | 'D' | 'S' | 'M' | null
  vertices: Record<string, { lat: number; lon: number }>
}
let mockState: MockState
vi.mock('../../../stores/useEditorStore', () => ({
  useEditorStore: (selector: (s: MockState) => unknown) => selector(mockState),
}))

import { BezierEditLayer, buildPathData } from '../BezierEditLayer'
import type { BezierAnchor } from '../BezierEditLayer'

// Iberia-bounds projection matching the fixture bbox (lon [-10,3], lat [36,44])
const PROJ: ProjectionConfig = {
  lonMin: -10,
  lonMax: 3,
  latMin: 36,
  latMax: 44,
  mapW: 1920,
  mapH: 1080,
  lonScale: Math.cos(((36 + 44) / 2) * (Math.PI / 180)),
}

/** Load the real IBERIA_BARONY_RING into the mocked store keyed b1#0..b1#N. */
function ringVertices(): Record<string, { lat: number; lon: number }> {
  const out: Record<string, { lat: number; lon: number }> = {}
  IBERIA_BARONY_RING.forEach(([lon, lat], i) => {
    out[`b1#${i}`] = { lat, lon }
  })
  return out
}

beforeEach(() => {
  mockState = {
    editableLayer: 'baronies',
    activeTerritoryId: 'b1',
    activeTool: 'V',
    vertices: ringVertices(),
  }
})

describe('BezierEditLayer render (Phase 08.1 Plan 02)', () => {
  it('BEZ-RENDER-01: renders a curve outline + a small anchor count (4..40), far below the raw vertex count, when a barony is selected in V-tool Bézier mode', () => {
    const rawVertexCount = IBERIA_BARONY_RING.length // ~100 raw ring vertices
    const { getAllByTestId, queryByTestId } = render(<BezierEditLayer projection={PROJ} currentScale={1} />)

    // One curve outline path
    expect(queryByTestId('bezier-curve-outline')).not.toBeNull()

    // Anchor squares: a handful, NOT hundreds
    const anchors = getAllByTestId('bezier-anchor')
    expect(anchors.length).toBeGreaterThanOrEqual(4)
    expect(anchors.length).toBeLessThanOrEqual(40)
    // far-below-raw clause: anchors are a sparse control set, not 1-per-vertex
    expect(anchors.length).toBeLessThan(rawVertexCount / 2)
  })

  it('BEZ-RENDER-02: renders zero nodes (no path, no anchors) when activeTerritoryId is null', () => {
    mockState.activeTerritoryId = null
    const { queryByTestId, queryAllByTestId } = render(<BezierEditLayer projection={PROJ} currentScale={1} />)
    expect(queryByTestId('bezier-curve-outline')).toBeNull()
    expect(queryAllByTestId('bezier-anchor')).toHaveLength(0)
    expect(queryByTestId('konva-layer')).toBeNull()
  })

  it('renders control handles + tethers ONLY for the active anchor — before any click, zero handle circles render', () => {
    const { queryAllByTestId, getAllByTestId } = render(<BezierEditLayer projection={PROJ} currentScale={1} />)
    // Before clicking any anchor: no handles, no tethers
    expect(queryAllByTestId('bezier-handle')).toHaveLength(0)
    expect(queryAllByTestId('bezier-tether')).toHaveLength(0)

    // Click the first anchor → activates it
    const anchors = getAllByTestId('bezier-anchor')
    fireEvent.click(anchors[0])

    // Now exactly two handle circles (cp1 + cp2) and two tethers render — for the active anchor only
    expect(getAllByTestId('bezier-handle')).toHaveLength(2)
    expect(getAllByTestId('bezier-tether')).toHaveLength(2)
  })

  it('does not render outside Bézier mode (e.g. landmask layer or non-V tool)', () => {
    mockState.editableLayer = 'landmask'
    const { queryByTestId } = render(<BezierEditLayer projection={PROJ} currentScale={1} />)
    expect(queryByTestId('konva-layer')).toBeNull()
  })

  it('sizes the anchor square in screen space: width = ANCHOR_BASE_PX / currentScale', () => {
    // At currentScale=4, anchorSize = 10 / 4 = 2.5 (explicit numeric fixture, not computed).
    // Verifies the G5 screen-space sizing: a constant ~10 CSS px square regardless of zoom.
    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} currentScale={4} />)
    const anchors = getAllByTestId('bezier-anchor')
    expect(anchors.length).toBeGreaterThan(0)
    // The Rect mock forwards width as data-width (string)
    expect(Number(anchors[0].getAttribute('data-width'))).toBeCloseTo(2.5, 6)
  })

  it('renders a live edited-contour overlay (bezier-edited-contour) whose points derive from store.vertices', () => {
    // G6 fix (Plan 08, option a): the overlay renders the active barony ring from
    // store.vertices as a distinct amber-dashed closed Line — visually distinct from the
    // colored raster BaronyLayer (backend GeoJSON) and the green Bézier curve outline.
    //
    // Fixture: 4-vertex square ring keyed 'b1#0'..'b1#3'.
    // Expected editedRingPts.length = 2 × 4 = 8 (explicit numeric fixture).
    // This proves the overlay maps each vertex lon/lat → canvas [x,y] pair.
    //
    // READ-ONLY: the overlay adds ZERO store writes; BEZ-IDENTITY-01 holds by construction.
    mockState.vertices = {
      'b1#0': { lat: 40.0, lon: -8.0 },
      'b1#1': { lat: 40.5, lon: -8.0 },
      'b1#2': { lat: 40.5, lon: -7.5 },
      'b1#3': { lat: 40.0, lon: -7.5 },
    }
    mockState.activeTerritoryId = 'b1'

    const { queryByTestId } = render(<BezierEditLayer projection={PROJ} currentScale={1} />)

    // The overlay Line must be present
    const overlay = queryByTestId('bezier-edited-contour')
    expect(overlay, 'bezier-edited-contour overlay Line must render when a barony is active').not.toBeNull()

    // data-point-count = 2 × 4 = 8 (explicit numeric fixture: 4 vertices → 8 numbers [x0,y0,...,x3,y3])
    expect(
      Number(overlay!.getAttribute('data-point-count')),
      'overlay points length must be 2 × vertexCount = 8 (4 vertices, explicit fixture)',
    ).toBe(8)
  })
})

describe('buildPathData closed ring (G1)', () => {
  /** Build a minimal BezierAnchor fixture with 3 anchors. */
  function makeAnchors(n: number): BezierAnchor[] {
    return Array.from({ length: n }, (_, i) => ({
      idx: i,
      anchorPx: [i * 100, i * 50] as [number, number],
      cp1Px: [i * 100 - 10, i * 50 - 5] as [number, number],
      cp2Px: [i * 100 + 10, i * 50 + 5] as [number, number],
      polyRangeStart: i * 5,
      polyRangeEnd: i * 5 + 4,
    }))
  }

  it('buildPathData with 3 anchors emits exactly 3 C commands (N=3, including closing segment)', () => {
    const anchors = makeAnchors(3)
    const d = buildPathData(anchors)
    // Count occurrences of ' C ' in the path string
    const cCount = (d.match(/ C /g) ?? []).length
    expect(cCount).toBe(3) // N cubic commands, not N-1
  })

  it('buildPathData with 4 anchors emits exactly 4 C commands (N=4, including closing segment)', () => {
    const anchors = makeAnchors(4)
    const d = buildPathData(anchors)
    const cCount = (d.match(/ C /g) ?? []).length
    expect(cCount).toBe(4)
  })

  it('buildPathData last C command targets anchor[0] anchorPx (ring closed back to start)', () => {
    const anchors = makeAnchors(3)
    const a0 = anchors[0]
    const d = buildPathData(anchors)
    // The path must end with the anchor[0] position as the final C endpoint
    const lastC = d.split(' C ').pop()!
    const parts = lastC.trim().split(/\s+/)
    // Last two numbers in the closing C command are the destination: anchor[0].anchorPx
    const endX = parseFloat(parts[parts.length - 2])
    const endY = parseFloat(parts[parts.length - 1])
    expect(endX).toBeCloseTo(a0.anchorPx[0], 6)
    expect(endY).toBeCloseTo(a0.anchorPx[1], 6)
  })

  it('buildPathData returns empty string for empty anchors array', () => {
    expect(buildPathData([])).toBe('')
  })
})
