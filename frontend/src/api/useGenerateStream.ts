import { useCallback, useEffect, useRef } from 'react'
import {
  PIPELINE_STAGES,
  useRunStore,
  type PipelineStage,
} from '../stores/useRunStore'

/**
 * EventSource subscriber for /api/v3/projects/{id}/generate/stream.
 *
 * Translates the Plan 02 SSE envelope:
 *   { event_type: "started"|"stage_start"|"stage_done"|"error"|"done",
 *     stage: PipelineStage|null, message: string, progress: number|null }
 * into useRunStore actions. Pitfall 9 (refresh-mid-run): if /stream 404s
 * because the producer is no longer alive (single-flight cleared), we
 * silently degrade — the /status poll will reconcile the real state.
 */
const PIPELINE_STAGE_SET = new Set<string>(PIPELINE_STAGES)

interface SseEnvelope {
  event_type: string
  stage?: string | null
  message?: string
  progress?: number | null
}

function isPipelineStage(s: unknown): s is PipelineStage {
  return typeof s === 'string' && PIPELINE_STAGE_SET.has(s)
}

export interface GenerateStreamHandle {
  subscribe: (projectId: string) => void
  close: () => void
}

export function useGenerateStream(): GenerateStreamHandle {
  const esRef = useRef<EventSource | null>(null)

  const close = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [])

  const subscribe = useCallback(
    (projectId: string) => {
      // Close any prior connection before opening a new one.
      close()
      const url = `/api/v3/projects/${projectId}/generate/stream`
      const es = new EventSource(url)
      esRef.current = es

      es.onmessage = (e: MessageEvent) => {
        const run = useRunStore.getState()
        let msg: SseEnvelope
        try {
          msg = JSON.parse(e.data) as SseEnvelope
        } catch {
          // T-03-FE-WORKSPACE-01: malformed envelope — log raw line, ignore.
          run.appendLog(`[parse-error] ${String(e.data).slice(0, 200)}`)
          return
        }

        const stage = isPipelineStage(msg.stage) ? msg.stage : null
        run.appendLog(
          `${msg.event_type}: ${msg.stage ?? ''} ${msg.message ?? ''}`.trim(),
        )

        switch (msg.event_type) {
          case 'started':
            return
          case 'stage_start':
            if (stage) run.startStage(stage)
            return
          case 'stage_done':
            if (stage) run.finishStage(stage)
            return
          case 'error':
            run.finish('error', msg.message ?? 'Erro desconhecido', stage ?? undefined)
            close()
            return
          case 'done':
            run.finish('generated')
            close()
            return
          default:
            return
        }
      }

      es.onerror = () => {
        // Pitfall 9: producer may have terminated cleanly before the consumer
        // attached; treat as silent degrade — do NOT push to error state.
        // /status query will reconcile the real outcome on next poll.
        close()
      }
    },
    [close],
  )

  // Cleanup on unmount.
  useEffect(() => {
    return () => close()
  }, [close])

  return { subscribe, close }
}
