import { create } from 'zustand'

/**
 * Phase 04 Plan 04-03 staging store. Phase 04 Plan 04-04 will migrate this state
 * into useRunStore via the 'rendering' state extension + revertStage/cancelRender
 * actions; until then, this store decouples the slider/toolbar plumbing from the
 * useRunStore type union so file ownership stays exclusive across Wave 3 plans.
 *
 * State machine (this store only):
 *   idle → rendering → idle | error
 * Cancel sets state back to 'idle' and stores priorTokens so CanvasViewer can
 * re-hydrate against the cached prior token (Plan 04-04 wires the canvas side).
 */
export type RenderState = 'idle' | 'rendering' | 'error'

export interface RenderStoreState {
  state: RenderState
  runId: string | null
  affectedStages: string[]
  priorTokens: Record<string, string>  // stage → prior_token (D-13 cancel revert)
  errorMessage: string | null
  startRender: (runId: string) => void
  revertStage: (stage: string, priorToken: string) => void
  finishRender: (state: 'idle' | 'error', errorMessage?: string) => void
  reset: () => void
}

const INITIAL = {
  state: 'idle' as RenderState,
  runId: null,
  affectedStages: [],
  priorTokens: {},
  errorMessage: null,
}

export const useRenderStore = create<RenderStoreState>((set) => ({
  ...INITIAL,
  startRender: (runId) => set({ state: 'rendering', runId, priorTokens: {}, errorMessage: null }),
  revertStage: (stage, priorToken) =>
    set((s) => ({ priorTokens: { ...s.priorTokens, [stage]: priorToken } })),
  finishRender: (state, errorMessage) => set({ state, errorMessage: errorMessage ?? null }),
  reset: () => set(INITIAL),
}))
