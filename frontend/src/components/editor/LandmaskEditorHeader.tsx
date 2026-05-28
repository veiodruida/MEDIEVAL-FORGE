/**
 * LandmaskEditorHeader — Phase 08 Plan 08 (LANDMASK-01, LANDMASK-02).
 * Phase 08 Plan 16: added editableLayer toggle (baronies ↔ landmask).
 *
 * Header component for the Landmask Editor layer panel. Provides:
 *   - "Editar landmask" Switch toggle: flips useEditorStore.editableLayer
 *     between 'baronies' (OFF) and 'landmask' (ON). data-testid="landmask-edit-toggle".
 *   - Manual/Auto-immediate mode RadioGroup toggle (D-05).
 *   - Orange Badge "Modo auto: ~10s por edição" shown in Auto mode (must_haves).
 *   - "Aplicar landmask" Button (variant=outline) shown in Manual mode only (UI-SPEC Discretion #5).
 *   - onApply callback triggers POST /editor/apply op_type='landmask_replace' via parent.
 *
 * WARNING-5 fix (Pitfall 3): PT/ES border (40 pts) is NOT editable via this header.
 * The border_polygon Konva node sits on a separate read-only layer (listening=false).
 * This header only controls the landmask polygon itself.
 *
 * REQ-IDs: LANDMASK-01, LANDMASK-02
 * D-05: Two modes — manual (batch Apply) vs auto-immediate (drag cascade ~10s).
 */
import React from 'react';
import { Box, Heading, RadioGroup, Badge, Button, Flex, Switch, Text } from '@radix-ui/themes';
import { useEditorStore } from '../../stores/useEditorStore';
import type { LandmaskMode } from '../../stores/useEditorStore';

interface LandmaskEditorHeaderProps {
  /** Project UUID — forwarded into onApply for POST /editor/apply routing. */
  projectId: string;
  /** Branch UUID — forwarded into onApply for branch-scoped persistence. */
  branchId: string;
  /**
   * Called when the "Aplicar landmask" button is clicked (manual mode only).
   * Parent constructs the fetch call with op_type='landmask_replace' and the
   * current landmask coords from VertexEditLayer.
   */
  onApply: () => Promise<void>;
}

export const LandmaskEditorHeader: React.FC<LandmaskEditorHeaderProps> = ({
  projectId: _projectId,
  branchId: _branchId,
  onApply,
}) => {
  const mode = useEditorStore((s) => s.landmaskMode);
  const setMode = useEditorStore((s) => s.setLandmaskMode);
  // Phase 08 Plan 16: editableLayer toggle (baronies ↔ landmask)
  const editableLayer = useEditorStore((s) => s.editableLayer);
  const setEditableLayer = useEditorStore((s) => s.setEditableLayer);

  const isLandmaskEditing = editableLayer === 'landmask';

  return (
    <Box>
      <Heading size="2">Landmask</Heading>
      <Flex direction="column" gap="2">
        {/* Phase 08 Plan 16: editableLayer toggle — visible affordance to enter landmask edit mode */}
        <Flex align="center" gap="2">
          <Switch
            data-testid="landmask-edit-toggle"
            checked={isLandmaskEditing}
            onCheckedChange={(checked) =>
              setEditableLayer(checked ? 'landmask' : 'baronies')
            }
          />
          <Text size="2">Editar landmask</Text>
        </Flex>

        <RadioGroup.Root
          value={mode}
          onValueChange={(v) => setMode(v as LandmaskMode)}
        >
          <RadioGroup.Item value="manual">
            Manual (Aplicar para regenerar)
          </RadioGroup.Item>
          <RadioGroup.Item value="auto-immediate">
            Auto imediato (~10s/edição)
          </RadioGroup.Item>
        </RadioGroup.Root>

        {/* Auto mode: show informational orange Badge (must_haves) */}
        {mode === 'auto-immediate' && (
          <Badge color="orange" variant="soft">
            Modo auto: ~10s por edição
          </Badge>
        )}

        {/* Manual mode: show Apply button (variant=outline per UI-SPEC Discretion #5) */}
        {mode === 'manual' && (
          <Button variant="outline" color="blue" onClick={onApply}>
            Aplicar landmask
          </Button>
        )}
      </Flex>
    </Box>
  );
};
