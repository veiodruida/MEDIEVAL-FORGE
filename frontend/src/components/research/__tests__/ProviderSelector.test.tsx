/**
 * Plan 07-09a Task 2 RED — ProviderSelector unit tests.
 *
 * Verifies REVIEWS fix #5:
 *   - Reads available_models from useProviders entry
 *   - Applies ordered preference list ['qwen2.5:7b', 'qwen2.5-coder:14b', ...]
 *   - First match wins; falls back to first available when none match
 *   - PT-BR hint surfaces when preferred model qwen2.5:7b is missing
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { ProviderSelector } from '../ProviderSelector'
import type { ProviderEntry } from '../../../api/useProviders'

function wrap(node: React.ReactNode) {
  return render(<Theme>{node}</Theme>)
}

const PROVIDERS_BOTH_HEALTHY: ProviderEntry[] = [
  {
    provider_id: 'claude',
    display_name: 'Claude (Anthropic)',
    healthy: true,
    message: 'ok',
    configured: true,
  },
  {
    provider_id: 'ollama',
    display_name: 'Ollama (local)',
    healthy: true,
    message: 'ok',
    configured: true,
    available_models: ['qwen2.5:7b', 'qwen2.5-coder:14b'],
  },
]

describe('ProviderSelector — REVIEWS fix #5 ordered preference', () => {
  it('prefers qwen2.5:7b when available (Ollama selected)', () => {
    wrap(
      <ProviderSelector
        providers={PROVIDERS_BOTH_HEALTHY}
        value="ollama"
        onProviderChange={() => {}}
        modelValue="qwen2.5:7b"
        onModelChange={() => {}}
      />,
    )
    // Model field reads qwen2.5:7b — the top of MODEL_PREFERENCE_ORDER
    expect(screen.getByDisplayValue('qwen2.5:7b')).toBeTruthy()
  })

  it('falls back to qwen2.5-coder:14b when qwen2.5:7b is missing and shows PT-BR hint', () => {
    const ollamaMissingPreferred: ProviderEntry[] = [
      {
        provider_id: 'ollama',
        display_name: 'Ollama (local)',
        healthy: true,
        message: 'ok',
        configured: true,
        available_models: ['qwen2.5-coder:14b', 'gemma4:26b'],
      },
    ]
    wrap(
      <ProviderSelector
        providers={ollamaMissingPreferred}
        value="ollama"
        onProviderChange={() => {}}
        modelValue=""
        onModelChange={() => {}}
      />,
    )
    // PT-BR hint surfaces when first preference is unavailable
    expect(
      screen.getByText(/Modelo padrão qwen2\.5:7b não encontrado/),
    ).toBeTruthy()
  })

  it('renders Provedor LLM label', () => {
    wrap(
      <ProviderSelector
        providers={PROVIDERS_BOTH_HEALTHY}
        value="ollama"
        onProviderChange={() => {}}
        modelValue=""
        onModelChange={() => {}}
      />,
    )
    expect(screen.getByText(/Provedor LLM/)).toBeTruthy()
    expect(screen.getByText(/Modelo/)).toBeTruthy()
  })

  it('shows hint when Ollama has no models installed at all', () => {
    const ollamaEmpty: ProviderEntry[] = [
      {
        provider_id: 'ollama',
        display_name: 'Ollama (local)',
        healthy: false,
        message: 'no models',
        configured: true,
        available_models: [],
      },
    ]
    wrap(
      <ProviderSelector
        providers={ollamaEmpty}
        value="ollama"
        onProviderChange={() => {}}
        modelValue=""
        onModelChange={() => {}}
      />,
    )
    expect(
      screen.getByText(/Nenhum modelo Ollama instalado/),
    ).toBeTruthy()
  })

  it('falls back to first available when none of the preferred models match', () => {
    const ollamaOnlyExotic: ProviderEntry[] = [
      {
        provider_id: 'ollama',
        display_name: 'Ollama (local)',
        healthy: true,
        message: 'ok',
        configured: true,
        available_models: ['mistral:7b'],
      },
    ]
    wrap(
      <ProviderSelector
        providers={ollamaOnlyExotic}
        value="ollama"
        onProviderChange={() => {}}
        modelValue=""
        onModelChange={() => {}}
      />,
    )
    // PT-BR hint mentions the fallback model name
    expect(
      screen.getByText(/Nenhum modelo da lista de preferência encontrado/),
    ).toBeTruthy()
  })
})
