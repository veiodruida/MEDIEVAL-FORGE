import { Card, Flex, Text } from '@radix-ui/themes'
import {
  CheckCircledIcon,
  CircleIcon,
  DotFilledIcon,
  ExclamationTriangleIcon,
} from '@radix-ui/react-icons'
import { PIPELINE_STAGES, type PipelineStage } from '../../stores/useRunStore'

export interface RunLogPanelProps {
  completedStages: PipelineStage[]
  currentStage: PipelineStage | null
  errorStage?: PipelineStage | null
}

type RowState = 'done' | 'active' | 'pending' | 'error'

function rowStateFor(
  stage: PipelineStage,
  completed: PipelineStage[],
  current: PipelineStage | null,
  errorStage: PipelineStage | null | undefined,
): RowState {
  if (errorStage === stage) return 'error'
  if (completed.includes(stage)) return 'done'
  if (current === stage) return 'active'
  return 'pending'
}

/**
 * Inline (not modal) list of the 11 canonical DAG stages. Each row gets a
 * glyph + copy per UI-SPEC §Canvas States. Driven by useRunStore via props.
 */
export function RunLogPanel({
  completedStages,
  currentStage,
  errorStage = null,
}: RunLogPanelProps) {
  return (
    <Card variant="surface" style={{ width: 280, maxHeight: 300, overflow: 'auto' }} p="3">
      <Flex direction="column" gap="1">
        {PIPELINE_STAGES.map((stage) => {
          const rs = rowStateFor(stage, completedStages, currentStage, errorStage)
          const testId = `stage-row-${rs}`
          let icon
          if (rs === 'done') {
            icon = <CheckCircledIcon style={{ color: 'var(--grass-9)' }} />
          } else if (rs === 'active') {
            icon = (
              <DotFilledIcon
                className="animate-pulse"
                style={{ color: 'var(--amber-9)' }}
              />
            )
          } else if (rs === 'error') {
            icon = <ExclamationTriangleIcon style={{ color: 'var(--red-9)' }} />
          } else {
            icon = <CircleIcon style={{ color: 'var(--gray-8)' }} />
          }
          return (
            <Flex key={stage} align="center" gap="2" data-testid={testId}>
              {icon}
              <Text size="1">{stage}</Text>
            </Flex>
          )
        })}
      </Flex>
    </Card>
  )
}
