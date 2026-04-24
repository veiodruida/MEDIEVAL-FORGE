import { create } from 'zustand'
import type { SaveStrategy, SaveStatus } from '../types/editing'
import { useProjectStore } from '../stores/useProjectStore'

const LS_KEY = 'mf:save-strategy'
const DEBOUNCE_MS = 1500

/** T-04-08-05: validate stored value is one of the known strategies; fallback to 'auto'. */
function loadStrategy(): SaveStrategy {
  try {
    const v = localStorage.getItem(LS_KEY) as SaveStrategy | null
    if (v === 'auto' || v === 'per_op' || v === 'explicit') return v
  } catch {
    // localStorage unavailable (SSR, sandboxed iframe, etc.)
  }
  return 'auto'
}

function saveStrategyToLS(s: SaveStrategy) {
  try {
    localStorage.setItem(LS_KEY, s)
  } catch {
    // ignore write failures
  }
}

interface PersistenceState {
  strategy: SaveStrategy
  status: SaveStatus
  lastEditAt: number | null
  setStrategy: (s: SaveStrategy) => void
  markEdit: () => void
  markSaved: () => void
  markUnsaved: () => void
}

export const usePersistenceStore = create<PersistenceState>()((set) => ({
  strategy: loadStrategy(),
  status: 'saved',
  lastEditAt: null,
  setStrategy: (s) => {
    saveStrategyToLS(s)
    // Switching to explicit while changes exist keeps unsaved status;
    // switching away resets to saved (backend is now persisting per-op).
    set((prev) => ({
      strategy: s,
      status: prev.status === 'unsaved' && s !== 'explicit' ? 'saved' : prev.status,
    }))
  },
  markEdit: () => set({ lastEditAt: Date.now(), status: 'saving' }),
  markSaved: () => set({ status: 'saved', lastEditAt: null }),
  markUnsaved: () => set({ status: 'unsaved' }),
}))

/**
 * T-04-08-03: single global debounce timer — cleared on every new call to
 * prevent stale 'saved' transitions from racing with subsequent edits.
 */
let debounceTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Call from every edit finalize callback (D-07).
 * Behavior depends on active strategy:
 *   auto    → status='saving' immediately; flips to 'saved' after 1.5s debounce
 *   per_op  → status='saved' immediately (backend already persisted per call)
 *   explicit→ status='unsaved'; backend was called with persist=false; waits for Ctrl+S
 */
export function onOperationFinalized() {
  const { strategy, markEdit, markSaved, markUnsaved } = usePersistenceStore.getState()
  if (strategy === 'auto') {
    markEdit()
    // T-04-08-03: clear stale timer before scheduling new one
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      markSaved()
      debounceTimer = null
    }, DEBOUNCE_MS)
  } else if (strategy === 'per_op') {
    markSaved()
  } else {
    // explicit
    markUnsaved()
  }
}

/**
 * Ctrl+S flush (explicit strategy only). Sends the full in-memory Zustand
 * snapshot to POST /api/projects/{id}/geometry/save.
 * No-op in auto/per_op (backend already persisted per op).
 */
export async function manualSave(): Promise<void> {
  const { strategy, markSaved, markUnsaved } = usePersistenceStore.getState()
  if (strategy !== 'explicit') return
  const { projectId, territories, capitals } = useProjectStore.getState()
  if (!projectId) return
  // Dynamic import avoids circular dependency; saveSnapshot imported lazily.
  const { saveSnapshot } = await import('../api/edit')
  try {
    await saveSnapshot(projectId, { territories, capitals })
    markSaved()
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('manualSave failed', err)
    markUnsaved() // remain unsaved; user can retry with Ctrl+S
  }
}

/** One-time initialization — call from app bootstrap (e.g. App.tsx useEffect). */
export function initPersistence() {
  const s = loadStrategy()
  usePersistenceStore.setState({
    strategy: s,
    status: 'saved', // start clean on page load
    lastEditAt: null,
  })
}

// Convenience hooks / actions for call sites
export const useSaveStatus = () => usePersistenceStore((s) => s.status)
export const useSaveStrategy = () => usePersistenceStore((s) => s.strategy)
export const setStrategy = (s: SaveStrategy) => usePersistenceStore.getState().setStrategy(s)
