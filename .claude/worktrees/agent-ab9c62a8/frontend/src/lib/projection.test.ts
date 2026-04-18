import { describe, it, expect } from 'vitest'
import {
  buildProjectionConfig,
  geoToCanvas,
  canvasToGeo,
  geoRingToKonvaPoints,
  computeFitToView,
} from './projection'

const iberiaBounds = { lonMin: -9.5, lonMax: 4.5, latMin: 35.0, latMax: 44.0 }
const cfg = buildProjectionConfig(iberiaBounds, 1920, 1080)

describe('buildProjectionConfig', () => {
  it('computes lonScale as cos of center latitude', () => {
    const centerLat = (iberiaBounds.latMin + iberiaBounds.latMax) / 2
    const expected = Math.cos((centerLat * Math.PI) / 180)
    expect(cfg.lonScale).toBeCloseTo(expected, 10)
  })
})

describe('geoToCanvas + canvasToGeo round-trip', () => {
  it('geo → canvas → geo round-trips within 1e-9 for 1000 random Iberia points', () => {
    // deterministic pseudo-random via linear congruential generator
    let seed = 42
    const rand = () => {
      seed = (seed * 1664525 + 1013904223) >>> 0
      return seed / 0xffffffff
    }
    for (let i = 0; i < 1000; i++) {
      const lon = iberiaBounds.lonMin + rand() * (iberiaBounds.lonMax - iberiaBounds.lonMin)
      const lat = iberiaBounds.latMin + rand() * (iberiaBounds.latMax - iberiaBounds.latMin)
      const [x, y] = geoToCanvas(lon, lat, cfg)
      const [lon2, lat2] = canvasToGeo(x, y, cfg)
      expect(Math.abs(lon2 - lon)).toBeLessThan(1e-9)
      expect(Math.abs(lat2 - lat)).toBeLessThan(1e-9)
    }
  })

  it('canvas → geo → canvas round-trips within 1e-6 for 1000 random pixel coords', () => {
    let seed = 77
    const rand = () => {
      seed = (seed * 1664525 + 1013904223) >>> 0
      return seed / 0xffffffff
    }
    for (let i = 0; i < 1000; i++) {
      const px = rand() * cfg.mapW
      const py = rand() * cfg.mapH
      const [lon, lat] = canvasToGeo(px, py, cfg)
      const [px2, py2] = geoToCanvas(lon, lat, cfg)
      expect(Math.abs(px2 - px)).toBeLessThan(1e-6)
      expect(Math.abs(py2 - py)).toBeLessThan(1e-6)
    }
  })
})

describe('geoRingToKonvaPoints', () => {
  it('output length === ring.length * 2', () => {
    const ring: [number, number][] = [
      [-9.0, 43.0], [-8.0, 43.0], [-8.0, 42.0], [-9.0, 42.0], [-9.0, 43.0],
    ]
    const pts = geoRingToKonvaPoints(ring, cfg)
    expect(pts.length).toBe(ring.length * 2)
  })

  it('produces alternating x,y values', () => {
    const ring: [number, number][] = [[-9.0, 43.0], [-8.0, 42.0]]
    const pts = geoRingToKonvaPoints(ring, cfg)
    const [x0, y0] = geoToCanvas(-9.0, 43.0, cfg)
    const [x1, y1] = geoToCanvas(-8.0, 42.0, cfg)
    expect(pts[0]).toBeCloseTo(x0)
    expect(pts[1]).toBeCloseTo(y0)
    expect(pts[2]).toBeCloseTo(x1)
    expect(pts[3]).toBeCloseTo(y1)
  })
})

describe('computeFitToView', () => {
  it('fits a 1920x1080 map into an 800x600 viewport with padding', () => {
    const { scale, x, y } = computeFitToView(1920, 1080, 800, 600)
    expect(scale).toBeGreaterThan(0)
    expect(scale).toBeLessThan(1)
    // centered
    expect(x).toBeGreaterThanOrEqual(0)
    expect(y).toBeGreaterThanOrEqual(0)
  })

  it('returns scale <= 1 when map larger than viewport', () => {
    const { scale } = computeFitToView(4000, 2000, 1000, 600)
    expect(scale).toBeLessThanOrEqual(1)
  })

  it('scale > 1 when map smaller than viewport', () => {
    const { scale } = computeFitToView(200, 100, 1920, 1080)
    expect(scale).toBeGreaterThan(1)
  })
})
