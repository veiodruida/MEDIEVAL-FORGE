import { Flex, Button, Tooltip, Separator } from '@radix-ui/themes'
import { useEditorStore } from '../../stores/useEditorStore'

/**
 * EditToolbar — minimal Phase 4 toolbar with Edit mode toggle.
 *
 * Merge/Split/Vertex/Undo buttons added in P06 and P07.
 * Keyboard shortcut "E" added in P07 alongside the full keyboard map.
 */
export function EditToolbar() {
  const editMode = useEditorStore((s) => s.editMode)
  const toggleEditMode = useEditorStore((s) => s.toggleEditMode)

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
      {/* Placeholder slots for P06 (Vertex, Merge trigger) + P07 (Split, Undo/Redo) */}
    </Flex>
  )
}
