import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Box, Flex } from '@radix-ui/themes'
import { useQueryClient } from '@tanstack/react-query'
import {
  useExport,
  useProject,
  useStatusManifest,
} from '../api/client'
import { useGenerateStream } from '../api/useGenerateStream'
import { useRunStore } from '../stores/useRunStore'
import { CanvasViewer } from '../components/canvas/CanvasViewer'
import { WorkspaceToolbar } from '../components/workspace/WorkspaceToolbar'
import { RunLogPanel } from '../components/workspace/RunLogPanel'
import { EmptyCanvasState } from '../components/workspace/EmptyCanvasState'
import { GeneratingCanvasState } from '../components/workspace/GeneratingCanvasState'
import { ErrorCanvasCallout } from '../components/workspace/ErrorCanvasCallout'

/**
 * ProjectDetailWorkspace — Phase 03 Plan 04 read-only Mapbox-style shell.
 *
 * Replaces the v1 stepper (697 LOC). Composes the WorkspaceToolbar +
 * canvas-state body + collapsible RunLogPanel. Wires the run state machine:
 *   POST /api/v3/projects/{id}/generate -> { run_id }
 *   EventSource /generate/stream -> useRunStore actions
 *   On done -> invalidate ['v3-status', id] + ['projects', id] (cacheVersion bump)
 */
export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const projectQ = useProject(id)
  const statusQ = useStatusManifest(id)
  const exportZip = useExport(id)
  const qc = useQueryClient()
  const stream = useGenerateStream()
  const run = useRunStore()
  const [logPanelOpen, setLogPanelOpen] = useState(false)

  const project = projectQ.data
  const status = statusQ.data

  const hasMap = Boolean(status?.has_artifacts?.['territory_metadata.json'])
  const hasArtifacts = useMemo(
    () => Object.values(status?.has_artifacts ?? {}).some(Boolean),
    [status?.has_artifacts],
  )

  // On mount / on status change: if server says we're already generating,
  // best-effort attach to the SSE stream. Pitfall 9 — if the producer has
  // already finished, /stream 404s; useGenerateStream silently degrades.
  useEffect(() => {
    if (!id) return
    if (statusQ.data?.status === 'generating' && run.state === 'idle') {
      run.start('reattach', 'generating')
      stream.subscribe(id)
    }
    return () => stream.close()
    // Only react to id + server status; do NOT depend on `run` (would re-subscribe).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, statusQ.data?.status])

  // Invalidate caches when a run finishes successfully so CanvasViewer
  // re-fetches with the new project.updated_at cacheVersion (D-19).
  useEffect(() => {
    if (run.state === 'generated' && id) {
      qc.invalidateQueries({ queryKey: ['v3-status', id] })
      qc.invalidateQueries({ queryKey: ['projects', id] })
    }
  }, [run.state, id, qc])

  const handleGenerate = useCallback(async () => {
    if (!id) return
    run.start('pending', 'generating')
    try {
      const r = await fetch(`/api/v3/projects/${id}/generate`, { method: 'POST' })
      if (!r.ok) {
        const text = await r.text().catch(() => '')
        run.finish('error', `${r.status}: ${text}`.trim())
        return
      }
      const body = (await r.json()) as { run_id: string; status: string }
      run.start(body.run_id, 'generating')
      stream.subscribe(id)
    } catch (err) {
      run.finish('error', (err as Error).message)
    }
  }, [id, run, stream])

  const handleExport = useCallback(() => {
    exportZip.mutate()
  }, [exportZip])

  const period = project ? `${project.period_start}-${project.period_end}` : ''
  const country = project?.country_qid ?? ''
  const lastLogLine = run.logLines.length > 0 ? run.logLines[run.logLines.length - 1] : null

  const body = (() => {
    if (run.state === 'error') {
      return (
        <ErrorCanvasCallout
          errorStage={run.errorStage}
          errorMessage={run.errorMessage ?? 'Erro desconhecido'}
          lastLogLine={lastLogLine}
          onRetry={handleGenerate}
        />
      )
    }
    if (run.state === 'generating' || run.state === 'ingesting') {
      return (
        <GeneratingCanvasState
          completedStages={run.completedStages}
          currentStage={run.currentStage}
        />
      )
    }
    if (hasMap && project) {
      return <CanvasViewer projectId={project.id} cacheVersion={project.updated_at} />
    }
    return (
      <EmptyCanvasState
        country={country}
        period={period}
        onGenerate={handleGenerate}
      />
    )
  })()

  return (
    <Flex direction="column" style={{ height: '100vh' }}>
      <WorkspaceToolbar
        project={project}
        runState={run.state}
        currentStage={run.currentStage}
        hasArtifacts={hasArtifacts}
        onGenerate={handleGenerate}
        onExport={handleExport}
        statusBadgeOpen={logPanelOpen}
        onToggleStatusBadge={() => setLogPanelOpen((o) => !o)}
      />
      <Box style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {body}
        {logPanelOpen && (
          <Box
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              zIndex: 30,
            }}
          >
            <RunLogPanel
              completedStages={run.completedStages}
              currentStage={run.currentStage}
              errorStage={run.errorStage}
            />
          </Box>
        )}
      </Box>
    </Flex>
  )
}
