/**
 * Phase 07 Plan 09a Task 2 — useResearchStream.
 *
 * EventSource consumer for /api/v3/research/stream/{run_id}. Mirrors the
 * lifecycle shape of `useRenderStream` but expresses its state as a single
 * `StreamState` reducer that the ResearchDialog + ResearchProgress can read
 * directly (no Zustand store — research-flow state is dialog-local, unlike
 * pipeline render state which lives in `useRunStore`).
 *
 * Behavioral contract (REVIEWS replan 2026-05-14):
 *
 * - **REVIEWS fix #3 (dual-shape SSE, Plan 03 verdict (a) — KEEP)**: Plan 03
 *   SUMMARY confirmed `retry.py` writes raw `data: Tentativa N/M: ...` SSE
 *   frames directly to the queue in addition to the v3 runner's structured
 *   envelopes. The handler accepts BOTH shapes:
 *     1. Structured JSON envelopes `{event_type, stage, message, progress,
 *        ...}` from the runner (07-RESEARCH §Pattern 5).
 *     2. Raw PT-BR `Tentativa N/M: {summary}` strings emitted by retry.py
 *        line 57.
 *
 * - **REVIEWS fix #7 (AbortError → terminal failed/aborted)**: a real cancel
 *   originating from the user (POST /stop fires an EventSource abort) is
 *   distinguished from a network error so the UI can render "Cancelada"
 *   instead of "Erro". Non-abort EventSource errors map to
 *   `error_code: 'network'`.
 *
 * - **CLAUDE.md zundo discipline**: the SSE loop is wrapped in
 *   `temporal.pause()/resume()` via the `getTemporalStore()` shim
 *   (see `frontend/src/stores/temporalAccess.ts`). Today this is a no-op;
 *   when zundo middleware is wired into uiStore in a future plan, this
 *   shim transparently routes pause/resume to the real undo gate.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { getTemporalStore } from '../stores/temporalAccess'

export type StreamPhase =
  | 'idle'
  | 'starting'
  | 'running'
  | 'succeeded'
  | 'failed'

export type ResearchStage = 'kingdoms' | 'duchies' | 'condados' | 'baronies'

export interface StreamState {
  phase: StreamPhase
  currentStage?: ResearchStage
  completedStages?: ResearchStage[]
  retryAttempt?: { current: number; max: number }
  /** REVIEWS fix #7 — 'aborted' (user cancel) | 'network' (EventSource error) | other backend codes. */
  error_code?: string
  /** REVIEWS fix #7 — human-readable PT-BR. */
  error_message?: string
  /**
   * UAT 2026-05-22 — accumulated raw model output. Backend providers
   * (ollama / llamacpp) forward delta chunks as `token` envelopes so the
   * dialog can render the model's output live. Empty when the provider
   * does not stream (e.g. claude cache-hit, or before the first token).
   */
  modelOutput?: string
  /**
   * UAT 2026-05-23 — last `progress` envelope's message (PT-BR). Providers
   * emit one every 2s while waiting for the first token so the user knows
   * the model is loading / prompt is being processed, not stuck. Cleared
   * once the first token arrives.
   */
  progressMessage?: string
}

interface ResearchSseEnvelope {
  event_type: string
  stage?: ResearchStage | string | null
  message?: string
  progress?: number | null
  status?: 'success' | 'error' | null
  error_code?: string
  attempt?: number
  max_retries?: number
  /** `token` envelope — raw model output delta forwarded by the provider. */
  text?: string
}

const STAGE_SET = new Set<ResearchStage>([
  'kingdoms',
  'duchies',
  'condados',
  'baronies',
])

function isResearchStage(s: unknown): s is ResearchStage {
  return typeof s === 'string' && STAGE_SET.has(s as ResearchStage)
}

const RETRY_RE = /^Tentativa\s+(\d+)\s*\/\s*(\d+)/

export interface ResearchStreamHandle {
  subscribe: (runId: string) => void
  close: () => void
  state: StreamState
}

export function useResearchStream(): ResearchStreamHandle {
  const esRef = useRef<EventSource | null>(null)
  const [state, setState] = useState<StreamState>({ phase: 'idle' })

  // Internal — close ES only, keep state. Used by the onerror path so the
  // failed phase survives until something else resets it.
  const closeEventSource = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [])

  // Public — close ES AND reset state to idle so reopening the dialog
  // doesn't show stale errors from the previous run.
  const close = useCallback(() => {
    closeEventSource()
    setState({ phase: 'idle' })
  }, [closeEventSource])

  const subscribe = useCallback(
    (runId: string) => {
      close()
      const url = `/api/v3/research/stream/${runId}`
      const es = new EventSource(url)
      esRef.current = es

      setState({ phase: 'starting', modelOutput: '' })

      es.onmessage = (e: MessageEvent) => {
        // CLAUDE.md zundo discipline — temporal.pause/resume wraps every
        // SSE-driven state mutation so the undo stack stays clean.
        const temporal = getTemporalStore()
        temporal.pause()
        try {
          handleMessage(e, setState)
        } finally {
          temporal.resume()
        }
      }

      es.onerror = (e: Event) => {
        // REVIEWS fix #7 — distinguish user-initiated abort from network errors.
        if (e instanceof DOMException && e.name === 'AbortError') {
          setState({
            phase: 'failed',
            error_code: 'aborted',
            error_message: 'Pesquisa cancelada pelo usuário.',
          })
        } else {
          // Do NOT clobber a terminal state we already received via onmessage.
          // The SSE replay path (backend serving last-terminal for fast
          // failures) closes the connection immediately after one event;
          // EventSource fires onerror on close, which would otherwise hide
          // the real backend message under a generic "network failure".
          setState((prev) =>
            prev.phase === 'failed' || prev.phase === 'succeeded'
              ? prev
              : {
                  phase: 'failed',
                  error_code: 'network',
                  error_message: 'Falha de rede durante a pesquisa.',
                },
          )
        }
        closeEventSource()
      }
    },
    [close, closeEventSource],
  )

  // Effect-cleanup mirrors useRenderStream: closing the EventSource on unmount
  // prevents the auto-reconnect storm flagged in T-07-09a-04.
  useEffect(() => () => close(), [close])

  return { subscribe, close, state }
}

function handleMessage(
  ev: MessageEvent,
  setState: React.Dispatch<React.SetStateAction<StreamState>>,
): void {
  let envelope: ResearchSseEnvelope | null = null
  let parsed = false
  try {
    envelope = JSON.parse(ev.data) as ResearchSseEnvelope
    parsed = true
  } catch {
    parsed = false
  }

  if (parsed && envelope && typeof envelope === 'object' && envelope.event_type) {
    dispatchStructured(envelope, setState)
    return
  }

  // REVIEWS fix #3 — dual-shape SSE: Plan 03 verdict (a) confirmed retry.py
  // emits raw PT-BR `Tentativa N/M` strings on the same queue. Parse them
  // here so the retry inline notice renders without forcing the runner to
  // double-emit a structured envelope.
  const raw = typeof ev.data === 'string' ? ev.data : ''
  const match = RETRY_RE.exec(raw.replace(/^data:\s*/, ''))
  if (match) {
    const current = Number(match[1])
    const max = Number(match[2])
    if (Number.isFinite(current) && Number.isFinite(max)) {
      setState((prev) => ({
        ...prev,
        retryAttempt: { current, max },
      }))
    }
  }
}

function dispatchStructured(
  env: ResearchSseEnvelope,
  setState: React.Dispatch<React.SetStateAction<StreamState>>,
): void {
  switch (env.event_type) {
    case 'started':
      setState({ phase: 'running' })
      return
    case 'stage_start': {
      if (isResearchStage(env.stage)) {
        const stage = env.stage as ResearchStage
        setState((prev) => ({
          ...prev,
          phase: 'running',
          currentStage: stage,
        }))
      }
      return
    }
    case 'stage_done': {
      if (isResearchStage(env.stage)) {
        const stage = env.stage as ResearchStage
        setState((prev) => ({
          ...prev,
          completedStages: [...(prev.completedStages ?? []), stage],
          currentStage: undefined,
        }))
      }
      return
    }
    case 'retry':
      if (
        typeof env.attempt === 'number' &&
        typeof env.max_retries === 'number'
      ) {
        setState((prev) => ({
          ...prev,
          retryAttempt: { current: env.attempt!, max: env.max_retries! },
        }))
      }
      return
    case 'token': {
      // UAT 2026-05-22 — append the provider-emitted delta to the live
      // model output. `text` is a small chunk (single token or short run);
      // the buffer is unbounded but capped implicitly by JSON response size.
      const delta = typeof env.text === 'string' ? env.text : ''
      if (!delta) return
      setState((prev) => ({
        ...prev,
        modelOutput: (prev.modelOutput ?? '') + delta,
        // First token replaces the "Processando prompt…" placeholder.
        progressMessage: undefined,
      }))
      return
    }
    case 'progress': {
      // UAT 2026-05-23 — heartbeat envelope emitted while waiting for the
      // first token. Surfaces elapsed time + status so the user sees the
      // model is loading / processing the prompt, not hung.
      const msg = typeof env.message === 'string' ? env.message : ''
      if (!msg) return
      setState((prev) => ({ ...prev, progressMessage: msg }))
      return
    }
    case 'terminal':
      if (env.status === 'success') {
        setState((prev) => ({
          ...prev,
          phase: 'succeeded',
          currentStage: undefined,
        }))
      } else {
        setState({
          phase: 'failed',
          error_code: env.error_code ?? 'unknown',
          error_message: env.message ?? 'Erro desconhecido.',
        })
      }
      return
    case 'error':
      setState({
        phase: 'failed',
        error_code: env.error_code ?? 'unknown',
        error_message: env.message ?? 'Erro desconhecido.',
      })
      return
    default:
      return
  }
}
