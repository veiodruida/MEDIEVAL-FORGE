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
import { useEffect, useMemo } from 'react'
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
      hint: 'Nenhum modelo Ollama instalado. Execute "ollama pull qwen2.5:7b".',
    }
  }
  for (const pref of MODEL_PREFERENCE_ORDER) {
    if (availableModels.includes(pref)) {
      const hint =
        pref !== MODEL_PREFERENCE_ORDER[0]
          ? `Modelo padrão qwen2.5:7b não encontrado — usando ${pref}. Execute "ollama pull qwen2.5:7b" para o melhor resultado.`
          : undefined
      return { model: pref, hint }
    }
  }
  return {
    model: availableModels[0],
    hint: `Nenhum modelo da lista de preferência encontrado — usando ${availableModels[0]}. Execute "ollama pull qwen2.5:7b" para o melhor resultado.`,
  }
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
}

export function ProviderSelector({
  providers,
  value,
  onProviderChange,
  modelValue,
  onModelChange,
  isLoading = false,
}: ProviderSelectorProps) {
  const selectedEntry = useMemo(
    () => providers?.find((p) => p.provider_id === value),
    [providers, value],
  )

  const availableModels = selectedEntry?.available_models ?? []
  const isLlamacpp = value === 'llamacpp'
  const isOllama = value === 'ollama'
  const isClaude = value === 'claude'

  // Llamacpp launcher state — only enabled when llamacpp is the active provider.
  const status = useLlamacppStatus(isLlamacpp)
  const launch = useLlamacppLaunch()
  const shutdown = useLlamacppShutdown()
  const isRunning = status.data?.running === true

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
          <Text size="1" color="orange" mt="1" as="p">
            {selectedEntry.message}
          </Text>
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
                {availableModels.map((m) => {
                  const label = isLlamacpp ? basename(m) : m
                  return (
                    <Select.Item
                      key={m}
                      value={m}
                      data-testid={`model-option-${label}`}
                    >
                      {label}
                    </Select.Item>
                  )
                })}
              </Select.Content>
            </Select.Root>
          )}
        </Box>
        {isOllama && ollamaPick.hint && (
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
    </Flex>
  )
}
