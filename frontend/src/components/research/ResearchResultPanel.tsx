/**
 * Post-success summary of the research overlay (UAT 2026-05-22).
 *
 * The user reported "fechou a janela e nao tenho certeza se o resultado esta
 * correto" — the dialog used to auto-close 1.2s after success without showing
 * what was actually written. This panel renders the per-condado entries
 * grouped by kingdom_owner so the user can verify names/notes before
 * dismissing the dialog.
 *
 * Reads `entries` from useResearchOverlay (backend overlay endpoint now
 * returns the full map, not just `covered_condado_ids`).
 */
import { Badge, Box, Flex, ScrollArea, Separator, Text } from '@radix-ui/themes'
import type { ResearchOverlay, ResearchOverlayEntry } from '../../api/useResearchOverlay'

export interface ResearchResultPanelProps {
  overlay: ResearchOverlay | undefined
  /** Loading state from the TanStack query so we can render a skeleton. */
  isLoading: boolean
}

interface KingdomGroup {
  kingdom: string
  rows: Array<{ id: string; entry: ResearchOverlayEntry }>
}

function groupByKingdom(
  entries: Record<string, ResearchOverlayEntry>,
): KingdomGroup[] {
  const buckets = new Map<string, KingdomGroup>()
  for (const [id, entry] of Object.entries(entries)) {
    const key = entry.kingdom_owner ?? '(sem reino)'
    let group = buckets.get(key)
    if (!group) {
      group = { kingdom: key, rows: [] }
      buckets.set(key, group)
    }
    group.rows.push({ id, entry })
  }
  for (const g of buckets.values()) {
    g.rows.sort((a, b) => a.id.localeCompare(b.id))
  }
  return Array.from(buckets.values()).sort((a, b) =>
    a.kingdom.localeCompare(b.kingdom),
  )
}

export function ResearchResultPanel({ overlay, isLoading }: ResearchResultPanelProps) {
  if (isLoading) {
    return (
      <Box mt="2">
        <Text size="2" color="gray">
          Carregando resultado…
        </Text>
      </Box>
    )
  }

  if (!overlay || !overlay.exists) {
    return (
      <Box mt="2">
        <Text size="2" color="gray">
          Nenhum resultado disponível.
        </Text>
      </Box>
    )
  }

  const entries = overlay.entries ?? {}
  const groups = groupByKingdom(entries)
  const total = overlay.covered_condado_ids.length

  return (
    <Box data-testid="research-result-panel" mt="2">
      <Flex align="center" gap="2" mb="2">
        <Text size="2" weight="medium">
          Resultado da pesquisa
        </Text>
        <Badge color="green" variant="soft">
          {total} condado{total === 1 ? '' : 's'}
        </Badge>
        {overlay.meta?.model && (
          <Text size="1" color="gray">
            {overlay.meta.provider} · {overlay.meta.model}
          </Text>
        )}
      </Flex>
      <ScrollArea
        type="auto"
        scrollbars="vertical"
        style={{ maxHeight: 260 }}
      >
        <Flex direction="column" gap="3" pr="2">
          {groups.map((g, gi) => (
            <Box key={g.kingdom}>
              {gi > 0 && <Separator size="4" mb="2" />}
              <Text size="2" weight="medium" color="indigo">
                {g.kingdom}
              </Text>
              <Flex direction="column" gap="2" mt="1">
                {g.rows.map(({ id, entry }) => (
                  <Box key={id}>
                    <Text size="2">
                      <strong>{entry.name ?? id}</strong>{' '}
                      <Text size="1" color="gray">
                        ({id})
                      </Text>
                    </Text>
                    {entry.historical_notes && (
                      <Text size="1" color="gray" as="p">
                        {entry.historical_notes}
                      </Text>
                    )}
                  </Box>
                ))}
              </Flex>
            </Box>
          ))}
        </Flex>
      </ScrollArea>
    </Box>
  )
}
