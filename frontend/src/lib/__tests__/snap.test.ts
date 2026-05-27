/* Phase 08 Plan 06b — snap utility tests (TOPO-03).
 * scale-aware snap: snap threshold = SNAP_SCREEN_PX / stageScale so the
 * visual snap radius is constant regardless of zoom level (Pitfall 7).
 *
 * Rule 1 deviation: stub used 'snapToVertex'; plan-spec API is 'snapToNeighbour'.
 * Replaced entirely per 08-06a precedent (Deviation #3).
 */
import { describe, it, expect } from 'vitest';
import { snapToNeighbour } from '../snap';
import type { SnapCandidate } from '../snap';

describe('snapToNeighbour — basic hit (TOPO-03)', () => {
  it('returns the candidate when cursor is within snap radius at scale=1', () => {
    // snap threshold = 5 / 1 = 5 world units; candidate at (0.0001, 0.0001) from origin
    const cursor = { lat: 0, lon: 0 };
    const candidates: SnapCandidate[] = [{ id: 'v1', lat: 0.0001, lon: 0.0001 }];
    const result = snapToNeighbour(cursor, candidates, 1, false);
    expect(result).not.toBeNull();
    expect(result?.id).toBe('v1');
    expect(result?.lat).toBeCloseTo(0.0001);
    expect(result?.lon).toBeCloseTo(0.0001);
  });

  it('returns null when cursor is farther than snap radius at scale=1', () => {
    // snap threshold = 5 / 1 = 5 world units; candidate at (10, 10) — outside
    const cursor = { lat: 0, lon: 0 };
    const candidates: SnapCandidate[] = [{ id: 'v1', lat: 10, lon: 10 }];
    const result = snapToNeighbour(cursor, candidates, 1, false);
    expect(result).toBeNull();
  });

  it('returns the nearest candidate when multiple are within snap radius', () => {
    const cursor = { lat: 0, lon: 0 };
    // Both within 5 world-unit radius; v2 is closer
    const candidates: SnapCandidate[] = [
      { id: 'v1', lat: 2.0, lon: 0 },
      { id: 'v2', lat: 0.5, lon: 0 },
    ];
    const result = snapToNeighbour(cursor, candidates, 1, false);
    expect(result?.id).toBe('v2');
  });
});

describe('snapToNeighbour — Alt-disable (TOPO-03 D-28)', () => {
  it('returns null when altHeld=true regardless of proximity', () => {
    // Candidate is directly at cursor — should snap, but Alt disables
    const cursor = { lat: 5.0, lon: 5.0 };
    const candidates: SnapCandidate[] = [{ id: 'v1', lat: 5.0, lon: 5.0 }];
    const result = snapToNeighbour(cursor, candidates, 1, true);
    expect(result).toBeNull();
  });
});

describe('snapToNeighbour — scale-aware threshold (Pitfall 7)', () => {
  it('snap threshold shrinks at higher zoom: at stageScale=10, threshold = 0.5 world units', () => {
    // Pitfall 7: snapWorldDist = SNAP_SCREEN_PX / stageScale = 5 / 10 = 0.5
    const cursor = { lat: 0, lon: 0 };
    // candidate at 0.3 world units — within 0.5 threshold
    const within: SnapCandidate[] = [{ id: 'close', lat: 0.3, lon: 0 }];
    expect(snapToNeighbour(cursor, within, 10, false)?.id).toBe('close');

    // candidate at 1.0 world units — outside 0.5 threshold
    const outside: SnapCandidate[] = [{ id: 'far', lat: 1.0, lon: 0 }];
    expect(snapToNeighbour(cursor, outside, 10, false)).toBeNull();
  });

  it('snap threshold doubles at half zoom: at stageScale=0.5, threshold = 10 world units', () => {
    // Pitfall 7: threshold = 5 / 0.5 = 10 world units
    const cursor = { lat: 0, lon: 0 };
    // candidate at 9.9 world units — within 10 threshold
    const within: SnapCandidate[] = [{ id: 'reachable', lat: 9.9, lon: 0 }];
    expect(snapToNeighbour(cursor, within, 0.5, false)?.id).toBe('reachable');

    // candidate at 11 world units — outside 10 threshold
    const outside: SnapCandidate[] = [{ id: 'unreachable', lat: 11, lon: 0 }];
    expect(snapToNeighbour(cursor, outside, 0.5, false)).toBeNull();
  });

  it('zoom=2 has half the pixel-space radius vs zoom=1 in world-units', () => {
    // At zoom=1: threshold = 5 world units. Candidate at 4.9 → snaps.
    const cursor = { lat: 0, lon: 0 };
    const candidate: SnapCandidate[] = [{ id: 'v', lat: 4.9, lon: 0 }];
    expect(snapToNeighbour(cursor, candidate, 1, false)).not.toBeNull();

    // At zoom=2: threshold = 2.5 world units. Same candidate at 4.9 → no snap.
    expect(snapToNeighbour(cursor, candidate, 2, false)).toBeNull();
  });
});

describe('snapToNeighbour — empty candidates', () => {
  it('returns null for empty candidate list', () => {
    const cursor = { lat: 0, lon: 0 };
    expect(snapToNeighbour(cursor, [], 1, false)).toBeNull();
  });
});
