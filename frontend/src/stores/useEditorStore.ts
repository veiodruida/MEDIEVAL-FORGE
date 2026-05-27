/* Phase 08 D-25 + D-V3-04: NEW store (not restored from deleted v1).
 * zundo temporal middleware; scope = editor ops only (D-25).
 * Partialize narrows history to {vertices, editLog} — selection/activeTool excluded.
 *
 * WARNING-6 fix: setVerticesAndLog is the SINGLE chokepoint for all undoable
 * vertex mutations. Plans 08-06a/b/07/08 inherit the sink wiring for free.
 *
 * Gemini review (UX): undoLabels/redoLabels string[] mirror zundo
 * pastStates/futureStates. Every undoable commit appends an op-type label;
 * undo()/redo() move labels between stacks via temporal.subscribe. Surfaced in
 * toolbar tooltip by 08-09.
 *
 * D-37: auto-snapshot every 25 edits. editsSinceSnapshot counter increments on
 * every undoable commit; resets to 0 when snapshot_persisted confirmed by sink.
 *
 * localStorage persists active_branch_id per D-37 (worst-case crash <25 edits).
 */
import { create } from 'zustand';
import { temporal } from 'zundo';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EditTool = 'V' | 'A' | 'D' | 'S' | 'M' | null;
export type LandmaskMode = 'manual' | 'auto-immediate';

export interface EditOp {
  op: 'move' | 'add' | 'delete' | 'split' | 'merge' | 'translate' | 'simplify' | 'multi_delete';
  ts: number;
  vertexIds?: string[];
  lat?: number;
  lon?: number;
  // Additional op-specific fields supplied by polygon ops (split/merge/translate)
  [key: string]: unknown;
}

export interface VertexCoord {
  lat: number;
  lon: number;
}

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface EditorState {
  // Branch state (NOT in zundo history — D-25)
  activeBranchId: string | null;
  landmaskMode: LandmaskMode;

  // Tool state (NOT in zundo history)
  activeTool: EditTool;
  activeTerritoryId: string | null;

  // Selection (NOT in zundo history — UI-SPEC Notes #2)
  selectedVertexIds: string[];

  // Editable state (IN zundo history — partialized)
  vertices: Record<string, VertexCoord>;
  editLog: EditOp[];

  // Counter for D-37 auto-snapshot cadence (NOT in zundo history — counts forward only)
  editsSinceSnapshot: number;

  // Gemini review (UX): op-type label stacks mirroring pastStates / futureStates.
  // NOT inside zundo partialize — mutated explicitly in lockstep with commits +
  // undo/redo via temporal.subscribe so 08-09 toolbar can show "Undo Split" vs "Undo".
  undoLabels: string[];
  redoLabels: string[];
}

// ---------------------------------------------------------------------------
// Actions shape
// ---------------------------------------------------------------------------

interface EditorActions {
  // Non-undoable
  selectTool: (t: EditTool) => void;
  setActiveTerritoryId: (id: string | null) => void;
  setSelectedVertexIds: (ids: string[]) => void;
  setActiveBranchId: (id: string | null) => void;
  setLandmaskMode: (m: LandmaskMode) => void;

  // Undoable (vertex/polygon ops) — all funnel through setVerticesAndLog
  moveVertex: (id: string, lat: number, lon: number) => void;
  addVertex: (id: string, lat: number, lon: number) => void;
  deleteVertices: (ids: string[]) => void;  // one undoable op per D-29 marquee

  // CHOKEPOINT: all undoable ops land here. Fires sink (TELEM-01) and includes
  // snapshot_payload_if_due on every 25th commit (D-37 auto-snapshot).
  setVerticesAndLog: (next: Record<string, VertexCoord>, op: EditOp) => void;
}

// ---------------------------------------------------------------------------
// Edit-event sink (WARNING-6)
// ---------------------------------------------------------------------------

export interface EditEventSinkPayload {
  branchId: string | null;
  op: EditOp;
  edits_since_snapshot: number;
  snapshot_payload_if_due?: { vertices: Record<string, VertexCoord>; editLog: EditOp[] };
}

export type EditEventSink = (
  payload: EditEventSinkPayload,
) => Promise<{ snapshot_persisted?: boolean } | void>;

// Module-level sink reference — registered by EditorSyncBridge after
// useAppendEditEvent mutation is constructed. Single chokepoint so 08-06a/b/07/08
// inherit the wiring for free.
let _editEventSink: EditEventSink | null = null;

export function registerEditEventSink(sink: EditEventSink | null): void {
  _editEventSink = sink;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useEditorStore = create<EditorState & EditorActions>()(
  temporal(
    (set, get) => ({
      // Initial state
      activeBranchId: null,
      landmaskMode: 'manual',
      activeTool: null,
      activeTerritoryId: null,
      selectedVertexIds: [],
      vertices: {},
      editLog: [],
      editsSinceSnapshot: 0,
      undoLabels: [],
      redoLabels: [],

      // Non-undoable actions
      selectTool: (t) => set({ activeTool: t }),
      setActiveTerritoryId: (id) => set({ activeTerritoryId: id }),
      setSelectedVertexIds: (ids) => set({ selectedVertexIds: ids }),
      setActiveBranchId: (id) => set({ activeBranchId: id }),
      setLandmaskMode: (m) => set({ landmaskMode: m }),

      // Undoable actions — all delegate to setVerticesAndLog (chokepoint)
      moveVertex: (id, lat, lon) => {
        const next = { ...get().vertices, [id]: { lat, lon } };
        get().setVerticesAndLog(next, { op: 'move', ts: Date.now(), vertexIds: [id], lat, lon });
      },

      addVertex: (id, lat, lon) => {
        const next = { ...get().vertices, [id]: { lat, lon } };
        get().setVerticesAndLog(next, { op: 'add', ts: Date.now(), vertexIds: [id], lat, lon });
      },

      deleteVertices: (ids) => {
        const next = { ...get().vertices };
        ids.forEach((i) => delete next[i]);
        get().setVerticesAndLog(next, { op: 'multi_delete', ts: Date.now(), vertexIds: ids });
      },

      // CHOKEPOINT — every undoable commit lands here.
      // 1. Updates vertices + editLog (enters zundo history).
      // 2. Appends op-type to undoLabels (Gemini UX); clears redoLabels (new commit invalidates redo).
      // 3. Fires the registered edit-event sink (TELEM-01).
      // 4. On 25th commit, includes snapshot_payload_if_due (D-37 auto-snapshot).
      setVerticesAndLog: (next, op) => {
        set((s) => ({
          vertices: next,
          editLog: [...s.editLog, op],
          editsSinceSnapshot: s.editsSinceSnapshot + 1,
          // Gemini review (UX): new commit invalidates redo stack (mirrors zundo clearing futureStates)
          undoLabels: [...s.undoLabels, op.op],
          redoLabels: [],
        }));

        const after = get();
        const sink = _editEventSink;
        if (sink) {
          const dueForSnapshot =
            after.editsSinceSnapshot > 0 && after.editsSinceSnapshot % 25 === 0;
          Promise.resolve(
            sink({
              branchId: after.activeBranchId,
              op,
              edits_since_snapshot: after.editsSinceSnapshot,
              snapshot_payload_if_due: dueForSnapshot
                ? { vertices: after.vertices, editLog: after.editLog }
                : undefined,
            }),
          )
            .then((res) => {
              if (res && res.snapshot_persisted) {
                // D-37: reset counter after confirmed auto-snapshot
                useEditorStore.setState({ editsSinceSnapshot: 0 });
              }
            })
            .catch(() => {
              // Silent — sink retries via TanStack mutation queue
            });
        }
      },
    }),
    {
      // D-25: history scope = editor ops only.
      // selectedVertexIds + activeTool + editsSinceSnapshot + undoLabels/redoLabels
      // are deliberately excluded.
      partialize: (s) => ({ vertices: s.vertices, editLog: s.editLog }),
      limit: 100, // D-25 history cap
      // equality: compare by reference for vertices and editLog arrays/objects.
      // Without equality, zundo compares the *new object* from partialize() to the
      // *old object* via Object.is — always false (different refs) → every setState
      // (even selectTool) would push to pastStates. Referential equality on the two
      // partialize fields means only real vertex/editLog mutations add history.
      equality: (a, b) => a.vertices === b.vertices && a.editLog === b.editLog,
    },
  ),
);

// ---------------------------------------------------------------------------
// Gemini review (UX): keep undoLabels/redoLabels in lockstep with zundo stacks.
// Subscribe to temporal state changes; detect undo vs redo vs clear by comparing
// previous and current pastStates/futureStates lengths.
//
// IMPORTANT: We must NOT call useEditorStore.setState() inside this subscriber —
// that would trigger zundo's wrapped store.setState which calls temporalHandleSet
// which triggers the subscriber again → infinite recursion (stack overflow).
//
// Solution: use the internal Zustand vanilla setState stored via getInternalSet()
// before the zundo wrapper overwrites it. This bypasses zundo's tracking for
// label-only updates (undoLabels/redoLabels are outside partialize anyway).
// ---------------------------------------------------------------------------

// Capture the vanilla Zustand setState before zundo wraps it.
// zundo wraps store.setState at middleware init time; we call getInternalSet()
// AFTER store creation — at that point store.setState IS the zundo-wrapped version.
// So we need a different approach: store a raw updater via the temporal handleSet hook
// or use getState() + setState() with a guard flag.

let _suppressSubscribe = false;
let _prevPastLen = 0;
let _prevFutureLen = 0;

useEditorStore.temporal.subscribe((temporalState) => {
  // Guard: if we're already inside this callback, skip (shouldn't happen with flag)
  if (_suppressSubscribe) return;

  const pastLen = temporalState.pastStates.length;
  const futureLen = temporalState.futureStates.length;

  const s = useEditorStore.getState();

  let nextUndoLabels: string[] | null = null;
  let nextRedoLabels: string[] | null = null;

  if (pastLen < _prevPastLen && futureLen > _prevFutureLen) {
    // undo() — pop one from undoLabels onto redoLabels
    if (s.undoLabels.length > 0) {
      const moved = s.undoLabels[s.undoLabels.length - 1];
      nextUndoLabels = s.undoLabels.slice(0, -1);
      nextRedoLabels = [...s.redoLabels, moved];
    }
  } else if (futureLen < _prevFutureLen && pastLen > _prevPastLen) {
    // redo() — pop one from redoLabels onto undoLabels
    if (s.redoLabels.length > 0) {
      const moved = s.redoLabels[s.redoLabels.length - 1];
      nextRedoLabels = s.redoLabels.slice(0, -1);
      nextUndoLabels = [...s.undoLabels, moved];
    }
  } else if (pastLen === 0 && futureLen === 0) {
    // temporal.clear() (branch switch) — reset both label stacks
    nextUndoLabels = [];
    nextRedoLabels = [];
  }

  if (nextUndoLabels !== null || nextRedoLabels !== null) {
    _suppressSubscribe = true;
    // Use the zundo-wrapped setState but with only non-partialized fields.
    // Since undoLabels/redoLabels are NOT in partialize({vertices, editLog}),
    // zundo's temporalHandleSet will compute pastState === currentState for the
    // partialized slice → equality check passes → no history entry added.
    // We add an explicit equality option to ensure this: see partialize config above.
    // Additionally, _suppressSubscribe prevents the re-entrant subscribe call from
    // doing anything even if the subscriber fires again during setState.
    useEditorStore.setState({
      ...(nextUndoLabels !== null ? { undoLabels: nextUndoLabels } : {}),
      ...(nextRedoLabels !== null ? { redoLabels: nextRedoLabels } : {}),
    });
    _suppressSubscribe = false;
  }

  _prevPastLen = pastLen;
  _prevFutureLen = futureLen;
});

// ---------------------------------------------------------------------------
// switchBranch — D-25 + D-37
// Rehydrates store from branch snapshot and clears temporal history.
// localStorage stores active_branch_id per D-37.
// ---------------------------------------------------------------------------

const LS_KEY = 'medieval-forge:active_branch_id';

export function switchBranch(
  branchId: string,
  snapshotPayload: {
    vertices: Record<string, VertexCoord>;
    editLog: EditOp[];
  },
): void {
  useEditorStore.setState({
    activeBranchId: branchId,
    vertices: snapshotPayload.vertices,
    editLog: snapshotPayload.editLog,
    selectedVertexIds: [],
    activeTool: null,
    activeTerritoryId: null,
    editsSinceSnapshot: 0,
    // Label stacks reset here for safety; temporal.subscribe also resets them on clear()
    undoLabels: [],
    redoLabels: [],
  });
  // D-25: clear history on branch switch
  useEditorStore.temporal.getState().clear();
  // D-37: persist active branch to localStorage
  try {
    localStorage.setItem(LS_KEY, branchId);
  } catch {
    // Ignore storage errors (private browsing, quota exceeded)
  }
}

export function loadPersistedActiveBranchId(): string | null {
  try {
    return localStorage.getItem(LS_KEY);
  } catch {
    return null;
  }
}
