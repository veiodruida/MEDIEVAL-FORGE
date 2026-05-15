import { useState } from 'react'
import { Badge, Box, Button, Flex, Heading, ScrollArea, Text, Tooltip } from '@radix-ui/themes'
import { MagnifyingGlassIcon } from '@radix-ui/react-icons'
import { useUIStore } from '../../stores/uiStore'
import { MultiSelectInspector } from './MultiSelectInspector'
import { pixelsToKm2 as pixelsToKm2Util } from '../../lib/pixelsToKm2'
import { useResearchOverlay } from '../../api/useResearchOverlay'
import { ResearchDialog } from '../research/ResearchDialog'
import { regionDisplayNameFor } from '../../utils/regionDisplay'
import type {
  BaronyRender,
  TerritoryMetadata,
  TerritoryMetadataCondado,
  TerritoryRender,
} from '../../hooks/useCanvasArtifacts'

/**
 * Plan 07-09b — REVIEWS fix #2 timestamp helpers.
 *
 * `timestampsMatch` absorbs seconds-precision rounding (within 1 second is
 * treated as "fresh-run"). `formatDate` renders UTC-stable `YYYY-MM-DD HH:mm`
 * inline because date-fns is NOT in package.json.
 */
function timestampsMatch(generatedAt: string, appliedAt: string): boolean {
  const g = new Date(generatedAt).getTime()
  const a = new Date(appliedAt).getTime()
  return Math.abs(a - g) < 1000
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

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
  id: string
  name: string
  country_qid: string
  period_start: number
  period_end: number
  /**
   * Plan 07-09b — gates the "Pesquisar metadados históricos" trigger.
   * Research is only available once geometric generation has produced the
   * 12-file artifact bundle (status === 'generated').
   */
  status: string
}


interface InspectorSidebarProps {
  metadata: TerritoryMetadata
  territories: TerritoryRender[]
  baronies: BaronyRender[]  // D-03 (Phase 04.1): supplies centroid for barony historical panel
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
  baronies,
  project,
}: InspectorSidebarProps) {
  const selectedIds = useUIStore((s) => s.selectedTerritoryIds)
  const selectedId = useUIStore((s) => s.selectedTerritoryId)
  const selectedBaronyId = useUIStore((s) => s.selectedBaronyId)
  const select = useUIStore((s) => s.select)

  // Plan 07-09b — ResearchDialog open-state lives here (BLOCKER 3: the
  // dialog is mounted INSIDE the InspectorSidebar, not in ProjectDetail.tsx).
  // `forceRefreshPreChecked` propagates to ResearchDialog via the
  // `initialForceRefresh` prop and is consumed when the user clicks
  // "Atualizar pesquisa" on a condado/barony with applied research.
  const [researchOpen, setResearchOpen] = useState(false)
  const [forceRefreshPreChecked, setForceRefreshPreChecked] = useState(false)
  const overlay = useResearchOverlay(project.id)
  const overlayData = overlay.data
  const meta = overlayData?.meta ?? null

  const condadoIdsForDialog = metadata.condados.map((c) => c.id)
  const regionDisplayName = regionDisplayNameFor(project.country_qid)

  function openResearchDialog(forceRefresh: boolean) {
    setForceRefreshPreChecked(forceRefresh)
    setResearchOpen(true)
  }

  /**
   * REVIEWS fix #2 — dual-timestamp microcopy. Single line when the LLM
   * output and the runner write-time are within 1s (fresh run); two lines
   * when they differ (cache hit re-applied later).
   */
  const microcopy =
    overlayData?.exists && meta ? (
      timestampsMatch(meta.generated_at, meta.applied_at) ? (
        <Text size="1" color="gray" data-testid="research-microcopy-single">
          {`Última pesquisa: ${meta.provider} · ${meta.model} · ${formatDate(meta.generated_at)}`}
        </Text>
      ) : (
        <Flex direction="column" gap="0" data-testid="research-microcopy-dual">
          <Text size="1" color="gray">
            {`Pesquisa gerada: ${meta.provider} · ${meta.model} · ${formatDate(meta.generated_at)}`}
          </Text>
          <Text size="1" color="gray">
            {`· aplicada: ${formatDate(meta.applied_at)}`}
          </Text>
        </Flex>
      )
    ) : null

  /**
   * Plan 07-09b — `<ResearchDialog>` is mounted ONCE at sidebar root so it
   * survives mode switches (placeholder → condado → barony). The trigger
   * button (placeholder mode) and the "Atualizar pesquisa" reopen link
   * (condado/barony mode) both share this single mount via local state.
   */
  const dialogMount = (
    <ResearchDialog
      open={researchOpen}
      onOpenChange={setResearchOpen}
      projectId={project.id}
      regionDisplayName={regionDisplayName}
      countryQid={project.country_qid}
      condadoIds={condadoIdsForDialog}
      initialForceRefresh={forceRefreshPreChecked}
    />
  )

  /**
   * Helper — render the "Pesquisa aplicada" + "Atualizar pesquisa" pair
   * for a given condado id. Used by both condado-mode (selected id) and
   * barony-mode (parent condado id).
   */
  function renderAppliedBadge(condadoId: string | undefined) {
    if (!condadoId) return null
    if (!overlayData?.exists) return null
    if (!overlayData.covered_condado_ids.includes(condadoId)) return null
    return (
      <Flex gap="2" align="center">
        <Badge color="green" variant="soft">Pesquisa aplicada</Badge>
        <Text
          size="1"
          color="gray"
          style={{ cursor: 'pointer', textDecoration: 'underline' }}
          onClick={() => openResearchDialog(true)}
          role="button"
        >
          Atualizar pesquisa
        </Text>
      </Flex>
    )
  }

  // Plan 03-08 follow-up adds a 4th mode: barony detail (Phase 04 will
  // build vertex-edit affordances on top of this). Order matters:
  //   selectedBaronyId set → barony detail (precedence over placeholder)
  //   else selectedIds.length === 0 → PT-BR placeholder (D-16)
  //   else selectedIds.length >= 2 → MultiSelectInspector aggregate
  //   else → single condado detail (D-14, English COPY locked)
  if (selectedBaronyId) {
    const barony = metadata.baronies.find((b) => b.name === selectedBaronyId)
    if (!barony) {
      return (
        <Flex direction="column" gap="3" data-testid="inspector-barony-missing">
          <Text size="2" color="gray" as="p">
            Baronia "{selectedBaronyId}" não encontrada nos metadados.
          </Text>
        </Flex>
      )
    }
    const parent = metadata.condados[barony.condado_idx]
    const duchyName = metadata.duchies[barony.duchy]?.name ?? barony.duchy
    const kingdomId = metadata.duchies[barony.duchy]?.kingdom ?? ''
    const kingdomName = metadata.kingdoms[kingdomId] ?? kingdomId

    // D-03 (Phase 04.1): centroid sourced from the GeoJSON (BaronyRender),
    // NOT from territory_metadata.json (which lacks centroid).
    const baronyRender = baronies.find((b) => b.name === selectedBaronyId)
    const centroid = baronyRender?.centroid

    // Plan 07-09b — surface the "Pesquisa aplicada" badge for the barony's
    // parent condado id (lookup via metadata.condados[barony.condado_idx]).
    const parentCondadoId = parent?.id
    return (
      <Flex direction="column" gap="3" data-testid="inspector-barony">
        <Heading size="3">{barony.name}</Heading>
        <Flex gap="2" wrap="wrap">
          <Badge color="amber" variant="soft">Kingdom: {kingdomName}</Badge>
          <Badge color="blue" variant="soft">Duchy: {duchyName}</Badge>
          <Badge color="grass" variant="soft">
            Condado: {parent?.name ?? barony.condado_idx}
          </Badge>
          <Badge color="gray" variant="soft">Barony</Badge>
        </Flex>
        {renderAppliedBadge(parentCondadoId)}
        {dialogMount}
        <Box>
          <Flex justify="between" align="center">
            <Text size="1" color="gray">Area</Text>
            <Text size="2">
              {`~${Math.round(pixelsToKm2(barony.pixel_count, metadata)).toLocaleString()} km²`}
            </Text>
          </Flex>
        </Box>

        {/* D-03: Source coordinate row.
            BaronyRender.centroid is stored as [lon, lat] per the
            canvas_sidecars.py emission contract. Display convention matches
            the condado branch: "lat, lon" (lat first), 3-decimal precision.
            Fallback "—" when the GeoJSON is older (pre-Phase 04.1) and the
            centroid property is absent — no NaN / 'undefined' leak. */}
        <Box>
          <Flex justify="between" align="center">
            <Text size="1" color="gray">Coordenada de origem</Text>
            <Text size="2" data-testid="barony-source-coord">
              {centroid
                ? `${centroid[1].toFixed(3)}, ${centroid[0].toFixed(3)}`
                : '—'}
            </Text>
          </Flex>
        </Box>

        {/* D-03: Source data file reference — non-clickable monospaced label
            (NOT a link; this is a local-only path, not a URL). */}
        <Box>
          <Text size="1" color="gray" as="p">Origem dos dados</Text>
          <Text
            size="2"
            as="p"
            data-testid="barony-source-file"
            style={{ fontFamily: 'monospace' }}
          >
            inicio/territory_data_v3.py
          </Text>
        </Box>

        {/* D-03: Collapsible PT-BR explainer of the Voronoi-from-centroids
            mechanic — answers the UAT gap "noticed very large baronies, are
            they really like this?". Frontier regions (Andalusia) have sparse
            historical centroids, which is expected behavior, not a bug.
            English equivalent kept inline as i18n placeholder. */}
        <Box>
          <details data-testid="barony-method-explainer">
            <summary style={{ cursor: 'pointer' }}>
              <Text size="2" weight="bold" as="span">
                Sobre o método
              </Text>
            </summary>
            <Box mt="2">
              <Text size="2" color="gray" as="p">
                As baronias são geradas por Voronoi a partir de centroides históricos.
                Regiões com poucos centroides (fronteira, Andalusia) produzem células
                maiores — isso é o comportamento esperado, não um erro do mapa.
              </Text>
              {/* English equivalent (i18n placeholder per CONTEXT.md D-03):
                  Baronies are generated via Voronoi tessellation from historical
                  centroids. Regions with few centroids (frontier, Andalusia)
                  produce larger cells — this is expected behavior, not a map error. */}
            </Box>
          </details>
        </Box>
      </Flex>
    )
  }

  if (selectedIds.length === 0) {
    // Plan 07-09b — placeholder mode adds the "Pesquisar metadados históricos"
    // trigger plus the REVIEWS fix #2 dual-timestamp microcopy line. The
    // Phase 03 D-16 PT-BR placeholder text above (PLACEHOLDER_PT) is
    // UNCHANGED per the COPY-block lock.
    const isReadyForResearch = project.status === 'generated'
    return (
      <Flex direction="column" gap="3" data-testid="inspector-placeholder">
        <Text size="2" color="gray" as="p">{PLACEHOLDER_PT}</Text>
        <Tooltip
          content="Gere o mapa antes de pesquisar metadados."
          // Force tooltip body visible to assistive tech / tests via
          // `data-tooltip-body` (the wrapper exposes the literal so vitest
          // can assert without dispatching pointer events).
        >
          <span data-testid="research-trigger-tooltip" data-tooltip-body="Gere o mapa antes de pesquisar metadados.">
            <Button
              variant="soft"
              size="2"
              disabled={!isReadyForResearch}
              onClick={() => openResearchDialog(false)}
              data-testid="research-trigger-button"
            >
              <MagnifyingGlassIcon />
              Pesquisar metadados históricos
            </Button>
          </span>
        </Tooltip>
        {microcopy}
        {dialogMount}
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
      {/* Plan 07-09b — Pesquisa aplicada badge + Atualizar pesquisa reopen link */}
      {renderAppliedBadge(condado.id)}
      {dialogMount}

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
