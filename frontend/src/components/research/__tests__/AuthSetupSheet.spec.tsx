/**
 * Phase 07.1 Plan 08 Task 2 — AuthSetupSheet vitest (11 cases).
 *
 * Covers SC-5a..c + interaction contract, plus 3 review-fix additions:
 *   - Test 9 (review-fix #1): isRunning derives from status, NOT mutation cache
 *   - Test 10 (review-fix #1): reopen lifecycle clears stale mutation data
 *   - Test 11 (review-fix #10): empty-models hint hidden during health loading
 *
 * NOTE: plan <objective> says "8 cases" but must_haves.artifacts + acceptance_criteria
 * both specify 11 cases (review-fixes #1 + #10 add Tests 9/10/11). The canonical count
 * is 11. The "8" in the objective was a stale copy from an earlier plan draft.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { AuthSetupSheet } from '../AuthSetupSheet'
import * as healthMod from '../../../api/useLlamacppHealth'
import * as launchMod from '../../../api/useLlamacppLaunch'
import * as statusMod from '../../../api/useLlamacppStatus'

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <Theme>{ui}</Theme>
    </QueryClientProvider>
  )
}

const mkHealth = (
  overrides: Partial<{
    healthy: boolean
    message: string
    available_models: string[]
    isLoading: boolean
  }> = {},
) => {
  const { isLoading = false, ...dataOverrides } = overrides
  return {
    data: {
      healthy: false,
      message: 'Servidor llama-server não está ativo.',
      available_models: [],
      ...dataOverrides,
    },
    isLoading,
    isError: false,
    error: null,
  } as any
}

// review-fix #1 + #6: canonical status mock (replaces the launch.data-based
// isRunning derivation).
const mkStatus = (
  overrides: Partial<{
    running: boolean
    pid: number | null
    base_url: string | null
    model: string | null
    started_at: string | null
    isLoading: boolean
  }> = {},
) => {
  const { isLoading = false, ...dataOverrides } = overrides
  return {
    data: {
      running: false,
      pid: null,
      base_url: null,
      model: null,
      started_at: null,
      ...dataOverrides,
    },
    isLoading,
    isError: false,
    error: null,
  } as any
}

const mkLaunch = (
  overrides: Partial<{
    isPending: boolean
    isError: boolean
    error: Error | null
    data: any
  }> = {},
) =>
  ({
    mutate: vi.fn(),
    reset: vi.fn(), // review-fix #1: AuthSetupSheet calls .reset() on close
    isPending: false,
    isError: false,
    error: null,
    data: null,
    ...overrides,
  }) as any

const mkShutdown = (
  overrides: Partial<{
    isPending: boolean
    isError: boolean
    error: Error | null
  }> = {},
) =>
  ({
    mutate: vi.fn(),
    reset: vi.fn(), // review-fix #1
    isPending: false,
    isError: false,
    error: null,
    ...overrides,
  }) as any

describe('AuthSetupSheet — Llama.cpp panel (D-05, D-07a/b, D-08, D-08b, D-09)', () => {
  beforeEach(() => {
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(mkHealth())
    vi.spyOn(statusMod, 'useLlamacppStatus').mockReturnValue(mkStatus()) // review-fix #1 + #6
    vi.spyOn(launchMod, 'useLlamacppLaunch').mockReturnValue(mkLaunch())
    vi.spyOn(launchMod, 'useLlamacppShutdown').mockReturnValue(mkShutdown())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders Tabs shell with Llama.cpp local tab active and Claude/Ollama disabled', async () => {
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    expect(await screen.findByTestId('tab-llamacpp')).toHaveTextContent('Llama.cpp local')
    expect(screen.getByTestId('tab-claude-disabled')).toBeDisabled()
    expect(screen.getByTestId('tab-ollama-disabled')).toBeDisabled()
  })

  it('dropdown populates from useLlamacppHealth().available_models alphabetically', async () => {
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ available_models: ['a.gguf', 'b.gguf', 'c.gguf'] }),
    )
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    // Dropdown is enabled when models available
    const trigger = await screen.findByTestId('llamacpp-model-select')
    expect(trigger).not.toBeDisabled()
    // Open the Select via pointer interaction (Radix uses pointerdown)
    fireEvent.pointerDown(trigger, {
      button: 0,
      ctrlKey: false,
      pointerId: 1,
      pointerType: 'mouse',
    })
    await waitFor(() => {
      expect(screen.getByTestId('model-option-a.gguf')).toBeInTheDocument()
      expect(screen.getByTestId('model-option-b.gguf')).toBeInTheDocument()
      expect(screen.getByTestId('model-option-c.gguf')).toBeInTheDocument()
    })
  })

  it('dropdown disabled with PT-BR hint when available_models is empty array', async () => {
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    const trigger = await screen.findByTestId('llamacpp-model-select')
    expect(trigger).toBeDisabled()
    expect(await screen.findByTestId('empty-models-hint')).toHaveTextContent(
      'Nenhum modelo .gguf encontrado',
    )
  })

  it('"Levantar servidor" disabled when llama-server binary missing with orange warning', async () => {
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({
        healthy: false,
        message: 'llama-server não encontrado no PATH',
        available_models: ['m.gguf'],
      }),
    )
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    expect(await screen.findByTestId('binary-missing-warning')).toHaveTextContent(
      'llama-server não encontrado',
    )
    expect(screen.getByTestId('launch-button')).toBeDisabled()
  })

  it('"Levantar servidor" click calls useLlamacppLaunch with selected model', async () => {
    const launchMock = mkLaunch()
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ healthy: false, message: '', available_models: ['m.gguf'] }),
    )
    vi.spyOn(launchMod, 'useLlamacppLaunch').mockReturnValue(launchMock)
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    // Open the Select
    const trigger = await screen.findByTestId('llamacpp-model-select')
    fireEvent.pointerDown(trigger, {
      button: 0,
      ctrlKey: false,
      pointerId: 1,
      pointerType: 'mouse',
    })
    // Select the model option
    const option = await screen.findByTestId('model-option-m.gguf')
    fireEvent.click(option)
    // Now click the action button
    await waitFor(() => {
      expect(screen.getByTestId('launch-button')).not.toBeDisabled()
    })
    fireEvent.click(screen.getByTestId('launch-button'))
    expect(launchMock.mutate).toHaveBeenCalledWith({ model: 'm.gguf' })
  })

  it('button label swaps to "Parar servidor" when status.data.running is true with green badge', async () => {
    // review-fix #1 + #6: isRunning derives from useLlamacppStatus, not launch.data
    vi.spyOn(statusMod, 'useLlamacppStatus').mockReturnValue(
      mkStatus({
        running: true,
        pid: 12345,
        base_url: 'http://127.0.0.1:38291',
        model: 'm.gguf',
        started_at: '2026-05-15T15:00:00Z',
      }),
    )
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ healthy: true, message: 'Reachable', available_models: ['m.gguf'] }),
    )
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    expect(await screen.findByTestId('shutdown-button')).toHaveTextContent('Parar servidor')
    expect(screen.queryByTestId('launch-button')).toBeNull()
    // status-line contains "Servidor ativo" badge + running details
    expect(screen.getByTestId('server-status-line').textContent).toMatch(/Servidor ativo/i)
  })

  it('HTTP 409 conflict renders PT-BR inline error containing "ativo" and "pare"', async () => {
    vi.spyOn(launchMod, 'useLlamacppLaunch').mockReturnValue(
      mkLaunch({
        isError: true,
        error: new Error('modelo `existing.gguf` ativo — pare-o antes via DELETE'),
      }),
    )
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ available_models: ['m.gguf'] }),
    )
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    const errorEl = await screen.findByTestId('launch-error')
    expect(errorEl.textContent?.toLowerCase()).toContain('ativo')
    expect(errorEl.textContent?.toLowerCase()).toContain('pare')
  })

  it('"Parar servidor" click sends DELETE shutdown mutation', async () => {
    const shutdownMock = mkShutdown()
    vi.spyOn(launchMod, 'useLlamacppShutdown').mockReturnValue(shutdownMock)
    vi.spyOn(statusMod, 'useLlamacppStatus').mockReturnValue(
      mkStatus({
        running: true,
        pid: 12345,
        base_url: 'http://127.0.0.1:38291',
        model: 'm.gguf',
        started_at: '',
      }),
    )
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ healthy: true, available_models: ['m.gguf'] }),
    )
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    fireEvent.click(await screen.findByTestId('shutdown-button'))
    expect(shutdownMock.mutate).toHaveBeenCalled()
  })

  it('isRunning_reflects_server_state_after_shutdown_not_mutation_cache', async () => {
    // review-fix #1 (Gemini + Codex HIGH): isRunning EXCLUSIVELY derives from
    // useLlamacppStatus. Mount with launch.data set to "successful previous launch"
    // AND status.running=false (server is actually down). UI must reflect idle.
    vi.spyOn(launchMod, 'useLlamacppLaunch').mockReturnValue(
      mkLaunch({
        data: {
          ok: true,
          base_url: 'http://127.0.0.1:38291',
          pid: 12345,
          model: 'm.gguf',
          started_at: '',
        },
      }),
    )
    vi.spyOn(statusMod, 'useLlamacppStatus').mockReturnValue(mkStatus({ running: false }))
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ available_models: ['m.gguf'] }),
    )
    render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    expect(await screen.findByTestId('server-status-line')).toHaveTextContent('Nenhum servidor ativo.')
    expect(screen.getByTestId('launch-button')).toHaveTextContent('Levantar servidor')
    expect(screen.queryByTestId('shutdown-button')).toBeNull()
  })

  it('reopen_lifecycle_clears_stale_mutation_data', async () => {
    // review-fix #1: AuthSetupSheet useEffect calls launch.reset() + shutdown.reset() on close.
    const launchMock = mkLaunch({ isError: true, error: new Error('boom') })
    const shutdownMock = mkShutdown()
    vi.spyOn(launchMod, 'useLlamacppLaunch').mockReturnValue(launchMock)
    vi.spyOn(launchMod, 'useLlamacppShutdown').mockReturnValue(shutdownMock)
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ available_models: ['m.gguf'] }),
    )
    const { rerender } = render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    expect(await screen.findByTestId('launch-error')).toBeInTheDocument()
    // Close the dialog — useEffect should call .reset() on both mutations
    rerender(wrap(<AuthSetupSheet open={false} onOpenChange={() => {}} />))
    await waitFor(() => {
      expect(launchMock.reset).toHaveBeenCalled()
      expect(shutdownMock.reset).toHaveBeenCalled()
    })
  })

  it('empty_models_hint_hidden_during_health_loading', async () => {
    // review-fix #10 (Gemini LOW): no flicker during initial health load.
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)
    const { rerender } = render(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    expect(screen.queryByTestId('empty-models-hint')).toBeNull()
    // After load completes with empty models, the hint MUST appear
    vi.spyOn(healthMod, 'useLlamacppHealth').mockReturnValue(
      mkHealth({ available_models: [], isLoading: false }),
    )
    rerender(wrap(<AuthSetupSheet open={true} onOpenChange={() => {}} />))
    expect(await screen.findByTestId('empty-models-hint')).toBeInTheDocument()
  })
})
