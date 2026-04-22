import { create } from "zustand";
import type { ResearchResult } from "../api/research";
import { fetchCachedManualResearch } from "../api/research";
import { kingdomColorFor } from "../lib/kingdomColors";

/**
 * Map each condado_id in the research result to its kingdom's palette color.
 * `kingdomIds` is the canonical ordered list of kingdom IDs (typically
 * Object.keys(result.kingdoms)); each kingdom's index in that list selects
 * its color via kingdomColorFor. Returns {} when result is null.
 *
 * Pure — no store reads, no side effects. Safe to call inside useMemo.
 */
export function computeCondadoColors(
  result: ResearchResult | null,
  kingdomIds: string[],
): Record<string, string> {
  if (!result) return {};
  const kingdomIndex = new Map<string, number>();
  kingdomIds.forEach((id, i) => kingdomIndex.set(id, i));
  const out: Record<string, string> = {};
  for (const a of result.condados_assignment) {
    const idx = kingdomIndex.get(a.kingdom_id);
    out[a.condado_id] = kingdomColorFor(a.kingdom_id, idx ?? -1);
  }
  return out;
}

type State = {
  dialogOpen: boolean;
  setDialogOpen: (v: boolean) => void;
  openDialog: (init: { country: string; periodStart: number; periodEnd: number }) => void;
  sheetOpenForProvider: string | null;
  openSheet: (p: string) => void;
  closeSheet: () => void;
  selectedProviderId: string;
  setSelectedProvider: (id: string) => void;
  country: string;
  setCountry: (v: string) => void;
  periodStart: number;
  setPeriodStart: (v: number) => void;
  periodEnd: number;
  setPeriodEnd: (v: number) => void;
  manualJson: string;
  setManualJson: (v: string) => void;
  /** Result from a successful manual (copy/paste) submission. */
  manualResult: ResearchResult | null;
  setManualResult: (result: ResearchResult | null) => void;
  loadCachedForProject: (projectId: string) => Promise<void>;
};

// NOTE: This store uses plain create() without zundo temporal middleware.
// Research dialog state is ephemeral UI state for a single session — it tracks
// LLM streaming progress and should NOT be recorded in the undo/redo history.
// Wrapping it in temporal.pause()/resume() is done at the call site in
// useResearchStream when invoking operations that could interfere with the
// canvas undo stack.
export const useResearchStore = create<State>((set) => ({
  dialogOpen: false,
  setDialogOpen: (v) => set({ dialogOpen: v }),
  openDialog: ({ country, periodStart, periodEnd }) =>
    set({ dialogOpen: true, country, periodStart, periodEnd }),
  sheetOpenForProvider: null,
  openSheet: (p) => set({ sheetOpenForProvider: p }),
  closeSheet: () => set({ sheetOpenForProvider: null }),
  selectedProviderId: "claude",
  setSelectedProvider: (id) => set({ selectedProviderId: id }),
  country: "Q29",
  setCountry: (v) => set({ country: v }),
  periodStart: 868,
  setPeriodStart: (v) => set({ periodStart: v }),
  periodEnd: 900,
  setPeriodEnd: (v) => set({ periodEnd: v }),
  manualJson: "",
  setManualJson: (v) => set({ manualJson: v }),
  manualResult: null,
  setManualResult: (result) => set({ manualResult: result }),
  loadCachedForProject: async (projectId: string) => {
    try {
      const cached = await fetchCachedManualResearch(projectId);
      set({ manualResult: cached });
    } catch {
      // Transient errors are non-fatal for canvas auto-load; leave
      // whatever manualResult is currently in the store untouched.
      // (Intentionally swallow — the UI falls back to file colors.)
    }
  },
}));
