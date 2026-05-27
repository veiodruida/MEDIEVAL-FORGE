/**
 * Phase 08 D-12 + D-35 + D-37: TanStack Query hooks for snapshots and edit-events.
 *
 * Endpoints consumed (under /api/v3/projects/{pid}/branches/{bid}/...):
 *   POST   "/snapshots"                            → create snapshot (201)
 *   GET    "/snapshots"                            → list snapshots
 *   POST   "/snapshots/{snapshot_id}/restore"      → restore snapshot → payload
 *   POST   "/edit-events"                          → append edit event (201)
 *
 * Query key shape:
 *   ['v3', 'branches', projectId, branchId, 'snapshots']
 *
 * WARNING-6 wiring: useAppendEditEvent is consumed by EditorSyncBridge which
 * registers the mutation's mutateAsync as the EditEventSink in useEditorStore.
 * This is the SINGLE network chokepoint for all vertex mutations.
 *
 * D-37 auto-snapshot: useAppendEditEvent accepts snapshot_payload_if_due.
 * The backend auto-creates a snapshot when edits_since_snapshot reaches 25.
 * The response {auto_snapshot} is non-null when a snapshot was persisted.
 * EditorSyncBridge maps this to {snapshot_persisted: true} so the store can
 * reset editsSinceSnapshot to 0.
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'
import type { EditOp, VertexCoord } from '../stores/useEditorStore'

// ---------------------------------------------------------------------------
// Types (matching backend response shapes)
// ---------------------------------------------------------------------------

export interface SnapshotSummary {
  id: string
  seq: number
  trigger: 'auto' | 'manual' | 'pre_slider_change'
  created_at: string
  size_bytes: number
}

export interface SnapshotCreatePayload {
  trigger: 'auto' | 'manual' | 'pre_slider_change'
  payload: Record<string, unknown>
}

export interface SnapshotCreateResult {
  snapshot_id: string
  seq: number
  created_at: string
}

export interface EditEventPayload {
  op_type: string
  payload: Record<string, unknown>
  snapshot_payload_if_due?: {
    vertices: Record<string, VertexCoord>
    editLog: EditOp[]
  }
}

export interface EditEventResult {
  event_id: number
  auto_snapshot: { snapshot_id: string; seq: number } | { error: string } | null
  edits_since_snapshot: number
}

// ---------------------------------------------------------------------------
// Shared fetch helper
// ---------------------------------------------------------------------------

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    let message = `${res.status} ${res.statusText}: ${text}`
    try {
      const json = JSON.parse(text)
      if (typeof json.detail === 'string') message = json.detail
      else if (typeof json.detail?.message === 'string') message = json.detail.message
    } catch {
      /* not JSON — keep original */
    }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

function snapshotBaseUrl(projectId: string, branchId: string): string {
  return `/api/v3/projects/${projectId}/branches/${branchId}/snapshots`
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

/**
 * useBranchSnapshots — GET /api/v3/projects/{pid}/branches/{bid}/snapshots
 *
 * Returns snapshots in reverse-chronological order (highest seq first).
 * Enabled only when both projectId and branchId are defined.
 */
export function useBranchSnapshots(
  projectId: string | undefined,
  branchId: string | undefined,
) {
  return useQuery<SnapshotSummary[]>({
    queryKey: ['v3', 'branches', projectId, branchId, 'snapshots'],
    queryFn: () =>
      jsonFetch<SnapshotSummary[]>(snapshotBaseUrl(projectId!, branchId!)),
    enabled: Boolean(projectId) && Boolean(branchId),
    staleTime: 15_000,
  })
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

/**
 * useCreateSnapshot — POST /api/v3/projects/{pid}/branches/{bid}/snapshots
 *
 * D-12: creates full snapshot blob (GeoJSON + cfg + edit-op log).
 * Returns {snapshot_id, seq, created_at} on 201.
 * Throws 413 if payload exceeds server MAX_DECOMPRESSED_BYTES (Pitfall 9:
 * frontend ONLY opens restore modal if response is 201 — not on error).
 */
export function useCreateSnapshot(
  projectId: string | undefined,
  branchId: string | undefined,
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: SnapshotCreatePayload) =>
      jsonFetch<SnapshotCreateResult>(
        snapshotBaseUrl(projectId!, branchId!),
        { method: 'POST', body: JSON.stringify(payload) },
      ),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ['v3', 'branches', projectId, branchId, 'snapshots'],
      }),
  })
}

/**
 * useRestoreSnapshot — POST /api/v3/projects/{pid}/branches/{bid}/snapshots/{snapId}/restore
 *
 * PERSIST-02: decompresses snapshot blob and returns full payload.
 * Frontend uses returned payload to call switchBranch() and rehydrate the store.
 */
export function useRestoreSnapshot(
  projectId: string | undefined,
  branchId: string | undefined,
) {
  return useMutation({
    mutationFn: (snapshotId: string) =>
      jsonFetch<Record<string, unknown>>(
        `${snapshotBaseUrl(projectId!, branchId!)}/${snapshotId}/restore`,
        { method: 'POST' },
      ),
  })
}

/**
 * useAppendEditEvent — POST /api/v3/projects/{pid}/branches/{bid}/edit-events
 *
 * D-35 + D-37: logs edit op; auto-snapshots when counter reaches 25.
 *
 * IMPORTANT — WARNING-6 chokepoint:
 * This mutation is consumed by EditorSyncBridge (frontend/src/components/editor/
 * EditorSyncBridge.tsx) which registers mutateAsync as the EditEventSink in
 * useEditorStore. ALL vertex mutations from plans 08-06a/b/07/08 flow through
 * this single network call.
 *
 * Response mapping for store integration:
 *   {auto_snapshot: {snapshot_id, seq}} → {snapshot_persisted: true}
 *   {auto_snapshot: null}               → {snapshot_persisted: false}
 *   {auto_snapshot: {error: ...}}       → {snapshot_persisted: false} (silent retry)
 *
 * Throws 409 EDIT_LOG_FULL when branch exceeds 10 000 ops (T-08-03b-02).
 */
export function useAppendEditEvent(
  projectId: string | undefined,
  branchId: string | undefined,
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: EditEventPayload) =>
      jsonFetch<EditEventResult>(
        `/api/v3/projects/${projectId}/branches/${branchId}/edit-events`,
        { method: 'POST', body: JSON.stringify(payload) },
      ),
    onSuccess: (data) => {
      // If an auto-snapshot was persisted, invalidate snapshot list
      if (data.auto_snapshot && !('error' in data.auto_snapshot)) {
        qc.invalidateQueries({
          queryKey: ['v3', 'branches', projectId, branchId, 'snapshots'],
        })
      }
    },
  })
}
