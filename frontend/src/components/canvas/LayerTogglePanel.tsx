import { Card, Flex, Text, Checkbox } from '@radix-ui/themes'
import { useUIStore, type LayerName } from '../../stores/uiStore'

const LAYERS: { key: LayerName; label: string }[] = [
  { key: 'terrain', label: 'Terrain' },
  { key: 'territories', label: 'Territories' },
  { key: 'borders', label: 'Borders' },
  { key: 'capitals', label: 'Capitals' },
  { key: 'labels', label: 'Labels' },
]

export function LayerTogglePanel() {
  const layerVisibility = useUIStore((s) => s.layerVisibility)
  const toggleLayer = useUIStore((s) => s.toggleLayer)

  return (
    <Card
      variant="surface"
      style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, width: 160 }}
    >
      <Flex direction="column" gap="2">
        <Text size="2" weight="bold">Layers</Text>
        {LAYERS.map(({ key, label }) => (
          <Flex key={key} align="center" gap="2">
            <Checkbox
              checked={layerVisibility[key]}
              onCheckedChange={() => toggleLayer(key)}
            />
            <Text size="2">{label}</Text>
          </Flex>
        ))}
      </Flex>
    </Card>
  )
}
