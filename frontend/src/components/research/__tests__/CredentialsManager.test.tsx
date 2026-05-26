/**
 * CredentialsManager tests — Phase 07.2 consolidation.
 *
 * Covers the .env auto-discover + per-provider key edit flow added when
 * the cloud-provider work (OpenRouter / OpenAI / Gemini) shipped. The
 * GET /api/v3/credentials response never carries raw key material — the
 * tests must reflect that contract.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CredentialsManager } from '../CredentialsManager'

const STATUS_ROWS = [
  {
    provider_id: 'openrouter',
    display_name: 'OpenRouter (free + paid)',
    configured: false,
    has_key: false,
    source: 'none',
    env_var: 'OPENROUTER_API_KEY',
    accepts_api_key: true,
  },
  {
    provider_id: 'openai',
    display_name: 'OpenAI (paid)',
    configured: true,
    has_key: true,
    source: 'db',
    env_var: 'OPENAI_API_KEY',
    accepts_api_key: true,
  },
  {
    provider_id: 'ollama',
    display_name: 'Ollama (local)',
    configured: true,
    has_key: false,
    source: 'env',
    env_var: null,
    accepts_api_key: false, // dropped from the rendered list
  },
]

function wrap(open = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Theme>
        <CredentialsManager open={open} onOpenChange={() => {}} />
      </Theme>
    </QueryClientProvider>,
  )
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('CredentialsManager', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists only providers that accept an API key', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    wrap(true)
    await waitFor(() => {
      expect(screen.getByTestId('credential-row-openrouter')).toBeInTheDocument()
    })
    expect(screen.getByTestId('credential-row-openai')).toBeInTheDocument()
    expect(screen.queryByTestId('credential-row-ollama')).toBeNull()
  })

  it('renders the correct source badge per provider', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    wrap(true)
    await waitFor(() =>
      expect(screen.getByTestId('credential-row-openrouter')).toBeInTheDocument(),
    )
    // openrouter -> source 'none' -> "Não configurada"
    expect(screen.getByText(/Não configurada/i)).toBeInTheDocument()
    // openai -> source 'db' -> "Configurada (DB)"
    expect(screen.getByText(/Configurada \(DB\)/i)).toBeInTheDocument()
  })

  it('disables Salvar until the draft key is long enough', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    wrap(true)
    await waitFor(() =>
      expect(screen.getByTestId('credential-input-openrouter')).toBeInTheDocument(),
    )
    const saveBtn = screen.getByTestId('credential-save-openrouter') as HTMLButtonElement
    expect(saveBtn.disabled).toBe(true)
    const input = screen.getByTestId('credential-input-openrouter')
    fireEvent.change(input, { target: { value: 'sk-real-key-1234' } })
    expect(saveBtn.disabled).toBe(false)
  })

  it('fires PUT /api/v3/credentials/{provider} on Salvar', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    // After save the hook invalidates the list query and refetches.
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ok: true, provider_id: 'openrouter' }),
    )
    fetchMock.mockResolvedValue(jsonResponse(STATUS_ROWS))
    wrap(true)
    await waitFor(() =>
      expect(screen.getByTestId('credential-input-openrouter')).toBeInTheDocument(),
    )
    const input = screen.getByTestId('credential-input-openrouter')
    fireEvent.change(input, { target: { value: 'sk-test-1234' } })
    fireEvent.click(screen.getByTestId('credential-save-openrouter'))
    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        ([url, opts]) =>
          url === '/api/v3/credentials/openrouter' && opts?.method === 'PUT',
      )
      expect(putCall).toBeTruthy()
      const body = JSON.parse(putCall![1].body as string)
      expect(body).toEqual({ key: 'sk-test-1234' })
    })
  })

  it('fires DELETE only when provider source is db', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    wrap(true)
    await waitFor(() =>
      expect(screen.getByTestId('credential-row-openai')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('credential-delete-openai')).toBeInTheDocument()
    expect(screen.queryByTestId('credential-delete-openrouter')).toBeNull()
  })

  it('imports the pasted .env via POST /api/v3/credentials/import', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        imported: ['openrouter', 'gemini'],
        skipped: ['SOME_UNKNOWN'],
        known_env_vars: ['OPENROUTER_API_KEY', 'GOOGLE_API_KEY'],
      }),
    )
    fetchMock.mockResolvedValue(jsonResponse(STATUS_ROWS))
    wrap(true)
    await waitFor(() =>
      expect(screen.getByTestId('credentials-env-text')).toBeInTheDocument(),
    )
    const textarea = screen.getByTestId('credentials-env-text')
    fireEvent.change(textarea, {
      target: { value: 'OPENROUTER_API_KEY=abc\nGOOGLE_API_KEY=def' },
    })
    fireEvent.click(screen.getByTestId('credentials-import-button'))
    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        ([url, opts]) =>
          url === '/api/v3/credentials/import' && opts?.method === 'POST',
      )
      expect(postCall).toBeTruthy()
    })
    await waitFor(() => {
      // Text spans multiple DOM nodes (<strong>2</strong> chaves importadas: …)
      // so match by joined textContent rather than getByText.
      const callout = document.querySelector('[data-accent-color="green"]')
      expect(callout?.textContent ?? '').toMatch(
        /2\s*chaves importadas:?\s*openrouter,?\s*gemini/i,
      )
    })
  })

  it('runs the auto-discover and surfaces the imported keys', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        imported: ['openrouter'],
        paths_checked: ['/home/u/.env'],
        paths_with_keys: ['/home/u/.env'],
      }),
    )
    fetchMock.mockResolvedValue(jsonResponse(STATUS_ROWS))
    wrap(true)
    await waitFor(() =>
      expect(screen.getByTestId('credentials-discover-button')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('credentials-discover-button'))
    await waitFor(() => {
      const getCall = fetchMock.mock.calls.find(
        ([url]) => url === '/api/v3/credentials/discover',
      )
      expect(getCall).toBeTruthy()
    })
    await waitFor(() =>
      expect(
        screen.getByText(/Importadas 1 chave: openrouter/i),
      ).toBeInTheDocument(),
    )
  })

  it('reports zero-imports outcome when no .env file yields new keys', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_ROWS))
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        imported: [],
        paths_checked: ['/home/u/.env', '/home/u/.medieval-forge/.env'],
        paths_with_keys: [],
      }),
    )
    wrap(true)
    await waitFor(() =>
      expect(screen.getByTestId('credentials-discover-button')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('credentials-discover-button'))
    await waitFor(() =>
      expect(
        screen.getByText(/Nenhuma chave nova encontrada/i),
      ).toBeInTheDocument(),
    )
  })
})
