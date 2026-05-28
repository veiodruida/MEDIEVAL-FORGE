/**
 * EditToolPalette — Phase 08 Plan 13, closes GAP-C (no visible edit-mode UI).
 *
 * This palette is a pure reflection of useEditorStore.activeTool — keyboard
 * shortcuts (useKeyboardShortcuts V/A/D/S/M) and palette buttons share one
 * state source. Clicking a button and pressing the corresponding key are
 * equivalent: both call useEditorStore.selectTool.
 *
 * Per 08-UI-SPEC §Tool Palette Zone (lines 141-160):
 * - Layout: Flex gap="1" of IconButton size="2"
 * - Active tool: variant="solid" color="blue"; inactive: variant="soft"
 * - Each button wrapped in Radix Tooltip (delayDuration 300ms)
 * - Icons from @radix-ui/react-icons
 *   NOTE: Scissors1Icon is not exported in the installed version; using
 *   ScissorsIcon instead (functionally identical for this context).
 *   MixIcon is available and used directly.
 */
import { Flex, IconButton, Tooltip } from '@radix-ui/themes';
import {
  CursorArrowIcon,
  PlusIcon,
  TrashIcon,
  ScissorsIcon,    // Scissors1Icon not in installed version — using ScissorsIcon
  MixIcon,
  Cross2Icon,
} from '@radix-ui/react-icons';
import type { ReactNode } from 'react';
import { useEditorStore } from '../../stores/useEditorStore';
import type { EditTool } from '../../stores/useEditorStore';

// ---------------------------------------------------------------------------
// Tool descriptor type
// ---------------------------------------------------------------------------

type ToolKey = EditTool | 'ESC';

interface ToolDescriptor {
  key: ToolKey;
  testid: string;
  icon: ReactNode;
  tooltip: string;
}

const TOOL_DESCRIPTORS: ToolDescriptor[] = [
  {
    key: 'V',
    testid: 'edit-tool-v',
    icon: <CursorArrowIcon />,
    tooltip: 'Selecionar vértice (V)',
  },
  {
    key: 'A',
    testid: 'edit-tool-a',
    icon: <PlusIcon />,
    tooltip: 'Adicionar vértice na aresta (A)',
  },
  {
    key: 'D',
    testid: 'edit-tool-d',
    icon: <TrashIcon />,
    tooltip: 'Excluir vértice selecionado (Del/D)',
  },
  {
    key: 'S',
    testid: 'edit-tool-s',
    icon: <ScissorsIcon />,
    tooltip: 'Dividir território — desenhe um corte (S)',
  },
  {
    key: 'M',
    testid: 'edit-tool-m',
    icon: <MixIcon />,
    tooltip: 'Mesclar territórios adjacentes (M)',
  },
  {
    key: 'ESC',
    testid: 'edit-tool-esc',
    icon: <Cross2Icon />,
    tooltip: 'Cancelar ação atual (Esc)',
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Visible V/A/D/S/M + Esc tool palette bound to useEditorStore.
 * Mount in WorkspaceToolbar between BranchPicker and Undo/Redo.
 */
export function EditToolPalette() {
  const activeTool = useEditorStore((s) => s.activeTool);
  const selectTool = useEditorStore((s) => s.selectTool);

  return (
    <Flex align="center" gap="1" data-testid="edit-tool-palette">
      {TOOL_DESCRIPTORS.map(({ key, testid, icon, tooltip }) => {
        // Esc button: 'ESC' never matches activeTool (EditTool type), so isActive
        // is always false for the cancel button — no special case needed.
        const isActive = activeTool === key;

        return (
          <Tooltip key={key} content={tooltip} delayDuration={300}>
            <IconButton
              size="2"
              variant={isActive ? 'solid' : 'soft'}
              color={isActive ? 'blue' : 'gray'}
              aria-pressed={isActive}
              aria-label={tooltip}
              data-testid={testid}
              onClick={() => selectTool(key === 'ESC' ? null : (key as EditTool))}
            >
              {icon}
            </IconButton>
          </Tooltip>
        );
      })}
    </Flex>
  );
}
