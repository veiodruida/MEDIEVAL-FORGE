import { Card, Flex, Text, Checkbox, Tooltip } from '@radix-ui/themes'
import { useUIStore, type LayerName } from '../../stores/uiStore'

// Quick-task 260420-hkr: vocabulary aligned with the Reino/Duquia/Condado
// hierarchy. Portuguese labels match InspectorSidebar copy.
// GAP-08 (02-05): Labels row carries a Tooltip explaining the zoom-gate so
// users don't perceive the toggle as broken at default zoom.
const LAYERS: { key: LayerName; label: string; hint?: string }[] = [
  { key: 'condados', label: 'Condados' },
  { key: 'baronies', label: 'Baronias' },
  { key: 'borders', label: 'Fronteiras' },
  { key: 'capitals', label: 'Capitais' },
  { key: 'labels', label: 'Nomes', hint: 'Zoom in 1.5× to show labels' },
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
        <Text size="2" weight="bold">Camadas</Text>
        {LAYERS.map(({ key, label, hint }) => {
          // Row renders checkbox + label; when a hint exists, append a dim
          // inline suffix (e.g. "(zoom ≥ 1.5×)") so the gate is discoverable
          // even for users who never hover for the Tooltip to appear.
          const rowContent = (
            <Flex align="center" gap="2">
              <Checkbox
                checked={layerVisibility[key]}
                onCheckedChange={() => toggleLayer(key)}
              />
              <Text size="2">{label}</Text>
              {hint && (
                <Text size="1" color="gray">(zoom ≥ 1.5×)</Text>
              )}
            </Flex>
          )
          return hint ? (
            <Tooltip key={key} content={hint}>
              {rowContent}
            </Tooltip>
          ) : (
            <Flex key={key} align="center" gap="2">
              <Checkbox
                checked={layerVisibility[key]}
                onCheckedChange={() => toggleLayer(key)}
              />
              <Text size="2">{label}</Text>
            </Flex>
          )
        })}
      </Flex>
    </Card>
  )
}
