import { create } from 'zustand'
import type { CfgOverrides, StageView } from '../api/render'

/**
 * D-05 + D-08: per-slider value + bounds; PARAM_DEFAULTS + PARAM_BOUNDS frozen here
 * (single source of truth for SliderCard render + clamp logic).
 */
export const PARAM_DEFAULTS = {
  smooth_sigma: 3.0,
  median_passes: 8,
  fragment_min_px: 600,
  blob_merge_px: 200,
} as const

export const PARAM_BOUNDS = {
  smooth_sigma: { min: 3.0, max: 4.5, step: 0.1 },
  median_passes: { min: 1, max: 12, step: 1 },
  fragment_min_px: { min: 0, max: 2000, step: 50 },
  blob_merge_px: { min: 0, max: 500, step: 25 },
} as const

export type SliderKey = keyof typeof PARAM_DEFAULTS

export interface PipelineParamsState {
  // Locally-edited slider values (current UI state)
  values: Record<SliderKey, number>
  // Last successfully POSTed values (for diff computation)
  lastRendered: Record<SliderKey, number>
  // Snapshot of values captured just before a render is dispatched.
  // Used by revertValues() to restore the slider UI on cancel (SC-4 D-13).
  preRenderValues: Record<SliderKey, number> | null
  // Stage view client-only — never sent to /generate; passed as body param to /render
  stageView: StageView
  // Sidebar collapse state
  sidebarOpen: boolean

  setValue: (key: SliderKey, value: number) => void
  resetSlider: (key: SliderKey) => void
  resetAll: () => void
  setStageView: (view: StageView) => void
  setSidebarOpen: (open: boolean) => void
  // Called by ParameterSidebar after a successful POST /render to mark which
  // values were rendered (for next diff). Captures preRenderValues snapshot first.
  markRendered: (values: Record<SliderKey, number>) => void
  // Called by useRenderStream on cancel to restore values to the pre-render snapshot.
  revertValues: () => void
}

export const usePipelineParams = create<PipelineParamsState>((set) => ({
  values: { ...PARAM_DEFAULTS },
  lastRendered: { ...PARAM_DEFAULTS },
  preRenderValues: null,
  stageView: 'render-final',
  sidebarOpen: true,

  setValue: (key, value) => set((s) => ({ values: { ...s.values, [key]: value } })),
  resetSlider: (key) =>
    set((s) => ({ values: { ...s.values, [key]: PARAM_DEFAULTS[key] } })),
  resetAll: () => set({ values: { ...PARAM_DEFAULTS } }),
  setStageView: (stageView) => set({ stageView }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  // Captures a snapshot of the PREVIOUSLY rendered values (lastRendered) before
  // overwriting it. The snapshot is used by revertValues() to restore the slider
  // UI on cancel — it represents the state that was correctly painted to canvas
  // before this render was triggered. (SC-4 D-13 cancel revert)
  markRendered: (values) =>
    set((s) => ({
      preRenderValues: { ...s.lastRendered },  // snapshot of prior painted state
      lastRendered: { ...values },
    })),
  // Restores slider values AND lastRendered to the pre-render snapshot on cancel.
  // Reverting lastRendered ensures the next slider change diffs against the render
  // that actually persists on canvas (not the cancelled one).
  // Falls back to PARAM_DEFAULTS if no snapshot exists (e.g., first-ever render).
  revertValues: () =>
    set((s) => ({
      values: s.preRenderValues ? { ...s.preRenderValues } : { ...PARAM_DEFAULTS },
      lastRendered: s.preRenderValues ? { ...s.preRenderValues } : { ...PARAM_DEFAULTS },
      preRenderValues: null,
    })),
}))

export function diffOverrides(
  values: Record<SliderKey, number>,
  lastRendered: Record<SliderKey, number>,
): CfgOverrides {
  const diff: CfgOverrides = {}
  for (const key of Object.keys(values) as SliderKey[]) {
    if (values[key] !== lastRendered[key]) {
      diff[key] = values[key]
    }
  }
  return diff
}
