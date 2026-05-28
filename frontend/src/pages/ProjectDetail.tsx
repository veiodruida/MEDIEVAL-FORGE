import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Box, Button, Flex, Text } from '@radix-ui/themes'
import * as Toast from '@radix-ui/react-toast'
import { useQueryClient } from '@tanstack/react-query'
import { useProject, useStatusManifest } from '../api/client'
import {
  useExportV3,
  ExportValidationError,
  type ExportResponse,
  type ValidationEnvelope,
} from '../api/useExportV3'
import { useGenerateStream } from '../api/useGenerateStream'
import { useRunStore } from '../stores/useRunStore'
import { CanvasViewer } from '../components/canvas/CanvasViewer'
import { ParameterSidebar } from '../components/canvas/ParameterSidebar'
import { WorkspaceToolbar } from '../components/workspace/WorkspaceToolbar'
import { RunLogPanel } from '../components/workspace/RunLogPanel'
import { EmptyCanvasState } from '../components/workspace/EmptyCanvasState'
import { GeneratingCanvasState } from '../components/workspace/GeneratingCanvasState'
import { ErrorCanvasCallout } from '../components/workspace/ErrorCanvasCallout'
import {
  ExportErrorDialog,
  type DryRunOutcome,
} from '../components/export/ExportErrorDialog'
import { regionDisplayNameFor } from '../utils/regionDisplay'
import { BranchInitializer } from '../components/editor/BranchInitializer'

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
  const exportMut = useExportV3(id)
  const qc = useQueryClient()
  const stream = useGenerateStream()
  const run = useRunStore()
  const [logPanelOpen, setLogPanelOpen] = useState(false)
  // D-08 envelope from the most recent 422; controls ExportErrorDialog open state.
  const [exportEnvelope, setExportEnvelope] = useState<ValidationEnvelope | null>(null)
  // Network/5xx failures render via Toast.Provider (already mounted in main.tsx).
  const [toastOpen, setToastOpen] = useState(false)
  const [toastMessage, setToastMessage] = useState('')

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

  /**
   * Phase 07 Plan 10 — v3 export flow.
   *
   * 1. mutateAsync({}) → backend returns 201 + ExportResponse with download_url
   *    (D-08 envelope on 422 → ExportValidationError → open ExportErrorDialog).
   * 2. fetch(download_url) → blob().
   * 3. URL.createObjectURL(blob) → anchor[download] → click → revokeObjectURL.
   *
   * Network/5xx (generic Error) surfaces via Toast.Provider per UI-SPEC §Surface 3.
   */
  const handleExport = useCallback(async () => {
    if (!id) return
    try {
      const data = (await exportMut.mutateAsync({})) as ExportResponse
      const downloadRes = await fetch(data.download_url)
      if (!downloadRes.ok) {
        throw new Error(`Falha ao baixar o ZIP (${downloadRes.status})`)
      }
      const blob = await downloadRes.blob()
      const url = URL.createObjectURL(blob)
      try {
        const a = document.createElement('a')
        a.href = url
        a.download = data.zip_filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
      } finally {
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      if (err instanceof ExportValidationError) {
        setExportEnvelope(err.envelope)
        return
      }
      const message = err instanceof Error ? err.message : String(err)
      setToastMessage(
        `Erro ao comunicar com o servidor de exportação: ${message}. Tente novamente.`,
      )
      setToastOpen(true)
    }
  }, [id, exportMut])

  /**
   * Dialog dry-run callback: runs the same mutation with `dryRun: true`.
   * Returns a discriminated outcome so the dialog can render the right body.
   */
  const handleDryRun = useCallback(async (): Promise<DryRunOutcome> => {
    try {
      const result = (await exportMut.mutateAsync({ dryRun: true })) as {
        dry_run: true
        passed: boolean
        errors: unknown[]
        warnings: unknown[]
      }
      if (result.passed) {
        return { kind: 'passed', passed: true }
      }
      // Defensive: backend wraps non-passing dry-runs in 422 (handled below),
      // but if a future server returns 200 with passed=false, surface as failure.
      return {
        kind: 'failed',
        envelope: {
          detail: {
            summary: `${(result.errors ?? []).length} errors blocked export`,
            errors: result.errors as never,
            warnings: result.warnings as never,
          },
        },
      }
    } catch (err) {
      if (err instanceof ExportValidationError) {
        return { kind: 'failed', envelope: err.envelope }
      }
      const message = err instanceof Error ? err.message : String(err)
      return { kind: 'network-error', message }
    }
  }, [exportMut])

  const handleCloseExportDialog = useCallback(() => {
    setExportEnvelope(null)
  }, [])

  const period = project ? `${project.period_start}-${project.period_end}` : ''
  const country = regionDisplayNameFor(project?.country_qid)
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
      return (
        <CanvasViewer
          projectId={project.id}
          cacheVersion={project.updated_at}
          project={project}
        />
      )
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
      {/* Phase 08 Plan 14 (GAP-B): auto-select active branch on load.
          Returns null — effect only. Ensures activeBranchId is non-null
          before user reaches for any edit tool. */}
      <BranchInitializer projectId={id} />
      <Flex style={{ flex: 1, overflow: 'hidden' }}>
        {id && <ParameterSidebar projectId={id} />}
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

      <ExportErrorDialog
        envelope={exportEnvelope}
        onClose={handleCloseExportDialog}
        onDryRun={handleDryRun}
        onRetryExport={handleExport}
      />

      <Toast.Root
        open={toastOpen}
        onOpenChange={setToastOpen}
        duration={8000}
        data-testid="export-network-toast"
        className="rounded-md border border-red-300 bg-white p-3 shadow-md"
      >
        <Toast.Title asChild>
          <Text size="2" color="red">
            {toastMessage}
          </Text>
        </Toast.Title>
        <Toast.Action altText="Fechar" asChild>
          <Button size="1" variant="soft" onClick={() => setToastOpen(false)}>
            Fechar
          </Button>
        </Toast.Action>
      </Toast.Root>
    </Flex>
  )
}
