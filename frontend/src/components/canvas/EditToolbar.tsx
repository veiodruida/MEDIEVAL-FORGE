import { Flex, Button, Tooltip, Separator, SegmentedControl } from '@radix-ui/themes'
import { useEditorStore } from '../../stores/useEditorStore'
import { useUIStore } from '../../stores/uiStore'

/**
 * EditToolbar — Phase 4 toolbar.
 *
 * Buttons:
 *   Editar        — global edit mode toggle (P05)
 *   Editar Vértices — enters vertex-edit for selected territory (P06)
 *   Dividir       — activates split tool; shows sub-mode segmented control (P07)
 *   Undo/Redo     — keyboard + toolbar buttons deferred to separate UndoRedoButtons
 *                   component; wired in Task 2 of P07.
 *
 * V keyboard shortcut and full keyboard map deferred to P07 Task 3 (useEditKeyboardMap).
 */
export function EditToolbar() {
  const editMode = useEditorStore((s) => s.editMode)
  const toggleEditMode = useEditorStore((s) => s.toggleEditMode)
  const vertexEditId = useEditorStore((s) => s.vertexEditCondadoId)
  const setVertexEditCondadoId = useEditorStore((s) => s.setVertexEditCondadoId)
  const activeTool = useEditorStore((s) => s.activeTool)
  const setActiveTool = useEditorStore((s) => s.setActiveTool)
  const splitSubMode = useEditorStore((s) => s.splitSubMode)
  const setSplitSubMode = useEditorStore((s) => s.setSplitSubMode)
  const selectedId = useUIStore((s) => s.selectedTerritoryId)

  const splitActive = activeTool === 'split'

  return (
    <Flex
      align="center"
      gap="2"
      px="3"
      py="2"
      style={{ borderBottom: '1px solid var(--gray-4)' }}
    >
      <Tooltip content="Alternar modo de edição (E)">
        <Button
          variant={editMode ? 'solid' : 'soft'}
          size="2"
          onClick={toggleEditMode}
          aria-pressed={editMode}
        >
          Editar
        </Button>
      </Tooltip>
      <Separator orientation="vertical" size="1" />
      {editMode && (
        <Tooltip content="Editar vértices da borda (V)">
          <Button
            variant={vertexEditId ? 'solid' : 'soft'}
            size="2"
            disabled={!selectedId && !vertexEditId}
            onClick={() => setVertexEditCondadoId(vertexEditId ? null : selectedId)}
          >
            Editar Vértices
          </Button>
        </Tooltip>
      )}
      {editMode && (
        <Tooltip content="Dividir território com linha de corte (S)">
          <Button
            variant={splitActive ? 'solid' : 'soft'}
            size="2"
            disabled={!selectedId && !splitActive}
            onClick={() => setActiveTool(splitActive ? 'select' : 'split')}
          >
            Dividir
          </Button>
        </Tooltip>
      )}
      {editMode && splitActive && (
        <SegmentedControl.Root
          value={splitSubMode}
          onValueChange={(v) => setSplitSubMode(v as 'snap' | 'polyline' | 'freehand')}
          size="1"
        >
          <SegmentedControl.Item value="snap">Snap</SegmentedControl.Item>
          <SegmentedControl.Item value="polyline">Polilinha</SegmentedControl.Item>
          <SegmentedControl.Item value="freehand">Livre</SegmentedControl.Item>
        </SegmentedControl.Root>
      )}
      {/* Undo/Redo buttons wired in Task 2 of P07 */}
    </Flex>
  )
}
