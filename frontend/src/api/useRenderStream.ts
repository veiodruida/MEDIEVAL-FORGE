import { useCallback, useEffect, useRef } from 'react'
import { useRunStore, PIPELINE_STAGES, type PipelineStage } from '../stores/useRunStore'
import { usePipelineParams } from '../stores/usePipelineParams'

const STAGE_SET = new Set<string>(PIPELINE_STAGES)
function isPipelineStage(s: unknown): s is PipelineStage {
  return typeof s === 'string' && STAGE_SET.has(s)
}

interface RenderSseEnvelope {
  event_type: string
  stage?: string | null
  message?: string
  progress?: number | null
  token?: string | null
}

export interface RenderStreamHandle {
  subscribe: (projectId: string) => void
  close: () => void
}

export function useRenderStream(): RenderStreamHandle {
  const esRef = useRef<EventSource | null>(null)

  const close = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [])

  const subscribe = useCallback((projectId: string) => {
    close()
    const url = `/api/v3/projects/${projectId}/render/stream`
    const es = new EventSource(url)
    esRef.current = es

    // Track if any stage_cancel event was received during this run.
    // Used to decide whether to call cancelRender() vs finish('generated') on done.
    // cancelRender() preserves priorTokens for CanvasViewer (Plan 04-04) to revert.
    let cancelled = false

    es.onmessage = (e: MessageEvent) => {
      const run = useRunStore.getState()
      let msg: RenderSseEnvelope
      try {
        msg = JSON.parse(e.data) as RenderSseEnvelope
      } catch {
        run.appendLog(`[parse-error] ${String(e.data).slice(0, 200)}`)
        return
      }
      const stage = isPipelineStage(msg.stage) ? msg.stage : null
      run.appendLog(`${msg.event_type}: ${msg.stage ?? ''} ${msg.message ?? ''}`.trim())

      switch (msg.event_type) {
        case 'started':
          return
        case 'stage_start':
          if (stage) run.startStage(stage)
          return
        case 'stage_done':
          if (stage) run.finishStage(stage)
          return
        case 'stage_cancel':
          // D-13: backend has already swapped to prior_token on its side.
          // Frontend records the prior_token so CanvasViewer (Plan 04-04) can
          // re-hydrate against the cached prior array.
          cancelled = true
          if (stage) run.revertStage(stage, msg.message ?? '')
          return
        case 'error':
          run.finish('error', msg.message ?? 'Erro desconhecido', stage ?? undefined)
          close()
          return
        case 'done':
          if (cancelled) {
            // SC-4 D-13: revert slider UI to pre-render values so user sees
            // the state that matches the canvas (prior artifacts re-displayed).
            usePipelineParams.getState().revertValues()
            run.cancelRender()
          } else {
            run.finish('generated')
          }
          close()
          return
        default:
          return
      }
    }

    es.onerror = () => {
      // Mirror useGenerateStream silent-degrade — /status reconciles.
      close()
    }
  }, [close])

  useEffect(() => () => close(), [close])

  return { subscribe, close }
}
