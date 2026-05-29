/**
 * Phase 08.1 Plan 06 — BezierEditLayer insert-anchor tests (Task 2).
 *
 * Covers G3: double-click on the curve outline inserts an anchor as a PURE
 * component-local NO-OP (zero setVerticesAndLog calls, store byte-identical),
 * and a subsequent drag via the existing op:'move' path commits the first mutation.
 *
 * Pattern mirrors useEditorStore.bezierIdentity.test.ts: the REAL store is used
 * (not mocked) so identity assertions are meaningful. react-konva is mocked (jsdom
 * has no canvas). The __forgeBezierTriggerInsert DEV hook is used to drive the
 * insert handler via an index (not page coords) — matching the plan's index-based
 * convention.
 *
 * ANTI-PATTERN GUARD: tests MUST NOT call setVerticesAndLog / setAnchors directly.
 * Everything flows through the real handler path via DEV hooks.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act } from '@testing-library/react'
import React from 'react'
import { IBERIA_BARONY_RING } from '../__fixtures__/iberiaBaronyRing'
import type { ProjectionConfig } from '../../../lib/projection'

// react-konva must be mocked — jsdom has no canvas.
vi.mock('react-konva', () => {
  const React = require('react')
  const passthrough =
    (testid: string): React.FC<{ children?: React.ReactNode; [k: string]: unknown }> =>
    ({ children, ...props }) =>
      React.createElement('div', { 'data-testid': testid, ...props }, children)
  return {
    Layer: passthrough('konva-layer'),
    Path: (props: Record<string, unknown>) =>
      React.createElement('div', {
        'data-testid': props['data-testid'] ?? 'konva-path',
        'data-d': props['data'],
        onClick: props['onClick'],
        onDoubleClick: props['onDblClick'],
        ...props,
      }),
    Rect: passthrough('konva-rect'),
    Circle: passthrough('konva-circle'),
    Line: passthrough('konva-line'),
  }
})

// REAL store + REAL component (no vi.mock of useEditorStore here).
import { useEditorStore } from '../../../stores/useEditorStore'
import type { VertexCoord } from '../../../stores/useEditorStore'
import { BezierEditLayer } from '../BezierEditLayer'

const PROJ: ProjectionConfig = {
  lonMin: -10,
  lonMax: 3,
  latMin: 36,
  latMax: 44,
  mapW: 1920,
  mapH: 1080,
  lonScale: Math.cos(((36 + 44) / 2) * (Math.PI / 180)),
}

/** Known polygon ring keyed b1#0..b1#N from the real Iberia barony fixture. */
function ringVertices(): Record<string, VertexCoord> {
  const out: Record<string, VertexCoord> = {}
  IBERIA_BARONY_RING.forEach(([lon, lat], i) => {
    out[`b1#${i}`] = { lat, lon }
  })
  return out
}

beforeEach(() => {
  // Reset the real store to a clean, deterministic Bézier-edit-ready state.
  const t = useEditorStore.temporal.getState()
  t.pause()
  useEditorStore.setState({
    editableLayer: 'baronies',
    activeTerritoryId: 'b1',
    activeTool: 'V',
    vertices: ringVertices(),
    editLog: [],
  })
  t.clear()
  t.resume()
})

describe('G3 insert-anchor — identity-safe NO-OP insert (08.1-06 Task 2)', () => {
  it('__forgeBezierTriggerInsert is registered on window in DEV mode after mount', () => {
    render(React.createElement(BezierEditLayer, { projection: PROJ }))
    expect(typeof (window as unknown as { __forgeBezierTriggerInsert?: unknown }).__forgeBezierTriggerInsert).toBe('function')
  })

  it('insert-without-drag: store.vertices byte-identical after __forgeBezierTriggerInsert(0)', () => {
    render(React.createElement(BezierEditLayer, { projection: PROJ }))

    const beforeStr = JSON.stringify(useEditorStore.getState().vertices)
    const beforeLen = useEditorStore.getState().editLog.length

    const fn = (window as unknown as { __forgeBezierTriggerInsert?: (s?: number) => boolean }).__forgeBezierTriggerInsert
    // The hook may return false if no segment 0 has a strictly-interior vertex (degenerate);
    // if it returns true the identity assertions MUST hold.
    const inserted = fn ? fn(0) : false

    if (inserted) {
      // PRIMARY ASSERTION: store byte-identical (identity-safe insert)
      expect(JSON.stringify(useEditorStore.getState().vertices)).toBe(beforeStr)
      expect(useEditorStore.getState().editLog.length).toBe(beforeLen)
    }
    // If inserted===false the segment had no interior vertex — acceptable for this fixture.
  })

  it('insert-without-drag: editLog length unchanged (no phantom commit)', () => {
    render(React.createElement(BezierEditLayer, { projection: PROJ }))

    const beforeLen = useEditorStore.getState().editLog.length
    const fn = (window as unknown as { __forgeBezierTriggerInsert?: (s?: number) => boolean }).__forgeBezierTriggerInsert
    if (fn) fn(0)
    // editLog must not grow on bare insert regardless of whether segment had interior vertex
    expect(useEditorStore.getState().editLog.length).toBe(beforeLen)
  })

  it('BEZ-IDENTITY-01 extended: insert-without-drag leaves vertices byte-identical AND editLog unchanged', () => {
    // This is the explicit extension of the BEZ-IDENTITY-01 contract from Plan 02.
    // Previously the contract covered mount+unmount. Now it covers mount+insert+no-drag.
    const beforeStr = JSON.stringify(useEditorStore.getState().vertices)
    const beforeLogLen = useEditorStore.getState().editLog.length

    render(React.createElement(BezierEditLayer, { projection: PROJ }))

    const fn = (window as unknown as { __forgeBezierTriggerInsert?: (s?: number) => boolean }).__forgeBezierTriggerInsert
    fn?.(0)

    expect(JSON.stringify(useEditorStore.getState().vertices)).toBe(beforeStr)
    expect(useEditorStore.getState().editLog.length).toBe(beforeLogLen)
  })
})

describe('G3 insert-anchor — range split correctness (08.1-06 Task 2)', () => {
  it('after insert, __forgeBezierState reports anchorCount increased by 1', async () => {
    render(React.createElement(BezierEditLayer, { projection: PROJ }))

    // Read beforeCount from window BEFORE insert (fresh hook reference)
    const readState = () => (window as unknown as { __forgeBezierState?: () => { anchorCount: number; activeAnchorIdx: number | null } }).__forgeBezierState?.()
    const beforeCount = readState()?.anchorCount ?? 0

    const insertFn = (window as unknown as { __forgeBezierTriggerInsert?: (s?: number) => boolean }).__forgeBezierTriggerInsert
    let inserted = false
    // act() flushes React state updates so anchorCount reflects the setAnchors call;
    // re-read window.__forgeBezierState AFTER act so we get the post-render closure.
    await act(async () => {
      inserted = insertFn ? insertFn(0) : false
    })

    // IBERIA_BARONY_RING segment 0 always has strictly-interior vertices (rangeEnd-rangeStart>=2);
    // Playwright confirms this on the real seeded data. Assert unconditionally so this test
    // cannot silently pass as a vacuous no-op.
    expect(inserted, 'segment 0 of Iberia barony must have a strictly-interior vertex (non-degenerate)').toBe(true)
    // Re-read from window after act — the useEffect re-registered the hook with the new anchor count
    const after = readState()
    expect(after?.anchorCount).toBe(beforeCount + 1)
  })
})

describe('G3 insert-then-drag commits via op:move (08.1-06 Task 2)', () => {
  it('drag after insert: editLog grows (first store mutation on drag, not on insert)', async () => {
    render(React.createElement(BezierEditLayer, { projection: PROJ }))

    const beforeLen = useEditorStore.getState().editLog.length

    const insertFn = (window as unknown as { __forgeBezierTriggerInsert?: (s?: number) => boolean }).__forgeBezierTriggerInsert
    let inserted = false
    // act() flushes React state updates (setAnchors + setActiveAnchorIdx)
    await act(async () => {
      inserted = insertFn ? insertFn(0) : false
    })

    // Unconditional: segment 0 of IBERIA_BARONY_RING always has interior vertices (Playwright confirmed).
    expect(inserted, 'segment 0 of Iberia barony must be insertable (non-degenerate)').toBe(true)

    // Store must still be unchanged after insert (identity-safe)
    expect(useEditorStore.getState().editLog.length).toBe(beforeLen)

    // Now drag the newly inserted anchor (it becomes activeAnchorIdx after insert)
    const stateFn = (window as unknown as { __forgeBezierState?: () => { anchorCount: number; activeAnchorIdx: number | null } }).__forgeBezierState
    const newIdx = stateFn?.()?.activeAnchorIdx

    expect(newIdx, 'inserted anchor must become the activeAnchorIdx').not.toBeNull()

    const dragFn = (window as unknown as { __forgeBezierTriggerDrag?: (idx?: number, dx?: number, dy?: number) => boolean }).__forgeBezierTriggerDrag
    expect(dragFn, '__forgeBezierTriggerDrag must be registered').toBeDefined()
    act(() => { dragFn!(newIdx!, 25, 25) })
    // First commit happens HERE (drag-after-insert) — store only writes on drag, never on insert
    expect(useEditorStore.getState().editLog.length).toBeGreaterThan(beforeLen)
    const lastEntry = useEditorStore.getState().editLog[useEditorStore.getState().editLog.length - 1]
    expect(lastEntry.op).toBe('move')
    expect(lastEntry.vertexIds.length).toBeGreaterThan(0)
  })
})

describe('G3 visible-outline listening contract (08.1-06 Task 2 — WARNING-2 pin)', () => {
  it('the bezier-hit-path element is rendered (separate from bezier-curve-outline)', () => {
    const { queryByTestId } = render(React.createElement(BezierEditLayer, { projection: PROJ }))
    // Both paths must exist: the non-interactive outline and the dedicated hit-Path
    expect(queryByTestId('bezier-curve-outline')).not.toBeNull()
    expect(queryByTestId('bezier-hit-path')).not.toBeNull()
  })

  it('bezier-curve-outline and bezier-hit-path are DISTINCT elements', () => {
    const { getAllByTestId } = render(React.createElement(BezierEditLayer, { projection: PROJ }))
    const outlines = getAllByTestId('bezier-curve-outline')
    const hits = getAllByTestId('bezier-hit-path')
    // They must be different DOM nodes
    expect(outlines[0]).not.toBe(hits[0])
  })
})
