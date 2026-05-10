/**
 * Wave 0 stub for Plan 04-03. DO NOT add production imports until 04-03
 * implementation. Keeping `it.skip` lets vitest run green and lets <verify>
 * commands in implementation plans return exit 0 with `skipped` reports.
 */
import { describe, it } from 'vitest'

describe('useRenderStream', () => {
  it.skip('subscribes to /api/v3/projects/{id}/render/stream', () => {})
  it.skip('translates stage_start envelope to runStore.startStage', () => {})
  it.skip('translates stage_done envelope to runStore.finishStage', () => {})
  it.skip('translates stage_cancel envelope to runStore.revertStage', () => {})
  it.skip('handles done envelope by closing EventSource and finish(generated)', () => {})
})
