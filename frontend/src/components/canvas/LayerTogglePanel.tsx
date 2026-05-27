import { Card, Flex, Text, Checkbox, Tooltip, Separator } from '@radix-ui/themes'
import { useUIStore, type LayerName } from '../../stores/uiStore'
import { LandmaskEditorHeader } from '../editor/LandmaskEditorHeader'

// Quick-task 260420-hkr: vocabulary aligned with the Reino/Duquia/Condado
// hierarchy. Portuguese labels match InspectorSidebar copy.
// GAP-08 (02-05): Labels row carries a Tooltip explaining the zoom-gate so
// users don't perceive the toggle as broken at default zoom.
const LAYERS: { key: LayerName; label: string; hint?: string }[] = [
  { key: 'condados', label: 'Condados' },
  { key: 'baronies', label: 'Baronias' },
  { key: 'borders', label: 'Fronteiras' },
  { key: 'capitals', label: 'Capitais' },
  { key: 'labels', label: 'Nomes', hint: 'Zoom in 1.5× to show labels' },
]

interface LayerTogglePanelProps {
  /** Optional: project + branch ids required when Landmask Editor row is visible. */
  projectId?: string
  branchId?: string
  /** Called when "Aplicar landmask" is clicked; parent POSTs landmask_replace. */
  onApplyLandmask?: () => Promise<void>
}

export function LayerTogglePanel({
  projectId,
  branchId,
  onApplyLandmask,
}: LayerTogglePanelProps = {}) {
  const layerVisibility = useUIStore((s) => s.layerVisibility)
  const toggleLayer = useUIStore((s) => s.toggleLayer)

  // Default no-op apply handler when parent doesn't supply one
  const handleApplyLandmask = onApplyLandmask ?? (() => Promise.resolve())

  return (
    <Card
      data-testid="layer-toggle-panel"
      variant="surface"
      style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, width: 180 }}
    >
      <Flex direction="column" gap="2">
        <Text size="2" weight="bold">Camadas</Text>
        {LAYERS.map(({ key, label, hint }) => {
          // Row renders checkbox + label; when a hint exists, append a dim
          // inline suffix (e.g. "(zoom ≥ 1.5×)") so the gate is discoverable
          // even for users who never hover for the Tooltip to appear.
          const rowContent = (
            <Flex align="center" gap="2" data-testid={`layer-toggle-${key}`}>
              <Checkbox
                checked={layerVisibility[key]}
                onCheckedChange={() => toggleLayer(key)}
              />
              <Text size="2">{label}</Text>
              {hint && (
                <Text size="1" color="gray">(zoom ≥ 1.5×)</Text>
              )}
            </Flex>
          )
          return hint ? (
            <Tooltip key={key} content={hint}>
              {rowContent}
            </Tooltip>
          ) : (
            <Flex key={key} align="center" gap="2" data-testid={`layer-toggle-${key}`}>
              <Checkbox
                checked={layerVisibility[key]}
                onCheckedChange={() => toggleLayer(key)}
              />
              <Text size="2">{label}</Text>
            </Flex>
          )
        })}

        {/* Phase 08 Plan 08: Landmask Editor section (LANDMASK-01, LANDMASK-02).
            Separator + LandmaskEditorHeader below the layer checkboxes.
            Only renders the header when projectId + branchId are provided by parent. */}
        <Separator size="4" />
        <LandmaskEditorHeader
          projectId={projectId ?? ''}
          branchId={branchId ?? ''}
          onApply={handleApplyLandmask}
        />
      </Flex>
    </Card>
  )
}
