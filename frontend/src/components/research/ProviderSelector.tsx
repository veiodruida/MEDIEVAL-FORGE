/**
 * Phase 07.1 — unified provider/model picker (replaces the old AuthSetupSheet flow).
 *
 * Responsibilities:
 *   1. Provedor LLM dropdown sourced from useProviders().
 *   2. Modelo dropdown — for llamacpp/ollama populated from provider.available_models;
 *      for claude a free-form TextField (claude has no installed-model list).
 *   3. Inline "Levantar / Parar servidor" controls when provider=llamacpp.
 *
 * REVIEWS fix #5 ordered preference (ollama only):
 *   1. qwen2.5:7b        (preferred — best balance for our prompts)
 *   2. qwen2.5-coder:14b (fallback)
 *   3. gemma4:26b        (fallback)
 *   4. deepseek-r1:14b   (fallback)
 *
 * For llamacpp the dropdown shows absolute .gguf paths (label = basename) — the
 * user picks one and clicks "Levantar servidor" inline; no separate dialog.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  Badge,
  Box,
  Button,
  Flex,
  Select,
  Spinner,
  Text,
  TextField,
} from '@radix-ui/themes'
import type { ProviderEntry } from '../../api/useProviders'
import { useLlamacppLaunch, useLlamacppShutdown } from '../../api/useLlamacppLaunch'
import { useLlamacppStatus } from '../../api/useLlamacppStatus'
import { useOllamaLaunch, useOllamaShutdown, useOllamaStatus } from '../../api/useOllamaLaunch'

const MODEL_PREFERENCE_ORDER = [
  'qwen2.5:7b',
  'qwen2.5-coder:14b',
  'gemma4:26b',
  'deepseek-r1:14b',
] as const

interface PickModelResult {
  model: string
  hint?: string
}

export function pickDefaultModel(
  availableModels: string[] | undefined,
): PickModelResult {
  if (!availableModels || availableModels.length === 0) {
    return {
      model: '',
      hint: 'Nenhum modelo Ollama instalado. Execute "ollama pull <modelo>".',
    }
  }
  // Honor the historical preference list when one of those models happens
  // to be installed, but DO NOT nag the user with "use qwen2.5:7b instead"
  // copy when they have a perfectly valid local model — only the dropdown
  // entries the user actually has on disk are recommendations.
  for (const pref of MODEL_PREFERENCE_ORDER) {
    if (availableModels.includes(pref)) {
      return { model: pref }
    }
  }
  return { model: availableModels[0] }
}

function basename(path: string): string {
  return path.replace(/\\/g, '/').split('/').pop() ?? path
}

export interface ProviderSelectorProps {
  providers: ProviderEntry[] | undefined
  value: string
  onProviderChange: (providerId: string) => void
  modelValue: string
  onModelChange: (model: string) => void
  isLoading?: boolean
  /**
   * UAT 2026-05-23 — opens the CredentialsManager modal so the user can
   * paste a key inline. Wired by ResearchDialog. Optional so the
   * component still mounts in isolation tests.
   */
  onOpenCredentials?: () => void
}

export function ProviderSelector({
  providers,
  value,
  onProviderChange,
  modelValue,
  onModelChange,
  isLoading = false,
  onOpenCredentials,
}: ProviderSelectorProps) {
  const selectedEntry = useMemo(
    () => providers?.find((p) => p.provider_id === value),
    [providers, value],
  )

  const availableModels = selectedEntry?.available_models ?? []
  const isLlamacpp = value === 'llamacpp'
  const isOllama = value === 'ollama'
  const isClaude = value === 'claude'

  // UAT 2026-05-23 — OpenRouter exposes hundreds of models, so the user
  // needs a search filter to find one. We always render the filter
  // textbox when the list has > 8 entries (threshold tuned so the
  // ollama/llamacpp short list isn't cluttered by an unneeded input).
  const [modelFilter, setModelFilter] = useState('')
  const filteredModels = useMemo(() => {
    if (!modelFilter.trim()) return availableModels
    const needle = modelFilter.trim().toLowerCase()
    return availableModels.filter((m) => m.toLowerCase().includes(needle))
  }, [availableModels, modelFilter])
  const showFilter = availableModels.length > 8 && !isClaude

  // Llamacpp launcher state — only enabled when llamacpp is the active provider.
  const status = useLlamacppStatus(isLlamacpp)
  const launch = useLlamacppLaunch()
  const shutdown = useLlamacppShutdown()
  const isRunning = status.data?.running === true

  // Ollama daemon launcher — enabled when ollama is the active provider.
  // Shutdown is only exposed when we own the spawned subprocess (status.owned).
  const ollamaStatus = useOllamaStatus(isOllama)
  const ollamaLaunch = useOllamaLaunch()
  const ollamaShutdown = useOllamaShutdown()
  const isOllamaRunning = ollamaStatus.data?.running === true
  const isOllamaOwned = ollamaStatus.data?.owned === true
  const isOllamaBinaryMissing =
    isOllama &&
    selectedEntry?.healthy === false &&
    (selectedEntry?.message ?? '').includes('não encontrado')

  const isBinaryMissing =
    isLlamacpp &&
    selectedEntry?.healthy === false &&
    (selectedEntry?.message ?? '').includes('não encontrado')

  // REVIEWS fix #5 — preference-based default for Ollama.
  const ollamaPick = useMemo(
    () =>
      isOllama
        ? pickDefaultModel(availableModels)
        : ({ model: '', hint: undefined } as PickModelResult),
    [isOllama, availableModels],
  )

  // Auto-pick a model when one isn't already selected:
  //   - Ollama: ordered preference list (qwen2.5:7b → fallback chain).
  //   - Llamacpp: first .gguf in available_models.
  // Claude: stays free-text (no installed-model list).
  useEffect(() => {
    if (modelValue !== '') return
    if (isOllama && ollamaPick.model) {
      onModelChange(ollamaPick.model)
      return
    }
    if (isLlamacpp && availableModels.length > 0) {
      onModelChange(availableModels[0])
    }
  }, [
    isOllama,
    isLlamacpp,
    modelValue,
    ollamaPick.model,
    availableModels,
    onModelChange,
  ])

  // Reset model when the provider changes (the previous selection is
  // meaningless under a new provider, e.g. ollama tag vs gguf path).
  useEffect(() => {
    onModelChange('')
    setModelFilter('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  const modelPlaceholder = isClaude ? 'claude-sonnet-4-6' : 'Selecione um modelo'

  const launchConflictMessage = launch.error?.message ?? ''
  const isConflict409 =
    launchConflictMessage.toLowerCase().includes('ativo') &&
    launchConflictMessage.toLowerCase().includes('pare')

  return (
    <Flex direction="column" gap="3">
      <Box>
        <Text
          as="label"
          size="2"
          weight="medium"
          htmlFor="research-provider-trigger"
        >
          Provedor LLM
        </Text>
        <Box mt="1">
          <Select.Root
            value={value}
            onValueChange={onProviderChange}
            disabled={isLoading || !providers || providers.length === 0}
          >
            <Select.Trigger
              id="research-provider-trigger"
              data-testid="research-provider-select"
              placeholder={
                isLoading ? 'Carregando provedores...' : 'Selecione um provedor'
              }
            />
            <Select.Content>
              {providers?.map((p) => (
                <Select.Item key={p.provider_id} value={p.provider_id}>
                  <Text size="2">
                    {p.display_name}
                    {!p.healthy && (
                      <Text size="1" color="gray">
                        {' '}
                        — indisponível
                      </Text>
                    )}
                  </Text>
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Root>
        </Box>
        {selectedEntry && !selectedEntry.healthy && !isLlamacpp && (
          <Flex direction="column" gap="2" mt="1">
            <Text size="1" color="orange" as="p">
              {selectedEntry.message}
            </Text>
            {/* UAT 2026-05-23 — when the error message tells the user to
                "Cole sua X em Configurações ou importe um .env", make
                that action one click away instead of a buried button
                in the dialog title row. */}
            {onOpenCredentials &&
              !isOllama &&
              (selectedEntry.message ?? '').toLowerCase().includes('chave') && (
                <Box>
                  <Button
                    type="button"
                    size="1"
                    variant="solid"
                    onClick={onOpenCredentials}
                    data-testid="provider-configure-key"
                  >
                    Configurar chave de API
                  </Button>
                </Box>
              )}
          </Flex>
        )}
      </Box>

      <Box>
        <Text
          as="label"
          size="2"
          weight="medium"
          htmlFor="research-model-input"
        >
          Modelo
        </Text>
        <Box mt="1">
          {isClaude ? (
            <TextField.Root
              id="research-model-input"
              data-testid="research-model-input"
              value={modelValue}
              onChange={(e) => onModelChange(e.target.value)}
              placeholder={modelPlaceholder}
            />
          ) : (
            <Flex direction="column" gap="2">
              {showFilter && (
                <TextField.Root
                  value={modelFilter}
                  onChange={(e) => setModelFilter(e.target.value)}
                  placeholder={`Filtrar ${availableModels.length} modelos…`}
                  data-testid="research-model-filter"
                />
              )}
              <Select.Root
                value={modelValue || undefined}
                onValueChange={onModelChange}
                disabled={availableModels.length === 0}
              >
                <Select.Trigger
                  id="research-model-input"
                  data-testid="research-model-select"
                  placeholder={
                    availableModels.length === 0
                      ? isLlamacpp
                        ? 'Nenhum .gguf encontrado'
                        : 'Nenhum modelo Ollama instalado'
                      : modelPlaceholder
                  }
                />
                <Select.Content>
                  {filteredModels.length === 0 ? (
                    <Box p="2">
                      <Text size="1" color="gray">
                        Nenhum modelo corresponde a "{modelFilter}".
                      </Text>
                    </Box>
                  ) : (
                    filteredModels.map((m) => {
                      const label = isLlamacpp ? basename(m) : m
                      const isFree = m.includes(':free')
                      return (
                        <Select.Item
                          key={m}
                          value={m}
                          data-testid={`model-option-${label}`}
                        >
                          <Flex align="center" gap="2">
                            <Text size="2">{label}</Text>
                            {isFree && (
                              <Badge color="green" variant="soft" size="1">
                                free
                              </Badge>
                            )}
                          </Flex>
                        </Select.Item>
                      )
                    })
                  )}
                </Select.Content>
              </Select.Root>
              {showFilter && modelFilter && (
                <Text size="1" color="gray">
                  {filteredModels.length} de {availableModels.length} modelos
                </Text>
              )}
            </Flex>
          )}
        </Box>
        {isOllama && ollamaPick.hint && (modelValue === '' || modelValue === ollamaPick.model) && (
          <Text size="1" color="orange" mt="1" as="p">
            {ollamaPick.hint}
          </Text>
        )}
        {isLlamacpp && availableModels.length === 0 && !isLoading && (
          <Text size="1" color="gray" mt="1" as="p">
            Nenhum modelo .gguf encontrado. Coloque arquivos em
            ~/.medieval-forge/models/, ~/llama.cpp/models/ ou C:\AI_Models (ou
            defina MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS).
          </Text>
        )}
      </Box>

      {isLlamacpp && (
        <Box>
          {isBinaryMissing && (
            <Text size="2" color="orange" as="p" data-testid="binary-missing-warning">
              llama-server não encontrado no PATH. Instale o llama.cpp ou defina
              LLAMA_SERVER_BIN.
            </Text>
          )}

          <Flex align="center" gap="2" mt="2" data-testid="server-status-line">
            {launch.isPending && (
              <>
                <Spinner size="1" />
                <Text size="2" color="gray">
                  Iniciando servidor…
                </Text>
              </>
            )}
            {shutdown.isPending && (
              <>
                <Spinner size="1" />
                <Text size="2" color="gray">
                  Parando servidor…
                </Text>
              </>
            )}
            {!launch.isPending && !shutdown.isPending && isRunning && status.data && (
              <>
                <Badge color="green" variant="soft">
                  Servidor ativo
                </Badge>
                <Text size="2">
                  {status.data.base_url} · PID {status.data.pid}
                </Text>
              </>
            )}
            {!launch.isPending && !shutdown.isPending && !isRunning && (
              <Text size="2" color="gray">
                Nenhum servidor ativo.
              </Text>
            )}
          </Flex>

          {launch.isError && (
            <Text size="2" color="red" as="p" mt="1" data-testid="launch-error">
              {isConflict409
                ? launch.error?.message
                : `Erro ao iniciar o servidor: ${launch.error?.message}. Verifique os logs do backend.`}
            </Text>
          )}

          {shutdown.isError && (
            <Text size="2" color="red" as="p" mt="1" data-testid="shutdown-error">
              Erro ao parar o servidor: {shutdown.error?.message}.
            </Text>
          )}

          <Box mt="2">
            {!isRunning ? (
              <Button
                type="button"
                data-testid="launch-button"
                onClick={() => modelValue && launch.mutate({ model: modelValue })}
                disabled={
                  !modelValue ||
                  availableModels.length === 0 ||
                  isBinaryMissing ||
                  launch.isPending
                }
              >
                Levantar servidor
              </Button>
            ) : (
              <Button
                type="button"
                data-testid="shutdown-button"
                color="red"
                variant="solid"
                onClick={() => shutdown.mutate()}
                disabled={shutdown.isPending}
              >
                Parar servidor
              </Button>
            )}
          </Box>
        </Box>
      )}

      {isOllama && (
        <Box>
          {isOllamaBinaryMissing && (
            <Text size="2" color="orange" as="p" data-testid="ollama-binary-missing-warning">
              Ollama não encontrado no PATH. Instale em https://ollama.com
            </Text>
          )}

          <Flex align="center" gap="2" mt="2" data-testid="ollama-status-line">
            {ollamaLaunch.isPending && (
              <>
                <Spinner size="1" />
                <Text size="2" color="gray">
                  Iniciando Ollama…
                </Text>
              </>
            )}
            {!ollamaLaunch.isPending && isOllamaRunning && (
              <>
                <Badge color="green" variant="soft">
                  Daemon ativo
                </Badge>
                <Text size="2">{ollamaStatus.data?.base_url}</Text>
              </>
            )}
            {!ollamaLaunch.isPending && !isOllamaRunning && (
              <Text size="2" color="gray">
                Ollama não está em execução.
              </Text>
            )}
          </Flex>

          {ollamaLaunch.isError && (
            <Text size="2" color="red" as="p" mt="1" data-testid="ollama-launch-error">
              Erro ao iniciar Ollama: {ollamaLaunch.error?.message}.
            </Text>
          )}

          {ollamaShutdown.isError && (
            <Text size="2" color="red" as="p" mt="1" data-testid="ollama-shutdown-error">
              Erro ao parar Ollama: {ollamaShutdown.error?.message}.
            </Text>
          )}

          <Box mt="2">
            {!isOllamaRunning ? (
              <Button
                type="button"
                data-testid="ollama-launch-button"
                onClick={() => ollamaLaunch.mutate()}
                disabled={isOllamaBinaryMissing || ollamaLaunch.isPending}
              >
                Iniciar Ollama
              </Button>
            ) : isOllamaOwned ? (
              <Button
                type="button"
                data-testid="ollama-shutdown-button"
                color="red"
                variant="solid"
                onClick={() => ollamaShutdown.mutate()}
                disabled={ollamaShutdown.isPending}
              >
                Parar Ollama
              </Button>
            ) : (
              <Text size="1" color="gray" as="p">
                Daemon iniciado externamente (Ollama Desktop) — pare pelo ícone
                da bandeja.
              </Text>
            )}
          </Box>
        </Box>
      )}
    </Flex>
  )
}
