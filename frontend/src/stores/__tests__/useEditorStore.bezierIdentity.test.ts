/**
 * Phase 08.1 Plan 02 — BEZ-IDENTITY-01: empty-log byte-identity guard (Task 2).
 *
 * This is the phase's single non-negotiable contract and the frontend port of the
 * backend `test_empty_edit_log_preserves_lookup_barony_png` parity test. It lands in
 * Wave 2 — BEFORE any drag-commit code (a later plan) — so the safety baseline is GREEN
 * before geometry can ever be written back.
 *
 * Recipe (RESEARCH §Identity Contract Test):
 *   1. Seed the REAL useEditorStore with a known polygon ring via setState wrapped in
 *      temporal.pause/resume (bypassing SelectionBridge for isolation).
 *   2. Capture JSON.stringify(vertices) + editLog.length.
 *   3. Mount the REAL BezierEditLayer (which runs fitPolygonToBezier + builds display state).
 *   4. Unmount it (simulating exit without any drag).
 *   5. Assert vertices are byte-identical (exact JSON.stringify match).
 *   6. Assert editLog.length is unchanged (no phantom entries).
 *
 * In this plan it passes by construction: BezierEditLayer is render+activate only and
 * never writes the store. react-konva is mocked (jsdom has no canvas) but the fit +
 * display-state effect still runs — that is exactly the entry path under test. The store
 * itself is the REAL one (NOT mocked) so the byte-identity guard is meaningful.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import React from 'react'
import { IBERIA_BARONY_RING } from '../../components/canvas/__fixtures__/iberiaBaronyRing'
import type { ProjectionConfig } from '../../lib/projection'

// react-konva must be mocked — jsdom has no canvas (Plan 01 didn't add the `canvas` dep).
// The mock still mounts/unmounts the component and runs its effects (the fit on entry).
vi.mock('react-konva', () => {
  const React = require('react')
  const passthrough =
    (testid: string): React.FC<{ children?: React.ReactNode }> =>
    ({ children }) =>
      React.createElement('div', { 'data-testid': testid }, children)
  return {
    Layer: passthrough('konva-layer'),
    Path: passthrough('konva-path'),
    Rect: passthrough('konva-rect'),
    Circle: passthrough('konva-circle'),
    Line: passthrough('konva-line'),
  }
})

// REAL store + REAL component (no vi.mock of useEditorStore here).
import { useEditorStore } from '../useEditorStore'
import type { VertexCoord } from '../useEditorStore'
import { BezierEditLayer } from '../../components/canvas/BezierEditLayer'

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

describe('BEZ-IDENTITY-01 — empty-log byte-identity guard (Phase 08.1 Plan 02)', () => {
  it('enter+exit Bézier edit mode with zero drags leaves useEditorStore.vertices byte-identical and editLog unchanged', () => {
    const beforeStr = JSON.stringify(useEditorStore.getState().vertices)
    const beforeLen = useEditorStore.getState().editLog.length

    // Enter Bézier edit mode: mount the real component (runs fitPolygonToBezier internally
    // + builds component-local display state). Then exit without dragging.
    const { unmount } = render(React.createElement(BezierEditLayer, { projection: PROJ }))
    unmount()

    expect(JSON.stringify(useEditorStore.getState().vertices)).toBe(beforeStr)
    expect(useEditorStore.getState().editLog.length).toBe(beforeLen)
  })

  it('the entry fit produces no phantom editLog entries even after the display state is built', () => {
    // Sanity guard distinct from the byte-identity match: the editLog stays empty,
    // proving setVerticesAndLog was never called on entry.
    const { unmount } = render(React.createElement(BezierEditLayer, { projection: PROJ }))
    expect(useEditorStore.getState().editLog).toHaveLength(0)
    unmount()
    expect(useEditorStore.getState().editLog).toHaveLength(0)
  })
})
