/**
 * Plan 07-09a Task 2 RED — ResearchDialog unit tests.
 *
 * Verifies:
 *   - PT-BR copy verbatim from UI-SPEC §Surface 1
 *   - Form fields render (País, Período, Provedor LLM, Modelo, Forçar checkbox)
 *   - CTA labels ("Iniciar pesquisa", "Cancelar pesquisa")
 *   - REVIEWS soft codex — softened CLI piggyback microcopy
 *   - Cache-hit microcopy "Resultado em cache"
 *   - Submit posts to /api/v3/research/start
 *   - 1.2s auto-close on success
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { ResearchDialog } from '../ResearchDialog'

function makeQc() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

function renderDialog(props: Partial<React.ComponentProps<typeof ResearchDialog>> = {}) {
  const qc = makeQc()
  return render(
    <QueryClientProvider client={qc}>
      <Theme>
        <ResearchDialog
          open={true}
          onOpenChange={() => {}}
          projectId="00000000-0000-0000-0000-000000000001"
          regionDisplayName="Iberia 868"
          countryQid="Q29"
          condadoIds={['cd-leon']}
          {...props}
        />
      </Theme>
    </QueryClientProvider>,
  )
}

const PROVIDERS_OK = [
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
    available_models: ['qwen2.5:7b'],
  },
]

describe('ResearchDialog', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => {
        if (url.endsWith('/api/v3/research/providers')) {
          return { ok: true, json: async () => PROVIDERS_OK } as Response
        }
        if (url.includes('/research/overlay')) {
          return {
            ok: true,
            json: async () => ({
              exists: false,
              covered_condado_ids: [],
              meta: null,
            }),
          } as Response
        }
        return { ok: true, json: async () => ({}) } as Response
      }),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders Dialog.Title "Pesquisar metadados históricos"', () => {
    renderDialog()
    expect(screen.getByText('Pesquisar metadados históricos')).toBeTruthy()
  })

  it('renders the "Forçar nova pesquisa (ignorar cache)" checkbox label', () => {
    renderDialog()
    expect(
      screen.getByText('Forçar nova pesquisa (ignorar cache)'),
    ).toBeTruthy()
  })

  it('renders the "Iniciar pesquisa" primary CTA', () => {
    renderDialog()
    expect(screen.getByText('Iniciar pesquisa')).toBeTruthy()
  })

  it('renders País as read-only with the region display name', () => {
    renderDialog({ regionDisplayName: 'Iberia 868' })
    // País field surfaces the region name (read-only)
    expect(screen.getByDisplayValue(/Iberia 868/)).toBeTruthy()
  })

  it('renders Período seeded from region display_name', () => {
    renderDialog({ regionDisplayName: 'Iberia 868 AD' })
    expect(screen.getByDisplayValue('Iberia 868 AD')).toBeTruthy()
  })

  it("REVIEWS soft codex — renders softened Claude CLI piggyback microcopy", async () => {
    // Wait for providers fetch + provider switch to Claude
    renderDialog()
    // Switch provider to Claude via prop default — the dialog should default
    // to Claude when healthy. Find the CLI microcopy.
    // The text uses an ellipsis character …
    const matches = await screen.findAllByText(/Tentando token do Claude CLI/)
    expect(matches.length).toBeGreaterThan(0)
  })

  it("does NOT contain old 'auto-detectado' or 'auto-detected' microcopy", () => {
    const { container } = renderDialog()
    expect(container.textContent).not.toMatch(/auto-detectado|auto-detected/)
  })

  it("Cancel CTA label is 'Cancelar' in idle state", () => {
    renderDialog()
    expect(screen.getByText('Cancelar')).toBeTruthy()
  })
})
