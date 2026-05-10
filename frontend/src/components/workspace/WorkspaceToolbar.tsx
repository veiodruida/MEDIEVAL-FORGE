import { Box, Button, Flex, IconButton, Text } from '@radix-ui/themes'
import { ChevronLeftIcon, MixerHorizontalIcon } from '@radix-ui/react-icons'
import { Link } from 'react-router-dom'
import { GenerateStatusBadge } from './GenerateStatusBadge'
import type { Project } from '../../api/client'
import type { PipelineStage, RunState } from '../../stores/useRunStore'
import { usePipelineParams } from '../../stores/usePipelineParams'
import { postRenderCancel } from '../../api/render'

export interface WorkspaceToolbarProps {
  project: Project | undefined
  runState: RunState
  currentStage: PipelineStage | null
  hasArtifacts?: boolean
  onGenerate: () => void
  onExport: () => void
  statusBadgeOpen: boolean
  onToggleStatusBadge: () => void
}

/**
 * 48px sticky toolbar per UI-SPEC §Layout Contract.
 * Left zone: ⬡ Params toggle + ← Projetos + project name.
 * Center: GenerateStatusBadge → red "Cancelar" button when state ∈ {generating, rendering}.
 * Right: Gerar Mapa / Regenerar (disabled when running) + Exportar ZIP.
 */
export function WorkspaceToolbar({
  project,
  runState,
  currentStage,
  hasArtifacts = false,
  onGenerate,
  onExport,
  onToggleStatusBadge,
}: WorkspaceToolbarProps) {
  const sidebarOpen = usePipelineParams((s) => s.sidebarOpen)
  const setSidebarOpen = usePipelineParams((s) => s.setSidebarOpen)

  // D-16: cancel button replaces badge when runState === 'rendering'.
  // UI-SPEC §State Machine: generating shows the badge (no cancel); only rendering shows cancel.
  // Rationale: /render/cancel cancels incremental re-renders; /generate runs have no SSE cancel.
  const isRunning =
    runState === 'generating' || runState === 'ingesting' || runState === 'rendering'
  const showCancel = runState === 'rendering'

  // Label flips to "Regenerar" once a run has started OR artifacts exist.
  const ctaLabel =
    hasArtifacts || runState === 'generated' || isRunning ? 'Regenerar' : 'Gerar Mapa'

  const handleCancel = async () => {
    if (!project) return
    await postRenderCancel(project.id).catch(() => {})
  }

  return (
    <Box
      data-testid="workspace-toolbar"
      style={{
        height: '48px',
        position: 'sticky',
        top: 0,
        zIndex: 20,
        background: 'var(--color-panel-solid)',
        borderBottom: '1px solid var(--gray-6)',
      }}
    >
      <Flex align="center" justify="between" px="4" gap="5" style={{ height: '100%' }}>
        <Flex align="center" gap="3">
          <IconButton
            size="2"
            variant="ghost"
            data-testid="toggle-parameter-sidebar"
            aria-label="Alternar painel de parâmetros"
            aria-pressed={sidebarOpen}
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <MixerHorizontalIcon />
          </IconButton>
          <Link to="/projects" style={{ textDecoration: 'none' }}>
            <Flex align="center" gap="1">
              <ChevronLeftIcon />
              <Text size="2">Projetos</Text>
            </Flex>
          </Link>
          {project && (
            <Text size="2" weight="bold" data-testid="project-name">
              {project.name}
            </Text>
          )}
        </Flex>

        {showCancel ? (
          <Button
            color="red"
            variant="solid"
            data-testid="cancel-render-button"
            onClick={handleCancel}
          >
            Cancelar
          </Button>
        ) : (
          <GenerateStatusBadge
            runState={runState}
            currentStage={currentStage}
            hasArtifacts={hasArtifacts}
            onClick={onToggleStatusBadge}
          />
        )}

        <Flex align="center" gap="2">
          <Button
            color="blue"
            variant="solid"
            disabled={isRunning}
            onClick={onGenerate}
          >
            {ctaLabel}
          </Button>
          <Button color="gray" variant="outline" onClick={onExport}>
            Exportar ZIP
          </Button>
        </Flex>
      </Flex>
    </Box>
  )
}
