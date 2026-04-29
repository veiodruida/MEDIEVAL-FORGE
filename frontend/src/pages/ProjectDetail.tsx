import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Box, Button, Card, Callout, Flex, Heading, Text, TextField, Tooltip } from '@radix-ui/themes'
import { useQueryClient } from '@tanstack/react-query'
import { useProject, useUpdateProject, useIngestStream, useGenerate, useExport, useIngestStatus, useTerritoryTemplate, useRenderModern, type Project } from '../api/client'
import { type TerritoryData } from './TerritoryEditor'
import { CanvasViewer } from '../components/canvas/CanvasViewer'
import { EditToolbar } from '../components/canvas/EditToolbar'
import { InspectorSidebar } from '../components/canvas/InspectorSidebar'
import { LegendCard } from '../components/canvas/LegendCard'
import { useCanvasArtifacts } from '../hooks/useCanvasArtifacts'
import { buildProjectionConfig } from '../lib/projection'
import { ResearchDialog } from '../components/research/ResearchDialog'
import { useResearchStore } from '../stores/useResearchStore'
import { useEditorStore } from '../stores/useEditorStore'
import { useValidationStore } from '../stores/useValidationStore'
import { SaveStatusIndicator } from '../components/canvas/SaveStatusIndicator'
import { SettingsPanel } from '../components/canvas/SettingsPanel'
import { useBeforeUnloadGuard } from '../hooks/useBeforeUnloadGuard'
import { ErrorBoundary } from 'react-error-boundary'
import { usePipelineStore } from '../stores/usePipelineStore'
import { Stepper } from '../components/pipeline/Stepper'
import { StepCard } from '../components/pipeline/StepCard'
import { ProviderEffortPicker } from '../components/pipeline/ProviderEffortPicker'
import { BaronyGranularitySlider } from '../components/ingest/BaronyGranularitySlider'
import { AssignmentEditor } from '../components/research/AssignmentEditor'
import { CodexViewer } from '../components/codex/CodexViewer'
import { TerrainDataSection } from '../components/pipeline/TerrainDataSection'

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
  const openResearchDialog = useResearchStore((s) => s.openDialog)
  const manualResult = useResearchStore((s) => s.manualResult)

  // Pipeline store
  const {
    currentStep,
    steps,
    setCurrentStep,
    setStepStatus,
    setStepProvider,
    setBaroniesGranularity,
  } = usePipelineStore()

  // AssignmentEditor dialog state
  const [assignmentEditorOpen, setAssignmentEditorOpen] = useState(false)

  // Detectar template de território baseado no país do projeto
  const iberiaQids = new Set(['Q29', 'Q45'])
  const templateRegion = project && iberiaQids.has(project.country_qid) ? 'iberia' : null
  const { data: templateData } = useTerritoryTemplate(templateRegion)

  const editMode = useEditorStore((s) => s.editMode)
  const errorCount = useValidationStore((s) => s.issues.filter((i) => i.severity === 'error').length)

  // D-07: browser navigation guard when explicit mode has unsaved changes
  useBeforeUnloadGuard()

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

  // Pipeline store sync: OSM ingest done
  useEffect(() => {
    if (!ingest.isStreaming && ingestStatus.data?.has_polygons) {
      setStepStatus('osm', 'done')
    }
  }, [ingest.isStreaming, ingestStatus.data?.has_polygons, setStepStatus])

  // Pipeline store sync: Map generated
  useEffect(() => {
    if (project?.status === 'generated' || project?.status === 'exported') {
      setStepStatus('map', 'done')
    }
  }, [project?.status, setStepStatus])

  if (isLoading) return <Box p="6"><Text>Carregando…</Text></Box>
  if (error) return <Box p="6"><Text color="red">{(error as Error).message}</Text></Box>
  if (!project) return null

  // TypeScript doesn't narrow `project` inside nested function bodies defined
  // after the guard above. Capture as const so renderStepContent can use it safely.
  const proj = project

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

  // Build statuses object for Stepper
  const stepperStatuses = {
    osm: steps.osm.status,
    baronies: steps.baronies.status,
    research: steps.research.status,
    map: steps.map.status,
    codex: steps.codex.status,
  }

  // Render active step content inside StepCard
  function renderStepContent() {
    switch (currentStep) {
      case 1:
        return (
          <StepCard
            title="1. Ingerir OSM"
            description="Descarrega polígonos geográficos reais via OpenStreetMap. Necessário antes de gerar o mapa medieval."
            footer={
              <>
                <Button onClick={() => ingest.start('osm')} disabled={ingest.isStreaming}>
                  {ingest.isStreaming ? 'Ingerindo…' : '1. OSM com polígonos (recomendado)'}
                </Button>
                {ingest.isStreaming && (
                  <Button color="red" variant="soft" onClick={() => ingest.stop()}>
                    Parar ingestão
                  </Button>
                )}
                <Button
                  variant="soft"
                  color="blue"
                  onClick={() => {
                    renderModern.mutate(undefined, {
                      onSuccess: () => setModernTs(Date.now()),
                    })
                  }}
                  disabled={renderModern.isPending || !ingestStatus.data?.has_polygons}
                  title={
                    !ingestStatus.data?.has_polygons
                      ? 'Precisa de polígonos OSM — ingerir via OSM primeiro'
                      : 'Renderiza o mapa moderno (validação visual dos dados)'
                  }
                >
                  {renderModern.isPending ? 'Renderizando…' : '2. Mapa moderno (validar dados)'}
                </Button>
                <Box mt="2">
                  <details>
                    <summary style={{ cursor: 'pointer', userSelect: 'none', fontSize: '0.875rem', color: 'var(--gray-11)' }}>
                      Avançado
                    </summary>
                    <Box mt="2">
                      <Button variant="soft" onClick={() => ingest.start('wikidata')} disabled={ingest.isStreaming}>
                        {ingest.isStreaming ? 'Ingerindo…' : 'Wikidata (só pontos — legado)'}
                      </Button>
                      <Text size="1" color="gray" as="p" mt="1">
                        Apenas pontos. Não gera polígonos. Use só se OSM falhar para a região.
                      </Text>
                    </Box>
                  </details>
                </Box>
              </>
            }
          >
            <>
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

              {/* Aviso de polígonos insuficientes */}
              {ingestStatus.data?.has_data && !ingestStatus.data?.has_polygons && (
                <Callout.Root size="1" color="amber" mb="2">
                  <Callout.Text>
                    <strong>Dados insuficientes para gerar.</strong> Os dados actuais são apenas pontos (Wikidata) — sem polígonos de fronteira.
                    O mapa ficaria todo azul. Use primeiro <strong>"1b. OSM com polígonos"</strong>.
                  </Callout.Text>
                </Callout.Root>
              )}

              {ingest.error && <Text color="red" size="2" mb="2">Erro: {ingest.error.message}</Text>}
              {renderModern.error && (
                <Text color="red" size="2" mb="2">
                  Erro ao renderizar mapa moderno: {(renderModern.error as Error).message}
                </Text>
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
                    src={`/api/projects/${proj.id}/preview/modern_map.png?t=${modernTs}`}
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
            </>
          </StepCard>
        )

      case 2:
        return (
          <StepCard
            title="2. Gerar Baronies"
            description="Define a granularidade das baronies — sub-unidades geográficas usadas na pesquisa histórica."
            footer={
              <Button
                onClick={() => {
                  // TODO: wire Gerar Baronies button to /baronies endpoint when available
                  // eslint-disable-next-line no-console
                  console.warn('Gerar Baronies: backend wiring not in scope for etapa-11')
                  setStepStatus('baronies', 'done')
                  setCurrentStep(3)
                }}
              >
                Gerar Baronies
              </Button>
            }
          >
            <BaronyGranularitySlider
              value={steps.baronies.granularity as (50 | 250 | 1000 | 'all')}
              onChange={(count) => setBaroniesGranularity(count)}
            />
          </StepCard>
        )

      case 3:
        return (
          <StepCard
            title="3. Pesquisa Histórica"
            description="Usa LLM para pesquisar dados históricos do período selecionado e atribuir baronies a condados medievais."
            footer={
              <Button
                color="blue"
                onClick={() => {
                  setStepStatus('research', 'active')
                  openResearchDialog({
                    country: proj.country_qid,
                    periodStart: proj.period_start,
                    periodEnd: proj.period_end,
                  })
                }}
                title="Pesquisa histórica com LLM — necessária antes de gerar o mapa"
              >
                Pesquisa histórica
              </Button>
            }
          >
            <>
              <ProviderEffortPicker
                providerId={steps.research.providerId ?? 'claude'}
                effort={steps.research.effort ?? 'medium'}
                onProviderChange={(id) => setStepProvider('research', id, steps.research.effort ?? 'medium')}
                onEffortChange={(e) => setStepProvider('research', steps.research.providerId ?? 'claude', e)}
              />
              {manualResult && (
                <Box mt="3">
                  <Button
                    variant="soft"
                    onClick={() => setAssignmentEditorOpen(true)}
                  >
                    Editar assignments
                  </Button>
                  <AssignmentEditor
                    open={assignmentEditorOpen}
                    onOpenChange={setAssignmentEditorOpen}
                    projectId={proj.id}
                    researchResult={manualResult as unknown as Parameters<typeof AssignmentEditor>[0]['researchResult']}
                  />
                </Box>
              )}
            </>
          </StepCard>
        )

      case 4:
        return (
          <StepCard
            title="4. Gerar Mapa"
            description="Gera o mapa medieval com Voronoi baseado nas baronies e dados históricos pesquisados."
            footer={
              <Button
                onClick={() => generate.mutate(territory as unknown as Record<string, unknown>)}
                disabled={
                  proj.status === 'generating' ||
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
                {proj.status === 'generating' ? 'Gerando…' : 'Gerar mapa'}
              </Button>
            }
          >
            <>
              {generate.error && (() => {
                const msg = (generate.error as Error).message
                const isResearchMissing = msg.includes('No cached research found')
                if (isResearchMissing) {
                  return (
                    <Callout.Root color="amber" size="2" mb="2">
                      <Callout.Text>
                        <strong>Pesquisa histórica em falta.</strong>{' '}
                        Execute <strong>"Pesquisa histórica"</strong> (etapa 3) antes de gerar o mapa.
                      </Callout.Text>
                    </Callout.Root>
                  )
                }
                return <Text color="red" size="2" mb="2">Erro: {msg}</Text>
              })()}
              {proj.status === 'error_generating' && Boolean(proj.generator_config?.last_error) && (
                <Text color="red" size="2" mb="2">Último erro: {String(proj.generator_config?.last_error ?? '')}</Text>
              )}
              {isGenerated && (
                <Text size="2" color="green">Mapa gerado. Veja o preview abaixo.</Text>
              )}
            </>
          </StepCard>
        )

      case 5:
        return (
          <StepCard
            title="5. Codex Histórico"
            description="Gera o codex medieval com categorias históricas usando LLM. O codex documenta o período histórico do mapa."
          >
            <>
              <ProviderEffortPicker
                providerId={steps.codex.providerId ?? 'claude'}
                effort={steps.codex.effort ?? 'medium'}
                onProviderChange={(id) => setStepProvider('codex', id, steps.codex.effort ?? 'medium')}
                onEffortChange={(e) => setStepProvider('codex', steps.codex.providerId ?? 'claude', e)}
              />
              <Box mt="3">
                <CodexViewer projectId={proj.id} />
              </Box>
            </>
          </StepCard>
        )

      default:
        return null
    }
  }

  return (
    <Box p="6">
      <Flex justify="between" align="center" mb="4">
        <Heading>{project.name}</Heading>
        <Flex gap="3" align="center">
          <SaveStatusIndicator />
          <SettingsPanel />
          <Link to="/projects"><Button variant="soft">← Todos os projetos</Button></Link>
        </Flex>
      </Flex>

      {/* Barra de progresso (status do projeto) */}
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
        <Box mb="4" style={{ borderRadius: 8, overflow: 'hidden', border: '1px solid var(--gray-4)' }}>
          <EditToolbar />
          <Flex style={{ height: 'calc(100vh - 260px)', minHeight: '500px' }}>
          <Box
            className="canvas-region"
            style={{ flex: 1, background: '#1a1a2e', overflow: 'hidden', position: 'relative' }}
          >
            <div style={{
              position: 'relative',
              width: '100%',
              height: '100%',
              outline: editMode ? '2px solid var(--accent-9)' : 'none',
              outlineOffset: editMode ? '-2px' : '0',
            }}>
              <CanvasViewer projectId={project.id} cacheVersion={project.updated_at} />
            </div>
            <LegendCard />
          </Box>
          <Box
            className="inspector-sidebar"
            style={{ width: 340, borderLeft: '1px solid var(--gray-4)', padding: 16, overflowY: 'auto' }}
          >
            <ErrorBoundary
              onError={(err) => {
                // T-02-05-02: log full stack to console for developer triage.
                // DO NOT render stack/message into the fallback UI (security:
                // avoid leaking internals to end users).
                // eslint-disable-next-line no-console
                console.error('[InspectorSidebar] boundary caught:', err)
              }}
              fallback={
                <Callout.Root color="red" size="1">
                  <Callout.Text>
                    Sidebar failed to load — check console.
                  </Callout.Text>
                </Callout.Root>
              }
            >
              <InspectorSidebarWrapper projectId={project.id} project={project} />
            </ErrorBoundary>
          </Box>
          </Flex>
        </Box>
      )}

      {/* Preview — destaque quando disponível */}
      {isGenerated && (
        <Card mb="4" style={{ border: '2px solid var(--green-6)', background: 'var(--green-1)' }}>
          <Flex justify="between" align="center" mb="3">
            <Heading size="3" style={{ color: 'var(--green-11)' }}>Mapa gerado</Heading>
            <Tooltip content={errorCount > 0 ? 'Corrija os erros de validação primeiro' : 'Exportar pacote Unity'}>
              <span>
                <Button variant="soft" color="green" onClick={() => exportZip.mutate()}
                  disabled={exportZip.isPending || errorCount > 0}>
                  {exportZip.isPending ? 'Preparando ZIP…' : '3. Exportar ZIP (Unity)'}
                </Button>
              </span>
            </Tooltip>
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

      {/* Terrain Data — Phase 2.1 terrain ingestion section (D-24: above Phase 1 Stepper) */}
      {id && <TerrainDataSection projectId={id} />}

      {/* Pipeline — Stepper + StepCard (replaces legacy Pipeline/Estrutura política Tabs block) */}
      <Stepper
        currentStep={currentStep}
        statuses={stepperStatuses}
        onStepClick={setCurrentStep}
      />
      {renderStepContent()}

      {/* ResearchDialog — mounted once outside pipeline; reads open state from useResearchStore */}
      <ResearchDialog projectId={project.id} />
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
  // Cache-bust token MUST match what CanvasViewer passes (project.updated_at)
  // so both components share the SAME TanStack Query cache entries. Without
  // this, InspectorSidebarWrapper ends up with a separate stale cache entry
  // (key ending in `undefined`) and renders pre-regeneration metadata —
  // e.g. a click on a newly-added condado like `aveiro` can't find it in
  // the wrapper's stale metadata.condados, so InspectorSidebar falls back
  // to project-overview state ("desconhecido / no details").
  const cacheVersion = project.updated_at
  const artifacts0 = useCanvasArtifacts(projectId, null, cacheVersion)
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

  const artifacts = useCanvasArtifacts(projectId, projection, cacheVersion)
  const territoriesQ = artifacts[0]

  if (metaQ.isPending || territoriesQ.isPending) {
    return <Text size="2" color="gray">Loading…</Text>
  }
  if (!artifacts[4].data || !territoriesQ.data) {
    return <Text size="2" color="gray">No inspector data.</Text>
  }

  return (
    <InspectorSidebar
      metadata={artifacts[4].data}
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
