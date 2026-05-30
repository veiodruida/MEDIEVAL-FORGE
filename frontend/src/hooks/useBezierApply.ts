/**
 * Phase 08.2 Plan 03 — useBezierApply hook
 *
 * Implements the Apply convergence flow per UI-SPEC §Interaction Contract:
 *   1. POST snapshot with { trigger:'manual', payload: { geojson:{}, region_config:{},
 *      edit_log: editLog, vertices } }  ← edit_log SNAKE_CASE (Pitfall 0)
 *   2. await postRender(projectId, {}, stageView) DIRECTLY — NOT via dispatch/diffOverrides
 *      (Pitfall 3: diffOverrides({}, lastRendered) is empty → silent no-op)
 *   3. useRunStore.getState().startRender(run_id)
 *   4. On 'rendering' → 'generated' transition: clear editLog via
 *      temporal.pause(); useEditorStore.setState({ editLog: [] }); temporal.resume()
 *
 * barony_name_to_idx is NEVER sent by the frontend (constraint #5 — backend builds it
 * from bars in _render_producer).
 *
 * baroniesQ refetch is automatic via cacheVersion (project.updated_at bump) — no
 * explicit refetch call needed.
 *
 * Threat mitigations:
 *   T-08.2-01: MAX_VERTEX_KEYS cap guard aborts Apply before POST if vertices exceed limit.
 *   T-08.2-05: edit_log (snake_case) enforced; never 'editLog' as a payload key.
 */
import { useEffect, useRef } from 'react'
import { useEditorStore } from '../stores/useEditorStore'
import { useRunStore } from '../stores/useRunStore'
import { postRender } from '../api/render'
import { usePipelineParams } from '../stores/usePipelineParams'
import type { StageView } from '../api/render'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * MAX_VERTEX_KEYS fallback (T-08.2-01 / ASVS V5).
 * When baronies count is not available, cap at this generous constant to prevent
 * oversized snapshot payloads. Derived as nb_typical_max * 200 (200 vertices/barony).
 * nb_typical_max = 200 baronies (Iberia has ~92 baronies; 200 is 2x headroom).
 */
export const MAX_VERTEX_KEYS_FALLBACK = 200 * 200 // 40 000

function snapshotUrl(projectId: string, branchId: string): string {
  return `/api/v3/projects/${projectId}/branches/${branchId}/snapshots`
}

// ---------------------------------------------------------------------------
// Core apply function (shared by manual + auto-immediate paths)
// ---------------------------------------------------------------------------

async function runApply(
  projectId: string,
  branchId: string,
  stageView: StageView | undefined,
  pendingApplyRef: React.MutableRefObject<boolean>,
): Promise<void> {
  const { vertices, editLog } = useEditorStore.getState()

  // T-08.2-01: cap guard — abort if vertices dict is oversized
  if (Object.keys(vertices).length > MAX_VERTEX_KEYS_FALLBACK) {
    console.warn('[useBezierApply] Apply aborted: vertices exceed MAX_VERTEX_KEYS_FALLBACK')
    return
  }

  // Step 1: POST snapshot
  // Payload uses edit_log (snake_case) — NOT camelCase editLog (Pitfall 0 / T-08.2-05)
  // barony_name_to_idx is NOT included (constraint #5 — backend builds from bars)
  const snapshotBody = {
    trigger: 'manual' as const,
    payload: {
      geojson: {},
      region_config: {},
      edit_log: editLog,
      vertices,
    },
  }

  const snapRes = await fetch(snapshotUrl(projectId, branchId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshotBody),
  })

  if (!snapRes.ok) {
    console.warn('[useBezierApply] Snapshot POST failed:', snapRes.status)
    return
  }

  // Mark a pending Apply so the subscription only clears editLog for OUR render
  pendingApplyRef.current = true

  // Step 2: call postRender DIRECTLY (not via dispatch/diffOverrides — Pitfall 3)
  const effectiveStageView = stageView ?? usePipelineParams.getState().stageView
  let run_id: string
  try {
    const resp = await postRender(projectId, {}, effectiveStageView)
    run_id = resp.run_id
  } catch (err) {
    pendingApplyRef.current = false
    console.warn('[useBezierApply] postRender failed:', err)
    return
  }

  // Step 3: transition RunStore to rendering
  useRunStore.getState().startRender(run_id)
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseBezierApplyReturn {
  /** Manual Apply: POST snapshot then postRender directly. */
  handleApplyEdits: (stageView?: StageView) => Promise<void>
  /** Auto-immediate Apply: same flow as handleApplyEdits, called after each edit. */
  triggerAutoApply: (stageView?: StageView) => Promise<void>
}

export function useBezierApply(
  projectId: string,
  branchId: string,
): UseBezierApplyReturn {
  // Ref to guard the render-success subscription: only clear editLog for a render
  // that THIS hook's Apply initiated. Prevents an unrelated parameter-studio render
  // from clearing a user's in-progress Bézier edits.
  const pendingApplyRef = useRef(false)

  // Subscribe to useRunStore transitions: 'rendering' → 'generated'
  // Must be inside useEffect to: (a) avoid leaking on re-renders, (b) run cleanup on unmount.
  useEffect(() => {
    let prevState = useRunStore.getState().state

    const unsubscribe = useRunStore.subscribe((next) => {
      const prevS = prevState
      prevState = next.state

      // Only fire when: prev=rendering, next=generated, AND this hook's Apply is pending
      if (prevS === 'rendering' && next.state === 'generated' && pendingApplyRef.current) {
        pendingApplyRef.current = false

        // Clear editLog via temporal.pause → setState → resume
        // This prevents the reset from appearing in undo history (UI-SPEC Note 8)
        // and triggers the editLog.length > 0 overlay guard to hide the overlay.
        const temporal = useEditorStore.temporal.getState()
        temporal.pause()
        useEditorStore.setState({ editLog: [] })
        temporal.resume()
      }
    })

    return () => {
      unsubscribe()
    }
  }, [])

  const handleApplyEdits = async (stageView?: StageView): Promise<void> => {
    await runApply(projectId, branchId, stageView, pendingApplyRef)
  }

  const triggerAutoApply = async (stageView?: StageView): Promise<void> => {
    // Auto-immediate: same flow as manual, posts a FRESH snapshot each time
    // (does NOT rely on the 25-edit auto-snapshot cadence — RESEARCH §492-497)
    await runApply(projectId, branchId, stageView, pendingApplyRef)
  }

  return { handleApplyEdits, triggerAutoApply }
}
