import { Button, Flex, Text } from '@radix-ui/themes'
import { ProviderSelector } from '../research/ProviderSelector'
import type { Effort } from '../../stores/usePipelineStore'

interface ProviderEffortPickerProps {
  providerId: string
  effort: Effort
  onProviderChange: (id: string) => void
  onEffortChange: (e: Effort) => void
}

const EFFORT_OPTIONS: { label: string; value: Effort }[] = [
  { label: 'Baixo', value: 'low' },
  { label: 'Médio', value: 'medium' },
  { label: 'Alto', value: 'high' },
]

export function ProviderEffortPicker({
  providerId,
  effort,
  onProviderChange,
  onEffortChange,
}: ProviderEffortPickerProps) {
  return (
    <Flex direction="column" gap="3">
      {/* Provider section */}
      <Flex direction="column" gap="1">
        <Text size="2" weight="medium">
          Provedor
        </Text>
        <ProviderSelector value={providerId} onChange={onProviderChange} />
      </Flex>

      {/* Effort section */}
      <Flex direction="column" gap="1">
        <Text size="2" weight="medium">
          Esforço
        </Text>
        <Flex gap="2">
          {EFFORT_OPTIONS.map((opt) => {
            const isActive = opt.value === effort
            return (
              <Button
                key={opt.value}
                type="button"
                variant={isActive ? 'solid' : 'soft'}
                data-active={String(isActive)}
                onClick={() => onEffortChange(opt.value)}
              >
                {opt.label}
              </Button>
            )
          })}
        </Flex>
      </Flex>
    </Flex>
  )
}
