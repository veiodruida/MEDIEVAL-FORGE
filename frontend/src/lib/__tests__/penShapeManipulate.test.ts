/**
 * Phase 08.3 Plan 11 — Task 1 TDD (RED → GREEN)
 * Pure ring-manipulation geometry helpers: translateRing + moveRingVertex.
 *
 * Project conventions: descriptive test names + explicit numeric fixtures.
 * Ring type = Array<{lat:number; lon:number}> (matches EditOp.ring in useEditorStore.ts:48).
 * first === last for a closed ring.
 */
import { describe, it, expect } from 'vitest'
import { translateRing, moveRingVertex } from '../penShapeManipulate'

// ── Shared fixture ────────────────────────────────────────────────────────────
// A closed ring: three distinct points + closing duplicate.
// lat=y, lon=x convention (matches manual_edit.py:587 xoff=d_lon, yoff=d_lat).
const CLOSED_RING: Array<{ lat: number; lon: number }> = [
  { lat: 10, lon: 20 },
  { lat: 10, lon: 24 },
  { lat: 14, lon: 24 },
  { lat: 10, lon: 20 }, // closing duplicate = index[0]
]

// ── translateRing ─────────────────────────────────────────────────────────────

describe('translateRing', () => {
  it('shifts every vertex by the given lat/lon delta', () => {
    const result = translateRing(CLOSED_RING, 2, -3)
    expect(result).toEqual([
      { lat: 12, lon: 17 },
      { lat: 12, lon: 21 },
      { lat: 16, lon: 21 },
      { lat: 12, lon: 17 },
    ])
  })

  it('preserves the closed-ring invariant (last === first after translate)', () => {
    const result = translateRing(CLOSED_RING, 2, -3)
    expect(result[0]).toEqual(result[result.length - 1])
  })

  it('with zero delta returns coordinate-equal ring (all vertices unchanged)', () => {
    const result = translateRing(CLOSED_RING, 0, 0)
    expect(result).toEqual(CLOSED_RING)
  })

  it('returns a NEW array (does not mutate the input ring)', () => {
    const originalRef = CLOSED_RING
    const result = translateRing(CLOSED_RING, 1, 1)
    expect(result).not.toBe(originalRef)
    // Input is unmodified
    expect(CLOSED_RING[0]).toEqual({ lat: 10, lon: 20 })
  })
})

// ── moveRingVertex ────────────────────────────────────────────────────────────

describe('moveRingVertex', () => {
  it('relocates only the vertex at index, leaving others unchanged', () => {
    const result = moveRingVertex(CLOSED_RING, 1, 11, 25)
    expect(result[1]).toEqual({ lat: 11, lon: 25 })
    // All other vertices unchanged
    expect(result[0]).toEqual({ lat: 10, lon: 20 })
    expect(result[2]).toEqual({ lat: 14, lon: 24 })
  })

  it('on the shared closing vertex (index=0) moves BOTH index 0 AND the last duplicate so ring stays closed', () => {
    const result = moveRingVertex(CLOSED_RING, 0, 9, 19)
    expect(result[0]).toEqual({ lat: 9, lon: 19 })
    expect(result[result.length - 1]).toEqual({ lat: 9, lon: 19 })
  })

  it('moving the last index on a closed ring also moves index 0 to keep closure', () => {
    const lastIdx = CLOSED_RING.length - 1
    const result = moveRingVertex(CLOSED_RING, lastIdx, 9, 19)
    expect(result[lastIdx]).toEqual({ lat: 9, lon: 19 })
    expect(result[0]).toEqual({ lat: 9, lon: 19 })
  })

  it('returns a NEW array (does not mutate input)', () => {
    const inputCopy = [...CLOSED_RING]
    const result = moveRingVertex(CLOSED_RING, 1, 11, 25)
    expect(result).not.toBe(CLOSED_RING)
    // Input unmodified
    expect(CLOSED_RING[1]).toEqual(inputCopy[1])
  })
})
