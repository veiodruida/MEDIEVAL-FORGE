/**
 * Phase 08 Plan 14 — BranchInitializer
 *
 * Closes the GAP-B branch-init defect: `useEditorStore.activeBranchId` starts
 * `null` and is ONLY set when the user explicitly opens the BranchPicker and
 * picks a branch. With `activeBranchId` null, wiring `branchId={activeBranchId}`
 * to VertexEditLayer still passes null → split/merge/translate early-return and
 * all polygon ops silently no-op.
 *
 * This component auto-selects the active branch on workspace load:
 *   1. If activeBranchId is already non-null → do nothing (idempotent).
 *   2. If branches list is empty/undefined → do nothing (wait for data).
 *   3. Try to match the localStorage-persisted branch id in the list.
 *   4. If persisted id is stale or absent → fall back to the `is_main` branch.
 *
 * NOTE: This component is READ-ONLY against localStorage — it never writes.
 * Persistence on explicit branch switch is handled exclusively by BranchPicker
 * (useEditorStore.ts:560-568). Do NOT call localStorage.setItem here.
 *
 * Returns null — no DOM output. Mirrors EditorSyncBridge.tsx null-return pattern.
 *
 * Mount once in ProjectDetail immediately after <WorkspaceToolbar />.
 */

import { useEffect } from 'react'
import { useBranches } from '../../api/branches'
import { useEditorStore, loadPersistedActiveBranchId } from '../../stores/useEditorStore'

interface BranchInitializerProps {
  projectId: string | undefined
}

export function BranchInitializer({ projectId }: BranchInitializerProps): null {
  const { data: branches = [] } = useBranches(projectId)
  const activeBranchId = useEditorStore((s) => s.activeBranchId)

  useEffect(() => {
    // Idempotent: if a branch is already active (user's explicit pick), do nothing.
    if (activeBranchId) return

    // Wait for branches data to arrive before making a decision.
    if (!branches || branches.length === 0) return

    // Try the persisted branch id from localStorage.
    const persisted = loadPersistedActiveBranchId()
    const match = persisted ? branches.find((b) => b.id === persisted) : undefined

    // Fall back to the main branch (or first branch if none marked is_main).
    const main = branches.find((b) => b.is_main) ?? branches[0]

    const chosen = match ?? main

    if (chosen) {
      useEditorStore.getState().setActiveBranchId(chosen.id)
    }
  }, [branches, activeBranchId])

  return null
}
