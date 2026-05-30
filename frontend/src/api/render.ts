/**
 * Phase 04 D-04 backend interface helpers.
 *
 * Wraps the 3 render endpoints + stage raster URL builder. CfgOverrides matches
 * the Pydantic RenderRequest.cfg_overrides on the backend (api/v3/render.py).
 */

export interface CfgOverrides {
  smooth_sigma?: number
  median_passes?: number
  fragment_min_px?: number
  blob_merge_px?: number
}

export type StageView =
  | 'landmask'
  | 'voronoi-raw'
  | 'cleanup'
  | 'smooth'
  | 'render-final'

export interface RenderResponse {
  run_id: string
  status: 'scheduled'
  kind: 'render'
}

export async function postRender(
  projectId: string,
  cfgOverrides: CfgOverrides,
  stageView?: StageView,
  branchId?: string,
): Promise<RenderResponse> {
  const body = JSON.stringify({
    cfg_overrides: cfgOverrides,
    stage_view: stageView,
    ...(branchId ? { branch_id: branchId } : {}),
  })
  const res = await fetch(`/api/v3/projects/${projectId}/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })
  if (!res.ok) {
    if (res.status === 409) throw new Error('RENDER_BUSY')
    if (res.status === 422) throw new Error('RENDER_VALIDATION')
    throw new Error(`RENDER_FAILED_${res.status}`)
  }
  return res.json() as Promise<RenderResponse>
}

export async function postRenderCancel(projectId: string): Promise<void> {
  const res = await fetch(`/api/v3/projects/${projectId}/render/cancel`, {
    method: 'POST',
  })
  // 404 means no alive task; treat as success (already done/cancelled).
  if (!res.ok && res.status !== 404) {
    throw new Error(`CANCEL_FAILED_${res.status}`)
  }
}

export function getStageRasterUrl(
  projectId: string,
  stageName: StageView,
  cacheVersion?: string,
): string {
  // render-final reads the existing visual_*.png artifacts directly — caller
  // should NOT call this for render-final.
  const v = cacheVersion ? `?v=${encodeURIComponent(cacheVersion)}` : ''
  return `/api/v3/projects/${projectId}/stage/${stageName}.png${v}`
}
