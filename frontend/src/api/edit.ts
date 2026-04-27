import type {
  MoveCapitalRequest,
  MoveCapitalResponse,
  MergeRequest,
  MergeResponse,
  SplitRequest,
  SplitResponse,
  ReshapeGeometryRequest,
  GeoJSONPolygon,
  GeoJSONMultiPolygon,
  Position,
  PaintTerrainRequest,
  PaintTerrainResponse,
} from '../types/editing'

const API_BASE = '/api'

export class EditApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'EditApiError'
  }
}

async function postJson<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new EditApiError(res.status, text)
  }
  return res.json() as Promise<TRes>
}

async function patchJson<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new EditApiError(res.status, text)
  }
  return res.json() as Promise<TRes>
}

/**
 * D-07: Persist flag controls whether each backend edit endpoint writes to
 * territories.geojson. When persist=false, the backend computes and returns
 * the new geometry but does NOT call save_territories. The frontend holds
 * the unsaved state in Zustand until the user flushes via Ctrl+S
 * (POST /api/projects/{id}/geometry/save).
 */
export interface EditOptions {
  persist: boolean
}

export const moveCapital = (
  projectId: string,
  condadoId: string,
  req: MoveCapitalRequest,
  opts: EditOptions = { persist: true },
): Promise<MoveCapitalResponse> => {
  const qs = opts.persist ? '' : '?persist=false'
  return postJson(`/projects/${projectId}/territories/${condadoId}/recalc${qs}`, req)
}

export const mergeTerritories = (
  projectId: string,
  req: MergeRequest,
  opts: EditOptions = { persist: true },
): Promise<MergeResponse> => {
  const qs = opts.persist ? '' : '?persist=false'
  return postJson(`/projects/${projectId}/territories/merge${qs}`, req)
}

export const splitTerritory = (
  projectId: string,
  condadoId: string,
  req: SplitRequest,
  opts: EditOptions = { persist: true },
): Promise<SplitResponse> => {
  const qs = opts.persist ? '' : '?persist=false'
  return postJson(`/projects/${projectId}/territories/${condadoId}/split${qs}`, req)
}

export const reshapeGeometry = (
  projectId: string,
  condadoId: string,
  req: ReshapeGeometryRequest,
  opts: EditOptions = { persist: true },
): Promise<{ condado_id: string; ok: true }> => {
  const qs = opts.persist ? '' : '?persist=false'
  return patchJson(`/projects/${projectId}/territories/${condadoId}/geometry${qs}`, req)
}

// --- Vertex handles (Plan 04 Task 3: Douglas-Peucker decimation endpoint) ---

export interface VertexHandle {
  lon: number
  lat: number
  source_index: number
}

export interface VertexHandlesResponse {
  handles: VertexHandle[]
}

export const fetchVertexHandles = (
  projectId: string,
  condadoId: string,
  target = 12,
): Promise<VertexHandlesResponse> =>
  fetch(`${API_BASE}/projects/${projectId}/territories/${condadoId}/vertex-handles?target=${target}`)
    .then((r) => {
      if (!r.ok) throw new EditApiError(r.status, r.statusText)
      return r.json() as Promise<VertexHandlesResponse>
    })

// --- D-07: Full-snapshot save (explicit strategy flush) ---

export interface SaveSnapshotRequest {
  territories: Record<string, GeoJSONPolygon | GeoJSONMultiPolygon>
  capitals: Record<string, Position>
}

/**
 * Flush full in-memory geometry snapshot to backend (D-07 explicit strategy).
 * Called on Ctrl+S when strategy === 'explicit'.
 * Backend endpoint: POST /api/projects/{id}/geometry/save
 */
export const saveSnapshot = (
  projectId: string,
  req: SaveSnapshotRequest,
): Promise<{ ok: true }> =>
  postJson(`/projects/${projectId}/geometry/save`, req)

// --- Phase 5: Terrain paint (EDIT-05) ---

/**
 * Assign terrain_type to a set of territories.
 * Backend validates land mask per centroid (ocean cells land in skipped_ids).
 * Persistence is server-side and unconditional — paint strokes always write through.
 * Backend endpoint: POST /api/projects/{id}/edit/paint-terrain
 */
export const paintTerrain = (
  projectId: string,
  req: PaintTerrainRequest,
): Promise<PaintTerrainResponse> =>
  postJson(`/projects/${projectId}/edit/paint-terrain`, req)
