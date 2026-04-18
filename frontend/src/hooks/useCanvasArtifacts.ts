import { useQueries } from '@tanstack/react-query'
import { geoRingToKonvaPoints, type ProjectionConfig } from '../lib/projection'

export interface TerritoryRender {
  id: string
  name: string
  points: number[]
  neighbors: string[]  // required string[] — populated by Task 1 territories.geojson emission
}

export interface BaronyRender {
  id: string
  name: string
  condado_id: string
  fill: string
  points: number[]
}

export interface TerritoryMetadataCondado {
  id: string
  name: string
  lon: number
  lat: number
  duchy: string
  kingdom: string
  pixel_center: [number, number]
  pixel_count: number
  baronies: string[]
  // neighbors is populated by Task 1 territories.geojson emission (hoisted client-side
  // when merging territories.geojson with metadata); always string[] for Phase 2 condados.
  neighbors: string[]
  // Optional capital city name (D-06.3). Present when the generator has a curated
  // capital name; absent triggers the "No capital assigned" sentinel in InspectorSidebar.
  capital_name?: string
}

export interface TerritoryMetadata {
  region: string
  map_size: [number, number]
  bounds: { lon_min: number; lon_max: number; lat_min: number; lat_max: number }
  kingdoms: Record<string, string>
  duchies: Record<string, { kingdom: string; name: string }>
  condados: TerritoryMetadataCondado[]
  baronies: Array<{ name: string; condado_idx: number; duchy: string; pixel_count: number }>
}

interface CondadoFeature {
  type: 'Feature'
  id: string
  geometry:
    | { type: 'Polygon'; coordinates: [number, number][][] }
    | { type: 'MultiPolygon'; coordinates: [number, number][][][] }
  properties: { id: string; name: string; neighbors: string[] }
}

interface BaronyFeature {
  type: 'Feature'
  id: string
  geometry:
    | { type: 'Polygon'; coordinates: [number, number][][] }
    | { type: 'MultiPolygon'; coordinates: [number, number][][][] }
  properties: { id: string; name: string; condado_id: string; fill: string }
}

interface FC<F> {
  type: 'FeatureCollection'
  features: F[]
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    if (res.status === 404) throw new Error('MAP_NOT_GENERATED')
    throw new Error('FETCH_FAILED')
  }
  return res.json() as Promise<T>
}

function firstOuterRing(
  g: CondadoFeature['geometry'] | BaronyFeature['geometry'],
): [number, number][] {
  return g.type === 'Polygon' ? g.coordinates[0] : g.coordinates[0][0]
}

/**
 * Returns a 5-tuple of query results:
 * [0] territories.geojson → TerritoryRender[]
 * [1] baronies.geojson → BaronyRender[]
 * [2] lookup_condado_colors.json → Record<string, string>
 * [3] lookup_barony_colors.json → Record<string, string>  (fallback display paths)
 * [4] territory_metadata.json → TerritoryMetadata
 *
 * Consumer migration note: plans 2.2 and 2.3 destructure by index.
 */
export function useCanvasArtifacts(
  projectId: string | undefined,
  projection: ProjectionConfig | null,
) {
  return useQueries({
    queries: [
      {
        // [0] territories.geojson → TerritoryRender[]
        queryKey: ['territories-geojson', projectId] as const,
        queryFn: () =>
          fetchJson<FC<CondadoFeature>>(
            `/api/projects/${projectId}/preview/territories.geojson`,
          ),
        enabled: Boolean(projectId && projection),
        staleTime: Infinity,
        gcTime: Infinity,
        select: (raw: FC<CondadoFeature>): TerritoryRender[] => {
          if (!projection) return []
          return raw.features.map((f) => ({
            id: f.properties.id,
            name: f.properties.name,
            points: geoRingToKonvaPoints(firstOuterRing(f.geometry), projection),
            neighbors: f.properties.neighbors,
          }))
        },
      },
      {
        // [1] baronies.geojson → BaronyRender[]
        queryKey: ['baronies-geojson', projectId] as const,
        queryFn: () =>
          fetchJson<FC<BaronyFeature>>(
            `/api/projects/${projectId}/preview/baronies.geojson`,
          ),
        enabled: Boolean(projectId && projection),
        staleTime: Infinity,
        gcTime: Infinity,
        select: (raw: FC<BaronyFeature>): BaronyRender[] => {
          if (!projection) return []
          return raw.features.map((f) => ({
            id: f.properties.id,
            name: f.properties.name,
            condado_id: f.properties.condado_id,
            fill: f.properties.fill,
            points: geoRingToKonvaPoints(firstOuterRing(f.geometry), projection),
          }))
        },
      },
      {
        // [2] lookup_condado_colors.json
        queryKey: ['condado-colors', projectId] as const,
        queryFn: () =>
          fetchJson<Record<string, string>>(
            `/api/projects/${projectId}/preview/lookup_condado_colors.json`,
          ),
        enabled: Boolean(projectId),
        staleTime: Infinity,
        gcTime: Infinity,
      },
      {
        // [3] lookup_barony_colors.json (kept for fallback display paths)
        queryKey: ['barony-colors', projectId] as const,
        queryFn: () =>
          fetchJson<Record<string, string>>(
            `/api/projects/${projectId}/preview/lookup_barony_colors.json`,
          ),
        enabled: Boolean(projectId),
        staleTime: Infinity,
        gcTime: Infinity,
      },
      {
        // [4] territory_metadata.json
        queryKey: ['territory-metadata', projectId] as const,
        queryFn: () =>
          fetchJson<TerritoryMetadata>(
            `/api/projects/${projectId}/preview/territory_metadata.json`,
          ),
        enabled: Boolean(projectId),
        staleTime: Infinity,
        gcTime: Infinity,
      },
    ],
  })
}
