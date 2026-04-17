import { Image, Layer } from 'react-konva'
import useImage from 'use-image'

interface BackgroundLayerProps {
  /** URL of the terrain PNG to render as background */
  src: string
  mapW: number
  mapH: number
}

/**
 * Renders the terrain PNG as the bottom-most Konva layer.
 * listening={false} disables hit detection on this layer (plan 2.1 — read-only).
 * Interaction layers added in plans 2.2/2.3 sit above this.
 */
export function BackgroundLayer({ src, mapW, mapH }: BackgroundLayerProps) {
  const [image] = useImage(src, 'anonymous')

  return (
    <Layer listening={false}>
      {image && (
        <Image
          image={image}
          x={0}
          y={0}
          width={mapW}
          height={mapH}
          listening={false}
        />
      )}
    </Layer>
  )
}
