/**
 * Phase 07 Plan 09a Task 2 — ResearchProgress sub-component.
 *
 * Renders the 4 PT-BR pipeline stage rows (Reinos → Ducados → Condados →
 * Baronias) reflecting the `StreamState` from `useResearchStream`. Wrapped
 * in a Radix `<ScrollArea>` clamped to `maxHeight: 240px` so long-running
 * retry loops do not push the dialog past viewport.
 *
 * REVIEWS fix #7 — terminal `failed` + `error_code === 'aborted'` renders
 * the label "Cancelada" (NOT "Erro") so the user distinguishes an intentional
 * cancel from an unexpected failure. Other failure codes still render
 * "Erro: {message}".
 */
import { Box, Flex, ScrollArea, Spinner, Text } from '@radix-ui/themes'
import {
  CheckCircledIcon,
  ExclamationTriangleIcon,
} from '@radix-ui/react-icons'
import type {
  ResearchStage,
  StreamState,
} from '../../hooks/useResearchStream'

const STAGE_ORDER: ResearchStage[] = [
  'kingdoms',
  'duchies',
  'condados',
  'baronies',
]

const STAGE_LABEL_PT_BR: Record<ResearchStage, string> = {
  // Reinos | Ducados | Condados | Baronias — PT-BR copy locked by
  // UI-SPEC §Copywriting "Stage labels (PT-BR, in pipeline order)".
  kingdoms: 'Reinos',
  duchies: 'Ducados',
  condados: 'Condados',
  baronies: 'Baronias',
}

type RowState = 'pending' | 'running' | 'completed' | 'failed'

function rowStateFor(stage: ResearchStage, state: StreamState): RowState {
  if (state.completedStages?.includes(stage)) return 'completed'
  if (state.phase === 'failed' && state.currentStage === stage) return 'failed'
  if (state.currentStage === stage) return 'running'
  return 'pending'
}

export interface ResearchProgressProps {
  state: StreamState
}

export function ResearchProgress({ state }: ResearchProgressProps) {
  return (
    <Box style={{ maxHeight: 240 }}>
      <ScrollArea
        type="auto"
        scrollbars="vertical"
        style={{ maxHeight: 240 }}
      >
        <Flex direction="column" gap="3" p="2">
          {STAGE_ORDER.map((stage) => (
            <StageRow
              key={stage}
              stage={stage}
              rowState={rowStateFor(stage, state)}
            />
          ))}

          {state.retryAttempt && (
            <Text size="2" color="amber">
              Tentativa {state.retryAttempt.current} de {state.retryAttempt.max}
            </Text>
          )}

          {/* REVIEWS fix #7 — Cancelada distinguished from Erro */}
          {state.phase === 'failed' && state.error_code === 'aborted' && (
            <Text size="2" color="gray">
              Cancelada
            </Text>
          )}
          {state.phase === 'failed' && state.error_code !== 'aborted' && (
            <Text size="2" color="red">
              Erro: {state.error_message ?? 'desconhecido'}
            </Text>
          )}

          {state.phase === 'succeeded' && (
            <Flex align="center" gap="2">
              <CheckCircledIcon style={{ color: 'var(--green-9)' }} />
              <Text size="2" color="gray">
                Pesquisa concluída.
              </Text>
            </Flex>
          )}
        </Flex>
      </ScrollArea>
    </Box>
  )
}

interface StageRowProps {
  stage: ResearchStage
  rowState: RowState
}

function StageRow({ stage, rowState }: StageRowProps) {
  const label = STAGE_LABEL_PT_BR[stage]
  const borderLeft =
    rowState === 'running' ? '2px solid var(--accent-9)' : '2px solid transparent'

  return (
    <Flex
      align="center"
      gap="2"
      style={{ borderLeft, paddingLeft: 8 }}
    >
      {rowState === 'running' && <Spinner size="1" />}
      {rowState === 'completed' && (
        <CheckCircledIcon style={{ color: 'var(--green-9)' }} />
      )}
      {rowState === 'failed' && (
        <ExclamationTriangleIcon style={{ color: 'var(--red-9)' }} />
      )}
      <Text
        size="2"
        color={rowState === 'pending' ? 'gray' : undefined}
      >
        {label}
      </Text>
    </Flex>
  )
}
