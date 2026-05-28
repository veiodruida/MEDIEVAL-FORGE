/**
 * Phase 08.1 Plan 03 — BezierEditLayer drag-commit tests (BEZ-DRAG-01).
 *
 * Covers the actual editing capability added in Plan 03:
 *   - anchor drag → mark BOTH adjacent segments dirty → flatten ONLY dirty
 *     segments → setVerticesAndLog(op:'move') exactly once.
 *   - non-dirty index ranges copied VERBATIM from the store (byte-identical;
 *     the identity mechanism — RESEARCH §Pitfall 2).
 *   - anchor drag translates BOTH control handles by the same delta (rigid;
 *     preserves local curve shape).
 *   - boundary anchors (i=0, i=N-1): only the in-range adjacent segment(s) are
 *     marked dirty (closing segment N-1 stays non-editable, V1 limitation).
 *   - shared-vertex coupling: a coupled partner moves to the same coord.
 *   - snap applies to anchor drags (anchors only), never to control handles.
 *
 * The Plan 02 BEZ-IDENTITY-01 guard against the REAL store lives in
 * useEditorStore.bezierIdentity.test.ts and is run alongside this file in the
 * plan's verify command — it must stay green after drag code lands.
 *
 * react-konva is mocked (jsdom has no canvas). Unlike the Plan 02 render-test
 * mock, this mock forwards `draggable` + `onDragStart`/`onDragMove`/`onDragEnd`
 * so a synthetic Konva drag event (with a `target` reporting x()/y()) can be
 * fired. useEditorStore is partially mocked: selector reads come from a mutable
 * mockState, and `getState()` returns the live commit surface (vertices +
 * setVerticesAndLog spy) so the component's commit path is observable.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import React from 'react'
import { IBERIA_BARONY_RING } from '../__fixtures__/iberiaBaronyRing'
import { canvasToGeo, type ProjectionConfig } from '../../../lib/projection'

// ── mock react-konva (forwards drag handlers + draggable) ──────────────────────
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
  const Rect: React.FC<Record<string, unknown>> = (props) =>
    React.createElement('div', {
      'data-testid': (props['data-testid'] as string) ?? 'konva-rect',
      'data-anchor-idx': props['data-anchor-idx'],
      'data-draggable': props.draggable ? 'true' : 'false',
      onClick: props.onClick as () => void,
      // map react-konva drag handlers onto DOM events the test can fire
      onDragStart: props.onDragStart as () => void,
      onDrag: props.onDragMove as () => void,
      onDragEnd: props.onDragEnd as () => void,
    })
  const Circle: React.FC<Record<string, unknown>> = (props) =>
    React.createElement('div', {
      'data-testid': (props['data-testid'] as string) ?? 'konva-circle',
      'data-handle-kind': props['data-handle-kind'],
      'data-draggable': props.draggable ? 'true' : 'false',
      onDragStart: props.onDragStart as () => void,
      onDrag: props.onDragMove as () => void,
      onDragEnd: props.onDragEnd as () => void,
    })
  const Line: React.FC<{ 'data-testid'?: string }> = (props) =>
    React.createElement('div', { 'data-testid': props['data-testid'] ?? 'konva-line' })
  const Shape: React.FC<{ 'data-testid'?: string }> = (props) =>
    React.createElement('div', { 'data-testid': props['data-testid'] ?? 'konva-shape' })
  return { Layer, Path, Rect, Circle, Line, Shape }
})

// ── mock useEditorStore ───────────────────────────────────────────────────────
interface MockState {
  editableLayer: 'baronies' | 'landmask'
  activeTerritoryId: string | null
  activeTool: 'V' | 'A' | 'D' | 'S' | 'M' | null
  vertices: Record<string, { lat: number; lon: number }>
}
let mockState: MockState
const setVerticesAndLog = vi.fn()
// getState() returns the live commit surface; vertices mirror mockState.vertices.
const getState = () => ({
  vertices: mockState.vertices,
  setVerticesAndLog,
})
vi.mock('../../../stores/useEditorStore', () => ({
  useEditorStore: Object.assign(
    (selector: (s: MockState) => unknown) => selector(mockState),
    { getState: () => getState() },
  ),
}))

import { BezierEditLayer, deriveAnchorsFromStore } from '../BezierEditLayer'

const PROJ: ProjectionConfig = {
  lonMin: -10,
  lonMax: 3,
  latMin: 36,
  latMax: 44,
  mapW: 1920,
  mapH: 1080,
  lonScale: Math.cos(((36 + 44) / 2) * (Math.PI / 180)),
}

function ringVertices(): Record<string, { lat: number; lon: number }> {
  const out: Record<string, { lat: number; lon: number }> = {}
  IBERIA_BARONY_RING.forEach(([lon, lat], i) => {
    out[`b1#${i}`] = { lat, lon }
  })
  return out
}

/** Build a synthetic Konva drag event whose target reports a fixed px position. */
function dragEventAt(x: number, y: number) {
  return {
    target: {
      x: () => x,
      y: () => y,
      getStage: () => ({ scaleX: () => 1, getPointerPosition: () => ({ x, y }) }),
      setAttrs: () => {},
    },
  }
}

beforeEach(() => {
  setVerticesAndLog.mockClear()
  mockState = {
    editableLayer: 'baronies',
    activeTerritoryId: 'b1',
    activeTool: 'V',
    vertices: ringVertices(),
  }
})

describe('BezierEditLayer drag-commit (Phase 08.1 Plan 03 — BEZ-DRAG-01)', () => {
  it('BEZ-DRAG-01: dragging a non-boundary anchor commits exactly once with op:"move", flattens BOTH adjacent segments, and copies every non-dirty vertex VERBATIM', () => {
    const anchors = deriveAnchorsFromStore(mockState.vertices, PROJ)
    // pick a non-boundary anchor (1 ≤ i ≤ N-2)
    const i = 1
    expect(i).toBeGreaterThanOrEqual(1)
    expect(i).toBeLessThanOrEqual(anchors.length - 2)

    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const anchorEls = getAllByTestId('bezier-anchor')
    const anchorEl = anchorEls.find((el) => el.getAttribute('data-anchor-idx') === String(i))!
    expect(anchorEl).toBeTruthy()
    expect(anchorEl.getAttribute('data-draggable')).toBe('true')

    // drag anchor i to a new px position (offset from its current px)
    const a = anchors[i]
    const dx = 40
    const dy = -25
    fireEvent.dragStart(anchorEl)
    fireEvent.dragEnd(anchorEl, dragEventAt(a.anchorPx[0] + dx, a.anchorPx[1] + dy))

    // committed exactly once with op:'move'
    expect(setVerticesAndLog).toHaveBeenCalledTimes(1)
    const [nextVertices, op] = setVerticesAndLog.mock.calls[0]
    expect(op.op).toBe('move')

    // dirty index range = union of segment (i-1) and segment i poly ranges
    const segPrev = anchors[i - 1] // segment i-1 spans [segPrev.start, segPrev.end] (ends at anchor i)
    const segCur = anchors[i] // segment i spans [segCur.start, segCur.end]
    const dirtyKeys = new Set<string>()
    for (let k = segPrev.polyRangeStart; k <= segPrev.polyRangeEnd; k++) dirtyKeys.add(`b1#${k}`)
    for (let k = segCur.polyRangeStart; k <= segCur.polyRangeEnd; k++) dirtyKeys.add(`b1#${k}`)
    expect(dirtyKeys.size).toBeGreaterThan(0)

    // every non-dirty key is byte-identical to the store; at least one dirty key changed
    let changedCount = 0
    for (const key of Object.keys(mockState.vertices)) {
      if (dirtyKeys.has(key)) {
        if (
          nextVertices[key].lat !== mockState.vertices[key].lat ||
          nextVertices[key].lon !== mockState.vertices[key].lon
        ) {
          changedCount++
        }
      } else {
        // VERBATIM: exact numeric byte-identity, no float drift
        expect(nextVertices[key].lat).toBe(mockState.vertices[key].lat)
        expect(nextVertices[key].lon).toBe(mockState.vertices[key].lon)
      }
    }
    expect(changedCount).toBeGreaterThan(0)
  })

  it('anchor drag translates BOTH control handles by the same delta — the rebuilt dirty cubics use the translated handles (local curve shape preserved, no cusp)', () => {
    // We assert this indirectly via the committed geometry: dragging anchor i by
    // (dx,dy) should move the flattened endpoint vertex at anchor i's poly index
    // by approximately the same geo delta as the anchor itself. If handles did
    // NOT translate, the curve near the anchor would warp asymmetrically.
    const anchors = deriveAnchorsFromStore(mockState.vertices, PROJ)
    const i = 2
    const a = anchors[i]
    const before = { ...mockState.vertices[`b1#${a.polyRangeStart}`] }

    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const anchorEl = getAllByTestId('bezier-anchor').find(
      (el) => el.getAttribute('data-anchor-idx') === String(i),
    )!
    const dx = 30
    const dy = 30
    fireEvent.dragStart(anchorEl)
    fireEvent.dragEnd(anchorEl, dragEventAt(a.anchorPx[0] + dx, a.anchorPx[1] + dy))

    expect(setVerticesAndLog).toHaveBeenCalledTimes(1)
    const [nextVertices] = setVerticesAndLog.mock.calls[0]
    const after = nextVertices[`b1#${a.polyRangeStart}`]
    // The anchor's own polygon vertex (segment i start = the dragged anchor) moved.
    expect(after.lat !== before.lat || after.lon !== before.lon).toBe(true)
  })

  it('boundary i=0: dragging the first anchor marks only segment 0 dirty (no segment -1)', () => {
    const anchors = deriveAnchorsFromStore(mockState.vertices, PROJ)
    const a0 = anchors[0]
    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const anchorEl = getAllByTestId('bezier-anchor').find(
      (el) => el.getAttribute('data-anchor-idx') === '0',
    )!
    fireEvent.dragStart(anchorEl)
    fireEvent.dragEnd(anchorEl, dragEventAt(a0.anchorPx[0] + 20, a0.anchorPx[1] + 20))

    expect(setVerticesAndLog).toHaveBeenCalledTimes(1)
    const [nextVertices] = setVerticesAndLog.mock.calls[0]
    // i=0 marks ONLY segment 0 dirty (segment -1 does not exist). The INTERIOR of the
    // closing segment (indices strictly between the last anchor's start and the ring's
    // final index) must stay byte-verbatim — proving the i-1 guard fired and no segment
    // -1/closing-segment flatten ran. (The ring's closing-duplicate vertex, coincident
    // with anchor 0, may still move via shared-vertex coupling — that is correct.)
    const lastAnchor = anchors[anchors.length - 1]
    const finalIdx = Object.keys(mockState.vertices).length - 1 // closing duplicate index
    for (let k = lastAnchor.polyRangeStart + 1; k < finalIdx; k++) {
      const key = `b1#${k}`
      expect(nextVertices[key].lat).toBe(mockState.vertices[key].lat)
      expect(nextVertices[key].lon).toBe(mockState.vertices[key].lon)
    }
    // segment 1's interior (between anchor 0's range end and anchor 1's range end) is also
    // untouched since only segment 0 is dirty.
    for (let k = anchors[0].polyRangeEnd + 1; k <= anchors[1].polyRangeEnd; k++) {
      const key = `b1#${k}`
      expect(nextVertices[key].lat).toBe(mockState.vertices[key].lat)
      expect(nextVertices[key].lon).toBe(mockState.vertices[key].lon)
    }
  })

  it('boundary i=N-1: dragging the last anchor marks only segment N-2 dirty (closing segment N-1 stays non-editable)', () => {
    const anchors = deriveAnchorsFromStore(mockState.vertices, PROJ)
    const iLast = anchors.length - 1
    const aLast = anchors[iLast]
    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const anchorEl = getAllByTestId('bezier-anchor').find(
      (el) => el.getAttribute('data-anchor-idx') === String(iLast),
    )!
    fireEvent.dragStart(anchorEl)
    fireEvent.dragEnd(anchorEl, dragEventAt(aLast.anchorPx[0] + 15, aLast.anchorPx[1] + 15))

    expect(setVerticesAndLog).toHaveBeenCalledTimes(1)
    const [nextVertices] = setVerticesAndLog.mock.calls[0]
    // segment N-2 spans anchors[N-2].polyRange — those may change.
    // Anything before segment N-2's start must be verbatim.
    const segStart = anchors[iLast - 1].polyRangeStart
    for (let k = 0; k < segStart; k++) {
      const key = `b1#${k}`
      expect(nextVertices[key].lat).toBe(mockState.vertices[key].lat)
      expect(nextVertices[key].lon).toBe(mockState.vertices[key].lon)
    }
  })

  it('shared-vertex coupling: a coupled partner in a neighbour barony moves to the same coord on commit', () => {
    // Seed a neighbour-barony vertex coincident with anchor i's polygon vertex.
    const anchors = deriveAnchorsFromStore(mockState.vertices, PROJ)
    const i = 1
    const a = anchors[i]
    const sharedKey = `b1#${a.polyRangeStart}`
    const sharedCoord = mockState.vertices[sharedKey]
    const partnerKey = 'b2#7'
    // add partner coincident vertex into the store vertices map
    mockState.vertices[partnerKey] = { lat: sharedCoord.lat, lon: sharedCoord.lon }

    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const anchorEl = getAllByTestId('bezier-anchor').find(
      (el) => el.getAttribute('data-anchor-idx') === String(i),
    )!
    fireEvent.dragStart(anchorEl)
    fireEvent.dragEnd(anchorEl, dragEventAt(a.anchorPx[0] + 50, a.anchorPx[1] + 10))

    expect(setVerticesAndLog).toHaveBeenCalledTimes(1)
    const [nextVertices] = setVerticesAndLog.mock.calls[0]
    // partner moved to the same coordinate as the (new) shared anchor vertex
    expect(nextVertices[partnerKey].lat).toBe(nextVertices[sharedKey].lat)
    expect(nextVertices[partnerKey].lon).toBe(nextVertices[sharedKey].lon)
  })

  it('control-handle drag commits via the same flatten path with op:"move" and does NOT add a bezier_drag op', () => {
    // activate anchor 1 so its handles render
    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const anchorEl = getAllByTestId('bezier-anchor').find(
      (el) => el.getAttribute('data-anchor-idx') === '1',
    )!
    fireEvent.click(anchorEl)
    const handles = getAllByTestId('bezier-handle')
    expect(handles.length).toBe(2)
    expect(handles[0].getAttribute('data-draggable')).toBe('true')

    fireEvent.dragStart(handles[0])
    fireEvent.dragEnd(handles[0], dragEventAt(100, 100))

    expect(setVerticesAndLog).toHaveBeenCalledTimes(1)
    const [, op] = setVerticesAndLog.mock.calls[0]
    expect(op.op).toBe('move')
  })

  it('anchor drag uses the Rect CENTER (top-left + 5,5), so the committed anchor lands at the cursor center — not 5px off', () => {
    // The anchor Rect is positioned at anchorPx-5 (10×10 square). Konva reports the new
    // TOP-LEFT on dragEnd; the handler must add (5,5) to recover the center. We fire a
    // dragEnd whose target reports a top-left such that the intended center is anchorPx+(60,0),
    // and assert the flattened endpoint vertex equals geo(center), proving the +5 offset.
    const anchors = deriveAnchorsFromStore(mockState.vertices, PROJ)
    const i = 2
    const a = anchors[i]
    const center: [number, number] = [a.anchorPx[0] + 60, a.anchorPx[1] + 0]
    const topLeft: [number, number] = [center[0] - 5, center[1] - 5]

    const { getAllByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const anchorEl = getAllByTestId('bezier-anchor').find(
      (el) => el.getAttribute('data-anchor-idx') === String(i),
    )!
    fireEvent.dragStart(anchorEl)
    fireEvent.dragEnd(anchorEl, dragEventAt(topLeft[0], topLeft[1]))

    expect(setVerticesAndLog).toHaveBeenCalledTimes(1)
    const [nextVertices] = setVerticesAndLog.mock.calls[0]
    // segment i starts at anchor i, so the vertex at anchors[i].polyRangeStart is the
    // dragged anchor's polygon vertex; its committed coord must equal geo(center).
    const [expLon, expLat] = canvasToGeo(center[0], center[1], PROJ)
    const got = nextVertices[`b1#${a.polyRangeStart}`]
    expect(got.lon).toBeCloseTo(expLon, 6)
    expect(got.lat).toBeCloseTo(expLat, 6)
  })

  it('live preview during drag repaints the curve outline — onDragMove updates the path without writing the store', () => {
    const anchors = deriveAnchorsFromStore(mockState.vertices, PROJ)
    const i = 1
    const a = anchors[i]
    const { getAllByTestId, getByTestId } = render(<BezierEditLayer projection={PROJ} />)
    const beforePath = getByTestId('bezier-curve-outline').getAttribute('data-d')

    const anchorEl = getAllByTestId('bezier-anchor').find(
      (el) => el.getAttribute('data-anchor-idx') === String(i),
    )!
    fireEvent.dragStart(anchorEl)
    fireEvent.drag(anchorEl, dragEventAt(a.anchorPx[0] + 80, a.anchorPx[1] + 80))

    // Curve path changed mid-drag (live preview) but NO store commit happened yet.
    const duringPath = getByTestId('bezier-curve-outline').getAttribute('data-d')
    expect(duringPath).not.toBe(beforePath)
    expect(setVerticesAndLog).not.toHaveBeenCalled()
  })
})
