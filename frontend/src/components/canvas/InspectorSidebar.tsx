import { Badge, Box, Flex, Heading, ScrollArea, Text } from '@radix-ui/themes'
import { useUIStore } from '../../stores/uiStore'
import { MultiSelectInspector } from './MultiSelectInspector'
import { pixelsToKm2 as pixelsToKm2Util } from '../../lib/pixelsToKm2'
import type {
  TerritoryMetadata,
  TerritoryMetadataCondado,
  TerritoryRender,
} from '../../hooks/useCanvasArtifacts'

function pixelsToKm2(pixelCount: number, metadata: TerritoryMetadata): number {
  return pixelsToKm2Util(pixelCount, metadata)
}

/**
 * D-16 placeholder shown when no territory is selected. PT-BR per UI-SPEC
 * §Copywriting Contract.
 */
const PLACEHOLDER_PT = 'Clique num território para ver detalhes'

/**
 * UI-SPEC Copywriting Contract — exact strings the inspector MUST render.
 * D-06.3 "No capital assigned" is a functional sentinel (not just copy), so
 * it lives here too and is also asserted verbatim in tests.
 */
const COPY = {
  PROJECT_OVERVIEW: 'Project overview',
  PATH_LABEL: 'Path:',
  CENTROID_LABEL: 'Centroid',
  CAPITAL_LABEL: 'Capital',
  ADJACENT_LABEL: 'Adjacent territories',
  NO_CAPITAL: 'No capital assigned',
  NO_NEIGHBORS: 'No adjacent territories',
} as const

interface ProjectSummary {
  name: string
  country_qid: string
  period_start: number
  period_end: number
}

interface InspectorSidebarProps {
  metadata: TerritoryMetadata
  territories: TerritoryRender[]
  project: ProjectSummary
}

/**
 * Inspector sidebar — two states driven by useUIStore.selectedTerritoryId:
 *
 *   (A) null  → project-summary state: name/country/period + 4 hierarchy counts
 *               (UI-SPEC §Copywriting Contract: heading "Project overview", stats
 *               "Kingdoms", "Duchies", "Condados", "Baronies").
 *
 *   (B) id    → territory-detail state: 4 groups per D-06 —
 *               Group 1  Hierarchy badges (kingdom amber, duchy blue, condado grass,
 *                        baronies count gray)
 *               Group 2  Identity / geometry (Path, Area, Centroid)
 *               Group 3  Capital (D-06.3 sentinel — "No capital assigned" when
 *                        capital_name is absent or blank)
 *               Group 4  Adjacent territories (neighbor chips → useUIStore.select)
 *
 * Copywriting strings are verbatim per UI-SPEC; the literal string
 * "No capital assigned" is required by D-06.3.
 */
export function InspectorSidebar({
  metadata,
  territories,
  project,
}: InspectorSidebarProps) {
  const selectedIds = useUIStore((s) => s.selectedTerritoryIds)
  const selectedId = useUIStore((s) => s.selectedTerritoryId)
  const select = useUIStore((s) => s.select)

  // D-17 dispatcher: 3 modes driven by selectedTerritoryIds.length.
  //   0 → PT-BR placeholder (D-16)
  //   1 → existing single-select detail view (D-14, English COPY locked)
  //   ≥2 → MultiSelectInspector aggregate
  if (selectedIds.length === 0) {
    return (
      <Flex direction="column" gap="3" data-testid="inspector-placeholder">
        <Text size="2" color="gray" as="p">{PLACEHOLDER_PT}</Text>
      </Flex>
    )
  }

  if (selectedIds.length >= 2) {
    return (
      <Box data-testid="inspector-multi">
        <MultiSelectInspector selectedIds={selectedIds} metadata={metadata} />
      </Box>
    )
  }

  const condado: TerritoryMetadataCondado | undefined = selectedId
    ? metadata.condados.find((c) => c.id === selectedId)
    : undefined

  if (!condado) {
    return (
      <Flex direction="column" gap="3">
        <Heading size="3">{COPY.PROJECT_OVERVIEW}</Heading>
        <Box>
          <Text size="2" weight="bold" as="p">
            {project.name}
          </Text>
          <Text size="1" color="gray" as="p">
            {project.country_qid} · {project.period_start}–{project.period_end} AD
          </Text>
        </Box>

        <Box>
          <Flex justify="between" align="center">
            <Text size="2" color="gray">Kingdoms</Text>
            <Badge color="amber">{Object.keys(metadata.kingdoms).length}</Badge>
          </Flex>
          <Flex justify="between" align="center">
            <Text size="2" color="gray">Duchies</Text>
            <Badge color="blue">{Object.keys(metadata.duchies).length}</Badge>
          </Flex>
          <Flex justify="between" align="center">
            <Text size="2" color="gray">Condados</Text>
            <Badge color="grass">{metadata.condados.length}</Badge>
          </Flex>
          <Flex justify="between" align="center">
            <Text size="2" color="gray">Baronies</Text>
            <Badge color="gray">{metadata.baronies.length}</Badge>
          </Flex>
        </Box>
      </Flex>
    )
  }

  // Territory detail
  const duchy = metadata.duchies[condado.duchy]
  const kingdomName = metadata.kingdoms[condado.kingdom] ?? condado.kingdom
  const duchyName = duchy?.name ?? condado.duchy
  const baronyCount = condado.baronies.length

  // `territories` is accepted as a prop so Phase 4+ can derive geometry-based
  // area from the projected points (Shoelace formula) rather than pixel_count.
  // Not used yet — pixel_count is still the authoritative area signal for Phase 2.
  void territories
  const neighbors = condado.neighbors

  const hasCapital =
    typeof condado.capital_name === 'string' &&
    condado.capital_name.trim().length > 0

  return (
    <Flex direction="column" gap="3" data-testid="inspector-single">
      <Heading size="3">{condado.name}</Heading>

      {/* Group 1: Hierarchy badges — amber / blue / grass / gray */}
      <Flex gap="2" wrap="wrap">
        <Badge color="amber" variant="soft">Kingdom: {kingdomName}</Badge>
        <Badge color="blue" variant="soft">Duchy: {duchyName}</Badge>
        <Badge color="grass" variant="soft">Condado</Badge>
        <Badge color="gray" variant="soft">Baronies: {baronyCount}</Badge>
      </Flex>

      {/* Group 2: identity / geometry */}
      <Box>
        <Text size="1" color="gray" as="p">
          {COPY.PATH_LABEL} {kingdomName} / {duchyName} / {condado.name}
        </Text>
      </Box>

      <Box>
        <Flex justify="between" align="center">
          <Text size="1" color="gray">Area</Text>
          <Text size="2">
            {`~${Math.round(pixelsToKm2(condado.pixel_count, metadata)).toLocaleString()} km²`}
          </Text>
        </Flex>
      </Box>

      {/* Centroid — ALWAYS its own row (separate from Capital) */}
      <Box>
        <Flex justify="between" align="center">
          <Text size="1" color="gray">{COPY.CENTROID_LABEL}</Text>
          <Text size="2">
            {condado.lat.toFixed(3)}, {condado.lon.toFixed(3)}
          </Text>
        </Flex>
      </Box>

      {/* Group 3: Capital — D-06.3 sentinel */}
      <Box>
        <Text size="1" color="gray" as="p">{COPY.CAPITAL_LABEL}</Text>
        {hasCapital ? (
          <>
            <Text size="2" as="p">
              {condado.capital_name}
            </Text>
            <Text size="1" color="gray" as="p">
              {condado.lat.toFixed(3)}, {condado.lon.toFixed(3)}
            </Text>
          </>
        ) : (
          <Text size="2" color="gray" as="p">{condado.name}</Text>
        )}
      </Box>

      {/* Group 4: Adjacent territories */}
      <Box>
        <Text size="1" color="gray" as="p" mb="1">{COPY.ADJACENT_LABEL}</Text>
        {neighbors.length === 0 ? (
          <Text size="2" color="gray">{COPY.NO_NEIGHBORS}</Text>
        ) : (
          <ScrollArea type="auto" scrollbars="vertical" style={{ maxHeight: 200 }}>
            <Flex gap="2" wrap="wrap">
              {neighbors.map((nId) => {
                const n = metadata.condados.find((c) => c.id === nId)
                const label = n?.name ?? nId
                return (
                  <button
                    key={nId}
                    data-testid={`neighbor-chip-${nId}`}
                    type="button"
                    onClick={() => select(nId)}
                    style={{
                      border: 'none',
                      padding: 0,
                      background: 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <Badge variant="soft" color="gray">{label}</Badge>
                  </button>
                )
              })}
            </Flex>
          </ScrollArea>
        )}
      </Box>
    </Flex>
  )
}
