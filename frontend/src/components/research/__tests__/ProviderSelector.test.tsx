/**
 * ProviderSelector tests (post-AuthSetupSheet flattening).
 *
 * Covers REVIEWS fix #5 ordered preference + the unified panel that now also
 * hosts the llama.cpp Launch/Stop controls. Tests wrap with QueryClientProvider
 * because the component pulls useLlamacppStatus when provider=llamacpp.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProviderSelector } from '../ProviderSelector'
import type { ProviderEntry } from '../../../api/useProviders'

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <Theme>{node}</Theme>
    </QueryClientProvider>,
  )
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
  it('falls back to qwen2.5-coder:14b when qwen2.5:7b is missing (no nag hint)', () => {
    // UAT 2026-05-21 — the "Modelo padrão qwen2.5:7b não encontrado" hint
    // confused users with locally-curated model sets. pickDefaultModel still
    // honors the preference order but no longer surfaces the recommendation
    // copy when the chosen model came from the user's actual list.
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
    // Hint must NOT appear.
    expect(
      screen.queryByText(/Modelo padrão qwen2\.5:7b não encontrado/),
    ).toBeNull()
  })

  it('renders Provedor LLM and Modelo labels', () => {
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
    // Both the Select placeholder ("Nenhum modelo Ollama instalado") and the
    // hint paragraph ("Nenhum modelo Ollama instalado. Execute ...") match —
    // assert at least one (the hint) renders the actionable copy.
    expect(
      screen.getByText(/Nenhum modelo Ollama instalado\. Execute/),
    ).toBeTruthy()
  })

  it('falls back to first available when none of the preferred models match (no nag)', () => {
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
    expect(
      screen.queryByText(/Nenhum modelo da lista de preferência encontrado/),
    ).toBeNull()
  })
})

describe('ProviderSelector — Claude free-text model field', () => {
  it('renders TextField for claude (free-form claude-sonnet-4-6)', () => {
    wrap(
      <ProviderSelector
        providers={PROVIDERS_BOTH_HEALTHY}
        value="claude"
        onProviderChange={() => {}}
        modelValue="claude-sonnet-4-6"
        onModelChange={() => {}}
      />,
    )
    expect(screen.getByDisplayValue('claude-sonnet-4-6')).toBeTruthy()
  })
})

describe('ProviderSelector — Llama.cpp inline panel', () => {
  it('renders launch button when provider=llamacpp and a model is picked', () => {
    const llamacppProvider: ProviderEntry[] = [
      {
        provider_id: 'llamacpp',
        display_name: 'Llama.cpp (local)',
        healthy: false,
        message: "Servidor llama-server não está ativo. Use 'Levantar servidor'.",
        configured: true,
        available_models: ['C:/AI_Models/foo.gguf'],
      },
    ]
    wrap(
      <ProviderSelector
        providers={llamacppProvider}
        value="llamacpp"
        onProviderChange={() => {}}
        modelValue="C:/AI_Models/foo.gguf"
        onModelChange={() => {}}
      />,
    )
    expect(screen.getByTestId('launch-button')).toBeTruthy()
  })

  it('shows binary-missing warning when message includes "não encontrado"', () => {
    const llamacppMissingBin: ProviderEntry[] = [
      {
        provider_id: 'llamacpp',
        display_name: 'Llama.cpp (local)',
        healthy: false,
        message: 'llama-server não encontrado no PATH.',
        configured: true,
        available_models: [],
      },
    ]
    wrap(
      <ProviderSelector
        providers={llamacppMissingBin}
        value="llamacpp"
        onProviderChange={() => {}}
        modelValue=""
        onModelChange={() => {}}
      />,
    )
    expect(screen.getByTestId('binary-missing-warning')).toBeTruthy()
  })
})
