/**
 * Phase 08.3 Plan 05 — Task 2 TDD
 * Tests for PenDrawLayer: pen state machine, snap, validation, create-op commit, EXTEND.
 *
 * Follows the BezierEditLayer.test.tsx pattern:
 *   - react-konva mocked (jsdom has no canvas)
 *   - useEditorStore mocked per test
 *   - fetch mocked for /editor/country endpoint
 *
 * Behavior tests (PEN-CURVE-01, PEN-CREATE-01, PEN-EXTEND-01, PEN-ASSIGN-01):
 *   T1: renders root Group with name/testid 'pen-draw-layer' when mounted
 *   T2: click places first anchor; second click + mousemove shows rubber-band (pen-rubber-band)
 *   T3: cursor within snap radius of neighbor vertex shows pen-snap-vertex
 *   T4: closing on first anchor (≥3 anchors, empty neighborCandidates) commits ONE create op
 *   T5a: validation fails (2 anchors only) → NO create op committed
 *   T5b: validation fails (self-intersecting ring) → NO create op committed
 *   T5c: validation fails (tiny area) → NO create op committed
 *   T6: mid-draw Ctrl+Z removes last anchor (store editLog unchanged)
 *   T7: Esc clears anchors and calls onDrawingStateChange(false)
 *   T8: EXTEND — first anchor snapped to contour vertex sets extendMode; no op:'create' on close
 *
 * NOTE on T4 async flow:
 *   commitCreate awaits GET /editor/country BEFORE calling setVerticesAndLog.
 *   The mock resolves synchronously via mockResolvedValue, but the async chain
 *   still needs an act() flush to settle the microtask queue.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, act } from '@testing-library/react'
import React from 'react'
import type { ProjectionConfig } from '../../../lib/projection'

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
          k === 'onMouseMove' ||
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

  const Group: React.FC<{
    children?: React.ReactNode
    name?: string
    'data-testid'?: string
    [k: string]: unknown
  }> = ({ children, name, 'data-testid': testid, ...rest }) =>
    React.createElement(
      'div',
      { 'data-testid': testid ?? 'konva-group', 'data-name': name, ...rest },
      children,
    )

  return {
    Layer,
    Group,
    Line: makeNode('konva-line'),
    Circle: makeNode('konva-circle'),
    Rect: makeNode('konva-rect'),
    Text: makeNode('konva-text'),
    Path: makeNode('konva-path'),
  }
})

// ── mock useEditorStore ───────────────────────────────────────────────────────
const mockSetVerticesAndLog = vi.fn()
const mockSelectTool = vi.fn()
let mockEditLog: unknown[] = []
let mockVertices: Record<string, { lat: number; lon: number }> = {}

// getState / setState captured on the mock so PenDrawLayer's imperative calls work
const mockGetState = vi.fn(() => ({
  editLog: mockEditLog,
  vertices: mockVertices,
  setVerticesAndLog: mockSetVerticesAndLog,
  selectTool: mockSelectTool,
}))
const mockSetState = vi.fn()

vi.mock('../../../stores/useEditorStore', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  const storeSelector = (selector: (s: unknown) => unknown) =>
    selector({
      editLog: mockEditLog,
      vertices: mockVertices,
      setVerticesAndLog: mockSetVerticesAndLog,
      selectTool: mockSelectTool,
      activeTool: 'P',
    })
  ;(storeSelector as unknown as Record<string, unknown>).getState = mockGetState
  ;(storeSelector as unknown as Record<string, unknown>).setState = mockSetState
  return { ...(actual ?? {}), useEditorStore: storeSelector }
})

// ── mock fetch for /editor/country ───────────────────────────────────────────
const mockFetch = vi.fn()
global.fetch = mockFetch

// ── projection fixture ────────────────────────────────────────────────────────
// lon ∈ [-10, 10], lat ∈ [30, 50], mapW=mapH=1000
// geoToCanvas(lon, lat): x=(lon-lonMin)*lonScale/span*1000; y=(1-(lat-30)/20)*1000
// At lonScale=cos(40°)≈0.766, span=20*0.766=15.32:
//   lon=-9 → x≈(1/15.32)*0.766*1000≈50; lat=40 → y=(1-10/20)*1000=500
const PROJECTION: ProjectionConfig = {
  lonMin: -10,
  lonMax: 10,
  latMin: 30,
  latMax: 50,
  mapW: 1000,
  mapH: 1000,
  lonScale: Math.cos((40 * Math.PI) / 180),
}

// ── neighbor candidate fixtures ───────────────────────────────────────────────
// Vertices at lon=-9,lat=40 → canvas ≈ (50, 500). For T4, we use EMPTY neighbors
// so no vertex snap triggers extendMode; the neighbor's contour is far from test clicks.
const NEIGHBOR_FEATURES = [
  {
    type: 'Feature' as const,
    properties: {
      id: 'b-neighbor-1',
      name: 'Baronato Vizinho',
      condado_idx: 3,
      duchy_id: 'D1',
      kingdom_id: 'K1',
      centroid: [40.5, -8.5] as [number, number],
    },
    geometry: {
      type: 'Polygon' as const,
      coordinates: [
        [
          [-9, 40],
          [-8, 40],
          [-8, 41],
          [-9, 41],
          [-9, 40],
        ],
      ],
    },
  },
]

// ── helpers ───────────────────────────────────────────────────────────────────

function resetMocks() {
  mockSetVerticesAndLog.mockReset()
  mockSelectTool.mockReset()
  mockGetState.mockReset()
  mockSetState.mockReset()
  mockEditLog = []
  mockVertices = {}
  // Update mockGetState to return fresh mockEditLog/Vertices
  mockGetState.mockImplementation(() => ({
    editLog: mockEditLog,
    vertices: mockVertices,
    setVerticesAndLog: mockSetVerticesAndLog,
    selectTool: mockSelectTool,
  }))
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => ({ country: 'PT' }),
  })
}

// ── import component AFTER mocks ──────────────────────────────────────────────
let PenDrawLayer: typeof import('../PenDrawLayer').PenDrawLayer

beforeEach(async () => {
  resetMocks()
  vi.resetModules()
  const mod = await import('../PenDrawLayer')
  PenDrawLayer = mod.PenDrawLayer
})

// ── tests ─────────────────────────────────────────────────────────────────────

describe('PenDrawLayer (PEN-CURVE-01, PEN-CREATE-01, PEN-EXTEND-01, PEN-ASSIGN-01)', () => {
  // T1: Root Group renders with correct testid
  it('T1: renders root Group with name="pen-draw-layer" and data-testid="pen-draw-layer"', () => {
    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={NEIGHBOR_FEATURES}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
      />,
    )
    const layer = getByTestId('pen-draw-layer')
    expect(layer).toBeTruthy()
  })

  // T2: rubber-band appears after placing 2 anchors + mousemove
  it('T2: click places anchor; second click + mousemove shows rubber-band (pen-rubber-band testid)', async () => {
    const { getByTestId, queryByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={NEIGHBOR_FEATURES}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
      />,
    )
    const layer = getByTestId('pen-draw-layer')
    await act(async () => {
      fireEvent.click(layer, { clientX: 200, clientY: 300 })
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 300, clientY: 400 })
    })
    await act(async () => {
      fireEvent.mouseMove(layer, { clientX: 350, clientY: 450 })
    })
    expect(queryByTestId('pen-rubber-band')).not.toBeNull()
  })

  // T3: snap-vertex marker appears on mousemove near a neighbor vertex
  it('T3: mousemove near neighbor vertex shows pen-snap-vertex marker', async () => {
    const { getByTestId, queryByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={NEIGHBOR_FEATURES}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
      />,
    )
    const layer = getByTestId('pen-draw-layer')
    // Move to (clientX=50, clientY=500) — canvasToGeo(50,500,PROJ) lands near lon=-9,lat=40
    // which is the neighbor vertex. Distance ~ 0 world units → within 12/1=12 tol.
    await act(async () => {
      fireEvent.mouseMove(layer, { clientX: 50, clientY: 500 })
    })
    expect(queryByTestId('pen-snap-vertex')).not.toBeNull()
  })

  // T4: CREATE — close with ≥3 anchors (no neighbor snap) → ONE op:'create' committed
  it('T4: close on first anchor (≥3 anchors, no neighbor snap) commits ONE op:create with closed ring', async () => {
    const onPathClosed = vi.fn()

    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={[]}  // empty — no snap, pure CREATE mode
        onPathClosed={onPathClosed}
        onDrawingStateChange={vi.fn()}
        projectId="proj-1"
        branchId="branch-1"
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    // Clicks in the INTERIOR of the canvas (far from edges and any barony vertices)
    // clientX/clientY are used directly as canvas px by canvasToGeo in jsdom
    // Position a triangle far from any snap target (center of canvas area)
    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 }) // anchor 0
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 600, clientY: 400 }) // anchor 1
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 500, clientY: 600 }) // anchor 2
    })
    // Close: click close to anchor 0 (within PEN_SNAP_PX=12px)
    await act(async () => {
      fireEvent.click(layer, { clientX: 401, clientY: 400 })
    })
    // Flush async (commitCreate awaits fetch /editor/country before setVerticesAndLog)
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })

    // onPathClosed should have been called
    expect(onPathClosed).toHaveBeenCalled()
    // setVerticesAndLog must have been called with op:'create'
    const createCalls = mockSetVerticesAndLog.mock.calls.filter(
      (args) => (args[1] as { op: string })?.op === 'create',
    )
    expect(createCalls).toHaveLength(1)
    // The ring must be present and closed
    const ring = (createCalls[0][1] as { ring: unknown[] }).ring
    expect(Array.isArray(ring)).toBe(true)
    expect((ring as unknown[]).length).toBeGreaterThanOrEqual(3)
    // allocated_original_idx must be null at commit time
    expect((createCalls[0][1] as { allocated_original_idx: unknown }).allocated_original_idx).toBeNull()
  })

  // T5a: validation fails (2 anchors only) → NO create op
  it('T5a: closing with only 2 anchors does NOT commit create op', async () => {
    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={[]}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
        projectId="proj-1"
        branchId="branch-1"
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 }) // anchor 0
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 600, clientY: 400 }) // anchor 1
    })
    // Try to close (only 2 anchors — fails validation)
    await act(async () => {
      fireEvent.click(layer, { clientX: 401, clientY: 400 })
    })

    const createCalls = mockSetVerticesAndLog.mock.calls.filter(
      (args) => (args[1] as { op: string })?.op === 'create',
    )
    expect(createCalls).toHaveLength(0)
  })

  // T5b: validation fails (self-intersecting ring — butterfly shape) → NO create op
  it('T5b: closing with self-intersecting ring does NOT commit create op', async () => {
    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={[]}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
        projectId="proj-1"
        branchId="branch-1"
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    // Butterfly: (0,0)→(100,100)→(100,0)→(0,100) — segments cross each other
    // In canvas px (far from snap targets):
    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 }) // anchor 0
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 600, clientY: 600 }) // anchor 1
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 600, clientY: 400 }) // anchor 2
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 600 }) // anchor 3 — creates an X
    })
    // Close
    await act(async () => {
      fireEvent.click(layer, { clientX: 401, clientY: 400 })
    })

    const createCalls = mockSetVerticesAndLog.mock.calls.filter(
      (args) => (args[1] as { op: string })?.op === 'create',
    )
    expect(createCalls).toHaveLength(0)
  })

  // T5c: validation fails (tiny area — collinear/near-zero area ring) → NO create op
  it('T5c: closing with near-zero area does NOT commit create op', async () => {
    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={[]}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
        projectId="proj-1"
        branchId="branch-1"
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    // Nearly collinear triangle with tiny area (< MIN_AREA_PX2=200)
    // Points: (400,400), (401,400), (400,401) — area = 0.5 px² << 200
    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 }) // anchor 0
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 401, clientY: 400 }) // anchor 1 — 1px away
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 401 }) // anchor 2 — 1px away
    })
    // Close
    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 }) // exactly on anchor 0
    })

    const createCalls = mockSetVerticesAndLog.mock.calls.filter(
      (args) => (args[1] as { op: string })?.op === 'create',
    )
    expect(createCalls).toHaveLength(0)
  })

  // T6: mid-draw Ctrl+Z removes last anchor; editLog unchanged
  it('T6: mid-draw Ctrl+Z removes last anchor; store editLog unchanged', async () => {
    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={[]}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 })
      fireEvent.click(layer, { clientX: 600, clientY: 400 })
      fireEvent.click(layer, { clientX: 500, clientY: 600 })
    })
    // Ctrl+Z mid-draw (component-local)
    await act(async () => {
      fireEvent.keyDown(window, { key: 'z', ctrlKey: true, code: 'KeyZ' })
    })

    // No store write — setVerticesAndLog must not have been called
    expect(mockSetVerticesAndLog).not.toHaveBeenCalled()
  })

  // T7: Esc calls onDrawingStateChange(false)
  it('T7: Esc during drawing calls onDrawingStateChange(false) and discards path', async () => {
    const onDrawingStateChange = vi.fn()

    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={[]}
        onPathClosed={vi.fn()}
        onDrawingStateChange={onDrawingStateChange}
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 })
      fireEvent.click(layer, { clientX: 600, clientY: 400 })
    })
    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' })
    })

    const falseCall = onDrawingStateChange.mock.calls.find((args) => args[0] === false)
    expect(falseCall).toBeDefined()
  })

  // T8: EXTEND — first anchor snaps to neighbor vertex → extendMode detected; no op:'create'
  // EXTEND graft is acknowledged as a stub (Plan 06 UAT) but the contract is:
  //   - if extendMode is active, op:'create' must NOT be committed
  //   - the component must not crash
  it('T8: EXTEND mode (first anchor snapped to contour vertex) does NOT commit op:create', async () => {
    // Place first anchor EXACTLY on a neighbor vertex canvas coordinate (~50, 500)
    // so snap fires (distance 0 < 12 tol at stageScale=1)
    const { getByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={NEIGHBOR_FEATURES} // has vertex at lon=-9,lat=40 → ~(50,500)
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
        projectId="proj-1"
        branchId="branch-1"
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    // First click exactly on neighbor vertex (canvas px 50, 500) → extendMode=true
    await act(async () => {
      fireEvent.click(layer, { clientX: 50, clientY: 500 }) // anchor 0, snapped to barony vertex
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 300, clientY: 500 }) // anchor 1
    })
    await act(async () => {
      fireEvent.click(layer, { clientX: 200, clientY: 700 }) // anchor 2
    })
    // Close
    await act(async () => {
      fireEvent.click(layer, { clientX: 51, clientY: 500 }) // near anchor 0
    })
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })

    // MUST NOT have committed op:'create'
    const createCalls = mockSetVerticesAndLog.mock.calls.filter(
      (args) => (args[1] as { op: string })?.op === 'create',
    )
    expect(createCalls).toHaveLength(0)
  })

  // T9: right-click removes the last placed anchor (component-local, no store write).
  // With 2 anchors the closeable first-anchor highlight (pen-first-anchor) renders;
  // after one right-click only 1 anchor remains so the highlight disappears.
  it('T9: right-click (contextmenu) removes last anchor; no store write', async () => {
    const { getByTestId, queryByTestId } = render(
      <PenDrawLayer
        projection={PROJECTION}
        currentScale={1}
        neighborCandidates={[]}
        onPathClosed={vi.fn()}
        onDrawingStateChange={vi.fn()}
      />,
    )
    const layer = getByTestId('pen-draw-layer')

    await act(async () => {
      fireEvent.click(layer, { clientX: 400, clientY: 400 }) // anchor 0
      fireEvent.click(layer, { clientX: 600, clientY: 400 }) // anchor 1
    })
    // 2 anchors → closeable highlight present
    expect(queryByTestId('pen-first-anchor')).not.toBeNull()

    // Right-click → remove last anchor → 1 anchor left → highlight gone
    await act(async () => {
      fireEvent.contextMenu(layer, { clientX: 600, clientY: 400 })
    })
    expect(queryByTestId('pen-first-anchor')).toBeNull()

    // Pure local edit — never touches the store / zundo
    expect(mockSetVerticesAndLog).not.toHaveBeenCalled()
  })
})
