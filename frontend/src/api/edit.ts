import type {
  MoveCapitalRequest,
  MoveCapitalResponse,
  MergeRequest,
  MergeResponse,
  SplitRequest,
  SplitResponse,
  ReshapeGeometryRequest,
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

export const moveCapital = (
  projectId: string,
  condadoId: string,
  req: MoveCapitalRequest,
): Promise<MoveCapitalResponse> =>
  postJson(`/projects/${projectId}/territories/${condadoId}/recalc`, req)

export const mergeTerritories = (
  projectId: string,
  req: MergeRequest,
): Promise<MergeResponse> =>
  postJson(`/projects/${projectId}/territories/merge`, req)

export const splitTerritory = (
  projectId: string,
  condadoId: string,
  req: SplitRequest,
): Promise<SplitResponse> =>
  postJson(`/projects/${projectId}/territories/${condadoId}/split`, req)

export const reshapeGeometry = (
  projectId: string,
  condadoId: string,
  req: ReshapeGeometryRequest,
): Promise<{ condado_id: string; ok: true }> =>
  patchJson(`/projects/${projectId}/territories/${condadoId}/geometry`, req)
