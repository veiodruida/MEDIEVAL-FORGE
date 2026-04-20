import { Card, Flex, Text } from '@radix-ui/themes'

const ITEMS: { color: 'amber' | 'blue' | 'grass'; label: string }[] = [
  { color: 'amber', label: 'Reino' },
  { color: 'blue', label: 'Duquia' },
  { color: 'grass', label: 'Condado' },
]

/**
 * Static legend card explaining the hierarchy badge colors used by
 * InspectorSidebar. Positioned bottom-left of the canvas so it does not
 * collide with LayerTogglePanel (top-left) or FitToViewButton (top-right).
 *
 * Quick-task 260420-hkr. No dynamic data — pure key for the amber/blue/grass
 * swatches; the gray "Baronies" badge is a count, not a hierarchy color.
 */
export function LegendCard() {
  return (
    <Card
      variant="surface"
      style={{ position: 'absolute', bottom: 12, left: 12, zIndex: 10, width: 160 }}
    >
      <Flex direction="column" gap="2">
        <Text size="2" weight="bold">Legenda</Text>
        {ITEMS.map(({ color, label }) => (
          <Flex key={label} align="center" gap="2">
            <span
              aria-hidden
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: `var(--${color}-9)`,
              }}
            />
            <Text size="2">{label}</Text>
          </Flex>
        ))}
      </Flex>
    </Card>
  )
}
