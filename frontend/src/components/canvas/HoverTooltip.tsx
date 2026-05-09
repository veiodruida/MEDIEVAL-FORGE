import { Card, Text } from '@radix-ui/themes'

interface Props {
  name: string | null
  x: number
  y: number
}

/**
 * D-15 hover tooltip — DOM div sibling to the Konva Stage, positioned via
 * Stage.getPointerPosition() coordinates fed in by the parent CanvasViewer.
 *
 * Radix Themes Tooltip cannot portal onto a Konva Stage (no DOM anchor), so
 * we render an absolute-positioned div with pointer-events:none and z-index:50
 * sitting above the canvas. The +8/+8 offset keeps the cursor from overlapping
 * the tooltip text.
 *
 * Returns null when name is null — keeps the DOM clean and allows React to
 * skip rendering when the pointer leaves the canvas.
 */
export function HoverTooltip({ name, x, y }: Props) {
  if (!name) return null
  return (
    <div
      style={{
        position: 'absolute',
        left: x + 8,
        top: y + 8,
        pointerEvents: 'none',
        zIndex: 50,
      }}
    >
      <Card variant="surface" style={{ padding: '4px 8px' }}>
        <Text size="1">{name}</Text>
      </Card>
    </div>
  )
}
