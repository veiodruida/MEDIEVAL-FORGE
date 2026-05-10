import { useDebouncedCallback } from 'use-debounce'
import { usePipelineParams, diffOverrides } from '../stores/usePipelineParams'
import { useRunStore } from '../stores/useRunStore'
import { postRender, postRenderCancel } from '../api/render'

/**
 * D-07 latest-wins dispatch hook: wraps the 250ms debounced render trigger.
 *
 * Latest-wins sequence (D-07):
 *   1. Cancel any in-flight render (POST /render/cancel — 404 treated as success).
 *   2. Compute diff of current values vs last rendered.
 *   3. If diff is non-empty, POST /render with overrides + stage_view.
 *   4. startRender(runId) → useRunStore transitions to 'rendering'.
 *   5. markRendered(values) → records the values just dispatched.
 *
 * Reset path: call returned `dispatch.flush()` to bypass the 250ms debounce
 * (use-debounce v10 DebouncedState exposes `.flush()` for immediate invocation).
 *
 * Note: This hook is separated from usePipelineParams to isolate the projectId
 * dependency and keep usePipelineParams a pure Zustand store with no side effects.
 * ParameterSidebar consumes this hook and wires the SSE subscription.
 */
export function useParameterStudioDispatch(
  projectId: string,
  onRenderStarted?: (runId: string) => void,
) {
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
      onRenderStarted?.(run_id)
    } catch (e) {
      const msg = (e as Error).message
      useRunStore.getState().finish('error', msg)
    }
  }, 250)

  return dispatch
}
