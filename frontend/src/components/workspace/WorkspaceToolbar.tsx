import { Box, Button, Flex, Text } from '@radix-ui/themes'
import { ChevronLeftIcon } from '@radix-ui/react-icons'
import { Link } from 'react-router-dom'
import { GenerateStatusBadge } from './GenerateStatusBadge'
import type { Project } from '../../api/client'
import type { PipelineStage, RunState } from '../../stores/useRunStore'

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
 * Left zone: ← Projetos + project name. Center: GenerateStatusBadge.
 * Right: Gerar Mapa / Regenerar (disabled when running) + Exportar ZIP.
 */
export function WorkspaceToolbar({
  project,
  runState,
  currentStage,
  hasArtifacts = false,
  onGenerate,
  onExport,
  statusBadgeOpen: _statusBadgeOpen,
  onToggleStatusBadge,
}: WorkspaceToolbarProps) {
  const isRunning = runState === 'generating' || runState === 'ingesting'
  // Label flips to "Regenerar" once a run has started OR artifacts exist —
  // the v1 stepper showed "Gerando…" mid-run; UI-SPEC §State Machine says the
  // CTA should remain a regenerate affordance during/after a run (just disabled).
  const ctaLabel =
    hasArtifacts || runState === 'generated' || isRunning ? 'Regenerar' : 'Gerar Mapa'

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
          <Link to="/projects" style={{ textDecoration: 'none' }}>
            <Flex align="center" gap="1">
              <ChevronLeftIcon />
              <Text size="2">Projetos</Text>
            </Flex>
          </Link>
          {project && (
            <Text size="2" weight="bold">
              {project.name}
            </Text>
          )}
        </Flex>

        <GenerateStatusBadge
          runState={runState}
          currentStage={currentStage}
          hasArtifacts={hasArtifacts}
          onClick={onToggleStatusBadge}
        />

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
