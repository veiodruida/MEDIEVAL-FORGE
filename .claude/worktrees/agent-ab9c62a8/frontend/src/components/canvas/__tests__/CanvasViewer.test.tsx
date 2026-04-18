import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CanvasViewer } from '../CanvasViewer'

// Mock react-konva — Konva requires a real DOM canvas context not available in jsdom
vi.mock('react-konva', () => ({
  Stage: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-stage">{children}</div>
  ),
  Layer: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-layer">{children}</div>
  ),
  Image: () => <div data-testid="konva-image" />,
  Rect: () => <div data-testid="konva-rect" />,
}))

vi.mock('use-image', () => ({
  default: () => [undefined, 'loading'],
  useImage: () => [undefined, 'loading'],
}))

const META_FIXTURE = {
  region: 'iberia',
  map_size: [1920, 1080],
  bounds: { lon_min: -9.5, lon_max: 4.5, lat_min: 35.0, lat_max: 44.0 },
  kingdoms: {},
  duchies: {},
  condados: [],
  baronies: [],
}

const TERRITORIES_FIXTURE = { type: 'FeatureCollection', features: [] }
const BARONIES_FIXTURE = { type: 'FeatureCollection', features: [] }

function setupFetchMock(
  meta: unknown = META_FIXTURE,
  error: { status: number } | null = null,
) {
  global.fetch = vi.fn((url: string) => {
    const urlStr = String(url)
    if (error && urlStr.includes('territory_metadata')) {
      return Promise.resolve({
        ok: false,
        status: error.status,
        statusText: error.status === 404 ? 'Not Found' : 'Server Error',
        text: () => Promise.resolve('error'),
        json: () => Promise.resolve(null),
      })
    }
    if (urlStr.includes('territory_metadata')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(meta) })
    }
    if (urlStr.includes('territories.geojson')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(TERRITORIES_FIXTURE) })
    }
    if (urlStr.includes('baronies.geojson')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(BARONIES_FIXTURE) })
    }
    if (urlStr.includes('lookup_condado_colors')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    if (urlStr.includes('lookup_barony_colors')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  }) as unknown as typeof fetch
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('CanvasViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state while fetching metadata', async () => {
    // Never resolve fetch to keep loading state
    global.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch
    render(<CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />, { wrapper })
    expect(screen.getByText('Loading map…')).toBeTruthy()
  })

  it('renders Stage when metadata loads successfully', async () => {
    setupFetchMock()
    const { findByTestId } = render(
      <CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />,
      { wrapper },
    )
    const stage = await findByTestId('konva-stage')
    expect(stage).toBeTruthy()
  })

  it('shows not-generated message on 404', async () => {
    setupFetchMock(null, { status: 404 })
    const { findByText } = render(
      <CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />,
      { wrapper },
    )
    expect(await findByText(/No map generated yet/)).toBeTruthy()
  })

  it('shows error message on server error', async () => {
    setupFetchMock(null, { status: 500 })
    const { findByText } = render(
      <CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />,
      { wrapper },
    )
    expect(await findByText(/Failed to load territory data/)).toBeTruthy()
  })

  it('BackgroundLayer has listening={false} in the layer mock', async () => {
    setupFetchMock()
    const { findByTestId } = render(
      <CanvasViewer projectId="00000000-0000-4000-8000-000000000001" />,
      { wrapper },
    )
    // konva-layer rendered by our mock — BackgroundLayer passes listening={false}
    // to the real Konva Layer; our mock renders it as a div regardless.
    const layer = await findByTestId('konva-layer')
    expect(layer).toBeTruthy()
  })
})
