import { useMemo } from 'react'
import { useQueries, keepPreviousData } from '@tanstack/react-query'
import { geoRingToKonvaPoints, type ProjectionConfig } from '../lib/projection'
import type { StageView } from '../api/render'

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
  // D-03 (Phase 04.1): geo centroid in lon/lat (degrees). Available when
  // the backend baronies.geojson includes the `centroid` property.
  centroid?: [number, number]
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
  // neighbors is NOT present on condados in territory_metadata.json; it is hoisted
  // client-side from territories.geojson .properties.neighbors by useCanvasArtifacts.
  // Callers see a merged TerritoryMetadata where every condado has neighbors: string[]
  // (empty array fallback if territories.geojson is not yet loaded). Quick-task 260420-hkr.
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
  properties: {
    id: string
    name: string
    condado_id: string
    fill: string
    // D-03 (Phase 04.1): backend canvas_sidecars.py emits the geo centroid
    // [lon, lat] for every barony. Optional because old artifacts on disk
    // (pre-Phase 04.1) may lack the field; downstream code falls back to
    // undefined rather than crashing.
    centroid?: [number, number]
  }
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
 * Returns a 6-tuple: 5 query results + stageRasterUrl string.
 * [0] territories.geojson → TerritoryRender[]
 * [1] baronies.geojson → BaronyRender[]
 * [2] condado_colors.json → Record<condado_id, '#rrggbb'> (sidecar from plan 02-04)
 * [3] barony_colors.json  → Record<barony_name, '#rrggbb'> (sidecar from plan 02-04)
 * [4] territory_metadata.json → TerritoryMetadata
 * [5] stageRasterUrl: string — URL of the raster to display in BackgroundLayer:
 *     - stageView === 'render-final' → /artifacts/visual_condado.png
 *     - otherwise → /stage/{stageView}.png (Plan 04-02 endpoint)
 *
 * queryKeys are re-keyed on stageView so a stage-view switch invalidates the
 * TanStack in-memory cache and forces re-fetch (D-09/D-10/D-11 visualization).
 *
 * Consumer migration note: plans 2.2 and 2.3 destructure by index.
 * The original lookup_*_colors.json files on disk keep their Unity-consumed
 * {"r,g,b": idx} shape untouched (D-04 black-box); the frontend consumes
 * these sidecar files instead.
 */
export function useCanvasArtifacts(
  projectId: string | undefined,
  projection: ProjectionConfig | null,
  // Cache-bust token: pass project.updated_at so that when the pipeline
  // regenerates, the queryKey AND the URL both change. The queryKey change
  // invalidates TanStack's in-memory cache; the URL change (?v=…) invalidates
  // the browser HTTP cache. Without this, staleTime: Infinity would hold the
  // prior map forever until a hard-refresh.
  cacheVersion?: string,
  // stageView differentiates which stage raster to show in BackgroundLayer.
  // Defaults to 'render-final' to preserve existing behavior for callers that
  // don't pass stageView. All 5 queryKeys include stageView so a stage-view
  // radio switch invalidates the TanStack cache (D-09/D-10/D-11).
  stageView: StageView = 'render-final',
) {
  const v = cacheVersion ? `?v=${encodeURIComponent(cacheVersion)}` : ''

  // 6th return value: URL of the raster that BackgroundLayer should display.
  // When stageView === 'render-final': use existing visual_condado.png path.
  // Otherwise: use the /stage/{name}.png endpoint added by Plan 04-02.
  const stageRasterUrl =
    stageView === 'render-final'
      ? `/api/v3/projects/${projectId}/artifacts/visual_condado.png${v}`
      : `/api/v3/projects/${projectId}/stage/${stageView}.png${v}`

  const results = useQueries({
    queries: [
      {
        // [0] territories.geojson → TerritoryRender[]
        queryKey: ['territories-geojson', projectId, cacheVersion, stageView] as const,
        queryFn: () =>
          fetchJson<FC<CondadoFeature>>(
            `/api/v3/projects/${projectId}/artifacts/territories.geojson${v}`,
          ),
        enabled: Boolean(projectId && projection),
        staleTime: Infinity,
        gcTime: Infinity,
        // Plan 04.1-05 D-01 E2E fix: keep prior data visible during cacheVersion
        // refetch so CanvasViewer stays out of the "Loading map…" branch.
        // Without this, the Stage unmounts on every slider drag → remount
        // resets prevBoundsKeyRef → fitToView fires → zoom reset (UAT gap #1).
        placeholderData: keepPreviousData,
        select: (raw: FC<CondadoFeature>): TerritoryRender[] => {
          if (!projection) return []
          const result: TerritoryRender[] = []
          for (const f of raw.features) {
            const rings: [number, number][][] =
              f.geometry.type === 'Polygon'
                ? [f.geometry.coordinates[0]]
                : f.geometry.coordinates.map((poly) => poly[0])
            for (const ring of rings) {
              result.push({
                id: f.properties.id,
                name: f.properties.name,
                points: geoRingToKonvaPoints(ring, projection),
                neighbors: f.properties.neighbors,
              })
            }
          }
          return result
        },
      },
      {
        // [1] baronies.geojson → BaronyRender[]
        queryKey: ['baronies-geojson', projectId, cacheVersion, stageView] as const,
        queryFn: () =>
          fetchJson<FC<BaronyFeature>>(
            `/api/v3/projects/${projectId}/artifacts/baronies.geojson${v}`,
          ),
        enabled: Boolean(projectId && projection),
        staleTime: Infinity,
        gcTime: Infinity,
        placeholderData: keepPreviousData,  // Plan 04.1-05 D-01 fix
        select: (raw: FC<BaronyFeature>): BaronyRender[] => {
          if (!projection) return []
          return raw.features.map((f) => ({
            id: f.properties.id,
            name: f.properties.name,
            condado_id: f.properties.condado_id,
            fill: f.properties.fill,
            points: geoRingToKonvaPoints(firstOuterRing(f.geometry), projection),
            centroid: f.properties.centroid,  // D-03: pass through if present
          }))
        },
      },
      {
        // [2] condado_colors.json sidecar — {condado_id: '#rrggbb'}
        queryKey: ['condado-colors', projectId, cacheVersion, stageView] as const,
        queryFn: () =>
          fetchJson<Record<string, string>>(
            `/api/v3/projects/${projectId}/artifacts/condado_colors.json${v}`,
          ),
        enabled: Boolean(projectId),
        staleTime: Infinity,
        gcTime: Infinity,
        placeholderData: keepPreviousData,  // Plan 04.1-05 D-01 fix
      },
      {
        // [3] barony_colors.json sidecar — {barony_name: '#rrggbb'}
        queryKey: ['barony-colors', projectId, cacheVersion, stageView] as const,
        queryFn: () =>
          fetchJson<Record<string, string>>(
            `/api/v3/projects/${projectId}/artifacts/barony_colors.json${v}`,
          ),
        enabled: Boolean(projectId),
        staleTime: Infinity,
        gcTime: Infinity,
        placeholderData: keepPreviousData,  // Plan 04.1-05 D-01 fix
      },
      {
        // [4] territory_metadata.json
        queryKey: ['territory-metadata', projectId, cacheVersion, stageView] as const,
        queryFn: () =>
          fetchJson<TerritoryMetadata>(
            `/api/v3/projects/${projectId}/artifacts/territory_metadata.json${v}`,
          ),
        enabled: Boolean(projectId),
        staleTime: Infinity,
        gcTime: Infinity,
        placeholderData: keepPreviousData,  // Plan 04.1-05 D-01 fix
      },
    ],
  })

  // Quick-task 260420-hkr: hoist neighbors from territories.geojson into
  // metadata.condados. The server's territory_metadata.json does NOT include
  // neighbor adjacency on condados; only territories.geojson features carry
  // .properties.neighbors. InspectorSidebar reads condado.neighbors.length,
  // which would crash on undefined. We merge here so every consumer of [4].data
  // sees a TerritoryMetadata with neighbors: string[] on every condado.
  const territoriesData = results[0].data
  const metaData = results[4].data
  const mergedMeta = useMemo<TerritoryMetadata | undefined>(() => {
    if (!metaData) return metaData
    if (!territoriesData) {
      return {
        ...metaData,
        condados: metaData.condados.map((c) => ({ ...c, neighbors: [] })),
      }
    }
    const neighborMap = new Map<string, string[]>()
    for (const t of territoriesData) {
      neighborMap.set(t.id, t.neighbors ?? [])
    }
    return {
      ...metaData,
      condados: metaData.condados.map((c) => ({
        ...c,
        neighbors: neighborMap.get(c.id) ?? [],
      })),
    }
  }, [territoriesData, metaData])

  // 6-tuple return: 5 query results + stageRasterUrl (string, not a query).
  // Consumers destructuring by index are backward-compatible up to index [4].
  // Index [5] is new for Phase 04: CanvasViewer reads it as BackgroundLayer src.
  return [
    results[0],
    results[1],
    results[2],
    results[3],
    { ...results[4], data: mergedMeta },
    stageRasterUrl,
  ] as const
}
