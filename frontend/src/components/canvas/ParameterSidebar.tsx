import { useCallback, useRef, useState } from 'react'
import { Box, Flex, ScrollArea, Separator, Text } from '@radix-ui/themes'
import { SliderCard } from './SliderCard'
import { StageViewToggle } from './StageViewToggle'
import { usePipelineParams, type SliderKey } from '../../stores/usePipelineParams'
import { useRenderStream } from '../../api/useRenderStream'
import { useParameterStudioDispatch } from '../../hooks/useParameterStudioDispatch'
import { useEditorStore } from '../../stores/useEditorStore'
import { useCreateSnapshot } from '../../api/snapshots'
import { SliderConflictDialog } from '../editor/SliderConflictDialog'

interface ParameterSidebarProps {
  projectId: string
}

const SIDEBAR_W = 320

const SLIDER_LABELS: Record<SliderKey, string> = {
  smooth_sigma: 'Suavização (σ)',
  median_passes: 'Passes Mediana',
  fragment_min_px: 'Fragmento mín. (px)',
  blob_merge_px: 'Fusão de blobs (px)',
}

export function ParameterSidebar({ projectId }: ParameterSidebarProps) {
  const sidebarOpen = usePipelineParams((s) => s.sidebarOpen)
  const renderStream = useRenderStream()

  // D-06 (Phase 04.1 WR-03): single canonical dispatch path.
  // useParameterStudioDispatch wraps the 250ms-debounced latest-wins sequence
  // + D-04 bounded RENDER_BUSY retry. We pass renderStream.subscribe via
  // onRenderStarted so the SSE consumer attaches once a run_id is returned.
  // useRenderStream.subscribe internally closes any prior EventSource — no
  // need for an explicit renderStream.close() here.
  const debouncedRender = useParameterStudioDispatch(projectId, (_runId) => {
    renderStream.subscribe(projectId)
  })

  // Reset bypasses debounce — flush() invokes the wrapped fn synchronously.
  const onResetCommit = useCallback(
    () => debouncedRender.flush(),
    [debouncedRender],
  )

  // ---------------------------------------------------------------------------
  // D-19 + Pitfall 9: Slider conflict intercept.
  // When slider changes while editLog.length > 0:
  //   1. POST snapshot with trigger='pre_slider_change' FIRST
  //   2. Only on 201 success → open SliderConflictDialog
  //   3. On error → toast (no dialog); slider reverts via pendingRenderRef cleanup
  // The debouncedRender is intercepted via the wrappedRender wrapper below.
  // ---------------------------------------------------------------------------

  const activeBranchId = useEditorStore((s) => s.activeBranchId)
  const editLog = useEditorStore((s) => s.editLog)
  const vertices = useEditorStore((s) => s.vertices)

  const createSnapshot = useCreateSnapshot(projectId, activeBranchId ?? undefined)

  const [conflictOpen, setConflictOpen] = useState(false)
  const [conflictSnapshotSeq, setConflictSnapshotSeq] = useState<number | null>(null)
  const [conflictBranchName, setConflictBranchName] = useState('main')

  // Holds the pending render dispatch that will fire after user confirms
  const pendingRenderRef = useRef<(() => void) | null>(null)
  // Holds the revert function to restore slider to previous value on cancel
  const pendingRevertRef = useRef<(() => void) | null>(null)

  /**
   * Wraps the debouncedRender to inject snapshot-before-modal logic (D-19).
   * SliderCard calls this on commit; if edits exist, we intercept.
   */
  const wrappedRender = useCallback(
    async (revertFn?: () => void) => {
      // No edits → dispatch directly, no conflict
      if (editLog.length === 0) {
        debouncedRender()
        return
      }

      // Edits exist → POST snapshot FIRST (Pitfall 9)
      pendingRenderRef.current = () => debouncedRender()
      pendingRevertRef.current = revertFn ?? null

      try {
        const result = await createSnapshot.mutateAsync({
          trigger: 'pre_slider_change',
          payload: {
            vertices,
            editLog,
          },
        })

        // Only on 201 (successful mutateAsync) → open dialog
        setConflictSnapshotSeq(result.seq)
        setConflictBranchName(activeBranchId ?? 'main')
        setConflictOpen(true)
      } catch {
        // Snapshot failed → no dialog; revert slider silently
        pendingRenderRef.current = null
        pendingRevertRef.current?.()
        pendingRevertRef.current = null
        // (toast is out of scope for this intercept — caller may add later)
      }
    },
    [editLog, vertices, activeBranchId, createSnapshot, debouncedRender],
  )

  const handleConflictConfirm = () => {
    setConflictOpen(false)
    // Proceed with the pending render dispatch
    pendingRenderRef.current?.()
    pendingRenderRef.current = null
    pendingRevertRef.current = null
  }

  const handleConflictCancel = () => {
    setConflictOpen(false)
    // Revert slider to previous value
    pendingRevertRef.current?.()
    pendingRenderRef.current = null
    pendingRevertRef.current = null
  }

  if (!sidebarOpen) return null

  const keys: SliderKey[] = [
    'smooth_sigma',
    'median_passes',
    'fragment_min_px',
    'blob_merge_px',
  ]

  return (
    <>
      <Box
        data-testid="parameter-sidebar"
        style={{
          width: SIDEBAR_W,
          height: '100%',
          overflow: 'hidden',
          borderRight: '1px solid var(--gray-6)',
          background: 'var(--color-panel-solid)',
        }}
      >
        <ScrollArea>
          <Flex direction="column" gap="4" p="4">
            <Text size="3" weight="bold">
              Parâmetros
            </Text>
            <StageViewToggle />
            <Separator size="4" />
            {keys.map((k) => (
              <SliderCard
                key={k}
                paramKey={k}
                label={SLIDER_LABELS[k]}
                onCommit={wrappedRender}
                onResetCommit={onResetCommit}
              />
            ))}
          </Flex>
        </ScrollArea>
      </Box>

      {/* D-19: Slider conflict dialog — only shown after snapshot 201 (Pitfall 9) */}
      <SliderConflictDialog
        open={conflictOpen}
        branchName={conflictBranchName}
        snapshotSeq={conflictSnapshotSeq}
        onConfirm={handleConflictConfirm}
        onCancel={handleConflictCancel}
      />
    </>
  )
}
