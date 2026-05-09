import { describe, it, expect, beforeEach } from 'vitest'
import { useRunStore, PIPELINE_STAGES, LOG_CAP } from '../useRunStore'

beforeEach(() => {
  useRunStore.getState().reset()
})

describe('useRunStore — initial state', () => {
  it('test_initial_state_is_idle: every field matches the documented baseline', () => {
    const s = useRunStore.getState()
    expect(s.state).toBe('idle')
    expect(s.runId).toBeNull()
    expect(s.currentStage).toBeNull()
    expect(s.completedStages).toEqual([])
    expect(s.logLines).toEqual([])
    expect(s.errorMessage).toBeNull()
    expect(s.errorStage).toBeNull()
  })

  it('test_pipeline_stages_tuple: 11 canonical stages in canonical order', () => {
    expect(PIPELINE_STAGES).toEqual([
      'landmask',
      'border',
      'voronoi',
      'cleanup',
      'smooth',
      'merge',
      'hierarchy',
      'render',
      'lookup',
      'metadata',
      'export',
    ])
    expect(PIPELINE_STAGES.length).toBe(11)
  })
})

describe('useRunStore — start action', () => {
  it('test_start_generating_flips_state_and_clears_buffers', () => {
    // Pre-populate to confirm clear-on-start semantics
    useRunStore.setState({
      logLines: ['old line'],
      completedStages: ['landmask'],
      errorMessage: 'previous error',
    })
    useRunStore.getState().start('run-123', 'generating')
    const s = useRunStore.getState()
    expect(s.state).toBe('generating')
    expect(s.runId).toBe('run-123')
    expect(s.completedStages).toEqual([])
    expect(s.logLines).toEqual([])
    expect(s.errorMessage).toBeNull()
  })

  it('test_start_ingesting_sets_state_to_ingesting', () => {
    useRunStore.getState().start('run-456', 'ingesting')
    expect(useRunStore.getState().state).toBe('ingesting')
    expect(useRunStore.getState().runId).toBe('run-456')
  })
})

describe('useRunStore — appendLog action', () => {
  it('test_appendLog_pushes_one_line', () => {
    useRunStore.getState().appendLog('hello')
    expect(useRunStore.getState().logLines).toEqual(['hello'])
  })

  it('test_appendLog_caps_at_500_dropping_oldest', () => {
    const store = useRunStore.getState()
    for (let i = 0; i < 600; i++) store.appendLog(`line-${i}`)
    const lines = useRunStore.getState().logLines
    expect(lines.length).toBe(LOG_CAP)
    expect(lines.length).toBe(500)
    // Oldest dropped: line-0 .. line-99 gone; line-100 is the new front
    expect(lines[0]).toBe('line-100')
    expect(lines[lines.length - 1]).toBe('line-599')
  })
})

describe('useRunStore — startStage / finishStage actions', () => {
  it('test_startStage_sets_currentStage', () => {
    useRunStore.getState().startStage('voronoi')
    expect(useRunStore.getState().currentStage).toBe('voronoi')
  })

  it('test_finishStage_pushes_and_clears_currentStage', () => {
    useRunStore.getState().startStage('voronoi')
    useRunStore.getState().finishStage('voronoi')
    const s = useRunStore.getState()
    expect(s.completedStages).toEqual(['voronoi'])
    expect(s.currentStage).toBeNull()
  })

  it('test_finishStage_is_idempotent: second call does NOT duplicate', () => {
    useRunStore.getState().finishStage('voronoi')
    useRunStore.getState().finishStage('voronoi')
    expect(useRunStore.getState().completedStages).toEqual(['voronoi'])
  })
})

describe('useRunStore — finish action', () => {
  it('test_finish_generated_preserves_runId_log_completedStages', () => {
    useRunStore.getState().start('run-789', 'generating')
    useRunStore.getState().appendLog('working…')
    useRunStore.getState().finishStage('landmask')
    useRunStore.getState().finish('generated')
    const s = useRunStore.getState()
    expect(s.state).toBe('generated')
    expect(s.runId).toBe('run-789')
    expect(s.logLines).toEqual(['working…'])
    expect(s.completedStages).toEqual(['landmask'])
    expect(s.errorMessage).toBeNull()
    expect(s.errorStage).toBeNull()
  })

  it('test_finish_error_sets_errorMessage_and_errorStage', () => {
    useRunStore.getState().start('run-789', 'generating')
    useRunStore.getState().finish('error', 'EOFError', 'voronoi')
    const s = useRunStore.getState()
    expect(s.state).toBe('error')
    expect(s.errorMessage).toBe('EOFError')
    expect(s.errorStage).toBe('voronoi')
  })
})

describe('useRunStore — reset action', () => {
  it('test_reset_returns_to_initial_state', () => {
    const store = useRunStore.getState()
    store.start('run-x', 'generating')
    store.appendLog('something')
    store.startStage('voronoi')
    store.finishStage('voronoi')
    store.finish('error', 'oops', 'voronoi')
    store.reset()
    const s = useRunStore.getState()
    expect(s.state).toBe('idle')
    expect(s.runId).toBeNull()
    expect(s.currentStage).toBeNull()
    expect(s.completedStages).toEqual([])
    expect(s.logLines).toEqual([])
    expect(s.errorMessage).toBeNull()
    expect(s.errorStage).toBeNull()
  })
})
