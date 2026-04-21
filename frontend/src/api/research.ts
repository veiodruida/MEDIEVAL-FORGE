import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type AuthMethod =
  | { type: "api_key"; env_var: string | null }
  | { type: "oauth"; authorize_url: string | null; scopes: string[] }
  | { type: "cli"; cli_command: string; auth_file_path: string }
  | { type: "none" };

export type Provider = {
  provider_id: "claude" | "openai" | "gemini" | "ollama";
  display_name: string;
  auth_methods: AuthMethod[];
  configured: boolean;
  healthy: boolean;
  default_model: string;
};

export type ResearchResult = {
  kingdoms: Record<string, string>;
  duchies: Record<string, [string, string]>;
  condados_assignment: Array<{ condado_id: string; kingdom_id: string; duchy_id: string }>;
  baronies: Record<string, Array<{ name: string; lon: number; lat: number }>>;
};

export const useProvidersQuery = () =>
  useQuery<Provider[]>({
    queryKey: ["llm", "providers"],
    queryFn: async () => {
      const r = await fetch("/api/llm/providers");
      if (!r.ok) throw new Error(`providers ${r.status}`);
      return r.json();
    },
    staleTime: 10_000,
  });

export const useHealthQuery = () =>
  useQuery<Record<string, { healthy: boolean; message: string }>>({
    queryKey: ["llm", "health"],
    queryFn: async () => {
      const r = await fetch("/api/llm/health");
      if (!r.ok) throw new Error(`health ${r.status}`);
      return r.json();
    },
    refetchInterval: 30_000,
  });

export const useCachedResultQuery = (
  projectId: string,
  provider: string,
  enabled: boolean
) =>
  useQuery<ResearchResult | null>({
    queryKey: ["research", "cached", projectId, provider],
    queryFn: async () => {
      const r = await fetch(
        `/api/projects/${projectId}/research/cached?provider=${provider}`
      );
      if (r.status === 404) return null;
      if (!r.ok) throw new Error(`cached ${r.status}`);
      return r.json();
    },
    enabled,
  });

export const useStoreCredentialMutation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { provider: string; api_key: string }) => {
      const r = await fetch(`/api/auth/credentials/${vars.provider}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: vars.api_key }),
      });
      if (!r.ok) throw new Error(`store ${r.status}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm"] }),
  });
};

export const useClearCredentialMutation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (provider: string) => {
      const r = await fetch(`/api/auth/credentials/${provider}`, {
        method: "DELETE",
      });
      if (!r.ok) throw new Error(`clear ${r.status}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm"] }),
  });
};

export const useOAuthStartMutation = () =>
  useMutation({
    mutationFn: async (provider: string) => {
      const r = await fetch(`/api/auth/oauth/${provider}/start`, {
        method: "POST",
      });
      if (!r.ok) throw new Error(`oauth-start ${r.status}`);
      return r.json() as Promise<{ authorize_url: string; state: string }>;
    },
  });
