/**
 * Phase 08.3 Plan 11 — Task 2 TDD
 * PenShapeManipulateLayer: body-drag + vertex-drag write op.ring on gesture-end.
 *
 * Follows the PenDrawLayer.test.tsx pattern:
 *   - react-konva mocked (jsdom has no canvas)
 *   - useEditorStore.setState drives test setup
 *   - Gesture-end writes NEW editLog array ref with manipulated ring (FACT 6a)
 *   - No store write mid-gesture (FACT 6b)
 *   - Esc discards (reverts to committed ring)
 *
 * Drag implementation (UAT fix — 08.3-11 debug session):
 *   Component now uses Konva `draggable` with onDragStart/onDragMove/onDragEnd.
 *   jsdom has no Konva Stage, so the mock forwards onDragStart/Move/End as DOM
 *   attributes and tests fire them via fireEvent with clientX/Y carrying canvas-space
 *   coordinates (same geoPxToEvent helper as before).
 *
 *   Body drag: onDragStart records start canvas-px; onDragEnd computes delta = end - start.
 *   Vertex drag: onDragEnd clientX/Y = new absolute canvas-space position.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import React from 'react'
import { translateRing, moveRingVertex } from '../../../lib/penShapeManipulate'
import type { ProjectionConfig } from '../../../lib/projection'
import { geoToCanvas } from '../../../lib/projection'

// ── mock react-konva ──────────────────────────────────────────────────────────
vi.mock('react-konva', () => {
  const React = require('react')

  const makeNode = (defaultTestId: string) => {
    const Comp: React.FC<Record<string, unknown>> = (props) => {
      const domProps: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(props)) {
        if (
          k.startsWith('data-') ||
          k === 'onClick' ||
          k === 'onMouseDown' ||
          k === 'onMouseMove' ||
          k === 'onMouseUp' ||
          k === 'onDragStart' ||
          k === 'onDragMove' ||
          k === 'onDragEnd' ||
          k === 'name' ||
          k === 'children'
        ) {
          domProps[k] = v
        }
      }
      domProps['data-testid'] = (props['data-testid'] as string | undefined) ?? defaultTestId
      return React.createElement('div', domProps, props['children'])
    }
    return Comp
  }

  const Layer: React.FC<{ children?: React.ReactNode; name?: string; [k: string]: unknown }> = ({
    children,
    name,
    ...rest
  }) =>
    React.createElement(
      'div',
      { 'data-testid': 'konva-layer', 'data-name': name, ...rest },
      children,
    )

  return {
    Layer,
    Line: makeNode('konva-line'),
    Circle: makeNode('konva-circle'),
    Rect: makeNode('konva-rect'),
  }
})

// ── useEditorStore mock ───────────────────────────────────────────────────────

let mockEditLog: import('../../../stores/useEditorStore').EditOp[] = []

const mockSetState = vi.fn((update: unknown) => {
  if (typeof update === 'function') {
    const next = update({ editLog: mockEditLog })
    if (next.editLog !== undefined) mockEditLog = next.editLog
  } else if (update && typeof update === 'object' && 'editLog' in (update as object)) {
    mockEditLog = (update as { editLog: import('../../../stores/useEditorStore').EditOp[] }).editLog
  }
})

const mockGetState = vi.fn(() => ({ editLog: mockEditLog }))

vi.mock('../../../stores/useEditorStore', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  const storeSelector = (selector: (s: unknown) => unknown) =>
    selector({ editLog: mockEditLog })
  ;(storeSelector as unknown as Record<string, unknown>).getState = mockGetState
  ;(storeSelector as unknown as Record<string, unknown>).setState = mockSetState
  return { ...(actual ?? {}), useEditorStore: storeSelector }
})

// ── projection fixture ────────────────────────────────────────────────────────
// Same projection as PenDrawLayer.test.tsx for consistency.
const PROJECTION: ProjectionConfig = {
  lonMin: -10,
  lonMax: 10,
  latMin: 30,
  latMax: 50,
  mapW: 1000,
  mapH: 1000,
  lonScale: Math.cos((40 * Math.PI) / 180),
}

// ── ring fixtures ─────────────────────────────────────────────────────────────
// A closed ring in geo space
const BASE_RING: Array<{ lat: number; lon: number }> = [
  { lat: 40, lon: -5 },
  { lat: 40, lon: -3 },
  { lat: 42, lon: -3 },
  { lat: 40, lon: -5 }, // closing duplicate
]

const CREATE_OP: import('../../../stores/useEditorStore').EditOp = {
  op: 'create',
  ts: 1000,
  ring: BASE_RING,
  allocated_original_idx: null,
  barony_meta: { name: 'TestBarony', condado_idx: 1, duchy_id: 'd1', kingdom_id: 'k1', country: 'PT' },
}

const CARVE_OP: import('../../../stores/useEditorStore').EditOp = {
  op: 'carve',
  ts: 2000,
  ring: BASE_RING,
  allocated_original_idx: null,
  barony_meta: { name: 'CarveBarony', condado_idx: 2, duchy_id: 'd1', kingdom_id: 'k1', country: 'ES' },
}

// ── helpers ───────────────────────────────────────────────────────────────────

function resetMocks() {
  mockSetState.mockClear()
  mockGetState.mockClear()
  mockEditLog = []
  mockGetState.mockImplementation(() => ({ editLog: mockEditLog }))
}

let PenShapeManipulateLayer: typeof import('../PenShapeManipulateLayer').PenShapeManipulateLayer

beforeEach(async () => {
  resetMocks()
  vi.resetModules()
  const mod = await import('../PenShapeManipulateLayer')
  PenShapeManipulateLayer = mod.PenShapeManipulateLayer
})

// ── helper: geo point → canvas-px clientX/clientY ─────────────────────────────
function geoPxToEvent(lat: number, lon: number): { clientX: number; clientY: number } {
  const [x, y] = geoToCanvas(lon, lat, PROJECTION)
  return { clientX: x, clientY: y }
}

// ── tests ─────────────────────────────────────────────────────────────────────

describe('PenShapeManipulateLayer', () => {
  // ── T1: inert when no pending create/carve op ─────────────────────────────
  it('T1: layer is inert (renders nothing) when editLog is empty (zero-edit path safety)', async () => {
    mockEditLog = []
    mockGetState.mockImplementation(() => ({ editLog: [] }))
    const { container } = render(
      <PenShapeManipulateLayer projection={PROJECTION} currentScale={1} />,
    )
    // No interactive elements rendered (only the outer wrapper)
    const lines = container.querySelectorAll('[data-testid="konva-line"]')
    const circles = container.querySelectorAll('[data-testid="konva-circle"]')
    const rects = container.querySelectorAll('[data-testid="konva-rect"]')
    expect(lines.length + circles.length + rects.length).toBe(0)
  })

  // ── T2: body-drag writes translateRing(op.ring) as NEW editLog array ref ──
  it('T2: commitTranslate writes a translated op.ring as a NEW editLog array ref on gesture-end (FACT 6a)', async () => {
    mockEditLog = [CREATE_OP]
    // Disable the mockSetState auto-mutation so originalLogRef stays stable
    // and we can compare it with the written value after the gesture.
    const capturedSets: unknown[] = []
    mockSetState.mockImplementation((update: unknown) => { capturedSets.push(update) })
    // Capture the original array reference BEFORE the gesture
    const originalLogRef = mockEditLog

    const { getByTestId } = render(
      <PenShapeManipulateLayer projection={PROJECTION} currentScale={1} />,
    )

    // Find the body shape element
    const bodyEl = getByTestId('pen-manipulate-body')

    // Simulate a body drag using onDragStart + onDragEnd.
    // jsdom fallback: clientX/Y carry canvas-space coordinates.
    // Start at ring[0] canvas position, end at +1 lat, +2 lon.
    const startPt = geoPxToEvent(40, -5)
    const endPt = geoPxToEvent(41, -3) // +1 lat, +2 lon

    fireEvent(bodyEl, new MouseEvent('dragstart', { bubbles: true, ...startPt }))
    fireEvent(bodyEl, new MouseEvent('dragend', { bubbles: true, ...endPt }))

    // setState must have been called exactly once (one undo entry — FACT 6b)
    expect(capturedSets).toHaveLength(1)

    // Extract the new editLog from the setState call argument
    const callArg = capturedSets[0] as Record<string, unknown>
    // commitRing uses setState({ editLog: log.map(...) }) — direct object, not function
    const newLog = callArg.editLog as typeof mockEditLog

    // The editLog must be a NEW reference (not the same array — FACT 6a)
    expect(newLog).not.toBe(originalLogRef)
    expect(newLog).toHaveLength(1)

    // Ring was translated: compare lat/lon approximately
    const newRing = newLog[0].ring as Array<{ lat: number; lon: number }>
    const dLat = newRing[0].lat - BASE_RING[0].lat
    const dLon = newRing[0].lon - BASE_RING[0].lon
    // dLat/dLon must be non-trivial (we dragged a real distance)
    expect(Math.abs(dLat) + Math.abs(dLon)).toBeGreaterThan(0.01)
    // All points shifted by the same delta
    for (let i = 0; i < BASE_RING.length; i++) {
      expect(newRing[i].lat).toBeCloseTo(BASE_RING[i].lat + dLat, 4)
      expect(newRing[i].lon).toBeCloseTo(BASE_RING[i].lon + dLon, 4)
    }
    // Closed-ring invariant preserved
    expect(newRing[0]).toEqual(newRing[newRing.length - 1])
  })

  // ── T3: vertex-drag writes moveRingVertex(op.ring) on gesture-end ─────────
  it('T3: commitVertexMove writes a single-vertex-edited op.ring on gesture-end', async () => {
    mockEditLog = [CREATE_OP]
    mockGetState.mockImplementation(() => ({ editLog: mockEditLog }))

    const { getAllByTestId } = render(
      <PenShapeManipulateLayer projection={PROJECTION} currentScale={1} />,
    )

    // Vertex handles: there are N-1 handles (closing duplicate is dropped from handle set)
    const handles = getAllByTestId('pen-manipulate-vertex')
    expect(handles.length).toBeGreaterThanOrEqual(1)

    // Drag first vertex handle (index 0) to a new position.
    // onDragEnd clientX/Y = new absolute canvas-space position.
    const newPos = geoPxToEvent(39, -6) // move vertex 0 to lat=39, lon=-6
    fireEvent(handles[0], new MouseEvent('dragstart', { bubbles: true, ...geoPxToEvent(BASE_RING[0].lat, BASE_RING[0].lon) }))
    fireEvent(handles[0], new MouseEvent('dragend', { bubbles: true, ...newPos }))

    expect(mockSetState).toHaveBeenCalledTimes(1)

    const callArg = mockSetState.mock.calls[0][0]
    const newLog = typeof callArg === 'function'
      ? callArg({ editLog: [CREATE_OP] }).editLog
      : callArg.editLog

    const newRing = newLog[0].ring as Array<{ lat: number; lon: number }>
    // vertex[1] and vertex[2] must remain unchanged
    expect(newRing[1].lat).toBeCloseTo(BASE_RING[1].lat, 4)
    expect(newRing[2].lat).toBeCloseTo(BASE_RING[2].lat, 4)
    // Closed-ring invariant: if index 0 was moved, last should also match
    expect(newRing[0]).toEqual(newRing[newRing.length - 1])
  })

  // ── T4: no store write during mid-gesture (one undo entry only) ───────────
  it('T4: in-progress drag does NOT write the store until gesture-end (one undo entry, FACT 6b)', async () => {
    mockEditLog = [CREATE_OP]
    mockGetState.mockImplementation(() => ({ editLog: mockEditLog }))

    const { getByTestId } = render(
      <PenShapeManipulateLayer projection={PROJECTION} currentScale={1} />,
    )

    const bodyEl = getByTestId('pen-manipulate-body')
    const start = geoPxToEvent(40, -5)

    fireEvent(bodyEl, new MouseEvent('dragstart', { bubbles: true, ...start }))
    // Multiple dragmove events mid-gesture — no store write expected
    fireEvent(bodyEl, new MouseEvent('dragmove', { bubbles: true, ...geoPxToEvent(40.5, -4.5) }))
    fireEvent(bodyEl, new MouseEvent('dragmove', { bubbles: true, ...geoPxToEvent(41, -4) }))

    // NO store write yet
    expect(mockSetState).not.toHaveBeenCalled()

    // Release — now one write
    fireEvent(bodyEl, new MouseEvent('dragend', { bubbles: true, ...geoPxToEvent(41, -4) }))
    expect(mockSetState).toHaveBeenCalledTimes(1)
  })

  // ── T5: Esc during drag discards manipulation (no store write) ────────────
  it('T5: Esc/cancel discards in-progress manipulation and does not write the store', async () => {
    mockEditLog = [CREATE_OP]
    mockGetState.mockImplementation(() => ({ editLog: mockEditLog }))

    const { getByTestId } = render(
      <PenShapeManipulateLayer projection={PROJECTION} currentScale={1} />,
    )

    const bodyEl = getByTestId('pen-manipulate-body')
    fireEvent(bodyEl, new MouseEvent('dragstart', { bubbles: true, ...geoPxToEvent(40, -5) }))
    fireEvent(bodyEl, new MouseEvent('dragmove', { bubbles: true, ...geoPxToEvent(41, -4) }))

    // Fire Esc — should discard and set dragCancelledRef
    fireEvent.keyDown(window, { key: 'Escape', bubbles: true, cancelable: true })

    // Should NOT have written to store
    expect(mockSetState).not.toHaveBeenCalled()

    // CRITICAL: Konva fires dragEnd even after Esc.  The component must NOT commit
    // on this subsequent dragEnd (dragCancelledRef gates it — FACT 6b).
    fireEvent(bodyEl, new MouseEvent('dragend', { bubbles: true, ...geoPxToEvent(41, -4) }))
    expect(mockSetState).not.toHaveBeenCalled()
  })

  // ── T6: carve op behaves identically to create op (FACT 4 symmetry) ───────
  it('T6: works identically for a carve pending op (CREATE/CARVE symmetry, FACT 4)', async () => {
    mockEditLog = [CARVE_OP]
    mockGetState.mockImplementation(() => ({ editLog: mockEditLog }))

    const { getByTestId } = render(
      <PenShapeManipulateLayer projection={PROJECTION} currentScale={1} />,
    )

    const bodyEl = getByTestId('pen-manipulate-body')
    const start = geoPxToEvent(40, -5)
    const end = geoPxToEvent(41, -4)

    fireEvent(bodyEl, new MouseEvent('dragstart', { bubbles: true, ...start }))
    fireEvent(bodyEl, new MouseEvent('dragend', { bubbles: true, ...end }))

    expect(mockSetState).toHaveBeenCalledTimes(1)

    const callArg = mockSetState.mock.calls[0][0]
    const newLog = typeof callArg === 'function'
      ? callArg({ editLog: [CARVE_OP] }).editLog
      : callArg.editLog

    // The op type must still be 'carve'
    expect(newLog[0].op).toBe('carve')
    // The ring was translated
    const newRing = newLog[0].ring as Array<{ lat: number; lon: number }>
    expect(newRing).not.toBe(BASE_RING)
  })
})
