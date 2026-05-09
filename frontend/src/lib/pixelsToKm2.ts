import type { TerritoryMetadata } from '../hooks/useCanvasArtifacts'

/**
 * Convert a pixel count to approximate km² using the territory metadata's
 * lat/lon bounds + map_size as the conversion frame.
 *
 * Pitfall 7: bounds + map_size MUST come from the loaded
 * `territory_metadata.json`. The center-latitude lon-scale correction handles
 * meridian convergence; without it, km² estimates near the poles are off by
 * ~30% for Iberia-latitude maps.
 *
 * Returns 0 if metadata is missing required fields (graceful fallback so the
 * inspector renders even with partial data during loading transitions).
 */
export function pixelsToKm2(
  pixelCount: number,
  metadata: Pick<TerritoryMetadata, 'bounds' | 'map_size'> | null | undefined,
): number {
  if (!metadata?.bounds || !metadata.map_size) return 0
  const { bounds, map_size } = metadata
  const centerLat = (bounds.lat_min + bounds.lat_max) / 2
  const lonScale = Math.cos((centerLat * Math.PI) / 180)
  const latKm = (bounds.lat_max - bounds.lat_min) * 111.32
  const lonKm = (bounds.lon_max - bounds.lon_min) * lonScale * 111.32
  const totalKm2 = latKm * lonKm
  const totalPixels = map_size[0] * map_size[1]
  if (totalPixels === 0) return 0
  return (pixelCount * totalKm2) / totalPixels
}
