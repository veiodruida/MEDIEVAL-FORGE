import { Badge } from '@radix-ui/themes'
import type { PipelineStage, RunState } from '../../stores/useRunStore'

export interface GenerateStatusBadgeProps {
  runState: RunState
  currentStage: PipelineStage | null
  hasArtifacts: boolean
  onClick: () => void
}

type BadgeColor = 'gray' | 'amber' | 'blue' | 'grass' | 'red'

interface BadgeShape {
  color: BadgeColor
  copy: string
}

function mapState(
  runState: RunState,
  currentStage: PipelineStage | null,
  hasArtifacts: boolean,
): BadgeShape {
  if (runState === 'error') return { color: 'red', copy: 'Erro' }
  if (runState === 'generating') {
    return { color: 'amber', copy: `Gerando: ${currentStage ?? '…'}` }
  }
  if (runState === 'ingesting') {
    return { color: 'blue', copy: 'Ingerindo…' }
  }
  if (runState === 'generated') return { color: 'grass', copy: 'Mapa gerado' }
  // idle
  if (hasArtifacts) return { color: 'grass', copy: 'Mapa gerado' }
  return { color: 'gray', copy: 'Pronto' }
}

/**
 * Clickable Radix Badge that maps the run state machine to a (color, copy)
 * pair per UI-SPEC §State Machine. Click expands the inline RunLogPanel.
 */
export function GenerateStatusBadge({
  runState,
  currentStage,
  hasArtifacts,
  onClick,
}: GenerateStatusBadgeProps) {
  const { color, copy } = mapState(runState, currentStage, hasArtifacts)
  return (
    <Badge
      data-testid="generate-status-badge"
      data-color={color}
      color={color}
      variant="soft"
      onClick={onClick}
      style={{ cursor: 'pointer' }}
    >
      {copy}
    </Badge>
  )
}
