import { describe, it, expect, beforeEach } from 'vitest'
import { usePipelineStore } from '../usePipelineStore'

function getState() {
  return usePipelineStore.getState()
}

function reset() {
  usePipelineStore.getState().reset()
}

describe('usePipelineStore', () => {
  beforeEach(() => {
    reset()
  })

  it('has default state: currentStep=1, every step.status=pending', () => {
    const state = getState()
    expect(state.currentStep).toBe(1)
    expect(state.steps.osm.status).toBe('pending')
    expect(state.steps.baronies.status).toBe('pending')
    expect(state.steps.research.status).toBe('pending')
    expect(state.steps.map.status).toBe('pending')
    expect(state.steps.codex.status).toBe('pending')
  })

  it('setCurrentStep(3) updates currentStep to 3', () => {
    getState().setCurrentStep(3)
    expect(getState().currentStep).toBe(3)
  })

  it('setStepStatus("research", "done") sets steps.research.status to done', () => {
    getState().setStepStatus('research', 'done')
    expect(getState().steps.research.status).toBe('done')
  })

  it('setStepProvider("research", "llamacpp", "high") sets providerId+effort', () => {
    getState().setStepProvider('research', 'llamacpp', 'high')
    const research = getState().steps.research
    expect(research.providerId).toBe('llamacpp')
    expect(research.effort).toBe('high')
  })

  it('setBaroniesGranularity(250) sets steps.baronies.granularity to 250', () => {
    getState().setBaroniesGranularity(250)
    expect(getState().steps.baronies.granularity).toBe(250)
  })

  it('reset() returns to default state', () => {
    getState().setCurrentStep(4)
    getState().setStepStatus('osm', 'done')
    getState().setBaroniesGranularity(1000)
    getState().reset()
    const state = getState()
    expect(state.currentStep).toBe(1)
    expect(state.steps.osm.status).toBe('pending')
    expect(state.steps.baronies.granularity).toBe(250)
  })
})
