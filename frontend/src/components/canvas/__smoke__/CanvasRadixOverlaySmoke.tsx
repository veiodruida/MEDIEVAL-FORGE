import { Stage, Layer, Rect } from 'react-konva'
import { Card, Text, Flex, Checkbox } from '@radix-ui/themes'

export function CanvasRadixOverlaySmoke() {
  return (
    <div data-testid="smoke-root" style={{ position: 'relative', width: 800, height: 600 }}>
      <Stage width={800} height={600}>
        <Layer>
          <Rect x={0} y={0} width={800} height={600} fill="#ff00ff" />
        </Layer>
      </Stage>
      <Card
        data-testid="smoke-card"
        variant="surface"
        style={{ position: 'absolute', top: 12, left: 12, width: 200 }}
      >
        <Flex direction="column" gap="2">
          <Text size="2" weight="bold">Layers</Text>
          <Flex align="center" gap="2"><Checkbox defaultChecked /><Text size="2">Terrain</Text></Flex>
          <Flex align="center" gap="2"><Checkbox defaultChecked /><Text size="2">Territories</Text></Flex>
        </Flex>
      </Card>
    </div>
  )
}
