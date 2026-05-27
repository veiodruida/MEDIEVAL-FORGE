/**
 * Phase 08 D-10..D-15: TanStack Query hooks for branch CRUD.
 *
 * Endpoints consumed (all under /api/v3/projects/{project_id}/branches):
 *   GET    ""                         → list branches (lazy-creates main)
 *   POST   ""                         → create branch (201)
 *   PATCH  "/{branch_id}"             → rename branch (200)
 *   DELETE "/{branch_id}"             → delete branch (204; 409 on main)
 *
 * Query key shape (mirrors useProviders / useProject patterns):
 *   ['v3', 'branches', projectId]
 *
 * Error handling: backend returns structured {detail: string | object} on
 * 409/400; jsonFetch extracts detail.message for BranchNameTakenError /
 * BranchProtectedError so consumers can display meaningful messages.
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Types (matching _branch_dict shape from branches.py router)
// ---------------------------------------------------------------------------

export interface Branch {
  id: string
  name: string
  is_main: boolean
  original_idx_high_water: number
  edits_since_snapshot: number
  created_at: string
  updated_at: string
}

export interface BranchCreatePayload {
  name: string
  parent_branch_id?: string | null
}

export interface BranchRenamePayload {
  name: string
}

// ---------------------------------------------------------------------------
// Shared fetch helper (mirrors useProject.ts jsonFetch pattern)
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

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

/**
 * useBranches — GET /api/v3/projects/{projectId}/branches
 *
 * Lazy-creates the `main` branch on first hit (D-10). Returns branches ordered
 * by updated_at desc. Enabled only when projectId is defined.
 */
export function useBranches(projectId: string | undefined) {
  return useQuery<Branch[]>({
    queryKey: ['v3', 'branches', projectId],
    queryFn: () =>
      jsonFetch<Branch[]>(`/api/v3/projects/${projectId}/branches`),
    enabled: Boolean(projectId),
    staleTime: 10_000,
  })
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

/**
 * useCreateBranch — POST /api/v3/projects/{projectId}/branches
 *
 * D-11: explicit branch creation only (no fork-on-first-edit).
 * D-22: inherits parent_branch_id original_idx_high_water if provided.
 * Returns {id, name, is_main} on 201.
 * Throws on 400 (name reserved / pattern violation) or 409 (name taken).
 */
export function useCreateBranch(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: BranchCreatePayload) =>
      jsonFetch<{ id: string; name: string; is_main: boolean }>(
        `/api/v3/projects/${projectId}/branches`,
        { method: 'POST', body: JSON.stringify(payload) },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['v3', 'branches', projectId] }),
  })
}

/**
 * useRenameBranch — PATCH /api/v3/projects/{projectId}/branches/{branchId}
 *
 * D-15: rename allowed on main. Returns {id, name}.
 * Throws on 409 (name taken).
 */
export function useRenameBranch(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      branchId,
      payload,
    }: {
      branchId: string
      payload: BranchRenamePayload
    }) =>
      jsonFetch<{ id: string; name: string }>(
        `/api/v3/projects/${projectId}/branches/${branchId}`,
        { method: 'PATCH', body: JSON.stringify(payload) },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['v3', 'branches', projectId] }),
  })
}

/**
 * useDeleteBranch — DELETE /api/v3/projects/{projectId}/branches/{branchId}
 *
 * D-15: main branch is delete-protected → 409 BRANCH_PROTECTED.
 * Returns void on 204.
 */
export function useDeleteBranch(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (branchId: string) =>
      jsonFetch<void>(
        `/api/v3/projects/${projectId}/branches/${branchId}`,
        { method: 'DELETE' },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['v3', 'branches', projectId] }),
  })
}
