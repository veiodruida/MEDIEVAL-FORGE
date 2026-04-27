import { useSyncExternalStore } from 'react'
import { Flex, Button, Tooltip, Separator, SegmentedControl, Text, Slider } from '@radix-ui/themes'
import { CounterClockwiseClockIcon } from '@radix-ui/react-icons'
import * as Icons from '@radix-ui/react-icons'
import { useEditorStore } from '../../stores/useEditorStore'
import { useProjectStore } from '../../stores/useProjectStore'
import { useUIStore } from '../../stores/uiStore'
import { TERRAIN_TYPES, TERRAIN_EMOJI, TERRAIN_LABELS_PT, type TerrainType } from '../../types/editing'

// Redo icon: try candidates in order; fall back to text arrow if none match.
// ReloadIcon confirmed present in installed @radix-ui/react-icons version.
const RedoIcon =
  (Icons as Record<string, React.ComponentType>).ReloadIcon ??
  (Icons as Record<string, React.ComponentType>).UpdateIcon ??
  null

/**
 * UndoRedoButtons — subscribes to temporal store via useSyncExternalStore for
 * reactive enabled/disabled state (zundo 2.3.0: temporal is a Zustand store,
 * not a React context; useSyncExternalStore is the canonical reactive-read pattern).
 *
 * Pitfall 7: labels live in useEditorStore. Undo/redo MUST pop the matching label.
 */
function UndoRedoButtons() {
  const undoLabels = useEditorStore((s) => s.undoLabels)
  const redoLabels = useEditorStore((s) => s.redoLabels)
  const popUndoLabel = useEditorStore((s) => s.popUndoLabel)
  const popRedoLabel = useEditorStore((s) => s.popRedoLabel)

  // useSyncExternalStore for reactive temporal lengths (re-renders on every undo/redo/set)
  const pastStatesLength = useSyncExternalStore(
    useProjectStore.temporal.subscribe,
    () => useProjectStore.temporal.getState().pastStates.length,
    () => 0,
  )
  const futureStatesLength = useSyncExternalStore(
    useProjectStore.temporal.subscribe,
    () => useProjectStore.temporal.getState().futureStates.length,
    () => 0,
  )

  const lastUndo = undoLabels.at(-1)
  const lastRedo = redoLabels.at(-1)

  const doUndo = () => {
    useProjectStore.temporal.getState().undo()
    popUndoLabel()
  }
  const doRedo = () => {
    useProjectStore.temporal.getState().redo()
    popRedoLabel()
  }

  return (
    <>
      <Tooltip content={lastUndo ? `Desfazer: ${lastUndo}` : 'Nada a desfazer'}>
        <Button
          size="2"
          variant="soft"
          disabled={pastStatesLength === 0}
          onClick={doUndo}
          aria-label="Desfazer"
        >
          <CounterClockwiseClockIcon />
        </Button>
      </Tooltip>
      <Tooltip content={lastRedo ? `Refazer: ${lastRedo}` : 'Nada a refazer'}>
        <Button
          size="2"
          variant="soft"
          disabled={futureStatesLength === 0}
          onClick={doRedo}
          aria-label="Refazer"
        >
          {RedoIcon ? <RedoIcon /> : <span aria-hidden>&#8618;</span>}
        </Button>
      </Tooltip>
    </>
  )
}

/**
 * EditToolbar — Phase 4 toolbar.
 *
 * Buttons:
 *   Editar           — global edit mode toggle (P05)
 *   Editar Vértices  — enters vertex-edit for selected territory (P06)
 *   Dividir          — activates split tool; shows sub-mode segmented control (P07)
 *   Undo / Redo      — CounterClockwiseClockIcon / ReloadIcon; tooltips show last action
 *                      label; disabled when history is exhausted (P07)
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

  // Phase 05: paint tool state
  const activeTerrain = useEditorStore((s) => s.activeTerrain)
  const brushRadius = useEditorStore((s) => s.brushRadius)
  const setActiveTerrain = useEditorStore((s) => s.setActiveTerrain)
  const setBrushRadius = useEditorStore((s) => s.setBrushRadius)

  const splitActive = activeTool === 'split'
  const paintActive = activeTool === 'paint'

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
      {/* Phase 05: paint terrain tool button */}
      {editMode && (
        <Tooltip content={!editMode ? 'Ative o modo de edição primeiro' : 'Ferramenta de pintura ativa (P)'}>
          <Button
            size="2"
            variant={paintActive ? 'solid' : 'soft'}
            color={paintActive ? 'iris' : 'gray'}
            disabled={!editMode}
            title={!editMode ? 'Ative o modo de edição primeiro' : 'Ferramenta de pintura ativa (P)'}
            onClick={() => {
              if (paintActive) {
                setActiveTool('none')
              } else {
                setActiveTool('paint')
                if (activeTerrain === null) setActiveTerrain('mountain')
              }
            }}
          >
            Pintar Terreno
          </Button>
        </Tooltip>
      )}
      {/* Phase 05: paint controls (terrain picker + radius slider) — shown only when paint tool is active */}
      {editMode && paintActive && (
        <Flex gap="2" align="center">
          <SegmentedControl.Root
            size="1"
            value={activeTerrain ?? 'mountain'}
            onValueChange={(v) => setActiveTerrain(v as TerrainType)}
          >
            {TERRAIN_TYPES.map((t) => (
              <SegmentedControl.Item key={t} value={t}>
                {TERRAIN_EMOJI[t]} {TERRAIN_LABELS_PT[t]}
              </SegmentedControl.Item>
            ))}
          </SegmentedControl.Root>
          <Text size="1">Raio: {brushRadius}px</Text>
          <Slider
            size="1"
            min={10}
            max={80}
            step={5}
            value={[brushRadius]}
            onValueChange={(v) => setBrushRadius(v[0])}
            style={{ width: 120 }}
          />
        </Flex>
      )}
      <Separator orientation="vertical" size="1" />
      <UndoRedoButtons />
    </Flex>
  )
}
