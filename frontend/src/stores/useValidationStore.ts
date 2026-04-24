import { create } from 'zustand'
import type { ValidationIssue } from '../types/editing'

/**
 * Lightweight validation issue store (D-06).
 * NOT wrapped in temporal — validation results are derived state,
 * not undoable history. They are recomputed on each edit-finalize callback.
 */
interface ValidationState {
  issues: ValidationIssue[]
  /** Replace all issues for the given affectedIds; keep issues for unaffected condados. */
  setIssuesForIds: (affectedIds: string[], newIssues: ValidationIssue[]) => void
  clearAll: () => void
}

export const useValidationStore = create<ValidationState>()((set) => ({
  issues: [],
  setIssuesForIds: (affectedIds, newIssues) =>
    set((s) => {
      const affected = new Set(affectedIds)
      // Drop old issues for affected condados; keep the rest
      const kept = s.issues.filter((i) => !affected.has(i.condado_id))
      return { issues: [...kept, ...newIssues] }
    }),
  clearAll: () => set({ issues: [] }),
}))
