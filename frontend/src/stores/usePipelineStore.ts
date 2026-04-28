import { create } from 'zustand'

export type StepId = 1 | 2 | 3 | 4 | 5
export type StepStatus = 'pending' | 'active' | 'done' | 'error'
export type Effort = 'low' | 'medium' | 'high'

export interface StepBase {
  status: StepStatus
  output?: unknown
  error?: string
}

export interface AIStep extends StepBase {
  providerId?: string
  effort?: Effort
}

export interface PipelineSteps {
  osm: StepBase
  baronies: StepBase & { granularity: number | 'all' }
  research: AIStep & { edited?: boolean }
  map: StepBase
  codex: AIStep & { sections?: Record<string, StepStatus> }
}

export interface PipelineState {
  currentStep: StepId
  steps: PipelineSteps
  setCurrentStep: (s: StepId) => void
  setStepStatus: (key: keyof PipelineSteps, status: StepStatus) => void
  setStepProvider: (key: 'research' | 'codex', providerId: string, effort: Effort) => void
  setBaroniesGranularity: (g: number | 'all') => void
  reset: () => void
}

const DEFAULT_STEPS: PipelineSteps = {
  osm: { status: 'pending' },
  baronies: { status: 'pending', granularity: 250 },
  research: { status: 'pending' },
  map: { status: 'pending' },
  codex: { status: 'pending', sections: {} },
}

function makeDefaultState(): Pick<PipelineState, 'currentStep' | 'steps'> {
  return {
    currentStep: 1,
    steps: {
      osm: { status: 'pending' },
      baronies: { status: 'pending', granularity: 250 },
      research: { status: 'pending' },
      map: { status: 'pending' },
      codex: { status: 'pending', sections: {} },
    },
  }
}

// NOTE: Plain create() — no zundo/temporal middleware. Pipeline navigation
// state is transient workflow state that must NOT be recorded in undo/redo
// history (§H decision in hazy-hatching-abelson plan).
export const usePipelineStore = create<PipelineState>()((set) => ({
  ...makeDefaultState(),

  setCurrentStep: (s) => set({ currentStep: s }),

  setStepStatus: (key, status) =>
    set((state) => ({
      steps: {
        ...state.steps,
        [key]: { ...state.steps[key], status },
      },
    })),

  setStepProvider: (key, providerId, effort) =>
    set((state) => ({
      steps: {
        ...state.steps,
        [key]: { ...state.steps[key], providerId, effort },
      },
    })),

  setBaroniesGranularity: (g) =>
    set((state) => ({
      steps: {
        ...state.steps,
        baronies: { ...state.steps.baronies, granularity: g },
      },
    })),

  reset: () => set(makeDefaultState()),
}))

// Silence unused var warning for DEFAULT_STEPS
void DEFAULT_STEPS
