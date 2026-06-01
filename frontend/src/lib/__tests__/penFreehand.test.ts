/**
 * Phase 08.3 Plan 08 — sampleAndSimplifyFreehand vitest spec (TDD RED→GREEN)
 *
 * Tests the pure Douglas-Peucker simplification + smoothing helper.
 * Descriptive test names + explicit numeric fixtures per project memory
 * feedback-tests-descriptive.
 */

import { describe, it, expect } from 'vitest'
import { sampleAndSimplifyFreehand } from '../penFlatten'
import type { ProjectionConfig } from '../projection'

// ── Minimal projection matching Iberia-scale lat/lon range ─────────────────
// Iberia: lon ~[-9, 3.3], lat ~[36, 43.8]; mapW/H 1920x1080 at 1x
const PROJ: ProjectionConfig = {
  lonMin: -9.5,
  lonMax: 3.5,
  latMin: 35.5,
  latMax: 44.0,
  mapW: 1920,
  mapH: 1080,
  lonScale: Math.cos(((35.5 + 44.0) / 2) * (Math.PI / 180)),
}

// ── Helper: generate a rough circular path (lat/lon points, noisy) ─────────
function circlePoints(
  centerLon: number,
  centerLat: number,
  radiusDeg: number,
  n: number,
  jitter: number,
): Array<{ lat: number; lon: number }> {
  const pts: Array<{ lat: number; lon: number }> = []
  for (let i = 0; i < n; i++) {
    const angle = (2 * Math.PI * i) / n
    const noise = () => (Math.random() - 0.5) * jitter
    pts.push({
      lon: centerLon + radiusDeg * Math.cos(angle) + noise(),
      lat: centerLat + radiusDeg * Math.sin(angle) + noise(),
    })
  }
  return pts
}

describe('sampleAndSimplifyFreehand', () => {
  it('collapses a jagged 200-point drag into a clean ≤30-point closed ring', () => {
    // Seed deterministic jitter by using a fixed-loop sequence (no Math.random seeding in vitest)
    const pts: Array<{ lat: number; lon: number }> = []
    for (let i = 0; i < 200; i++) {
      const angle = (2 * Math.PI * i) / 200
      // Small jitter: ±0.005 degrees — typical "shaky hand" drag noise
      const jitter = ((i * 17 + 3) % 100) * 0.0001 - 0.005
      pts.push({
        lon: -5.0 + 0.2 * Math.cos(angle) + jitter,
        lat: 40.0 + 0.1 * Math.sin(angle) + jitter,
      })
    }

    const result = sampleAndSimplifyFreehand(pts, PROJ)

    // RDP must reduce the 200 jagged points to a clean ring
    expect(result.length).toBeGreaterThanOrEqual(3)
    expect(result.length).toBeLessThanOrEqual(30)

    // Ring must be closed (first === last within floating-point tolerance)
    const first = result[0]!
    const last = result[result.length - 1]!
    expect(Math.abs(first.lat - last.lat)).toBeLessThan(1e-9)
    expect(Math.abs(first.lon - last.lon)).toBeLessThan(1e-9)
  })

  it('collinear run collapses to its endpoints — 50 collinear points + 2 corners', () => {
    // Build: corner A → 50 collinear points along a horizontal line → corner B
    // Then close back to A (triangle with one very long side)
    const cornerA = { lon: -6.0, lat: 40.0 }
    const cornerB = { lon: -4.0, lat: 40.0 }
    const cornerC = { lon: -5.0, lat: 41.0 }

    const pts: Array<{ lat: number; lon: number }> = [cornerA]
    // 50 collinear points from A to B (all on lat=40 line)
    for (let i = 1; i <= 50; i++) {
      pts.push({
        lon: cornerA.lon + (cornerB.lon - cornerA.lon) * (i / 51),
        lat: 40.0,
      })
    }
    pts.push(cornerB)
    pts.push(cornerC)
    // Don't add A again — sampleAndSimplifyFreehand appends the closing point

    const result = sampleAndSimplifyFreehand(pts, PROJ)

    // The 50 collinear interior points should mostly collapse.
    // We allow up to ~6 points total (3 corners + closing + minor quantization artifacts).
    expect(result.length).toBeGreaterThanOrEqual(3)
    expect(result.length).toBeLessThanOrEqual(6)
  })

  it('output ring is closed (first === last) and non-degenerate for a simple lasso', () => {
    // Simple 8-point diamond shape
    const pts: Array<{ lat: number; lon: number }> = [
      { lon: -5.0, lat: 40.5 }, // top
      { lon: -4.8, lat: 40.3 },
      { lon: -4.7, lat: 40.0 }, // right
      { lon: -4.8, lat: 39.7 },
      { lon: -5.0, lat: 39.5 }, // bottom
      { lon: -5.2, lat: 39.7 },
      { lon: -5.3, lat: 40.0 }, // left
      { lon: -5.2, lat: 40.3 },
    ]

    const result = sampleAndSimplifyFreehand(pts, PROJ)

    expect(result.length).toBeGreaterThanOrEqual(3)

    // Closed ring invariant
    const first = result[0]!
    const last = result[result.length - 1]!
    expect(Math.abs(first.lat - last.lat)).toBeLessThan(1e-9)
    expect(Math.abs(first.lon - last.lon)).toBeLessThan(1e-9)

    // At least 2 distinct interior points (not all same position)
    const distinctCount = new Set(result.map((p) => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`)).size
    expect(distinctCount).toBeGreaterThanOrEqual(3)
  })

  it('empty / degenerate input returns [] for < 3 input points', () => {
    expect(sampleAndSimplifyFreehand([], PROJ)).toEqual([])
    expect(sampleAndSimplifyFreehand([{ lon: -5.0, lat: 40.0 }], PROJ)).toEqual([])
    expect(sampleAndSimplifyFreehand([{ lon: -5.0, lat: 40.0 }, { lon: -4.0, lat: 40.0 }], PROJ)).toEqual([])
  })
})
