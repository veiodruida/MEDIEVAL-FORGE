import { Flex, Button, Tooltip, Separator } from '@radix-ui/themes'
import { useEditorStore } from '../../stores/useEditorStore'
import { useUIStore } from '../../stores/uiStore'

/**
 * EditToolbar — Phase 4 toolbar with Edit mode toggle + Editar Vértices button.
 *
 * "Editar Vértices" button (P06):
 *   - Visible when editMode is true.
 *   - Active (solid) when vertexEditCondadoId is set.
 *   - Disabled when no single territory is selected AND not already in vertex-edit mode.
 *   - Clicking enters vertex-edit for the selected territory; clicking again exits.
 *
 * V keyboard shortcut deferred to P07 alongside the full keyboard map.
 * Split/Undo/Redo buttons deferred to P07.
 */
export function EditToolbar() {
  const editMode = useEditorStore((s) => s.editMode)
  const toggleEditMode = useEditorStore((s) => s.toggleEditMode)
  const vertexEditId = useEditorStore((s) => s.vertexEditCondadoId)
  const setVertexEditCondadoId = useEditorStore((s) => s.setVertexEditCondadoId)
  const selectedId = useUIStore((s) => s.selectedTerritoryId)

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
      {/* Placeholder slots for P07 (Split, Undo/Redo) */}
    </Flex>
  )
}
