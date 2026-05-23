/**
 * TanStack Query hooks for the credentials manager (UAT 2026-05-23).
 *
 * Backs the CredentialsManager dialog. The list endpoint NEVER returns
 * the raw key (T-07.2-CRED-01 mitigation) — only `{has_key, source}` so
 * the UI can render a status badge per provider.
 *
 * Endpoints (mounted at /api/v3/credentials):
 *   GET    /credentials                — list status rows
 *   PUT    /credentials/{provider_id}  — set a single key (body: { key })
 *   DELETE /credentials/{provider_id}  — wipe a single key
 *   POST   /credentials/import         — batch import from a .env blob
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

export interface CredentialStatus {
  provider_id: string
  display_name: string
  configured: boolean
  has_key: boolean
  source: 'db' | 'env' | 'none'
  env_var: string | null
  accepts_api_key: boolean
}

export interface ImportResult {
  imported: string[]
  skipped: string[]
  known_env_vars: string[]
}

export interface DiscoverResult {
  imported: string[]
  paths_checked: string[]
  paths_with_keys: string[]
}

const QUERY_KEY = ['v3', 'credentials'] as const

export function useCredentials(enabled = true) {
  return useQuery<CredentialStatus[]>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const r = await fetch('/api/v3/credentials')
      if (!r.ok) throw new Error(`credentials list failed: ${r.status}`)
      return r.json()
    },
    enabled,
    staleTime: 10_000,
  })
}

export function useSetCredential() {
  const qc = useQueryClient()
  return useMutation<
    { ok: boolean; provider_id: string },
    Error,
    { providerId: string; key: string }
  >({
    mutationFn: async ({ providerId, key }) => {
      const r = await fetch(`/api/v3/credentials/${providerId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      })
      if (!r.ok) {
        const text = await r.text()
        throw new Error(text || `set credential failed: ${r.status}`)
      }
      return r.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      // Provider health flips healthy=true once a key lands, so refresh
      // /providers too. The list is used by ProviderSelector to render
      // the dropdown's "indisponível" badge.
      qc.invalidateQueries({ queryKey: ['v3', 'research', 'providers'] })
    },
  })
}

export function useDeleteCredential() {
  const qc = useQueryClient()
  return useMutation<
    { ok: boolean; provider_id: string },
    Error,
    { providerId: string }
  >({
    mutationFn: async ({ providerId }) => {
      const r = await fetch(`/api/v3/credentials/${providerId}`, {
        method: 'DELETE',
      })
      if (!r.ok) {
        const text = await r.text()
        throw new Error(text || `delete credential failed: ${r.status}`)
      }
      return r.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['v3', 'research', 'providers'] })
    },
  })
}

export function useImportDotenv() {
  const qc = useQueryClient()
  return useMutation<ImportResult, Error, { text: string }>({
    mutationFn: async ({ text }) => {
      const r = await fetch('/api/v3/credentials/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!r.ok) {
        const body = await r.text()
        throw new Error(body || `.env import failed: ${r.status}`)
      }
      return r.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['v3', 'research', 'providers'] })
    },
  })
}

/**
 * Manual rescan of well-known `.env` locations (~/.env,
 * ~/.medieval-forge/.env, ./.env). The same routine runs once on
 * backend startup; this hook lets the user trigger it again after
 * dropping a fresh file without restarting the backend.
 */
export function useDiscoverDotenv() {
  const qc = useQueryClient()
  return useMutation<DiscoverResult, Error, void>({
    mutationFn: async () => {
      // GET (not POST) — see backend note: avoids the `POST /{provider}`
      // wildcard intercepting "discover" as a provider id.
      const r = await fetch('/api/v3/credentials/discover')
      if (!r.ok) {
        const body = await r.text()
        throw new Error(body || `.env discover failed: ${r.status}`)
      }
      return r.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['v3', 'research', 'providers'] })
    },
  })
}
