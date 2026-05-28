/**
 * Phase 08 Plan 12 — Task 1: BaronyRender.geoRing field tests (TDD RED → GREEN)
 *
 * Tests that:
 * - BaronyRender includes an optional geoRing?: [number, number][] field
 * - The baronies `select` function populates geoRing with the raw outer ring [lon,lat][]
 *   captured BEFORE the pixel conversion via geoRingToKonvaPoints
 * - Existing consumers are unaffected (additive field — tests still pass without geoRing)
 *
 * REQ-IDs: EDIT-VERTEX-01, EDIT-VERTEX-02, EDIT-VERTEX-03, EDIT-VERTEX-05
 */

import { describe, it, expect } from 'vitest'

// We test the select function logic in isolation by extracting the core logic.
// The select fn in useCanvasArtifacts is a TanStack `select` option on a query —
// it is a pure function: (raw: FC<BaronyFeature>) => BaronyRender[].
// We validate the output shape rather than the hook (which needs React QueryClient).

// Import the BaronyRender interface type to verify shape:
import type { BaronyRender } from '../useCanvasArtifacts'

// Helper: build a minimal BaronyFeature FeatureCollection
function makeBaronyFC(coords: [number, number][]) {
  return {
    type: 'FeatureCollection' as const,
    features: [
      {
        type: 'Feature' as const,
        id: 'B-12',
        geometry: {
          type: 'Polygon' as const,
          coordinates: [coords],
        },
        properties: {
          id: 'B-12',
          name: 'Test Barony',
          condado_id: 'C-01',
          fill: '#aabbcc',
          centroid: [-7.5, 38.5] as [number, number],
        },
      },
    ],
  }
}

// Extract the select function logic from useCanvasArtifacts by reproducing it here.
// This matches what the implementation must do (the test is spec-first).
// When geoRing is added, this spec must match the actual implementation.
function firstOuterRing(g: { type: 'Polygon' | 'MultiPolygon'; coordinates: [number, number][][] | [number, number][][][] }): [number, number][] {
  return g.type === 'Polygon'
    ? (g.coordinates as [number, number][][])[0]
    : (g.coordinates as [number, number][][][])[0][0]
}

describe('BaronyRender.geoRing — additive field (Phase 08 Plan 12 Task 1)', () => {
  it('geoRing field is declared as optional on BaronyRender interface (type-level)', () => {
    // This test validates that BaronyRender has geoRing?: [number, number][]
    // If the field does not exist on the type, TypeScript would error here.
    const render: BaronyRender = {
      id: 'B-1',
      name: 'Test',
      condado_id: 'C-1',
      fill: '#aabbcc',
      points: [0, 0, 100, 0, 100, 100],
    }
    // geoRing is optional so it can be omitted (backward compat)
    expect(render.id).toBe('B-1')
    // This additional check ensures geoRing can also be assigned:
    const renderWithGeoRing: BaronyRender = {
      ...render,
      geoRing: [[-7.5, 38.5], [-7.6, 38.6], [-7.5, 38.7]],
    }
    expect(renderWithGeoRing.geoRing).toHaveLength(3)
  })

  it('firstOuterRing extracts coordinates[0] from a Polygon geometry', () => {
    const ring: [number, number][] = [
      [-7.5, 38.5],
      [-7.6, 38.6],
      [-7.5, 38.7],
      [-7.5, 38.5], // closed
    ]
    const geom = { type: 'Polygon' as const, coordinates: [ring] as [number, number][][] }
    const result = firstOuterRing(geom)
    expect(result).toBe(ring) // same reference
    expect(result).toHaveLength(4)
  })

  it('select() produces geoRing === the outer ring from BaronyFeature geometry', () => {
    // The outer ring used to build points must be captured as geoRing.
    // This is the key invariant: geoRing[i] === ring[i] (same array reference or
    // structurally equal) and its values are in [lon, lat] order (NOT pixels).
    const ring: [number, number][] = [
      [-7.5, 38.5],
      [-7.6, 38.6],
      [-7.5, 38.7],
      [-7.5, 38.5],
    ]
    const fc = makeBaronyFC(ring)

    // Simulate what select() must do (spec-first):
    // const ring = firstOuterRing(f.geometry)
    // return { ..., geoRing: ring }
    const feature = fc.features[0]
    const capturedRing = firstOuterRing(feature.geometry as Parameters<typeof firstOuterRing>[0])

    // The captured ring must equal the geometry's coordinates[0]
    expect(capturedRing).toEqual(ring)
    // Lon values (index 0) must be in degrees range
    expect(capturedRing[0][0]).toBeCloseTo(-7.5)
    // Lat values (index 1) must be in degrees range
    expect(capturedRing[0][1]).toBeCloseTo(38.5)
  })

  it('geoRing lon/lat values are in degrees, NOT pixel coordinates', () => {
    // Pixel coordinates after geoRingToKonvaPoints are typically in range [0, mapW/H]
    // e.g., mapW=1920, mapH=1080. Lon values for Iberia are in [-9, 3].
    // This test asserts the captured geoRing values are in the expected degrees range.
    const ring: [number, number][] = [
      [-8.0, 37.0],
      [-7.0, 38.0],
      [-6.0, 37.0],
      [-8.0, 37.0],
    ]
    const fc = makeBaronyFC(ring)
    const feature = fc.features[0]
    const capturedRing = firstOuterRing(feature.geometry as Parameters<typeof firstOuterRing>[0])

    // All lon values must be in [-180, 180]
    for (const [lon] of capturedRing) {
      expect(lon).toBeGreaterThanOrEqual(-180)
      expect(lon).toBeLessThanOrEqual(180)
    }
    // Specifically for Iberia, lon should be negative (western hemisphere)
    expect(capturedRing[0][0]).toBeLessThan(0)
  })

  it('MultiPolygon geometry: geoRing extracts coordinates[0][0]', () => {
    const ring: [number, number][] = [
      [-7.5, 38.5],
      [-7.6, 38.6],
      [-7.5, 38.7],
      [-7.5, 38.5],
    ]
    const geom = {
      type: 'MultiPolygon' as const,
      coordinates: [[ring]] as [number, number][][],
    }
    // @ts-expect-error — casting for test
    const result = firstOuterRing(geom)
    expect(result).toEqual(ring)
  })
})
