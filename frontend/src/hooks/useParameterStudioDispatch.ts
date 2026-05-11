import { useRef } from 'react'
import { useDebouncedCallback } from 'use-debounce'
import { usePipelineParams, diffOverrides } from '../stores/usePipelineParams'
import { useRunStore } from '../stores/useRunStore'
import { postRender, postRenderCancel } from '../api/render'

/**
 * D-07 latest-wins dispatch hook (Phase 04) + D-04 bounded RENDER_BUSY retry (Phase 04.1).
 *
 * Latest-wins sequence (D-07):
 *   1. Cancel any in-flight render (POST /render/cancel — 404 treated as success).
 *   2. Compute diff of current values vs last rendered.
 *   3. If diff is non-empty, POST /render with overrides + stage_view.
 *   4. startRender(runId) → useRunStore transitions to 'rendering'.
 *   5. markRendered(values) → records the values just dispatched.
 *
 * RENDER_BUSY race recovery (D-04 / WR-01 + Phase 04.1 bounded extension):
 *   postRenderCancel(200) only means stop_event is set — the worker thread
 *   takes ~0.5s to reach the next _check_cancel before is_run_alive() flips
 *   to None. A debounce timer firing in that window receives 409 from /render.
 *   Instead of transitioning the store to 'error', we re-queue the dispatch
 *   via the DebouncedState ref. Bounded to 3 retries within a 1.5s window
 *   (per 04.1-CONTEXT.md D-04). On the 4th consecutive 409, surface
 *   useRunStore.finish('error', 'RENDER_BUSY') — real backend failure, not race.
 *
 *   Counter resets on:
 *   - any successful postRender (run_id returned)
 *   - the 1.5s window expiring with no new 409 (next 409 starts at attempt 1)
 *
 * Reset path: call returned `dispatch.flush()` to bypass the 250ms debounce
 * (use-debounce v10 DebouncedState exposes `.flush()` for immediate invocation).
 *
 * Note: This hook is separated from usePipelineParams to isolate the projectId
 * dependency and keep usePipelineParams a pure Zustand store with no side effects.
 * ParameterSidebar consumes this hook and wires the SSE subscription.
 */
export const RENDER_BUSY_MAX_RETRIES = 3
export const RENDER_BUSY_WINDOW_MS = 1500

export function useParameterStudioDispatch(
  projectId: string,
  onRenderStarted?: (runId: string) => void,
) {
  // Per-(project_id) retry state to support multiple open projects without
  // sharing counter state (T-04.1-02-02 mitigation).
  const retryState = useRef<Map<string, { count: number; windowStart: number }>>(new Map())

  const dispatch = useDebouncedCallback(async () => {
    const { values, lastRendered, stageView } = usePipelineParams.getState()
    const diff = diffOverrides(values, lastRendered)
    if (Object.keys(diff).length === 0) return
    // Latest-wins (D-07): cancel the in-flight render (if any) before posting new.
    await postRenderCancel(projectId).catch(() => {})
    try {
      const { run_id } = await postRender(projectId, diff, stageView)
      useRunStore.getState().startRender(run_id)
      usePipelineParams.getState().markRendered(values)
      // Success: clear retry counter for this project (D-04).
      retryState.current.delete(projectId)
      onRenderStarted?.(run_id)
    } catch (e) {
      const msg = (e as Error).message
      if (msg === 'RENDER_BUSY') {
        const now = Date.now()
        const entry = retryState.current.get(projectId)
        // Reset counter if no entry yet, or the 1.5s window has expired.
        const fresh =
          entry === undefined || now - entry.windowStart >= RENDER_BUSY_WINDOW_MS
        const nextCount = fresh ? 1 : entry!.count + 1
        const windowStart = fresh ? now : entry!.windowStart
        retryState.current.set(projectId, { count: nextCount, windowStart })
        if (nextCount <= RENDER_BUSY_MAX_RETRIES) {
          // Re-queue the debounced dispatch — DebouncedState exposes the call
          // form to re-trigger at the 250ms debounce.
          dispatch()
          return
        }
        // Exhausted retries within the window — real backend failure.
        retryState.current.delete(projectId)
        useRunStore.getState().finish('error', 'RENDER_BUSY')
        return
      }
      useRunStore.getState().finish('error', msg)
    }
  }, 250)

  return dispatch
}
