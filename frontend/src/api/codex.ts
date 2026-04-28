// CodexResult TS types mirroring backend/medieval_forge/services/llm/schemas.py (lines 134-217).
// The 12 category keys are fixed by the backend Pydantic schema with extra='forbid'.
export const CODEX_CATEGORY_KEYS = [
  "currency", "attributes", "health", "traits",
  "feudal",   "politics",   "dynasty","religion",
  "culture",  "economy",    "military","events",
] as const;

export type CodexCategoryKey = typeof CODEX_CATEGORY_KEYS[number];

// Portuguese display labels for the tab UI (pt-BR copy).
// Map keys are the 12 backend keys above.
export const CODEX_CATEGORY_LABELS: Record<CodexCategoryKey, string> = {
  currency:   "Moeda",
  attributes: "Atributos",
  health:     "Saúde",
  traits:     "Traços",
  feudal:     "Feudalismo",
  politics:   "Política",
  dynasty:    "Dinastias",
  religion:   "Religião",
  culture:    "Cultura",
  economy:    "Economia",
  military:   "Militar",
  events:     "Eventos",
};

export interface CodexEntity {
  id: string;
  name: string;
  description: string; // markdown
}

export interface CodexCategory {
  summary: string;
  entries: CodexEntity[];
}

export type CodexResult = Record<CodexCategoryKey, CodexCategory>;

export async function fetchCachedCodex(
  projectId: string,
  provider: string,
  model?: string,
  focus?: string[],
): Promise<CodexResult | null> {
  const params = new URLSearchParams({ provider });
  if (model) params.set("model", model);
  if (focus && focus.length) params.set("focus", focus.join(","));
  const r = await fetch(`/api/projects/${projectId}/codex/cached?${params}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`cached ${r.status}`);
  return r.json();
}

export async function fetchCodexPrompt(
  projectId: string,
  focus?: string[],
): Promise<string> {
  const params = new URLSearchParams();
  if (focus && focus.length) params.set("focus", focus.join(","));
  const url = `/api/projects/${projectId}/codex/prompt${
    params.toString() ? `?${params}` : ""
  }`;
  const r = await fetch(url);
  if (!r.ok) {
    const body = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(body.detail ?? `prompt ${r.status}`);
  }
  const d = await r.json();
  return d.prompt as string;
}
