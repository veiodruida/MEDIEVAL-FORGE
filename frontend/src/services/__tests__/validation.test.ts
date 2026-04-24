import { describe, it, expect } from 'vitest'
import { validateTerritories } from '../validation'
import type { ProjectGeometryState } from '../../types/editing'

// Simple triangle polygon (valid): 4 positions (3 unique + closing repeat)
const VALID_TRIANGLE = {
  type: 'Polygon' as const,
  coordinates: [
    [[-8.0, 41.0], [-7.0, 42.0], [-9.0, 42.0], [-8.0, 41.0]],
  ],
}

// A square polygon enclosing the capital
const SQUARE_AROUND_CAPITAL = {
  type: 'Polygon' as const,
  coordinates: [
    [[-9.0, 40.0], [-7.0, 40.0], [-7.0, 43.0], [-9.0, 43.0], [-9.0, 40.0]],
  ],
}

describe('validateTerritories', () => {
  it('returns no issues for a valid polygon with capital inside', () => {
    const state: ProjectGeometryState = {
      territories: { condA: SQUARE_AROUND_CAPITAL },
      capitals: { condA: [-8.0, 41.5] }, // inside the square
    }
    const issues = validateTerritories(['condA'], state)
    expect(issues).toHaveLength(0)
  })

  it('returns empty_polygon when exterior ring is empty', () => {
    const state: ProjectGeometryState = {
      territories: {
        condA: { type: 'Polygon', coordinates: [[]] },
      },
      capitals: {},
    }
    const issues = validateTerritories(['condA'], state)
    expect(issues).toHaveLength(1)
    expect(issues[0].rule).toBe('empty_polygon')
    expect(issues[0].severity).toBe('error')
    expect(issues[0].condado_id).toBe('condA')
  })

  it('returns polygon_invalid when ring has fewer than 4 positions', () => {
    const state: ProjectGeometryState = {
      territories: {
        condA: {
          type: 'Polygon',
          coordinates: [
            [[-8.0, 41.0], [-7.0, 42.0], [-8.0, 41.0]], // only 3 positions
          ],
        },
      },
      capitals: {},
    }
    const issues = validateTerritories(['condA'], state)
    expect(issues).toHaveLength(1)
    expect(issues[0].rule).toBe('polygon_invalid')
    expect(issues[0].severity).toBe('error')
  })

  it('returns polygon_invalid when ring has duplicate consecutive points', () => {
    const state: ProjectGeometryState = {
      territories: {
        condA: {
          type: 'Polygon',
          coordinates: [
            [[-8.0, 41.0], [-8.0, 41.0], [-7.0, 42.0], [-8.0, 41.0]], // dup at pos 0,1
          ],
        },
      },
      capitals: {},
    }
    const issues = validateTerritories(['condA'], state)
    expect(issues).toHaveLength(1)
    expect(issues[0].rule).toBe('polygon_invalid')
    expect(issues[0].severity).toBe('error')
  })

  it('returns capital_outside when capital is outside the polygon', () => {
    const state: ProjectGeometryState = {
      territories: { condA: SQUARE_AROUND_CAPITAL },
      capitals: { condA: [-5.0, 41.5] }, // clearly outside x range
    }
    const issues = validateTerritories(['condA'], state)
    expect(issues).toHaveLength(1)
    expect(issues[0].rule).toBe('capital_outside')
    expect(issues[0].severity).toBe('error')
  })

  it('skips condados whose id is not in the territories map', () => {
    const state: ProjectGeometryState = {
      territories: {},
      capitals: {},
    }
    // asking to validate a non-existent id should just produce no issues
    const issues = validateTerritories(['nonexistent'], state)
    expect(issues).toHaveLength(0)
  })

  it('only validates the specified affectedIds even when territories has more', () => {
    const state: ProjectGeometryState = {
      territories: {
        condA: SQUARE_AROUND_CAPITAL,
        condB: { type: 'Polygon', coordinates: [[]] }, // invalid, but not in affectedIds
      },
      capitals: { condA: [-8.0, 41.5] },
    }
    const issues = validateTerritories(['condA'], state)
    // condB is invalid but wasn't in affectedIds — should not appear
    expect(issues.filter((i) => i.condado_id === 'condB')).toHaveLength(0)
    expect(issues).toHaveLength(0) // condA is valid
  })
})
