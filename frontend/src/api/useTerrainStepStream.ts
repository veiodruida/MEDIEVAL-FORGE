import { useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export type TerrainStep = 'overpass' | 'hydrosheds' | 'dem' | 'ridges'
export type TerrainStepStatus = 'pendente' | 'rodando' | 'pronto' | 'erro'

export interface TerrainStepHandle {
  lines: string[]
  status: TerrainStepStatus
  error: Error | null
  start: (params?: { sensitivity?: 'low' | 'med' | 'high' }) => Promise<void>
  stop: () => Promise<void>
}

export function useTerrainStepStream(
  projectId: string | undefined,
  step: TerrainStep,
): TerrainStepHandle {
  const qc = useQueryClient()
  const [lines, setLines] = useState<string[]>([])
  const [status, setStatus] = useState<TerrainStepStatus>('pendente')
  const [error, setError] = useState<Error | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const stop = useCallback(async () => {
    // Server-side stop: scoped (project_id, step). T-01-04.
    if (projectId) {
      try {
        await fetch(`/api/projects/${projectId}/terrain/stop?step=${step}`, { method: 'POST' })
      } catch {
        // Client abort below — even if stop endpoint fails.
      }
    }
    abortRef.current?.abort()
  }, [projectId, step])

  const start = useCallback(
    async (params?: { sensitivity?: 'low' | 'med' | 'high' }) => {
      if (!projectId) return
      // Re-run semantics (D-26): always overwrite — clear local state.
      const controller = new AbortController()
      abortRef.current = controller
      setLines([])
      setError(null)
      setStatus('rodando')
      let url = `/api/projects/${projectId}/terrain/${step}`
      if (step === 'ridges' && params?.sensitivity) {
        url += `?sensitivity=${params.sensitivity}`
      }
      let sawError = false
      try {
        const res = await fetch(url, { method: 'POST', signal: controller.signal })
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          let idx
          while ((idx = buf.indexOf('\n\n')) !== -1) {
            const block = buf.slice(0, idx)
            buf = buf.slice(idx + 2)
            const text = block
              .split('\n')
              .map((l) => (l.startsWith('data: ') ? l.slice(6) : l))
              .join('\n')
            if (text.startsWith('ERROR') || text.startsWith('412')) sawError = true
            setLines((prev) => [...prev, text])
          }
        }
        setStatus(sawError ? 'erro' : 'pronto')
      } catch (e) {
        const err = e as Error
        if (err.name !== 'AbortError') {
          setError(err)
          setStatus('erro')
        } else {
          setStatus('pendente')
        }
      } finally {
        abortRef.current = null
        qc.invalidateQueries({ queryKey: ['projects', projectId] })
      }
    },
    [projectId, step, qc],
  )

  return { lines, status, error, start, stop }
}
