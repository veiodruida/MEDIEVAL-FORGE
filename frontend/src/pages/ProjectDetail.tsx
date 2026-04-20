import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Box, Button, Card, Callout, Flex, Heading, Tabs, Text, TextField } from '@radix-ui/themes'
import { useQueryClient } from '@tanstack/react-query'
import { useProject, useUpdateProject, useIngestStream, useGenerate, useExport, useIngestStatus, useTerritoryTemplate, useRenderModern, type Project } from '../api/client'
import { TerritoryEditor, type TerritoryData } from './TerritoryEditor'
import { CanvasViewer } from '../components/canvas/CanvasViewer'
import { InspectorSidebar } from '../components/canvas/InspectorSidebar'
import { LegendCard } from '../components/canvas/LegendCard'
import { useCanvasArtifacts } from '../hooks/useCanvasArtifacts'
import { buildProjectionConfig } from '../lib/projection'

const STATUS_LABEL: Record<string, string> = {
  created: 'Criado',
  ingested: 'Dados ingeridos',
  generating: 'Gerando mapa…',
  generated: 'Mapa gerado',
  exported: 'Exportado',
  error_ingesting: 'Erro na ingestão',
  error_generating: 'Erro na geração',
}

const DEFAULT_TERRITORY: TerritoryData = {
  kingdoms: { K_PORT: 'Reino de Portugal' },
  duchies: {
    D_MINHO: ['K_PORT', 'Minho'],
    D_DOURO: ['K_PORT', 'Douro'],
  },
  condados: [
    ['C_BRAGA', 'Braga', -8.43, 41.55, 'D_MINHO', [['Baronia de Braga', -8.43, 41.55]]],
    ['C_PORTO', 'Porto', -8.61, 41.15, 'D_DOURO', [['Baronia do Porto', -8.61, 41.15]]],
    ['C_VIANA', 'Viana do Castelo', -8.83, 41.69, 'D_MINHO', [['Baronia de Viana', -8.83, 41.69]]],
    ['C_VISEU', 'Viseu', -7.91, 40.65, 'D_DOURO', [['Baronia de Viseu', -7.91, 40.65]]],
  ],
}

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: project, isLoading, error } = useProject(id)
  const update = useUpdateProject(id || '')
  const ingest = useIngestStream(id)
  const generate = useGenerate(id)
  const exportZip = useExport(id)
  const ingestStatus = useIngestStatus(id)
  const renderModern = useRenderModern(id)
  const qc = useQueryClient()
  const [modernTs, setModernTs] = useState(0)

  // Detectar template de território baseado no país do projeto
  const iberiaQids = new Set(['Q29', 'Q45'])
  const templateRegion = project && iberiaQids.has(project.country_qid) ? 'iberia' : null
  const { data: templateData } = useTerritoryTemplate(templateRegion)

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ name: '', period_start: 0, period_end: 0 })
  const [territory, setTerritory] = useState<TerritoryData>(DEFAULT_TERRITORY)
  const [templateLoaded, setTemplateLoaded] = useState(false)

  // Carregar template de território quando disponível (apenas uma vez)
  useEffect(() => {
    if (templateData && !templateLoaded) {
      setTerritory(templateData as unknown as TerritoryData)
      setTemplateLoaded(true)
    }
  }, [templateData, templateLoaded])

  // Invalidar status de ingestão quando streaming terminar
  useEffect(() => {
    if (!ingest.isStreaming) {
      qc.invalidateQueries({ queryKey: ['ingest-status', id] })
    }
  }, [ingest.isStreaming, id, qc])

  // Cache-busting: atualiza quando status muda para 'generated'
  const [previewTs, setPreviewTs] = useState(() => Date.now())
  const prevStatus = useRef<string | undefined>(undefined)
  useEffect(() => {
    if (project?.status === 'generated' && prevStatus.current !== 'generated') {
      setPreviewTs(Date.now())
    }
    prevStatus.current = project?.status
  }, [project?.status])

  if (isLoading) return <Box p="6"><Text>Carregando…</Text></Box>
  if (error) return <Box p="6"><Text color="red">{(error as Error).message}</Text></Box>
  if (!project) return null

  const startEdit = () => {
    setDraft({ name: project.name, period_start: project.period_start, period_end: project.period_end })
    setEditing(true)
  }
  const save = async () => {
    await update.mutateAsync({
      name: draft.name,
      period_start: Number(draft.period_start),
      period_end: Number(draft.period_end),
    })
    setEditing(false)
  }

  const isGenerated = project.status === 'generated' || project.status === 'exported'
  const hasError = project.status.startsWith('error')

  return (
    <Box p="6">
      <Flex justify="between" align="center" mb="4">
        <Heading>{project.name}</Heading>
        <Link to="/projects"><Button variant="soft">← Todos os projetos</Button></Link>
      </Flex>

      {/* Barra de progresso */}
      <Card mb="4">
        <Flex gap="4" align="center" wrap="wrap">
          {[
            { step: '1. Ingerir', done: ['ingested', 'generating', 'generated', 'exported'].includes(project.status) },
            { step: '2. Gerar', done: isGenerated },
            { step: '3. Exportar', done: project.status === 'exported' },
          ].map(({ step, done }) => (
            <Flex key={step} align="center" gap="1">
              <Box style={{ width: 10, height: 10, borderRadius: '50%', background: done ? 'var(--green-9)' : 'var(--gray-5)' }} />
              <Text size="2" weight={done ? 'bold' : 'regular'} color={done ? undefined : 'gray'}>{step}</Text>
            </Flex>
          ))}
          <Text size="2" color={hasError ? 'red' : 'gray'} ml="auto">
            {STATUS_LABEL[project.status] ?? project.status}
          </Text>
        </Flex>
      </Card>

      {/* Canvas Viewer — two-region layout: canvas area + inspector sidebar placeholder.
          GAP-05 (02-05): height is viewport-relative so the Stage fills the central
          column on any browser size. Pre-canvas block measures ~170-200px
          (Box p="6" + Flex header mb="4" + progress Card mb="4"). calc(100vh - 220px)
          leaves a 20-50px margin; minHeight guards short viewports. Tune here if the
          canvas feels cramped. */}
      {isGenerated && (
        <Flex mb="4" style={{ height: 'calc(100vh - 220px)', minHeight: '500px', borderRadius: 8, overflow: 'hidden' }}>
          <Box
            className="canvas-region"
            style={{ flex: 1, background: '#1a1a2e', overflow: 'hidden', position: 'relative' }}
          >
            <CanvasViewer projectId={project.id} cacheVersion={project.updated_at} />
            <LegendCard />
          </Box>
          <Box
            className="inspector-sidebar"
            style={{ width: 340, borderLeft: '1px solid var(--gray-4)', padding: 16, overflowY: 'auto' }}
          >
            <InspectorSidebarWrapper projectId={project.id} project={project} />
          </Box>
        </Flex>
      )}

      {/* Preview — destaque quando disponível */}
      {isGenerated && (
        <Card mb="4" style={{ border: '2px solid var(--green-6)', background: 'var(--green-1)' }}>
          <Flex justify="between" align="center" mb="3">
            <Heading size="3" style={{ color: 'var(--green-11)' }}>Mapa gerado</Heading>
            <Button variant="soft" color="green" onClick={() => exportZip.mutate()}
              disabled={exportZip.isPending}>
              {exportZip.isPending ? 'Preparando ZIP…' : '3. Exportar ZIP (Unity)'}
            </Button>
          </Flex>
          <Flex gap="3" wrap="wrap">
            {[
              { file: 'territories.png', label: 'Territórios' },
              { file: 'borders.png',     label: 'Lookup map (Unity)' },
              { file: 'terrain.png',     label: 'Máscara de terreno' },
            ].map(({ file, label }) => (
              <Box key={file}>
                <Text size="1" weight="medium" as="p" mb="1">{label}</Text>
                <img
                  src={`/api/projects/${project.id}/preview/${file}?t=${previewTs}`}
                  alt={label}
                  style={{ display: 'block', maxWidth: 320, border: '1px solid var(--green-7)', borderRadius: 6 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.opacity = '0.3' }}
                />
              </Box>
            ))}
          </Flex>
          {exportZip.error && <Text color="red" size="2" mt="2">Erro na exportação: {(exportZip.error as Error).message}</Text>}
        </Card>
      )}

      {/* Info do projeto */}
      <Card mb="4">
        <Flex direction="column" gap="2">
          <Text><strong>País:</strong> {project.country_qid} &nbsp;|&nbsp; <strong>Período:</strong> {project.period_start}–{project.period_end} AD</Text>
          {project.bbox_lon_min != null && (
            <Text size="2" color="gray">
              Área: lon [{project.bbox_lon_min}, {project.bbox_lon_max}] · lat [{project.bbox_lat_min}, {project.bbox_lat_max}]
            </Text>
          )}
          <Text size="2" color="gray">ID: {project.id}</Text>
          {!editing && <Button variant="soft" style={{ width: 'fit-content' }} onClick={startEdit}>Editar</Button>}
        </Flex>
      </Card>

      {editing && (
        <Card mb="4">
          <Heading size="3" mb="2">Editar projeto</Heading>
          <Flex direction="column" gap="2">
            <TextField.Root value={draft.name} onChange={(e) => setDraft((s) => ({ ...s, name: e.target.value }))} />
            <Flex gap="2">
              <TextField.Root type="number" value={draft.period_start}
                onChange={(e) => setDraft((s) => ({ ...s, period_start: Number(e.target.value) }))} />
              <TextField.Root type="number" value={draft.period_end}
                onChange={(e) => setDraft((s) => ({ ...s, period_end: Number(e.target.value) }))} />
            </Flex>
            <Flex gap="2">
              <Button onClick={save} disabled={update.isPending}>{update.isPending ? 'Salvando…' : 'Salvar'}</Button>
              <Button variant="soft" onClick={() => setEditing(false)}>Cancelar</Button>
            </Flex>
          </Flex>
        </Card>
      )}

      {/* Pipeline + Editor */}
      <Card>
        <Tabs.Root defaultValue="pipeline">
          <Tabs.List>
            <Tabs.Trigger value="pipeline">Pipeline</Tabs.Trigger>
            <Tabs.Trigger value="territory">Estrutura política</Tabs.Trigger>
          </Tabs.List>

          {/* ── Aba Pipeline ── */}
          <Tabs.Content value="pipeline">
            <Box pt="3">
              <Text size="2" color="gray" as="p" mb="3">
                Execute em ordem: <strong>1. Ingerir OSM</strong> → <strong>2. Gerar mapa</strong> → <strong>3. Exportar ZIP</strong>.
              </Text>

              {/* Status dos dados guardados */}
              {ingestStatus.data && (
                ingestStatus.data.has_data ? (
                  <Card mb="3" style={{
                    background: ingestStatus.data.has_polygons ? 'var(--green-1)' : 'var(--amber-1)',
                    border: `1px solid ${ingestStatus.data.has_polygons ? 'var(--green-6)' : 'var(--amber-6)'}`,
                  }}>
                    <Flex align="center" gap="2">
                      <Text style={{ fontSize: 18 }}>{ingestStatus.data.has_polygons ? '✅' : '⚠️'}</Text>
                      <Box style={{ flex: 1 }}>
                        <Text size="2" weight="medium">
                          {ingestStatus.data.has_polygons
                            ? `Dados OSM guardados — ${ingestStatus.data.polygon_count} polígonos prontos para gerar`
                            : `Dados Wikidata guardados — ${ingestStatus.data.point_count} pontos (sem polígonos)`}
                        </Text>
                        <Text size="1" color="gray" as="p">
                          {(ingestStatus.data.size_bytes / 1024).toFixed(0)} KB ·{' '}
                          {ingestStatus.data.last_modified
                            ? `Ingerido em ${new Date(ingestStatus.data.last_modified).toLocaleString('pt-BR')}`
                            : ''}
                          {!ingestStatus.data.has_polygons && ' — use OSM para gerar mapas visíveis'}
                        </Text>
                      </Box>
                      <Text size="1" color="gray">Não precisa reingerir</Text>
                    </Flex>
                  </Card>
                ) : (
                  <Callout.Root size="1" mb="3">
                    <Callout.Text>
                      <strong>Sem dados geográficos.</strong> Use <strong>"Ingerir via OSM"</strong> para descarregar polígonos reais.
                      Com a bounding box definida, a ingestão é muito mais rápida (~1-2 min).
                    </Callout.Text>
                  </Callout.Root>
                )
              )}

              {/* Aviso de polígonos insuficientes ANTES do botão Gerar */}
              {ingestStatus.data?.has_data && !ingestStatus.data?.has_polygons && (
                <Callout.Root size="1" color="amber" mb="2">
                  <Callout.Text>
                    <strong>Dados insuficientes para gerar.</strong> Os dados actuais são apenas pontos (Wikidata) — sem polígonos de fronteira.
                    O mapa ficaria todo azul. Use primeiro <strong>"1b. OSM com polígonos"</strong>.
                  </Callout.Text>
                </Callout.Root>
              )}

              <Flex gap="2" mb="3" wrap="wrap">
                <Button variant="soft" onClick={() => ingest.start('wikidata')} disabled={ingest.isStreaming}>
                  {ingest.isStreaming ? 'Ingerindo…' : '1a. Wikidata (só pontos)'}
                </Button>
                <Button onClick={() => ingest.start('osm')} disabled={ingest.isStreaming}>
                  {ingest.isStreaming ? 'Ingerindo…' : '1b. OSM com polígonos (recomendado)'}
                </Button>
                <Button
                  variant="soft"
                  color="blue"
                  onClick={() => {
                    renderModern.mutate(undefined, {
                      onSuccess: () => setModernTs(Date.now()),
                    })
                  }}
                  disabled={
                    renderModern.isPending ||
                    !ingestStatus.data?.has_polygons
                  }
                  title={
                    !ingestStatus.data?.has_polygons
                      ? 'Precisa de polígonos OSM — ingerir via OSM primeiro'
                      : 'Renderiza o mapa moderno (validação visual dos dados)'
                  }
                >
                  {renderModern.isPending ? 'Renderizando…' : '1c. Mapa moderno (validar dados)'}
                </Button>
                <Button
                  onClick={() => generate.mutate(territory as unknown as Record<string, unknown>)}
                  disabled={
                    project.status === 'generating' ||
                    generate.isPending ||
                    (ingestStatus.data?.has_data === true && !ingestStatus.data?.has_polygons)
                  }
                  color={ingestStatus.data?.has_data && !ingestStatus.data?.has_polygons ? 'gray' : undefined}
                  title={
                    ingestStatus.data?.has_data && !ingestStatus.data?.has_polygons
                      ? 'Ingerido apenas pontos (Wikidata) — use OSM primeiro'
                      : 'Gerar mapa com a estrutura de territórios definida'
                  }
                >
                  {project.status === 'generating' ? 'Gerando…' : '2. Gerar mapa'}
                </Button>
                {!isGenerated && (
                  <Button variant="soft" color="green" disabled>3. Exportar ZIP</Button>
                )}
              </Flex>

              {ingest.error && <Text color="red" size="2" mb="2">Erro: {ingest.error.message}</Text>}
              {generate.error && <Text color="red" size="2" mb="2">Erro: {(generate.error as Error).message}</Text>}
              {renderModern.error && (
                <Text color="red" size="2" mb="2">
                  Erro ao renderizar mapa moderno: {(renderModern.error as Error).message}
                </Text>
              )}
              {project.status === 'error_generating' && Boolean(project.generator_config?.last_error) && (
                <Text color="red" size="2" mb="2">Último erro: {String(project.generator_config?.last_error ?? '')}</Text>
              )}

              {/* Pré-visualização do mapa moderno (validação geográfica) */}
              {modernTs > 0 && (
                <Card mb="3" style={{ background: 'var(--blue-1)', border: '1px solid var(--blue-6)' }}>
                  <Heading size="2" mb="1" style={{ color: 'var(--blue-11)' }}>
                    Mapa moderno — validação geográfica
                  </Heading>
                  <Text size="1" color="gray" as="p" mb="2">
                    Cada cor representa uma província/município da ingestão OSM.
                    Use esta imagem para confirmar que o bounding box e os dados estão corretos
                    antes de gerar o mapa medieval.
                  </Text>
                  <img
                    src={`/api/projects/${project.id}/preview/modern_map.png?t=${modernTs}`}
                    alt="Mapa moderno"
                    style={{
                      display: 'block',
                      width: '100%',
                      maxWidth: 900,
                      border: '1px solid var(--blue-7)',
                      borderRadius: 6,
                    }}
                  />
                </Card>
              )}

              <Text size="2" weight="medium" as="p" mb="1">Log da ingestão:</Text>
              <pre id="ingest-log" style={{
                padding: 8, background: '#f5f5f5', borderRadius: 4,
                maxHeight: 200, overflow: 'auto', fontSize: 11, whiteSpace: 'pre-wrap', minHeight: 40,
              }}>
                {ingest.lines.length > 0
                  ? ingest.lines.join('')
                  : <span style={{ color: '#999' }}>Nenhuma ingestão iniciada.</span>}
              </pre>
            </Box>
          </Tabs.Content>

          {/* ── Aba Estrutura política ── */}
          <Tabs.Content value="territory">
            <Box pt="3">
              <Callout.Root size="1" mb="3">
                <Callout.Text>
                  <strong>O que é isto?</strong> Define a hierarquia política do <em>jogo</em> — não vem da ingestão.
                  A ingestão baixa fronteiras geográficas reais; aqui define-se como o Game Designer divide
                  o território em reinos, ducados e territórios jogáveis.
                  O gerador usa as coordenadas de cada território para atribuir municípios via Voronoi.
                </Callout.Text>
              </Callout.Root>
              <TerritoryEditor value={territory} onChange={setTerritory} />
            </Box>
          </Tabs.Content>
        </Tabs.Root>
      </Card>
    </Box>
  )
}

/**
 * Wrapper that builds ProjectionConfig from the loaded metadata + project bbox
 * and hands metadata/territories/project to InspectorSidebar. Uses the same
 * data source as CanvasViewer (/preview/territory_metadata.json); TanStack
 * Query dedups the fetches.
 *
 * Advisor note: the wrapper derives its projection from metaQ.data.bounds (the
 * generator's actual bounds) rather than project.bbox_* (ingest bbox) so it
 * stays consistent with CanvasViewer even when those values differ.
 */
function InspectorSidebarWrapper({
  projectId,
  project,
}: {
  projectId: string
  project: Project
}) {
  const artifacts0 = useCanvasArtifacts(projectId, null)
  const metaQ = artifacts0[4]

  const projection = useMemo(() => {
    if (!metaQ.data) return null
    const [mapW, mapH] = metaQ.data.map_size
    const { bounds } = metaQ.data
    return buildProjectionConfig(
      {
        lonMin: bounds.lon_min,
        lonMax: bounds.lon_max,
        latMin: bounds.lat_min,
        latMax: bounds.lat_max,
      },
      mapW,
      mapH,
    )
  }, [metaQ.data])

  const artifacts = useCanvasArtifacts(projectId, projection)
  const territoriesQ = artifacts[0]

  if (metaQ.isPending || territoriesQ.isPending) {
    return <Text size="2" color="gray">Loading…</Text>
  }
  if (!metaQ.data || !territoriesQ.data) {
    return <Text size="2" color="gray">No inspector data.</Text>
  }

  return (
    <InspectorSidebar
      metadata={metaQ.data}
      territories={territoriesQ.data}
      project={{
        name: project.name,
        country_qid: project.country_qid,
        period_start: project.period_start,
        period_end: project.period_end,
      }}
    />
  )
}
