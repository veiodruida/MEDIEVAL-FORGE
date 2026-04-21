import { create } from "zustand";

type State = {
  dialogOpen: boolean;
  setDialogOpen: (v: boolean) => void;
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
}));
