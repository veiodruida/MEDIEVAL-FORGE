/**
 * Phase 07.1 Plan 07 Task 2 — ResearchDialog numeric period inputs (9 vitest cases).
 *
 * Covers SC-1e / SC-1f:
 *   D-01: two number inputs (Início + Fim)
 *   D-02: min=1 max=2100 step=1 attributes
 *   D-03: empty when Project.period_start is null
 *   D-04c: payload uses integer period_start / period_end (no period_label)
 *
 * review-fix #2 (Gemini HIGH): Test 9 locks the hasSeeded gate contract
 * — seeding must wait for useProject to resolve, not just the open-transition tick.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

import { ResearchDialog } from '../ResearchDialog'

// ---------------------------------------------------------------------------
// Module mocks (hoisted by Vitest — must be at top level)
// ---------------------------------------------------------------------------

vi.mock('../../../api/useProviders', () => ({
  useProviders: vi.fn(),
}))

vi.mock('../../../api/useResearchOverlay', () => ({
  useResearchOverlay: vi.fn(),
}))

vi.mock('../../../hooks/useResearchStream', () => ({
  useResearchStream: vi.fn(),
}))

vi.mock('../../../api/useProject', () => ({
  useProject: vi.fn(),
}))

// Import after vi.mock so we get the mocked versions
import { useProject } from '../../../api/useProject'
import { useProviders } from '../../../api/useProviders'
import { useResearchOverlay } from '../../../api/useResearchOverlay'
import { useResearchStream } from '../../../hooks/useResearchStream'

const mockUseProject = vi.mocked(useProject)
const mockUseProviders = vi.mocked(useProviders)
const mockUseResearchOverlay = vi.mocked(useResearchOverlay)
const mockUseResearchStream = vi.mocked(useResearchStream)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <Theme>{ui}</Theme>
    </QueryClientProvider>
  )
}

const SEEDED_PROJECT = {
  id: 'p1',
  name: 'Iberia',
  period_start: 868,
  period_end: 1000,
  country_qid: 'Q29',
  region_key: 'iberia_868',
  bbox_lon_min: null,
  bbox_lon_max: null,
  bbox_lat_min: null,
  bbox_lat_max: null,
  generator_config: null,
  status: 'ready',
  created_at: '',
  updated_at: '',
}

const BLANK_PROJECT = { ...SEEDED_PROJECT, period_start: null, period_end: null }

const DEFAULT_PROPS = {
  onOpenChange: vi.fn(),
  projectId: 'p1',
  regionDisplayName: 'Ibéria',
  countryQid: 'Q29',
  condadoIds: [],
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ResearchDialog — numeric period inputs (D-01, D-02, D-03, D-04c)', () => {
  let fetchSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    // Default mocks for all tests — individual tests override as needed
    // Provide a healthy provider so canSubmit can become true when period is valid
    mockUseProviders.mockReturnValue({
      data: [{ provider_id: 'claude', healthy: true }],
      isLoading: false,
    } as any)
    mockUseResearchOverlay.mockReturnValue({ data: { exists: false } } as any)
    mockUseResearchStream.mockReturnValue({
      state: { phase: 'idle' },
      subscribe: vi.fn(),
      close: vi.fn(),
    } as any)
    mockUseProject.mockReturnValue({ data: SEEDED_PROJECT, isLoading: false } as any)

    fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ run_id: 'run-1', status: 'scheduled' }),
    })
    vi.stubGlobal('fetch', fetchSpy)
    vi.spyOn(console, 'log').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders Início and Fim number inputs with min=1 max=2100 step=1', async () => {
    render(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    const start = await screen.findByTestId('research-period-start')
    const end = await screen.findByTestId('research-period-end')

    expect(start).toHaveAttribute('type', 'number')
    expect(start).toHaveAttribute('min', '1')
    expect(start).toHaveAttribute('max', '2100')
    expect(start).toHaveAttribute('step', '1')

    expect(end).toHaveAttribute('type', 'number')
    expect(end).toHaveAttribute('min', '1')
    expect(end).toHaveAttribute('max', '2100')
    expect(end).toHaveAttribute('step', '1')
  })

  it('seeds inputs from Project.period_start and Project.period_end on open transition', async () => {
    const { rerender } = render(wrap(<ResearchDialog {...DEFAULT_PROPS} open={false} />))
    rerender(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    const start = await screen.findByTestId('research-period-start') as HTMLInputElement
    const end = await screen.findByTestId('research-period-end') as HTMLInputElement

    await waitFor(() => expect(start.value).toBe('868'))
    expect(end.value).toBe('1000')
  })

  it('renders empty inputs when Project.period_start is null', async () => {
    mockUseProject.mockReturnValue({ data: BLANK_PROJECT, isLoading: false } as any)

    render(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    const start = await screen.findByTestId('research-period-start') as HTMLInputElement
    const end = await screen.findByTestId('research-period-end') as HTMLInputElement

    expect(start.value).toBe('')
    expect(end.value).toBe('')
  })

  it('disables CTA when periodStart > periodEnd with PT-BR error message', async () => {
    render(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    const start = await screen.findByTestId('research-period-start')
    const end = await screen.findByTestId('research-period-end')

    fireEvent.change(start, { target: { value: '1000' } })
    fireEvent.change(end, { target: { value: '868' } })

    const submit = screen.getByRole('button', { name: /iniciar pesquisa/i })
    expect(submit).toBeDisabled()
    expect(screen.getByTestId('period-error-start-gt-end')).toHaveTextContent(
      'O início deve ser menor ou igual ao fim.'
    )
  })

  it('disables CTA when periodStart is 0 (below min)', async () => {
    mockUseProject.mockReturnValue({ data: BLANK_PROJECT, isLoading: false } as any)

    render(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    const start = await screen.findByTestId('research-period-start')
    const end = await screen.findByTestId('research-period-end')

    fireEvent.change(start, { target: { value: '0' } })
    fireEvent.change(end, { target: { value: '900' } })

    expect(screen.getByRole('button', { name: /iniciar pesquisa/i })).toBeDisabled()
  })

  it('disables CTA when periodEnd is 2101 (above max)', async () => {
    mockUseProject.mockReturnValue({ data: BLANK_PROJECT, isLoading: false } as any)

    render(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    const start = await screen.findByTestId('research-period-start')
    const end = await screen.findByTestId('research-period-end')

    fireEvent.change(start, { target: { value: '800' } })
    fireEvent.change(end, { target: { value: '2101' } })

    expect(screen.getByRole('button', { name: /iniciar pesquisa/i })).toBeDisabled()
  })

  it('submit payload carries period_start and period_end as JSON integers not strings', async () => {
    render(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    // Wait for seed to settle (868 / 1000 from SEEDED_PROJECT)
    const submit = await screen.findByRole('button', { name: /iniciar pesquisa/i })
    await waitFor(() => expect(submit).not.toBeDisabled())

    fireEvent.click(submit)

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())

    const call = fetchSpy.mock.calls.find((c: unknown[]) =>
      String(c[0]).includes('/research/start')
    )
    expect(call).toBeDefined()

    const body = JSON.parse((call![1] as RequestInit).body as string)

    expect(body.period_start).toBe(868)
    expect(typeof body.period_start).toBe('number')
    expect(body.period_end).toBe(1000)
    expect(typeof body.period_end).toBe('number')
    expect('period_label' in body).toBe(false)
  })

  it('period_inputs_seed_when_project_resolves_after_open', async () => {
    // review-fix #2 (Gemini HIGH): hasSeeded gate must wait for useProject
    // to resolve, not just for the open-transition tick.
    mockUseProject.mockReturnValue({ data: undefined, isLoading: true } as any)

    const { rerender } = render(
      wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />)
    )

    // Project still loading — inputs must render empty
    const startInitial = await screen.findByTestId('research-period-start') as HTMLInputElement
    const endInitial = await screen.findByTestId('research-period-end') as HTMLInputElement
    expect(startInitial.value).toBe('')
    expect(endInitial.value).toBe('')

    // useProject resolves
    mockUseProject.mockReturnValue({ data: SEEDED_PROJECT, isLoading: false } as any)
    rerender(wrap(<ResearchDialog {...DEFAULT_PROPS} open={true} />))

    const startAfter = await screen.findByTestId('research-period-start') as HTMLInputElement
    const endAfter = await screen.findByTestId('research-period-end') as HTMLInputElement
    await waitFor(() => expect(startAfter.value).toBe('868'))
    expect(endAfter.value).toBe('1000')
  })
})
