/**
 * Phase 07 Plan 09a Task 2 — ResearchDialog (Radix Dialog.Root).
 *
 * Owns the 4-field form (País, Período, Provedor LLM, Modelo) plus the
 * paste-API-key conditional row, the cache-hit microcopy, the SSE-driven
 * ResearchProgress sub-component, and the CTA state machine
 * (Idle → Submitting → Streaming → Success/Error). UI-SPEC §Surface 1.
 *
 * Plan 09a OWNS the component; Plan 09b MOUNTS it inside InspectorSidebar.
 * This file therefore receives `open` + `onOpenChange` as controlled props
 * — no internal `<Dialog.Trigger>`, no module-level state.
 *
 * REVIEWS soft codex — CLI piggyback microcopy uses
 * "Tentando token do Claude CLI…" (with an ellipsis character) followed by
 * the explicit fallback hint. The old auto-flag-detected copy is removed.
 *
 * Auto-close behavior (CONTEXT D-09): on terminal success, the dialog
 * stays mounted for 1.2s to render the success affordance, then closes
 * via `onOpenChange(false)`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Box,
  Button,
  Checkbox,
  Dialog,
  Flex,
  Text,
  TextField,
} from '@radix-ui/themes'
import { useProviders } from '../../api/useProviders'
import { useProject } from '../../api/useProject'
import { useResearchOverlay } from '../../api/useResearchOverlay'
import { useResearchStream } from '../../hooks/useResearchStream'
import { ProviderSelector } from './ProviderSelector'
import { ResearchProgress } from './ResearchProgress'

export interface ResearchDialogProps {
  open: boolean
  onOpenChange: (next: boolean) => void
  projectId: string
  regionDisplayName: string
  countryQid: string
  condadoIds: string[]
  /** When true, pre-checks the "Forçar nova pesquisa" checkbox on open. */
  initialForceRefresh?: boolean
}

function pickDefaultProvider(providers: { provider_id: string; healthy: boolean }[] | undefined): string {
  if (!providers || providers.length === 0) return ''
  const claude = providers.find((p) => p.provider_id === 'claude' && p.healthy)
  if (claude) return claude.provider_id
  const firstHealthy = providers.find((p) => p.healthy)
  if (firstHealthy) return firstHealthy.provider_id
  return providers[0]!.provider_id
}

export function ResearchDialog({
  open,
  onOpenChange,
  projectId,
  regionDisplayName,
  countryQid,
  condadoIds,
  initialForceRefresh = false,
}: ResearchDialogProps) {
  // Provider list + overlay state. Both queries are enabled only while the
  // dialog is open so we do not poll providers from a background mount.
  const { data: providers, isLoading: providersLoading } = useProviders(open)
  const overlay = useResearchOverlay(open ? projectId : undefined)

  const { data: project } = useProject(projectId)
  const [periodStart, setPeriodStart] = useState<number | null>(null)
  const [periodEnd, setPeriodEnd] = useState<number | null>(null)
  const [hasSeeded, setHasSeeded] = useState(false)
  const [provider, setProvider] = useState<string>('')
  const [model, setModel] = useState<string>('')
  const [forceRefresh, setForceRefresh] = useState(initialForceRefresh)
  const [apiKey, setApiKey] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const stream = useResearchStream()
  const streamPhase = stream.state.phase

  // Default provider once the /providers query lands.
  useEffect(() => {
    if (!open) return
    if (provider !== '') return
    setProvider(pickDefaultProvider(providers))
  }, [open, provider, providers])

  // Seed period inputs from useProject once both the dialog is open AND
  // useProject has resolved. The hasSeeded gate prevents overwriting user
  // edits on re-renders. Resets on close so the next open re-seeds fresh.
  // review-fix #2 (Gemini HIGH): wasOpenRef raced when useProject was still
  // loading at the open-transition tick — hasSeeded + project truthy guard fixes that.
  useEffect(() => {
    if (open && project && !hasSeeded) {
      setPeriodStart(project.period_start ?? null)
      setPeriodEnd(project.period_end ?? null)
      setHasSeeded(true)
    }
    if (!open) {
      setHasSeeded(false) // arm for the next open
    }
  }, [open, project, hasSeeded])

  // Auto-close 1.2s after terminal success (UI-SPEC §Interaction Contract).
  const autoCloseRef = useRef<number | null>(null)
  useEffect(() => {
    if (streamPhase !== 'succeeded') return
    autoCloseRef.current = window.setTimeout(() => { onOpenChange(false) }, 1200)
    return () => {
      if (autoCloseRef.current !== null) {
        window.clearTimeout(autoCloseRef.current)
        autoCloseRef.current = null
      }
    }
  }, [streamPhase, onOpenChange])

  const isStreaming = streamPhase === 'running' || streamPhase === 'starting'

  const canSubmit = useMemo(() => {
    if (submitting || isStreaming) return false
    const periodValid =
      typeof periodStart === 'number' &&
      typeof periodEnd === 'number' &&
      periodStart >= 1 && periodStart <= 2100 &&
      periodEnd >= 1 && periodEnd <= 2100 &&
      periodStart <= periodEnd
    if (!periodValid) return false
    if (!provider) return false
    return true
  }, [submitting, isStreaming, periodStart, periodEnd, provider])

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!canSubmit) return
      setSubmitError(null)
      setSubmitting(true)
      try {
        const res = await fetch('/api/v3/research/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: projectId,
            provider,
            model,
            country_qid: countryQid,
            period_start: periodStart,
            period_end: periodEnd,
            condado_ids: condadoIds,
            force_refresh: forceRefresh,
          }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `start failed: ${res.status}`)
        }
        const body = (await res.json()) as { run_id: string }
        stream.subscribe(body.run_id)
      } catch (err) {
        setSubmitError(
          err instanceof Error
            ? err.message
            : 'Erro inesperado ao iniciar a pesquisa.',
        )
      } finally {
        setSubmitting(false)
      }
    },
    [
      canSubmit,
      projectId,
      provider,
      model,
      countryQid,
      periodStart,
      periodEnd,
      condadoIds,
      forceRefresh,
      stream,
    ],
  )

  const handleCancelStream = useCallback(() => {
    // Fire-and-forget /stop, then close the EventSource so the AbortError
    // branch in useResearchStream maps to {phase:'failed', error_code:'aborted'}.
    fetch(`/api/v3/research/stop/${projectId}`, { method: 'POST' }).catch(() => {
      // best-effort
    })
    stream.close()
  }, [projectId, stream])

  const handleDialogChange = useCallback(
    (next: boolean) => {
      if (!next) {
        // Close → reset transient state, but keep last-typed values so the
        // user does not lose typed Período on accidental ESC.
        stream.close()
        setSubmitError(null)
      }
      onOpenChange(next)
    },
    [onOpenChange, stream],
  )

  const cacheHit =
    overlay.data?.exists && !forceRefresh && streamPhase === 'idle'

  return (
    <>
    <Dialog.Root open={open} onOpenChange={handleDialogChange}>
      <Dialog.Content
        data-testid="research-dialog"
        style={{ maxWidth: 560 }}
      >
        <Dialog.Title>Pesquisar metadados históricos</Dialog.Title>
        <Dialog.Description>
          <Text size="2" color="gray">
            Use um modelo de linguagem para preencher nomes históricos e notas
            dos condados. A geração geométrica do mapa NÃO depende desta
            pesquisa.
          </Text>
        </Dialog.Description>

        <form onSubmit={handleSubmit}>
          <Flex direction="column" gap="3" mt="4">
            {/* País — read-only, derived from the project's region. */}
            <Box>
              <Text as="label" size="2" weight="medium" htmlFor="research-country-input">
                País
              </Text>
              <Box mt="1">
                <TextField.Root
                  id="research-country-input"
                  value={`${regionDisplayName} (somente leitura — definido pelo projeto)`}
                  readOnly
                />
              </Box>
            </Box>

            {/* Período — two numeric inputs (D-01, D-02, UI-SPEC §Surface 1) */}
            <Flex direction="column" gap="1">
              <Text as="label" size="2" weight="medium">Período</Text>
              <Flex gap="2">
                <Box style={{ flex: 1 }}>
                  <Text as="label" size="2" weight="medium" htmlFor="research-period-start">Início</Text>
                  <Box mt="1">
                    <TextField.Root
                      id="research-period-start"
                      data-testid="research-period-start"
                      type="number"
                      min={1}
                      max={2100}
                      step={1}
                      inputMode="numeric"
                      placeholder="Ex.: 800"
                      value={periodStart ?? ''}
                      onChange={(e) => {
                        const v = e.target.value
                        setPeriodStart(v === '' ? null : Number(v))
                      }}
                    />
                  </Box>
                </Box>
                <Box style={{ flex: 1 }}>
                  <Text as="label" size="2" weight="medium" htmlFor="research-period-end">Fim</Text>
                  <Box mt="1">
                    <TextField.Root
                      id="research-period-end"
                      data-testid="research-period-end"
                      type="number"
                      min={1}
                      max={2100}
                      step={1}
                      inputMode="numeric"
                      placeholder="Ex.: 900"
                      value={periodEnd ?? ''}
                      onChange={(e) => {
                        const v = e.target.value
                        setPeriodEnd(v === '' ? null : Number(v))
                      }}
                    />
                  </Box>
                </Box>
              </Flex>
              <Text size="1" color="gray">Anos AD (1–2100). Início ≤ Fim.</Text>
              {periodStart !== null && periodEnd !== null && periodStart > periodEnd && (
                <Text size="1" color="red" data-testid="period-error-start-gt-end">
                  O início deve ser menor ou igual ao fim.
                </Text>
              )}
            </Flex>

            {/* Provedor LLM + Modelo + Llama.cpp controls (unified panel) */}
            <ProviderSelector
              providers={providers}
              value={provider}
              onProviderChange={setProvider}
              modelValue={model}
              onModelChange={setModel}
              isLoading={providersLoading}
            />

            {/* REVIEWS soft codex — softened CLI piggyback microcopy. */}
            {provider === 'claude' && (
              <Text size="1" color="gray">
                Tentando token do Claude CLI…{' '}
                <em>Se rejeitado, voltamos para a chave salva no DB.</em>
              </Text>
            )}

            {/* Paste-API-key — visible only for Claude when no provider key is
                configured. Type=password so it does not echo in the clear
                (T-07-09a-01). */}
            {provider === 'claude' && (
              <Box>
                <Text as="label" size="2" weight="medium" htmlFor="research-api-key">
                  Chave do Anthropic
                </Text>
                <Box mt="1">
                  <TextField.Root
                    id="research-api-key"
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-ant-..."
                  />
                </Box>
                <Text size="1" color="gray" mt="1" as="p">
                  A chave será salva localmente em ~/.medieval-forge/medieval_forge.db.
                </Text>
              </Box>
            )}

            {/* Forçar nova pesquisa */}
            <Flex align="center" gap="2">
              <Checkbox
                id="research-force-refresh"
                checked={forceRefresh}
                onCheckedChange={(v) => setForceRefresh(v === true)}
              />
              <Text as="label" size="2" htmlFor="research-force-refresh">
                Forçar nova pesquisa (ignorar cache)
              </Text>
            </Flex>

            {/* Cache-hit microcopy — UI-SPEC §Copywriting */}
            {cacheHit && (
              <Text size="2" color="green">
                Resultado em cache disponível — clique em "Iniciar pesquisa"
                para reaplicar sem nova chamada.
              </Text>
            )}

            {/* Submission error inline (NEVER a toast — per UI-SPEC). */}
            {submitError && (
              <Text size="2" color="red">
                Erro ao comunicar com {provider}: {submitError}. Verifique a
                rede e as credenciais.
              </Text>
            )}

            {/* Per-stage progress list + retry inline notice + terminal label. */}
            {(isStreaming || streamPhase === 'failed' || streamPhase === 'succeeded') && (
              <ResearchProgress state={stream.state} />
            )}

            {/* CTA row — rodapé layout (UI-SPEC §Copywriting Surface 1) */}
            <Flex gap="2" justify="end" mt="2" align="center">
              <Flex gap="2">
                {isStreaming ? (
                  <Button
                    type="button"
                    color="red"
                    variant="solid"
                    onClick={handleCancelStream}
                    data-testid="research-cancel-stream"
                  >
                    Cancelar pesquisa
                  </Button>
                ) : (
                  <>
                    <Button
                      type="button"
                      variant="soft"
                      onClick={() => handleDialogChange(false)}
                    >
                      Cancelar
                    </Button>
                    <Button
                      type="submit"
                      disabled={!canSubmit}
                      data-testid="research-submit"
                    >
                      {submitting ? 'Iniciando...' : 'Iniciar pesquisa'}
                    </Button>
                  </>
                )}
              </Flex>
            </Flex>
          </Flex>
        </form>
      </Dialog.Content>
    </Dialog.Root>
    </>
  )
}
