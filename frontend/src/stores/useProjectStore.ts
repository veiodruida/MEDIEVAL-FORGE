import { create } from 'zustand'
import { temporal } from 'zundo'
import type {
  ProjectGeometryState,
  GeoJSONPolygon,
  GeoJSONMultiPolygon,
  Position,
} from '../types/editing'

// Explicit geometry slice type used by the diff function and partialize.
// Avoids the `ReturnType<typeof partialize>` self-reference issue in TS.
type GeometrySlice = Pick<ProjectStore, 'territories' | 'capitals'>

interface ProjectStore extends ProjectGeometryState {
  // --- geometry-only state (INCLUDED in partialize) ---
  territories: Record<string, GeoJSONPolygon | GeoJSONMultiPolygon>
  capitals: Record<string, Position>

  // --- transient state (EXCLUDED by partialize — must never enter undo history) ---
  projectId: string | null       // hydrated on project open, not an undoable change
  loading: boolean               // transient flag during fetch

  // --- actions ---
  hydrate: (projectId: string, territories: ProjectStore['territories'], capitals: ProjectStore['capitals']) => void
  setCapital: (condadoId: string, position: Position) => void
  setTerritory: (condadoId: string, geometry: GeoJSONPolygon | GeoJSONMultiPolygon) => void
  applyBatchUpdate: (territories: Partial<ProjectStore['territories']>, capitals: Partial<ProjectStore['capitals']>) => void
  removeTerritories: (ids: string[]) => void
}

// partialize: ONLY geometry enters undo history. projectId + loading are transient.
function partialize(state: ProjectStore): GeometrySlice {
  return {
    territories: state.territories,
    capitals: state.capitals,
  }
}

export const useProjectStore = create<ProjectStore>()(
  temporal(
    (set) => ({
      territories: {},
      capitals: {},
      projectId: null,
      loading: false,

      hydrate: (projectId, territories, capitals) =>
        set({ projectId, territories, capitals, loading: false }),

      setCapital: (condadoId, position) =>
        set((s) => ({ capitals: { ...s.capitals, [condadoId]: position } })),

      setTerritory: (condadoId, geometry) =>
        set((s) => ({ territories: { ...s.territories, [condadoId]: geometry } })),

      applyBatchUpdate: (territories, capitals) =>
        set((s) => ({
          territories: { ...s.territories, ...territories } as ProjectStore['territories'],
          capitals: { ...s.capitals, ...capitals } as ProjectStore['capitals'],
        })),

      removeTerritories: (ids) =>
        set((s) => {
          const nextT = { ...s.territories }
          const nextC = { ...s.capitals }
          for (const id of ids) {
            delete nextT[id]
            delete nextC[id]
          }
          return { territories: nextT, capitals: nextC }
        }),
    }),
    {
      partialize,

      // diff: CRITICAL — NOT diff: true. zundo 2.3.0 requires a function.
      // Pitfall 1 (04-RESEARCH.md): full snapshots at 800 territories = 100-250MB.
      // Store only changed keys (territories delta + capitals delta).
      // NOTE: pastState = what state WAS before the change (values to restore to on undo).
      //       Return PAST values for changed keys so undo restores them correctly.
      diff: (pastState, currentState) => {
        const result: Partial<GeometrySlice> = {}
        let changed = false

        // Compare territories (reference + shallow key-level)
        if (pastState.territories !== currentState.territories) {
          const tDelta: Record<string, GeoJSONPolygon | GeoJSONMultiPolygon> = {}
          const seen = new Set<string>()
          const past = pastState.territories ?? {}
          const curr = currentState.territories ?? {}
          for (const id of Object.keys(curr)) {
            seen.add(id)
            if (past[id] !== curr[id]) {
              // Store the PAST value so undo restores it
              tDelta[id] = past[id]
              changed = true
            }
          }
          for (const id of Object.keys(past)) {
            if (!seen.has(id)) {
              // Key was deleted — store the past value so undo restores it
              tDelta[id] = past[id]
              changed = true
            }
          }
          if (Object.keys(tDelta).length > 0) {
            result.territories = tDelta as GeometrySlice['territories']
          }
        }

        // Compare capitals (same pattern)
        if (pastState.capitals !== currentState.capitals) {
          const cDelta: Record<string, Position> = {}
          const past = pastState.capitals ?? {}
          const curr = currentState.capitals ?? {}
          for (const id of Object.keys(curr)) {
            if (past[id] !== curr[id]) {
              cDelta[id] = past[id]
              changed = true
            }
          }
          // Handle deleted capitals
          for (const id of Object.keys(past)) {
            if (!(id in curr)) {
              cDelta[id] = past[id]
              changed = true
            }
          }
          if (Object.keys(cDelta).length > 0) {
            result.capitals = cDelta as GeometrySlice['capitals']
          }
        }

        return changed ? result : null
      },

      limit: 50,
    },
  ),
)

/**
 * Compound-op batching: augment zundo's pause/resume to record ONE history entry
 * for all mutations between pause() and resume() (D-05 / EDIT-08).
 *
 * zundo 2.3.0 native behavior:
 *   - pause(): sets isTracking=false — drops subsequent state changes from history
 *   - resume(): sets isTracking=true — does NOT flush any accumulated changes
 *
 * We need resume() to record exactly ONE history entry covering all paused changes.
 * Override pause/resume on the temporal store state after creation:
 *   - pause() captures pre-pause partialized state + calls original pause
 *   - resume() sets isTracking=true, then calls _handleSet with the captured
 *     pre-pause snapshot so it records one undo entry for the entire batch.
 */
;(function patchTemporalPauseResume() {
  let prePauseSnapshot: Partial<GeometrySlice> | null = null

  const temporalStore = useProjectStore.temporal

  temporalStore.setState({
    pause: () => {
      // Capture partialized state BEFORE any mutations
      prePauseSnapshot = partialize(useProjectStore.getState())
      // Disable tracking (native zundo behavior)
      temporalStore.setState({ isTracking: false })
    },
    resume: () => {
      // Re-enable tracking FIRST — future setState calls will be tracked again
      temporalStore.setState({ isTracking: true })

      // Now record one history entry for the entire paused batch
      if (prePauseSnapshot !== null) {
        const currentState = partialize(useProjectStore.getState())
        const hasChanged =
          prePauseSnapshot.territories !== currentState.territories ||
          prePauseSnapshot.capitals !== currentState.capitals
        if (hasChanged) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const s = temporalStore.getState() as any
          if (typeof s._handleSet === 'function') {
            s._handleSet(prePauseSnapshot, undefined, currentState, undefined)
          }
        }
        prePauseSnapshot = null
      }
    },
  })
})()

/**
 * beginTransaction / endTransaction: thin wrappers over augmented pause/resume.
 *
 * Research §Pattern 2: use pause()/resume() for compound ops (D-05, EDIT-08).
 * Every async edit (capital drag → N neighbor recalcs) wraps its state mutations
 * between these calls so they register as ONE undo step.
 *
 * Pairs with useEditorStore.pushUndoLabel() — caller pushes label AFTER endTransaction.
 */
export function beginTransaction(): void {
  useProjectStore.temporal.getState().pause()
}

export function endTransaction(): void {
  useProjectStore.temporal.getState().resume()
}
