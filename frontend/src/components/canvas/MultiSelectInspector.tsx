import { useMemo } from 'react'
import { Badge, Box, Flex, Heading, ScrollArea, Text } from '@radix-ui/themes'
import { pixelsToKm2 } from '../../lib/pixelsToKm2'
import type { TerritoryMetadata } from '../../hooks/useCanvasArtifacts'

interface Props {
  selectedIds: string[]
  metadata: TerritoryMetadata
}

/**
 * D-17 Multi-select aggregate inspector.
 *
 * Renders, for the current 2+-territory selection:
 *   - heading: "X condados selecionados"
 *   - "Área total" + summed pixel_count converted to km² (via pixelsToKm2 util)
 *   - "Reinos" + Flex of amber Badge per unique kingdom name
 *   - "Ducados" + Flex of blue Badge per unique duchy name
 *   - "Condados" + ScrollArea (maxHeight 200px) listing each condado name
 *
 * No per-territory metadata is shown here (single-select view in
 * InspectorSidebar covers that — D-14).
 */
export function MultiSelectInspector({ selectedIds, metadata }: Props) {
  const aggregate = useMemo(() => {
    const condados = metadata.condados.filter((c) => selectedIds.includes(c.id))
    const totalPixelCount = condados.reduce((sum, c) => sum + (c.pixel_count ?? 0), 0)
    const kingdomNames = Array.from(
      new Set(condados.map((c) => metadata.kingdoms[c.kingdom] ?? c.kingdom)),
    )
    const duchyNames = Array.from(
      new Set(condados.map((c) => metadata.duchies[c.duchy]?.name ?? c.duchy)),
    )
    const condadoNames = condados.map((c) => c.name)
    return { condados, totalPixelCount, kingdomNames, duchyNames, condadoNames }
  }, [selectedIds, metadata])

  const totalKm2 = pixelsToKm2(aggregate.totalPixelCount, metadata)

  return (
    <Flex direction="column" gap="3">
      <Heading size="3">{selectedIds.length} condados selecionados</Heading>

      <Box>
        <Text size="2" weight="bold" as="p">Área total</Text>
        <Text size="2" as="p">
          {`~${Math.round(totalKm2).toLocaleString()} km²`}
        </Text>
      </Box>

      <Box>
        <Text size="2" weight="bold" as="p" mb="1">Reinos</Text>
        <Flex gap="1" wrap="wrap">
          {aggregate.kingdomNames.map((k) => (
            <Badge key={k} color="amber" variant="soft">{k}</Badge>
          ))}
        </Flex>
      </Box>

      <Box>
        <Text size="2" weight="bold" as="p" mb="1">Ducados</Text>
        <Flex gap="1" wrap="wrap">
          {aggregate.duchyNames.map((d) => (
            <Badge key={d} color="blue" variant="soft">{d}</Badge>
          ))}
        </Flex>
      </Box>

      <Box>
        <Text size="2" weight="bold" as="p" mb="1">Condados</Text>
        <ScrollArea type="auto" scrollbars="vertical" style={{ maxHeight: 200 }}>
          <Flex direction="column" gap="1">
            {aggregate.condadoNames.map((n, i) => (
              <Text key={`${n}-${i}`} size="2">{n}</Text>
            ))}
          </Flex>
        </ScrollArea>
      </Box>
    </Flex>
  )
}
