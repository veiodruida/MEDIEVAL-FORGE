/**
 * Phase 08.2 Plan 03 — BezierApplyControls
 *
 * Apply Edits control group for the WorkspaceToolbar right-zone.
 * Extracted to keep WorkspaceToolbar under ~250 LOC (planner-permitted per UI-SPEC §"New files" note).
 *
 * Renders only when: editableLayer === 'baronies' && activeTerritoryId !== null && activeTool === 'V'
 * (the Bézier mode predicate — same as bezierMode flag in WorkspaceToolbar).
 *
 * Layout (UI-SPEC §"Toolbar Layout"):
 *   [AUTO SWITCH] [Aplicar edições]
 *   When auto ON: [AUTO SWITCH] [orange Badge "Modo auto: ~3-5s por edição"]
 *
 * Pitfall 3 avoidance: Apply calls postRender directly via useBezierApply (not dispatch/diffOverrides).
 */
import { Badge, Button, Flex, Switch, Text } from '@radix-ui/themes'
import { useEditorStore } from '../../stores/useEditorStore'
import { useBezierApply } from '../../hooks/useBezierApply'
import { usePipelineParams } from '../../stores/usePipelineParams'
import { useRenderStream } from '../../api/useRenderStream'
import type { StageView } from '../../api/render'

interface BezierApplyControlsProps {
  projectId: string
  branchId: string | null
  isRunning: boolean
}

export function BezierApplyControls({
  projectId,
  branchId,
  isRunning,
}: BezierApplyControlsProps) {
  const bezierApplyMode = useEditorStore((s) => s.bezierApplyMode)
  const setBezierApplyMode = useEditorStore((s) => s.setBezierApplyMode)
  const editLog = useEditorStore((s) => s.editLog)
  const stageView = usePipelineParams((s) => s.stageView)

  const { handleApplyEdits } = useBezierApply(projectId, branchId ?? '')

  // Phase 08.2 Plan 04 Rule 1 fix: subscribe to the SSE render stream so the
  // RunStore receives the rendering→generated transition and useBezierApply's
  // subscribe callback can clear editLog (clear-on-converge).
  // Without this, postRender fires but no SSE consumer is open, so RunStore
  // stays in 'rendering' indefinitely and editLog is never reset.
  const renderStream = useRenderStream()

  const handleApply = () => {
    // Subscribe to SSE BEFORE handleApplyEdits calls postRender, mirroring
    // the pattern in ParameterSidebar/useParameterStudioDispatch (onRenderStarted).
    renderStream.subscribe(projectId)
    handleApplyEdits(stageView as StageView)
  }

  return (
    <Flex align="center" gap="2">
      {/* Mode switch: OFF = manual, ON = auto-immediate */}
      <Switch
        data-testid="bezier-apply-auto-switch"
        checked={bezierApplyMode === 'auto-immediate'}
        onCheckedChange={(v) => setBezierApplyMode(v ? 'auto-immediate' : 'manual')}
        size="1"
      />
      <Text size="1" color="gray">Auto-aplicar</Text>

      {/* Orange cost badge — visible only when auto-immediate is ON */}
      {bezierApplyMode === 'auto-immediate' && (
        <Badge color="orange" variant="soft">
          Modo auto: ~3-5s por edição
        </Badge>
      )}

      {/* Apply button — visible only in manual mode */}
      {bezierApplyMode === 'manual' && (
        <Button
          variant="outline"
          color="blue"
          disabled={editLog.length === 0 || isRunning}
          onClick={handleApply}
          data-testid="bezier-apply-edits-btn"
        >
          Aplicar edições
        </Button>
      )}
    </Flex>
  )
}
