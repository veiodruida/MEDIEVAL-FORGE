/**
 * Phase 08 Plan 12 — Task 2: SelectionBridge component tests (TDD RED → GREEN)
 *
 * SelectionBridge closes GAP-A: it subscribes to useUIStore selection and wires:
 *   - barony selected → setActiveTerritoryId(id) + vertices map populated
 *   - condado selected (while barony active, D-03) → clear activeTerritoryId + vertices
 *   - deselect (null) → clear activeTerritoryId + vertices
 *
 * Vertex id scheme: "${baronyId}#${index}" (stable, zundo-diff-safe).
 * Loading vertices uses setState({ vertices }) NOT setVerticesAndLog (no undo entry).
 * pause()/resume() wraps the setState call to prevent zundo history pollution.
 *
 * REQ-IDs: EDIT-VERTEX-01, EDIT-VERTEX-02, EDIT-VERTEX-03, EDIT-VERTEX-05, PERF-01
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import React from 'react'

// ── Mock stores ────────────────────────────────────────────────────────────────

// Track calls to setActiveTerritoryId and setState
const mockSetActiveTerritoryId = vi.fn()
const mockPause = vi.fn()
const mockResume = vi.fn()

// Track the last vertices passed to setState
let capturedVertices: Record<string, { lat: number; lon: number }> = {}

// useUIStore state that tests can mutate
let mockSelectedBaronyId: string | null = null
let mockSelectedTerritoryId: string | null = null

vi.mock('../../../stores/uiStore', () => ({
  useUIStore: (selector: (s: unknown) => unknown) =>
    selector({
      selectedBaronyId: mockSelectedBaronyId,
      selectedTerritoryId: mockSelectedTerritoryId,
    }),
}))

vi.mock('../../../stores/useEditorStore', () => {
  const storeModule = {
    useEditorStore: (selector: (s: unknown) => unknown) =>
      selector({ activeTerritoryId: null }),
    // Expose getState so SelectionBridge can call setActiveTerritoryId
    // via useEditorStore.getState().setActiveTerritoryId(...)
    // and setState for direct vertices update
  }
  // Attach static methods: getState and setState (as a mock that captures vertices)
  Object.assign(storeModule.useEditorStore, {
    getState: () => ({
      setActiveTerritoryId: mockSetActiveTerritoryId,
    }),
    setState: (partial: Record<string, unknown>) => {
      if (partial.vertices !== undefined) {
        capturedVertices = partial.vertices as Record<string, { lat: number; lon: number }>
      }
    },
    temporal: {
      getState: () => ({
        pause: mockPause,
        resume: mockResume,
      }),
    },
  })
  return storeModule
})

// ── Import component AFTER mocks ───────────────────────────────────────────────
// SelectionBridge does not exist yet — this import will fail until Task 2 is implemented (RED).
import { SelectionBridge } from '../SelectionBridge'
import type { BaronyRender } from '../../../hooks/useCanvasArtifacts'

// ── Helpers ────────────────────────────────────────────────────────────────────

function makeBarony(id: string, ring: [number, number][]): BaronyRender {
  return {
    id,
    name: `Barony ${id}`,
    condado_id: 'C-01',
    fill: '#aabbcc',
    points: [0, 0, 10, 0, 10, 10, 0, 10],
    geoRing: ring,
  }
}

const RING_B12: [number, number][] = [
  [-7.5, 38.5],
  [-7.6, 38.6],
  [-7.5, 38.7],
  [-7.4, 38.6],
  [-7.5, 38.5], // closed — last point === first point
]

const RING_B13: [number, number][] = [
  [-8.0, 37.0],
  [-8.1, 37.1],
  [-8.0, 37.2],
  [-8.0, 37.0],
]

function renderBridge(baronies: BaronyRender[]) {
  return render(React.createElement(SelectionBridge, { baronies }))
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('SelectionBridge — GAP-A bridge (Phase 08 Plan 12 Task 2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    capturedVertices = {}
    mockSelectedBaronyId = null
    mockSelectedTerritoryId = null
  })

  it('renders null — no DOM output', () => {
    const { container } = renderBridge([])
    expect(container.firstChild).toBeNull()
  })

  describe('barony selection → setActiveTerritoryId + vertices populated', () => {
    it('selects barony B-12: setActiveTerritoryId called with "B-12"', () => {
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      expect(mockSetActiveTerritoryId).toHaveBeenCalledWith('B-12')
    })

    it('selects barony B-12: vertices non-empty (has entries)', () => {
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      expect(Object.keys(capturedVertices).length).toBeGreaterThan(0)
    })

    it('vertex ids use stable "${baronyId}#${index}" scheme', () => {
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      // Closed ring [lon0,lat0]...[lon4,lat4] where last===first → n=4 unique vertices
      // Keys must be B-12#0, B-12#1, B-12#2, B-12#3
      expect('B-12#0' in capturedVertices).toBe(true)
      expect('B-12#1' in capturedVertices).toBe(true)
      expect('B-12#2' in capturedVertices).toBe(true)
      expect('B-12#3' in capturedVertices).toBe(true)
    })

    it('closed ring: duplicate last point is dropped (n unique vertices)', () => {
      // RING_B12 has 5 points but [0] === [4] (closed) → 4 unique vertices
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      expect(Object.keys(capturedVertices)).toHaveLength(4)
    })

    it('each vertex value has {lat, lon} in degrees', () => {
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      // RING_B12[0] = [-7.5, 38.5] → lon=-7.5, lat=38.5
      const v0 = capturedVertices['B-12#0']
      expect(v0).toBeDefined()
      expect(v0.lon).toBeCloseTo(-7.5)
      expect(v0.lat).toBeCloseTo(38.5)
    })

    it('vertex order matches ring index (B-12#1 = ring[1])', () => {
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      // RING_B12[1] = [-7.6, 38.6] → lon=-7.6, lat=38.6
      const v1 = capturedVertices['B-12#1']
      expect(v1.lon).toBeCloseTo(-7.6)
      expect(v1.lat).toBeCloseTo(38.6)
    })

    it('open ring (no duplicate last): all points included', () => {
      // RING_B13 has 4 points, last ≠ first → 4 vertices
      mockSelectedBaronyId = 'B-13'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-13', RING_B13)]
      renderBridge(baronies)
      expect(Object.keys(capturedVertices)).toHaveLength(4)
    })
  })

  describe('condado selection (D-03) → clear activeTerritoryId + vertices', () => {
    it('condado selected: setActiveTerritoryId called with null', () => {
      mockSelectedBaronyId = null
      mockSelectedTerritoryId = 'C-05'
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      expect(mockSetActiveTerritoryId).toHaveBeenCalledWith(null)
    })

    it('condado selected: vertices cleared to {}', () => {
      mockSelectedBaronyId = null
      mockSelectedTerritoryId = 'C-05'
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      expect(capturedVertices).toEqual({})
    })
  })

  describe('deselect (both null) → clear', () => {
    it('deselect: setActiveTerritoryId called with null', () => {
      mockSelectedBaronyId = null
      mockSelectedTerritoryId = null
      renderBridge([makeBarony('B-12', RING_B12)])
      expect(mockSetActiveTerritoryId).toHaveBeenCalledWith(null)
    })

    it('deselect: vertices cleared to {}', () => {
      mockSelectedBaronyId = null
      mockSelectedTerritoryId = null
      renderBridge([makeBarony('B-12', RING_B12)])
      expect(capturedVertices).toEqual({})
    })
  })

  describe('pause/resume wraps setState to prevent undo history pollution', () => {
    it('calls temporal.pause() before and resume() after loading vertices', () => {
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      expect(mockPause).toHaveBeenCalled()
      expect(mockResume).toHaveBeenCalled()
    })

    it('calls temporal.pause() and resume() on deselect too', () => {
      mockSelectedBaronyId = null
      mockSelectedTerritoryId = null
      renderBridge([makeBarony('B-12', RING_B12)])
      expect(mockPause).toHaveBeenCalled()
      expect(mockResume).toHaveBeenCalled()
    })
  })

  describe('barony not found in baronies list', () => {
    it('selected barony id not in list: activeTerritoryId set but vertices empty', () => {
      mockSelectedBaronyId = 'B-99' // not in list
      mockSelectedTerritoryId = null
      const baronies = [makeBarony('B-12', RING_B12)]
      renderBridge(baronies)
      expect(mockSetActiveTerritoryId).toHaveBeenCalledWith('B-99')
      expect(capturedVertices).toEqual({})
    })
  })

  describe('barony selected but geoRing is missing', () => {
    it('barony without geoRing: activeTerritoryId set but vertices empty', () => {
      mockSelectedBaronyId = 'B-12'
      mockSelectedTerritoryId = null
      const baronies: BaronyRender[] = [{
        id: 'B-12',
        name: 'Test',
        condado_id: 'C-01',
        fill: '#aabb',
        points: [0, 0],
        // geoRing intentionally omitted
      }]
      renderBridge(baronies)
      expect(mockSetActiveTerritoryId).toHaveBeenCalledWith('B-12')
      expect(capturedVertices).toEqual({})
    })
  })
})
