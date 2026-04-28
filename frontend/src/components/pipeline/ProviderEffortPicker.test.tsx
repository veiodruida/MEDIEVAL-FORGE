import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Theme } from '@radix-ui/themes'
import { ProviderEffortPicker } from './ProviderEffortPicker'
import { useResearchStore } from '../../stores/useResearchStore'

const mockProviders = [
  {
    provider_id: 'claude',
    display_name: 'Claude (Anthropic)',
    auth_methods: [{ type: 'cli', cli_command: 'claude', auth_file_path: '~/.claude' }],
    configured: true,
    healthy: true,
    default_model: 'claude-sonnet-4-6',
  },
  {
    provider_id: 'llamacpp',
    display_name: 'Llama.cpp (local)',
    auth_methods: [{ type: 'none' }],
    configured: true,
    healthy: true,
    default_model: 'default',
  },
]

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <Theme>{children}</Theme>
    </QueryClientProvider>
  )
  return { Wrapper, qc }
}

beforeEach(() => {
  useResearchStore.setState({
    sheetOpenForProvider: null,
  })
  vi.spyOn(globalThis, 'fetch').mockImplementation((url: RequestInfo | URL) => {
    const urlStr = String(url)
    if (urlStr.includes('/api/llm/providers')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockProviders),
      } as Response)
    }
    if (urlStr.includes('/api/llm/health')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ claude: { healthy: true }, llamacpp: { healthy: true } }),
      } as Response)
    }
    return Promise.resolve({ ok: false, status: 404 } as Response)
  })
})

describe('ProviderEffortPicker', () => {
  it('renders ProviderSelector with current providers including llamacpp', async () => {
    const { Wrapper } = makeWrapper()
    await act(async () => {
      render(
        <Wrapper>
          <ProviderEffortPicker
            providerId="llamacpp"
            effort="medium"
            onProviderChange={vi.fn()}
            onEffortChange={vi.fn()}
          />
        </Wrapper>,
      )
    })
    expect(await screen.findByText('Llama.cpp (local)')).toBeInTheDocument()
    expect(await screen.findByText('Claude (Anthropic)')).toBeInTheDocument()
  })

  it('renders 3 effort buttons: Baixo / Médio / Alto with current effort active', async () => {
    const { Wrapper } = makeWrapper()
    await act(async () => {
      render(
        <Wrapper>
          <ProviderEffortPicker
            providerId="claude"
            effort="medium"
            onProviderChange={vi.fn()}
            onEffortChange={vi.fn()}
          />
        </Wrapper>,
      )
    })
    const baixoBtn = await screen.findByRole('button', { name: 'Baixo' })
    const medioBtn = await screen.findByRole('button', { name: 'Médio' })
    const altoBtn = await screen.findByRole('button', { name: 'Alto' })
    expect(baixoBtn).toBeInTheDocument()
    expect(medioBtn).toBeInTheDocument()
    expect(altoBtn).toBeInTheDocument()
    expect(medioBtn).toHaveAttribute('data-active', 'true')
    expect(baixoBtn).toHaveAttribute('data-active', 'false')
    expect(altoBtn).toHaveAttribute('data-active', 'false')
  })

  it('clicking a different effort button calls onEffortChange with new value', async () => {
    const onEffortChange = vi.fn()
    const { Wrapper } = makeWrapper()
    await act(async () => {
      render(
        <Wrapper>
          <ProviderEffortPicker
            providerId="claude"
            effort="medium"
            onProviderChange={vi.fn()}
            onEffortChange={onEffortChange}
          />
        </Wrapper>,
      )
    })
    const altoBtn = await screen.findByRole('button', { name: 'Alto' })
    fireEvent.click(altoBtn)
    expect(onEffortChange).toHaveBeenCalledWith('high')
  })

  it('changing provider via ProviderSelector triggers onProviderChange', async () => {
    const onProviderChange = vi.fn()
    const { Wrapper } = makeWrapper()
    await act(async () => {
      render(
        <Wrapper>
          <ProviderEffortPicker
            providerId="claude"
            effort="low"
            onProviderChange={onProviderChange}
            onEffortChange={vi.fn()}
          />
        </Wrapper>,
      )
    })
    // Wait for providers to load, then find the llamacpp radio button by role and click it
    // Radix RadioGroup.Item renders as role="radio" with accessible name from its label
    await screen.findByText('Llama.cpp (local)')
    const radios = screen.getAllByRole('radio')
    // radios[0] = claude (current), radios[1] = llamacpp
    fireEvent.click(radios[1])
    expect(onProviderChange).toHaveBeenCalledWith('llamacpp')
  })
})
