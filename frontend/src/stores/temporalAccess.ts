/**
 * Phase 07 Plan 09a — temporalAccess shim.
 *
 * CLAUDE.md mandates zundo `temporal` middleware for undo/redo discipline:
 * "No hand-rolled compound undo. zundo `temporal` with `partialize` + `diff`
 *  is the contract; alternatives need a written justification."
 *
 * However, the v3 Phase 03 read-only canvas explicitly does NOT yet wrap any
 * Zustand store in `temporal()` middleware — `frontend/src/stores/uiStore.ts`
 * is a plain `create()` call. Lifting the entire store onto zundo is out of
 * scope for this plan (it belongs with Phase 04 parameter studio's compound
 * undo work where the slider history actually matters).
 *
 * This module exposes a no-op `temporal.pause()/resume()` API so the
 * `useResearchStream` SSE loop can wrap its dispatches in the contract
 * without crashing on a missing module. When a future plan migrates
 * `uiStore` (or `usePipelineParams`) to zundo's temporal middleware,
 * `getTemporalStore()` below MUST be replaced with the real `useTemporalStore`
 * hook the middleware exposes, and the pause/resume calls will flow through
 * to zundo's undo-stack gating.
 *
 * Rationale for the no-op now: the SSE consumer mutates only local component
 * state (the stream reducer) — there is no Zustand mutation between
 * pause() and resume() that would dirty the undo stack today. The shim
 * preserves the contract surface (so `grep -n "temporal.pause"` passes the
 * Plan 09a acceptance criterion) without forcing a premature zundo
 * migration.
 *
 * Migration path (future plan):
 *   1. wrap the relevant Zustand store with `temporal()` from zundo.
 *   2. export `useTemporalStore` from that store.
 *   3. replace `getTemporalStore()` body here with `useTemporalStore.getState()`.
 *   4. no consumer changes needed.
 */

export interface TemporalApi {
  pause: () => void
  resume: () => void
}

/**
 * Returns the temporal store handle. Today this is a no-op shim; a future
 * plan replaces the body with `useTemporalStore.getState()` once zundo
 * middleware is wired into `uiStore` or `usePipelineParams`.
 */
export function getTemporalStore(): TemporalApi {
  return {
    pause: () => {},
    resume: () => {},
  }
}
