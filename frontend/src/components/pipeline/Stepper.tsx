import { Box, Flex, Text } from '@radix-ui/themes'
import type { StepId, StepStatus } from '../../stores/usePipelineStore'

interface StepperProps {
  currentStep: StepId
  statuses: {
    osm: StepStatus
    baronies: StepStatus
    research: StepStatus
    map: StepStatus
    codex: StepStatus
  }
  onStepClick?: (s: StepId) => void
}

const STEPS: { id: StepId; key: keyof StepperProps['statuses']; label: string }[] = [
  { id: 1, key: 'osm', label: 'OSM' },
  { id: 2, key: 'baronies', label: 'Baronies' },
  { id: 3, key: 'research', label: 'Pesquisa' },
  { id: 4, key: 'map', label: 'Mapa' },
  { id: 5, key: 'codex', label: 'Codex' },
]

const STATUS_BG: Record<StepStatus, string> = {
  pending: 'var(--gray-5)',
  active: 'var(--accent-9)',
  done: 'var(--green-9)',
  error: 'var(--red-9)',
}

const STATUS_GLYPH: Record<StepStatus, string> = {
  pending: '○',
  active: '⚙',
  done: '✓',
  error: '✕',
}

export function Stepper({ currentStep, statuses, onStepClick }: StepperProps) {
  return (
    <Flex align="center" gap="0" mb="4" data-testid="pipeline-stepper">
      {STEPS.map((step, idx) => {
        const status = statuses[step.key]
        const isCurrent = step.id === currentStep

        const nodeEl = (
          <Flex direction="column" align="center" gap="1" style={{ minWidth: 60 }}>
            <Box
              data-status={status}
              aria-current={isCurrent ? 'step' : undefined}
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: STATUS_BG[status],
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: 16,
                fontWeight: 'bold',
                boxShadow: isCurrent ? '0 0 0 3px var(--accent-7)' : undefined,
                cursor: onStepClick ? 'pointer' : 'default',
              }}
            >
              {STATUS_GLYPH[status]}
            </Box>
            <Text size="1" color={isCurrent ? undefined : 'gray'} weight={isCurrent ? 'bold' : 'regular'}>
              {step.label}
            </Text>
          </Flex>
        )

        return (
          <Flex key={step.id} align="center" gap="0" style={{ flex: 1, minWidth: 0 }}>
            {onStepClick ? (
              <button
                type="button"
                data-status={status}
                aria-current={isCurrent ? 'step' : undefined}
                onClick={() => onStepClick(step.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 4,
                  minWidth: 60,
                }}
                aria-label={step.label}
              >
                <Box
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: STATUS_BG[status],
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: 16,
                    fontWeight: 'bold',
                    boxShadow: isCurrent ? '0 0 0 3px var(--accent-7)' : undefined,
                  }}
                >
                  {STATUS_GLYPH[status]}
                </Box>
                <Text size="1" color={isCurrent ? undefined : 'gray'} weight={isCurrent ? 'bold' : 'regular'}>
                  {step.label}
                </Text>
              </button>
            ) : (
              nodeEl
            )}
            {idx < STEPS.length - 1 && (
              <Box
                style={{
                  flex: 1,
                  height: 2,
                  background: statuses[STEPS[idx + 1].key] === 'pending' ? 'var(--gray-4)' : 'var(--accent-6)',
                  marginBottom: 20,
                }}
              />
            )}
          </Flex>
        )
      })}
    </Flex>
  )
}
