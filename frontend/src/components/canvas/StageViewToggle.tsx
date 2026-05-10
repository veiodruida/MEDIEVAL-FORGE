import { Flex, RadioGroup, Text } from '@radix-ui/themes'
import { usePipelineParams } from '../../stores/usePipelineParams'
import type { StageView } from '../../api/render'

const OPTIONS: Array<{ value: StageView; label: string }> = [
  { value: 'landmask', label: 'Máscara terrestre' },
  { value: 'voronoi-raw', label: 'Voronoi bruto' },
  { value: 'cleanup', label: 'Limpeza' },
  { value: 'smooth', label: 'Suavização' },
  { value: 'render-final', label: 'Mapa final' },
]

export function StageViewToggle() {
  const stageView = usePipelineParams((s) => s.stageView)
  const setStageView = usePipelineParams((s) => s.setStageView)

  return (
    <Flex direction="column" gap="2" data-testid="stage-view-toggle">
      <Text size="1" color="gray">
        Vista do estágio
      </Text>
      <RadioGroup.Root
        value={stageView}
        onValueChange={(v) => setStageView(v as StageView)}
        aria-label="Vista do estágio"
      >
        <Flex direction="column" gap="2">
          {OPTIONS.map((opt) => (
            <Text as="label" size="2" key={opt.value}>
              <Flex align="center" gap="2">
                <RadioGroup.Item value={opt.value} />
                {opt.label}
              </Flex>
            </Text>
          ))}
        </Flex>
      </RadioGroup.Root>
    </Flex>
  )
}
