import { Box, Button, Flex, IconButton, Text, Tooltip } from '@radix-ui/themes'
import { ChevronLeftIcon, MixerHorizontalIcon } from '@radix-ui/react-icons'
import { Link } from 'react-router-dom'
import { GenerateStatusBadge } from './GenerateStatusBadge'
import { BezierApplyControls } from './BezierApplyControls'
import type { Project } from '../../api/client'
import type { PipelineStage, RunState } from '../../stores/useRunStore'
import { usePipelineParams } from '../../stores/usePipelineParams'
import { postRenderCancel } from '../../api/render'
import { useEditorStore } from '../../stores/useEditorStore'
import type { EditTool } from '../../stores/useEditorStore'
import { BranchPicker } from '../editor/BranchPicker'
import { EditorSyncBridge } from '../editor/EditorSyncBridge'
import { EditToolPalette } from '../editor/EditToolPalette'

// ---------------------------------------------------------------------------
// Gemini review (UX): Portuguese label map for undo/redo tooltip per EditOp.op.
// Surfaced in toolbar via undoLabels / redoLabels from useEditorStore (08-04).
// ---------------------------------------------------------------------------

export const OP_LABEL_PT: Record<string, string> = {
  move: 'Mover Vértice',
  add: 'Adicionar Vértice',
  delete: 'Remover Vértice',
  multi_delete: 'Remover Vértices',
  split: 'Dividir',
  merge: 'Mesclar',
  translate: 'Mover Polígono',
  simplify: 'Simplificar',
  landmask_vertex_move: 'Mover Vértice (Landmask)',
  landmask_vertex_add: 'Adicionar Vértice (Landmask)',
  landmask_vertex_delete: 'Remover Vértice (Landmask)',
}

export interface WorkspaceToolbarProps {
  project: Project | undefined
  runState: RunState
  currentStage: PipelineStage | null
  hasArtifacts?: boolean
  onGenerate: () => void
  onExport: () => void
  statusBadgeOpen: boolean
  onToggleStatusBadge: () => void
}

/**
 * 48px sticky toolbar per UI-SPEC §Layout Contract.
 * Left zone: ⬡ Params toggle + ← Projetos + project name.
 * Center: GenerateStatusBadge → red "Cancelar" button when state ∈ {generating, rendering}.
 * Right: BranchPicker (D-13) + Undo/Redo (undoLabels tooltip per Gemini review) +
 *        Gerar Mapa / Regenerar (disabled when running) + Exportar ZIP.
 *
 * WARNING-6: EditorSyncBridge mounted once here so the edit-event sink is
 * registered for the whole workspace session (plan 08-04 requirement).
 */
export function WorkspaceToolbar({
  project,
  runState,
  currentStage,
  hasArtifacts = false,
  onGenerate,
  onExport,
  onToggleStatusBadge,
}: WorkspaceToolbarProps) {
  const sidebarOpen = usePipelineParams((s) => s.sidebarOpen)
  const setSidebarOpen = usePipelineParams((s) => s.setSidebarOpen)

  // Gemini review (UX): undo/redo tooltip labels from undoLabels/redoLabels stacks.
  const undoLabels = useEditorStore((s) => s.undoLabels)
  const redoLabels = useEditorStore((s) => s.redoLabels)
  const activeBranchId = useEditorStore((s) => s.activeBranchId)

  // Phase 08.1: derive the Bézier-mode disabled-tool set here (WorkspaceToolbar
  // owns the mode knowledge) and thread it into the Bézier-unaware EditToolPalette
  // (UI-SPEC Note #7). Bézier mode = editing a selected barony with the V tool;
  // A (add vertex) and D (delete vertex) are unavailable while curve-editing.
  const editableLayer = useEditorStore((s) => s.editableLayer)
  const activeTerritoryId = useEditorStore((s) => s.activeTerritoryId)
  const activeTool = useEditorStore((s) => s.activeTool)
  const bezierMode =
    editableLayer === 'baronies' && activeTerritoryId !== null && activeTool === 'V'
  const disabledTools: EditTool[] = bezierMode ? ['A', 'D'] : []
  const canUndo = useEditorStore.temporal.getState().pastStates.length > 0
  const canRedo = useEditorStore.temporal.getState().futureStates.length > 0

  const undoTopLabel = undoLabels.at(-1)
  const redoTopLabel = redoLabels.at(-1)
  const undoTooltip = undoTopLabel
    ? `Desfazer ${OP_LABEL_PT[undoTopLabel] ?? undoTopLabel}`
    : 'Desfazer'
  const redoTooltip = redoTopLabel
    ? `Refazer ${OP_LABEL_PT[redoTopLabel] ?? redoTopLabel}`
    : 'Refazer'

  const handleUndo = () => useEditorStore.temporal.getState().undo()
  const handleRedo = () => useEditorStore.temporal.getState().redo()

  // D-16: cancel button replaces badge when runState === 'rendering'.
  // UI-SPEC §State Machine: generating shows the badge (no cancel); only rendering shows cancel.
  // Rationale: /render/cancel cancels incremental re-renders; /generate runs have no SSE cancel.
  const isRunning =
    runState === 'generating' || runState === 'ingesting' || runState === 'rendering'
  const showCancel = runState === 'rendering'

  // Label flips to "Regenerar" once a run has started OR artifacts exist.
  const ctaLabel =
    hasArtifacts || runState === 'generated' || isRunning ? 'Regenerar' : 'Gerar Mapa'

  const handleCancel = async () => {
    if (!project) return
    await postRenderCancel(project.id).catch(() => {})
  }

  return (
    <Box
      data-testid="workspace-toolbar"
      style={{
        height: '48px',
        position: 'sticky',
        top: 0,
        zIndex: 20,
        background: 'var(--color-panel-solid)',
        borderBottom: '1px solid var(--gray-6)',
      }}
    >
      <Flex align="center" justify="between" px="4" gap="5" style={{ height: '100%' }}>
        <Flex align="center" gap="3">
          <IconButton
            size="2"
            variant="ghost"
            data-testid="toggle-parameter-sidebar"
            aria-label="Alternar painel de parâmetros"
            aria-pressed={sidebarOpen}
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <MixerHorizontalIcon />
          </IconButton>
          <Link to="/projects" style={{ textDecoration: 'none' }}>
            <Flex align="center" gap="1">
              <ChevronLeftIcon />
              <Text size="2">Projetos</Text>
            </Flex>
          </Link>
          {project && (
            <Text size="2" weight="bold" data-testid="project-name">
              {project.name}
            </Text>
          )}
        </Flex>

        {showCancel ? (
          <Button
            color="red"
            variant="solid"
            data-testid="cancel-render-button"
            onClick={handleCancel}
          >
            Cancelar
          </Button>
        ) : (
          <GenerateStatusBadge
            runState={runState}
            currentStage={currentStage}
            hasArtifacts={hasArtifacts}
            onClick={onToggleStatusBadge}
          />
        )}

        <Flex align="center" gap="2">
          {/* D-13: Branch Picker zone — left of "Gerar Mapa" per UI-SPEC §Toolbar Layout */}
          <BranchPicker projectId={project?.id} />

          {/* GAP-C closure (08-13): visible V/A/D/S/M tool palette per UI-SPEC §Tool Palette Zone.
              Bound to useEditorStore.activeTool/selectTool — same state as keyboard shortcuts.
              Phase 08.1: disabledTools threads the Bézier-mode-derived A/D disable set. */}
          <EditToolPalette disabledTools={disabledTools} />

          {/* Phase 08.2 Plan 03: Apply Edits control group (Switch + Badge + Apply button).
              Visibility predicate: editableLayer==='baronies' && activeTerritoryId !== null && activeTool==='V'
              Placed BETWEEN EditToolPalette and Undo/Redo per UI-SPEC §"Toolbar Layout". */}
          {bezierMode && project && (
            <BezierApplyControls
              projectId={project.id}
              branchId={activeBranchId}
              isRunning={isRunning}
            />
          )}

          {/* Undo/Redo buttons with dynamic tooltip from undoLabels/redoLabels (Gemini review) */}
          <Tooltip content={undoTooltip}>
            <Button
              variant="ghost"
              size="2"
              disabled={!canUndo}
              onClick={handleUndo}
              data-testid="toolbar-undo-btn"
              aria-label={undoTooltip}
              title={undoTooltip}
            >
              ↩
            </Button>
          </Tooltip>
          <Tooltip content={redoTooltip}>
            <Button
              variant="ghost"
              size="2"
              disabled={!canRedo}
              onClick={handleRedo}
              data-testid="toolbar-redo-btn"
              aria-label={redoTooltip}
              title={redoTooltip}
            >
              ↪
            </Button>
          </Tooltip>

          <Button
            color="blue"
            variant="solid"
            disabled={isRunning}
            onClick={onGenerate}
          >
            {ctaLabel}
          </Button>
          <Button color="gray" variant="outline" onClick={onExport}>
            Exportar ZIP
          </Button>
        </Flex>
      </Flex>

      {/* WARNING-6: EditorSyncBridge registers the edit-event sink once for the
          whole workspace session. Mount here so all plans (08-06a/b/07/08/09)
          inherit the wiring automatically without per-component setup. */}
      <EditorSyncBridge
        projectId={project?.id}
        branchId={activeBranchId}
      />
    </Box>
  )
}
