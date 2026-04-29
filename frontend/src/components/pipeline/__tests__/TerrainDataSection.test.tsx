/**
 * RED tests for TerrainDataSection + useTerrainStepStream.
 *
 * 7 tests covering:
 *  - render contract (collapsed by default, header badge, expansion, 4 step cards)
 *  - ridge slider (low/med/high selector)
 *  - initial status badges (pendente)
 *  - interaction: run button calls POST endpoint
 *  - interaction: stop button appears while running, calls stop endpoint
 *  - shared SSE log panel streams active step lines
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import React from 'react'
import { Theme } from '@radix-ui/themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TerrainDataSection } from '../TerrainDataSection'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <Theme>{children}</Theme>
    </QueryClientProvider>
  )
  return Wrapper
}

function makeSSEResponse(lines: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      for (const l of lines) controller.enqueue(encoder.encode(`data: ${l}\n\n`))
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

/** Never-resolving SSE stream (simulates ongoing run) */
function makeInfiniteSSEResponse(): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      // Emit one line to show rodando state, then block forever
      controller.enqueue(encoder.encode('data: running...\n\n'))
      // never calls controller.close() — simulates infinite stream
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TerrainDataSection', () => {
  let originalFetch: typeof globalThis.fetch

  beforeEach(() => {
    originalFetch = globalThis.fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  // -------------------------------------------------------------------------
  // Render contract
  // -------------------------------------------------------------------------

  it('renders collapsed by default with header badge showing 0/4 datasets prontos', () => {
    const Wrapper = makeWrapper()
    render(<TerrainDataSection projectId="abc" />, { wrapper: Wrapper })

    // Header heading must be visible
    expect(screen.getByText('Terrain Data')).toBeInTheDocument()

    // Badge must show 0/4 datasets prontos
    expect(screen.getByText(/0\/4 datasets prontos/)).toBeInTheDocument()

    // Step cards must NOT be in the DOM when collapsed
    expect(screen.queryByText('Overpass terrain')).not.toBeInTheDocument()
    expect(screen.queryByText('HydroSHEDS basins')).not.toBeInTheDocument()
    expect(screen.queryByText('DEM (Copernicus)')).not.toBeInTheDocument()
    expect(screen.queryByText('Ridges (derive)')).not.toBeInTheDocument()
  })

  it('expands on header click revealing four step cards', () => {
    const Wrapper = makeWrapper()
    render(<TerrainDataSection projectId="abc" />, { wrapper: Wrapper })

    // Click the trigger to expand
    const trigger = screen.getByRole('button', { name: /Expandir Terrain Data/i })
    fireEvent.click(trigger)

    // All 4 step card titles must be visible
    expect(screen.getByText('Overpass terrain')).toBeInTheDocument()
    expect(screen.getByText('HydroSHEDS basins')).toBeInTheDocument()
    expect(screen.getByText('DEM (Copernicus)')).toBeInTheDocument()
    expect(screen.getByText('Ridges (derive)')).toBeInTheDocument()
  })

  it('ridge card has a low/med/high selector inside the Ridges card', () => {
    const Wrapper = makeWrapper()
    render(<TerrainDataSection projectId="abc" />, { wrapper: Wrapper })

    // Expand
    const trigger = screen.getByRole('button', { name: /Expandir Terrain Data/i })
    fireEvent.click(trigger)

    // The ridge-sensitivity-slider test-id should be present
    const slider = screen.getByTestId('ridge-sensitivity-slider')
    expect(slider).toBeInTheDocument()

    // The three options should be visible inside the selector area
    expect(within(slider).getByText('low')).toBeInTheDocument()
    expect(within(slider).getByText('med')).toBeInTheDocument()
    expect(within(slider).getByText('high')).toBeInTheDocument()
  })

  it('each step card shows "pendente" badge initially', () => {
    const Wrapper = makeWrapper()
    render(<TerrainDataSection projectId="abc" />, { wrapper: Wrapper })

    // Expand
    const trigger = screen.getByRole('button', { name: /Expandir Terrain Data/i })
    fireEvent.click(trigger)

    // Exactly 4 "pendente" badges
    const badges = screen.getAllByText('pendente')
    expect(badges).toHaveLength(4)
  })

  // -------------------------------------------------------------------------
  // Interaction contract
  // -------------------------------------------------------------------------

  it('clicking run on Overpass calls POST /api/projects/abc/terrain/overpass', async () => {
    const Wrapper = makeWrapper()

    // Default fetch mock returning empty SSE response to prevent unhandled rejections
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('/terrain/stop')) {
        return Promise.resolve(new Response('', { status: 200 }))
      }
      return Promise.resolve(makeSSEResponse([]))
    })

    render(<TerrainDataSection projectId="abc" />, { wrapper: Wrapper })

    // Expand
    fireEvent.click(screen.getByRole('button', { name: /Expandir Terrain Data/i }))

    // Get the Overpass card section and click its run button
    // Cards are rendered in order: overpass, hydrosheds, dem, ridges
    // getAllByRole('button', { name: 'Executar' })[0] is overpass
    const runButtons = screen.getAllByRole('button', { name: 'Executar' })
    fireEvent.click(runButtons[0])

    // Assert fetch called with the overpass endpoint
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/projects\/abc\/terrain\/overpass$/),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('running step shows Parar button and calls stop endpoint', async () => {
    const Wrapper = makeWrapper()

    // Track calls per URL
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('/terrain/stop')) {
        return Promise.resolve(new Response('', { status: 200 }))
      }
      if (typeof url === 'string' && url.includes('/terrain/hydrosheds')) {
        return Promise.resolve(makeInfiniteSSEResponse())
      }
      return Promise.resolve(makeSSEResponse([]))
    })

    render(<TerrainDataSection projectId="abc" />, { wrapper: Wrapper })

    // Expand
    fireEvent.click(screen.getByRole('button', { name: /Expandir Terrain Data/i }))

    // Click run on hydrosheds (index 1 — second card)
    const runButtons = screen.getAllByRole('button', { name: 'Executar' })
    fireEvent.click(runButtons[1])

    // "Parar ingestão" should appear and status badge should become "rodando"
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Parar ingestão' })).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText('rodando')).toBeInTheDocument()
    })

    // Click stop
    fireEvent.click(screen.getByRole('button', { name: 'Parar ingestão' }))

    // Assert stop endpoint was called
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/projects\/abc\/terrain\/stop\?step=hydrosheds/),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('shared log panel displays active step SSE lines', async () => {
    const Wrapper = makeWrapper()

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('/terrain/stop')) {
        return Promise.resolve(new Response('', { status: 200 }))
      }
      if (typeof url === 'string' && url.includes('/terrain/dem')) {
        return Promise.resolve(makeSSEResponse(['linha 1', 'linha 2']))
      }
      return Promise.resolve(makeSSEResponse([]))
    })

    render(<TerrainDataSection projectId="abc" />, { wrapper: Wrapper })

    // Expand
    fireEvent.click(screen.getByRole('button', { name: /Expandir Terrain Data/i }))

    // Click run on DEM (index 2 — third card)
    const runButtons = screen.getAllByRole('button', { name: 'Executar' })
    fireEvent.click(runButtons[2])

    // The shared log panel should contain both lines
    const logPanel = await screen.findByTestId('terrain-shared-log')
    await waitFor(() => {
      expect(logPanel).toHaveTextContent('linha 1')
      expect(logPanel).toHaveTextContent('linha 2')
    })
  })
})
