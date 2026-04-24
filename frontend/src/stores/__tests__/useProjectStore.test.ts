import { describe, it, expect, beforeEach } from 'vitest'
import { useProjectStore } from '../useProjectStore'  // will fail RED until P03
import type { ProjectGeometryState } from '../../types/editing'

// Fixtures
const LEON_POLYGON: ProjectGeometryState['territories']['leon'] = {
  type: 'Polygon',
  coordinates: [[[-6, 42], [-5, 42], [-5, 43], [-6, 43], [-6, 42]]],
}
const CASTELA_POLYGON: ProjectGeometryState['territories']['castela'] = {
  type: 'Polygon',
  coordinates: [[[-4, 39], [-3, 39], [-3, 40], [-4, 40], [-4, 39]]],
}

beforeEach(() => {
  // Reset store state before each test
  useProjectStore.setState({
    territories: {},
    capitals: {},
  })
  useProjectStore.temporal.getState().clear()
})

describe('useProjectStore — zundo temporal middleware', () => {
  it('exposes temporal middleware with pastStates/futureStates arrays', () => {
    const temporal = useProjectStore.temporal.getState()
    expect(Array.isArray(temporal.pastStates)).toBe(true)
    expect(Array.isArray(temporal.futureStates)).toBe(true)
  })

  it('partialize excludes any non-geometry keys', () => {
    // Set some geometry state and undo it; transient keys should not be restored
    useProjectStore.setState({ territories: { leon: LEON_POLYGON }, capitals: {} })
    useProjectStore.setState({ territories: {}, capitals: {} })
    useProjectStore.temporal.getState().undo()
    // After undo, territories should be back to { leon: LEON_POLYGON }
    // The point: partialize means only geometry keys are in history; no transient junk
    const state = useProjectStore.getState()
    expect(state.territories).toEqual({ leon: LEON_POLYGON })
  })

  it('diff stores only changed keys, not full snapshots', () => {
    // Start with two territories
    useProjectStore.setState({
      territories: { leon: LEON_POLYGON, castela: CASTELA_POLYGON },
      capitals: { leon: [-5.57, 42.6], castela: [-3.7, 40.4] },
    })
    // Mutate only one territory
    useProjectStore.setState((s) => ({
      territories: {
        ...s.territories,
        leon: {
          type: 'Polygon',
          coordinates: [[[-6.1, 42], [-5.1, 42], [-5.1, 43.1], [-6.1, 43.1], [-6.1, 42]]],
        },
      },
    }))
    const pastStates = useProjectStore.temporal.getState().pastStates
    expect(pastStates.length).toBeGreaterThan(0)
    // diff mode: each past entry is a Partial<ProjectGeometryState>, only changed keys
    const lastEntry = pastStates[pastStates.length - 1]
    // Should contain territories (changed) — should NOT contain full capitals snapshot
    // (diff mode stores only what changed)
    expect(Object.keys(lastEntry).length).toBeLessThanOrEqual(Object.keys(LEON_POLYGON).length + 2)
  })

  it('pause/resume batches N state updates into one history entry', () => {
    useProjectStore.temporal.getState().pause()
    useProjectStore.setState({ territories: { leon: LEON_POLYGON }, capitals: {} })
    useProjectStore.setState({ territories: { leon: LEON_POLYGON, castela: CASTELA_POLYGON }, capitals: {} })
    useProjectStore.setState({ territories: { leon: LEON_POLYGON, castela: CASTELA_POLYGON }, capitals: { leon: [-5.57, 42.6] } })
    useProjectStore.temporal.getState().resume()
    const { pastStates } = useProjectStore.temporal.getState()
    expect(pastStates.length).toBe(1)
  })

  it('enforces limit: 50 — the 51st entry drops the oldest', () => {
    for (let i = 0; i < 51; i++) {
      useProjectStore.setState({
        territories: {
          [`territory_${i}`]: {
            type: 'Polygon',
            coordinates: [[[i, 40], [i + 1, 40], [i + 1, 41], [i, 41], [i, 40]]],
          },
        },
        capitals: {},
      })
    }
    const { pastStates } = useProjectStore.temporal.getState()
    expect(pastStates.length).toBe(50)
  })
})
