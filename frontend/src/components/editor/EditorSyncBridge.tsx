/**
 * Phase 08 WARNING-6: EditorSyncBridge — server-state ↔ store synchronisation.
 *
 * PURPOSE: This component is the SINGLE wiring point between useEditorStore's
 * EditEventSink and the backend POST /edit-events endpoint. It must be mounted
 * ONCE inside WorkspaceToolbar (or the workspace shell) so that ALL vertex
 * mutations from VertexEditLayer, BranchPicker, and polygon op tools (plans
 * 08-06a/b, 08-07, 08-08) automatically flow to the backend with zero
 * per-component wiring.
 *
 * MOUNT POINT REQUIREMENT (for plan 08-09):
 *   Mount <EditorSyncBridge projectId={projectId} branchId={activeBranchId} />
 *   once inside WorkspaceToolbar or the top-level workspace shell component.
 *   Do NOT mount it inside individual tool components — one instance only.
 *
 * LIFECYCLE:
 *   - On mount: registers the sink via registerEditEventSink(mutateAsync adapter)
 *   - On unmount: deregisters via registerEditEventSink(null)
 *   - branchId change: useEffect re-registration picks up new branchId automatically
 *     because mutateAsync closes over the current branchId via useAppendEditEvent.
 *
 * RESPONSE ADAPTATION (D-37):
 *   Backend returns {event_id, auto_snapshot, edits_since_snapshot}.
 *   Adapter maps to {snapshot_persisted: boolean} so the store can reset
 *   editsSinceSnapshot to 0 when a snapshot was confirmed (D-37 contract).
 *
 * Returns null — no DOM output.
 */
import { useEffect } from 'react'
import { registerEditEventSink } from '../../stores/useEditorStore'
import { useAppendEditEvent } from '../../api/snapshots'
import type { EditEventSinkPayload } from '../../stores/useEditorStore'

interface EditorSyncBridgeProps {
  projectId: string | undefined
  branchId: string | null
}

export function EditorSyncBridge({
  projectId,
  branchId,
}: EditorSyncBridgeProps): null {
  const { mutateAsync } = useAppendEditEvent(
    projectId ?? undefined,
    branchId ?? undefined,
  )

  useEffect(() => {
    if (!projectId || !branchId) {
      // No active project/branch — clear sink so ops are buffered locally
      registerEditEventSink(null)
      return
    }

    // Register the sink: adapts EditEventSinkPayload → EditEventPayload and
    // maps the backend response to {snapshot_persisted: boolean} (D-37).
    registerEditEventSink(async (payload: EditEventSinkPayload) => {
      const result = await mutateAsync({
        op_type: payload.op.op,
        payload: payload.op as unknown as Record<string, unknown>,
        snapshot_payload_if_due: payload.snapshot_payload_if_due,
      })
      // D-37: snapshot_persisted = true when backend confirmed auto-snapshot
      const snapshotPersisted =
        result.auto_snapshot !== null &&
        result.auto_snapshot !== undefined &&
        !('error' in result.auto_snapshot)
      return { snapshot_persisted: snapshotPersisted }
    })

    return () => {
      // Cleanup: deregister sink on unmount or when projectId/branchId changes
      registerEditEventSink(null)
    }
  }, [projectId, branchId, mutateAsync])

  return null
}
