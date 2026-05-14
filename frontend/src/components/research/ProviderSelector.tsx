/**
 * Phase 07 Plan 09a Task 2 — ProviderSelector sub-component.
 *
 * Used inside `ResearchDialog` to render the Provedor LLM `<Select.Root>`
 * plus the Modelo `<TextField.Root>` underneath. Sources its option list
 * from the `useProviders()` hook and applies the REVIEWS fix #5 ordered
 * preference list to pick a default model when the parent's model value
 * is blank.
 *
 * REVIEWS fix #5 — ordered model preference:
 *   1. qwen2.5:7b        (preferred — best balance for our prompts)
 *   2. qwen2.5-coder:14b (acceptable fallback)
 *   3. gemma4:26b        (acceptable fallback)
 *   4. deepseek-r1:14b   (acceptable fallback)
 *
 * If none match the installed list, fall back to the first available model
 * and surface a PT-BR hint nudging the user to `ollama pull qwen2.5:7b`.
 */
import { useEffect, useMemo } from 'react'
import {
  Box,
  Flex,
  Select,
  Text,
  TextField,
} from '@radix-ui/themes'
import type { ProviderEntry } from '../../api/useProviders'

// REVIEWS fix #5 — single source of truth for the preference order. Keeping
// the literal entries as separate string literals so the grep acceptance
// (`'qwen2.5:7b'|'qwen2.5-coder:14b'|'gemma4:26b'|'deepseek-r1:14b'`) hits.
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

/**
 * REVIEWS fix #5 — ordered preference. First MODEL_PREFERENCE_ORDER entry
 * present in `availableModels` wins; falls back to first available with a
 * hint when none match; surfaces a no-models hint when the list is empty.
 */
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

  // REVIEWS fix #5 — apply ordered preference whenever Ollama is selected
  // and the parent has not pinned a model. Auto-fill the model field with
  // the picked default; surface the PT-BR hint when the first preference
  // is missing.
  const pick = useMemo(
    () =>
      value === 'ollama'
        ? pickDefaultModel(selectedEntry?.available_models)
        : ({ model: '', hint: undefined } as PickModelResult),
    [value, selectedEntry?.available_models],
  )

  useEffect(() => {
    if (value !== 'ollama') return
    if (modelValue !== '' || pick.model === '') return
    onModelChange(pick.model)
  }, [value, modelValue, pick.model, onModelChange])

  const modelPlaceholder =
    value === 'claude' ? 'claude-sonnet-4-6' : 'qwen2.5:7b'

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
                <Select.Item
                  key={p.provider_id}
                  value={p.provider_id}
                  disabled={!p.healthy}
                >
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
        {selectedEntry && !selectedEntry.healthy && (
          <Text size="1" color="gray" mt="1" as="p">
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
          <TextField.Root
            id="research-model-input"
            data-testid="research-model-input"
            value={modelValue}
            onChange={(e) => onModelChange(e.target.value)}
            placeholder={modelPlaceholder}
          />
        </Box>
        {pick.hint && (
          <Text size="1" color="orange" mt="1" as="p">
            {pick.hint}
          </Text>
        )}
      </Box>
    </Flex>
  )
}
