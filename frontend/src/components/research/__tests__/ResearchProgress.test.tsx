/**
 * Plan 07-09a Task 2 RED — ResearchProgress unit tests.
 *
 * Verifies (REVIEWS fix #7):
 *   - 4 stage rows render PT-BR labels
 *   - aborted terminal state renders "Cancelada" (NOT "Erro")
 *   - non-abort failure renders "Erro: {message}"
 *   - retry inline notice renders "Tentativa N de 3"
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { ResearchProgress } from '../ResearchProgress'
import type { StreamState } from '../../../hooks/useResearchStream'

function wrap(node: React.ReactNode) {
  return render(<Theme>{node}</Theme>)
}

describe('ResearchProgress', () => {
  it('renders the 4 PT-BR stage labels (Reinos, Ducados, Condados, Baronias)', () => {
    const state: StreamState = { phase: 'idle' }
    wrap(<ResearchProgress state={state} />)
    expect(screen.getByText('Reinos')).toBeTruthy()
    expect(screen.getByText('Ducados')).toBeTruthy()
    expect(screen.getByText('Condados')).toBeTruthy()
    expect(screen.getByText('Baronias')).toBeTruthy()
  })

  it('highlights the running stage with the current label', () => {
    const state: StreamState = {
      phase: 'running',
      currentStage: 'condados',
    }
    wrap(<ResearchProgress state={state} />)
    expect(screen.getByText('Condados')).toBeTruthy()
  })

  it("REVIEWS fix #7 — aborted terminal state renders 'Cancelada', NOT 'Erro'", () => {
    const state: StreamState = {
      phase: 'failed',
      error_code: 'aborted',
      error_message: 'Pesquisa cancelada pelo usuário.',
    }
    wrap(<ResearchProgress state={state} />)
    expect(screen.getByText('Cancelada')).toBeTruthy()
    // Should NOT show Erro:
    expect(screen.queryByText(/^Erro:/)).toBeNull()
  })

  it("network failure renders 'Erro:' message", () => {
    const state: StreamState = {
      phase: 'failed',
      error_code: 'network',
      error_message: 'Falha de rede durante a pesquisa.',
    }
    wrap(<ResearchProgress state={state} />)
    expect(screen.getByText(/Erro:/)).toBeTruthy()
    expect(screen.queryByText('Cancelada')).toBeNull()
  })

  it('renders retry inline notice "Tentativa N de 3" when retryAttempt is set', () => {
    const state: StreamState = {
      phase: 'running',
      currentStage: 'condados',
      retryAttempt: { current: 2, max: 3 },
    }
    wrap(<ResearchProgress state={state} />)
    expect(screen.getByText(/Tentativa 2 de 3/)).toBeTruthy()
  })

  it('renders success affordance when phase is succeeded', () => {
    const state: StreamState = { phase: 'succeeded' }
    wrap(<ResearchProgress state={state} />)
    // The component should expose a success cue — concluded
    expect(screen.getByText(/concluí|conclu/i)).toBeTruthy()
  })
})
