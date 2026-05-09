import { Box, Flex, Text } from '@radix-ui/themes'
import { RunLogPanel } from './RunLogPanel'
import type { PipelineStage } from '../../stores/useRunStore'

export interface GeneratingCanvasStateProps {
  completedStages: PipelineStage[]
  currentStage: PipelineStage | null
}

/**
 * D-07 generating state — caption + inline RunLogPanel centered on canvas.
 */
export function GeneratingCanvasState({
  completedStages,
  currentStage,
}: GeneratingCanvasStateProps) {
  return (
    <Box
      data-testid="generating-canvas-state"
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Flex direction="column" align="center" gap="3">
        <Text size="2" color="gray">
          Gerando mapa…
        </Text>
        <RunLogPanel completedStages={completedStages} currentStage={currentStage} />
      </Flex>
    </Box>
  )
}
