/**
 * Phase 07.1 Plan 08 Task 1 — AuthSetupSheet (Radix Dialog).
 *
 * SC-5 deliverable: model dropdown from useLlamacppHealth().available_models,
 * "Levantar servidor" / "Parar servidor" buttons via useLlamacppLaunch /
 * useLlamacppShutdown. PT-BR microcopy per UI-SPEC §Surface 2.
 *
 * Controlled props pattern (D-05): ResearchDialog owns the open state and
 * passes it down. The sheet is mounted as a sibling Dialog.Root (NOT nested
 * inside ResearchDialog's Dialog.Content) per §Pattern 3 in the context doc.
 *
 * review-fix #1 (Gemini + Codex HIGH): isRunning derives EXCLUSIVELY from
 * useLlamacppStatus().data?.running. The old Boolean(launch.data?.ok)
 * derivation read the TanStack mutation cache which never clears on its own,
 * so closing and reopening the sheet left the UI permanently showing "running".
 *
 * review-fix #6 (Codex MEDIUM): useLlamacppStatus is the canonical backend
 * health poll; AuthSetupSheet enables it only while the sheet is open.
 *
 * review-fix #10 (Gemini LOW): empty-models hint is hidden while
 * health.isLoading to avoid a flash of the hint on the open transition.
 */
import { useEffect, useState } from 'react'
import {
  Badge,
  Button,
  Dialog,
  Flex,
  Select,
  Spinner,
  Tabs,
  Text,
} from '@radix-ui/themes'

import { useLlamacppHealth } from '../../api/useLlamacppHealth'
import { useLlamacppLaunch, useLlamacppShutdown } from '../../api/useLlamacppLaunch'
import { useLlamacppStatus } from '../../api/useLlamacppStatus'

export interface AuthSetupSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AuthSetupSheet({ open, onOpenChange }: AuthSetupSheetProps) {
  const [selectedModel, setSelectedModel] = useState<string | null>(null)

  // Only fetch while the sheet is open to avoid background polling.
  const health = useLlamacppHealth(open)

  // review-fix #1 + #6: canonical "is a server running?" source.
  // Polls every 5s but only while the sheet is open.
  const status = useLlamacppStatus(open)

  const launch = useLlamacppLaunch()
  const shutdown = useLlamacppShutdown()

  const availableModels = health.data?.available_models ?? []

  const isBinaryMissing =
    health.data?.healthy === false &&
    (health.data?.message ?? '').includes('não encontrado')

  // review-fix #1 (Gemini + Codex HIGH): isRunning derives EXCLUSIVELY from
  // the canonical backend GET /llamacpp/launch status. The old derivation
  // Boolean(launch.data?.ok) was broken: TanStack mutation cache retains
  // launch.data indefinitely so "Parar servidor" left the UI permanently
  // showing "Servidor ativo".
  const isRunning = status.data?.running === true

  // review-fix #1: on dialog close, reset both mutations so reopening shows
  // a clean state (no stale launch.data / error from a previous session).
  useEffect(() => {
    if (!open) {
      launch.reset()
      shutdown.reset()
    }
  }, [open, launch, shutdown])

  const conflictMessage = launch.error?.message ?? ''
  // 409 conflict messages from the backend contain both "ativo" and "pare" (PT-BR).
  const isConflict409 =
    conflictMessage.toLowerCase().includes('ativo') &&
    conflictMessage.toLowerCase().includes('pare')

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content
        data-testid="auth-setup-sheet"
        style={{ maxWidth: 480 }}
      >
        <Dialog.Title>Configurar provedores</Dialog.Title>
        <Dialog.Description>
          Configure os provedores LLM locais. As configurações são salvas localmente.
        </Dialog.Description>

        <Tabs.Root defaultValue="llamacpp" mt="4">
          <Tabs.List>
            <Tabs.Trigger value="llamacpp" data-testid="tab-llamacpp">
              Llama.cpp local
            </Tabs.Trigger>
            {/* D-05 layout reserve — Claude/Ollama tabs disabled until those
                providers are wired in a future plan (D-06 functional scope). */}
            <Tabs.Trigger value="claude" disabled data-testid="tab-claude-disabled">
              Claude
            </Tabs.Trigger>
            <Tabs.Trigger value="ollama" disabled data-testid="tab-ollama-disabled">
              Ollama
            </Tabs.Trigger>
          </Tabs.List>

          <Tabs.Content value="llamacpp">
            <Flex direction="column" gap="3" mt="3">

              {/* Binary missing warning (orange, per UI-SPEC §Surface 2) */}
              {isBinaryMissing && (
                <Text size="2" color="orange" data-testid="binary-missing-warning">
                  llama-server não encontrado no PATH. Instale o llama.cpp ou defina LLAMA_SERVER_BIN.
                </Text>
              )}

              {/* Model dropdown — D-09 */}
              <Flex direction="column" gap="1">
                <Text as="label" size="2" weight="medium" htmlFor="llamacpp-model-select">
                  Modelos disponíveis
                </Text>
                <Select.Root
                  value={selectedModel ?? undefined}
                  onValueChange={setSelectedModel}
                  disabled={availableModels.length === 0}
                >
                  <Select.Trigger
                    id="llamacpp-model-select"
                    data-testid="llamacpp-model-select"
                    placeholder="Selecione um modelo .gguf"
                  />
                  <Select.Content>
                    {availableModels.map((m) => (
                      <Select.Item key={m} value={m} data-testid={`model-option-${m}`}>
                        {m}
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>

                {/* review-fix #10 (Gemini LOW): hide the hint while health is still
                    loading to avoid a flicker on the open transition. */}
                {availableModels.length === 0 && !health.isLoading && (
                  <Text size="1" color="gray" data-testid="empty-models-hint">
                    Coloque arquivos .gguf em ~/.medieval-forge/models/{' '}
                    (ou defina MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR).
                  </Text>
                )}
              </Flex>

              {/* Status line — shows spinner during transitions, then
                  running info or idle label. */}
              <Flex align="center" gap="2" data-testid="server-status-line">
                {launch.isPending && (
                  <>
                    <Spinner size="1" />
                    <Text size="2" color="gray">Iniciando servidor…</Text>
                  </>
                )}
                {shutdown.isPending && (
                  <>
                    <Spinner size="1" />
                    <Text size="2" color="gray">Parando servidor…</Text>
                  </>
                )}
                {!launch.isPending && !shutdown.isPending && isRunning && status.data && (
                  <>
                    <Badge color="green" variant="soft">Servidor ativo</Badge>
                    <Text size="2">
                      Servidor ativo — {status.data.base_url} · PID {status.data.pid}
                    </Text>
                  </>
                )}
                {!launch.isPending && !shutdown.isPending && !isRunning && (
                  <Text size="2" color="gray">Nenhum servidor ativo.</Text>
                )}
              </Flex>

              {/* Launch error display */}
              {launch.isError && (
                <Text size="2" color="red" data-testid="launch-error">
                  {isConflict409
                    ? launch.error?.message
                    : `Erro ao iniciar o servidor: ${launch.error?.message}. Verifique os logs do backend.`}
                </Text>
              )}

              {/* Shutdown error display */}
              {shutdown.isError && (
                <Text size="2" color="red" data-testid="shutdown-error">
                  Erro ao parar o servidor: {shutdown.error?.message}.
                </Text>
              )}

              {/* Action button — toggles between "Levantar servidor" (idle)
                  and "Parar servidor" (running, red solid). */}
              {!isRunning ? (
                <Button
                  data-testid="launch-button"
                  onClick={() => selectedModel && launch.mutate({ model: selectedModel })}
                  disabled={
                    !selectedModel ||
                    availableModels.length === 0 ||
                    isBinaryMissing ||
                    launch.isPending
                  }
                >
                  Levantar servidor
                </Button>
              ) : (
                <Button
                  data-testid="shutdown-button"
                  color="red"
                  variant="solid"
                  onClick={() => shutdown.mutate()}
                  disabled={shutdown.isPending}
                >
                  Parar servidor
                </Button>
              )}

            </Flex>
          </Tabs.Content>
        </Tabs.Root>

        <Flex justify="end" mt="4">
          <Dialog.Close>
            <Button variant="soft" data-testid="auth-setup-sheet-close">
              Fechar
            </Button>
          </Dialog.Close>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  )
}
