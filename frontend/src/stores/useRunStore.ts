import { create } from 'zustand'

/**
 * useRunStore — SSE-driven run state machine for Phase 03 read-only canvas.
 *
 * Owns the lifecycle of a single in-flight pipeline run:
 *   idle → ingesting → generating → generated | error
 *
 * The 12 canonical pipeline stages match the cfg.on_stage emit order from
 * Plan 04-01 (services/pipeline/__init__.py). Each stage emits {start, done}
 * pairs that this store translates into currentStage / completedStages.
 *
 * logLines is capped at LOG_CAP=500 entries; once exceeded, the oldest entry
 * is dropped (FIFO via slice(-LOG_CAP)). Mitigates T-03-FE-PLUMB-01 — the
 * accumulator cannot grow unbounded if the pipeline streams thousands of
 * lines on a long run.
 */
export const PIPELINE_STAGES = [
  'landmask',
  'border',
  'voronoi',
  'median',
  'fragment',
  'smooth',
  'merge',
  'hierarchy',
  'render',
  'lookup',
  'metadata',
  'export',
] as const

export type PipelineStage = (typeof PIPELINE_STAGES)[number]

export type RunState = 'idle' | 'ingesting' | 'generating' | 'generated' | 'error'

export const LOG_CAP = 500

export interface RunStoreState {
  state: RunState
  runId: string | null
  currentStage: PipelineStage | null
  completedStages: PipelineStage[]
  logLines: string[]
  errorMessage: string | null
  errorStage: PipelineStage | null

  start: (runId: string, kind: 'ingesting' | 'generating') => void
  appendLog: (line: string) => void
  startStage: (stage: PipelineStage) => void
  finishStage: (stage: PipelineStage) => void
  finish: (
    state: 'generated' | 'error',
    errorMessage?: string,
    errorStage?: PipelineStage,
  ) => void
  reset: () => void
}

const INITIAL: Omit<
  RunStoreState,
  'start' | 'appendLog' | 'startStage' | 'finishStage' | 'finish' | 'reset'
> = {
  state: 'idle',
  runId: null,
  currentStage: null,
  completedStages: [],
  logLines: [],
  errorMessage: null,
  errorStage: null,
}

export const useRunStore = create<RunStoreState>((set) => ({
  ...INITIAL,

  start: (runId, kind) =>
    set({
      state: kind,
      runId,
      currentStage: null,
      completedStages: [],
      logLines: [],
      errorMessage: null,
      errorStage: null,
    }),

  appendLog: (line) =>
    set((s) => ({
      logLines: [...s.logLines, line].slice(-LOG_CAP),
    })),

  startStage: (stage) => set({ currentStage: stage }),

  finishStage: (stage) =>
    set((s) => {
      // Idempotent — calling finishStage twice for the same stage is a no-op
      // beyond clearing currentStage. Mirrors the cfg.on_stage('done') contract
      // which guarantees order but not uniqueness across producer retries.
      if (s.completedStages.includes(stage)) {
        return { currentStage: s.currentStage === stage ? null : s.currentStage }
      }
      return {
        completedStages: [...s.completedStages, stage],
        currentStage: s.currentStage === stage ? null : s.currentStage,
      }
    }),

  finish: (state, errorMessage, errorStage) =>
    set({
      state,
      errorMessage: errorMessage ?? null,
      errorStage: errorStage ?? null,
    }),

  reset: () => set({ ...INITIAL }),
}))
