/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor, within } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { ReactNode } from 'react'

import { ProjectDetail } from '../../../pages/ProjectDetail'
import { useRunStore, PIPELINE_STAGES } from '../../../stores/useRunStore'

// ---------------------------------------------------------------------------
// EventSource polyfill — jsdom does not implement EventSource. This in-memory
// shim lets the test inject SSE messages synchronously via instance.emit().
// ---------------------------------------------------------------------------

interface FakeEventSourceCtor {
  new (url: string): FakeEventSource
  instances: FakeEventSource[]
}

class FakeEventSource {
  static instances: FakeEventSource[] = []
  url: string
  readyState = 1
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    ;(this.constructor as unknown as FakeEventSourceCtor).instances.push(this)
  }

  emit(data: unknown) {
    if (this.closed) return
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent)
  }

  emitRaw(raw: string) {
    if (this.closed) return
    this.onmessage?.({ data: raw } as MessageEvent)
  }

  triggerError() {
    this.onerror?.(new Event('error'))
  }

  close() {
    this.closed = true
    this.readyState = 2
  }
}

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

const PROJECT_FIXTURE = {
  id: 'p1',
  name: 'Iberia 868',
  country_qid: 'Q29',
  period_start: 868,
  period_end: 900,
  bbox_lon_min: null,
  bbox_lon_max: null,
  bbox_lat_min: null,
  bbox_lat_max: null,
  generator_config: null,
  status: 'created',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const STATUS_EMPTY = {
  status: 'created',
  has_artifacts: {
    'territory_metadata.json': false,
    'lookup_condado.png': false,
    'lookup_barony.png': false,
  },
  last_generated_at: null,
}

const STATUS_GENERATED = {
  status: 'generated',
  has_artifacts: {
    'territory_metadata.json': true,
    'lookup_condado.png': true,
    'lookup_barony.png': true,
  },
  last_generated_at: '2026-01-02T00:00:00Z',
}

interface MockFetchOpts {
  status?: typeof STATUS_EMPTY
  generateOk?: boolean
  generateBody?: { run_id?: string; status?: string }
  generateStatus?: number
}

function installFetchMock(opts: MockFetchOpts = {}) {
  const status = opts.status ?? STATUS_EMPTY
  const generateOk = opts.generateOk ?? true
  const generateBody = opts.generateBody ?? { run_id: 'r-server-1', status: 'scheduled' }
  const fetchMock = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/v3/projects/') && u.endsWith('/status')) {
      return new Response(JSON.stringify(status), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }
    if (u.includes('/api/projects/') && !u.includes('/api/v3/')) {
      // useProject(id) -> /api/projects/p1
      return new Response(JSON.stringify(PROJECT_FIXTURE), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }
    if (u.endsWith('/generate') && init?.method === 'POST') {
      if (!generateOk) {
        return new Response('boom', {
          status: opts.generateStatus ?? 500,
        })
      }
      return new Response(JSON.stringify(generateBody), {
        status: 202,
        headers: { 'content-type': 'application/json' },
      })
    }
    // Default: 404 to surface unexpected calls.
    return new Response(JSON.stringify({ detail: `unmocked ${u}` }), { status: 404 })
  })
  ;(globalThis as any).fetch = fetchMock
  return fetchMock
}

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <Theme>
          <MemoryRouter initialEntries={['/projects/p1']}>
            <Routes>
              <Route path="/projects/:id" element={children} />
            </Routes>
          </MemoryRouter>
        </Theme>
      </QueryClientProvider>
    )
  }
}

// CanvasViewer is heavy + Konva — stub it to a marker div.
vi.mock('../../canvas/CanvasViewer', () => ({
  CanvasViewer: ({ projectId, cacheVersion }: { projectId: string; cacheVersion?: string }) => (
    <div data-testid="canvas-viewer" data-project-id={projectId} data-cache-version={cacheVersion} />
  ),
}))

beforeEach(() => {
  FakeEventSource.instances = []
  ;(globalThis as any).EventSource = FakeEventSource as unknown as typeof EventSource
  useRunStore.getState().reset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProjectDetail workspace shell', () => {
  it('renders EmptyCanvasState when status=created and no artifacts', async () => {
    installFetchMock({ status: STATUS_EMPTY })
    const Wrapper = makeWrapper()
    render(
      <Wrapper>
        <ProjectDetail />
      </Wrapper>,
    )
    await waitFor(() => {
      expect(screen.getByTestId('empty-canvas-state')).toBeInTheDocument()
    })
    expect(within(screen.getByTestId('workspace-toolbar')).getByRole('button', { name: 'Gerar Mapa' })).toBeEnabled()
  })

  it('clicking "Gerar Mapa" POSTs /generate and starts run state', async () => {
    const fetchMock = installFetchMock({ status: STATUS_EMPTY })
    const Wrapper = makeWrapper()
    render(
      <Wrapper>
        <ProjectDetail />
      </Wrapper>,
    )
    await waitFor(() => screen.getByTestId('empty-canvas-state'))

    fireEvent.click(within(screen.getByTestId('workspace-toolbar')).getByRole('button', { name: 'Gerar Mapa' }))

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map((c) => String(c[0]))
      expect(calls.some((u) => u.endsWith('/generate'))).toBe(true)
    })
    await waitFor(() => {
      expect(useRunStore.getState().state).toBe('generating')
    })
    expect(useRunStore.getState().runId).toBe('r-server-1')
    expect(FakeEventSource.instances.length).toBeGreaterThan(0)
    expect(FakeEventSource.instances[0].url).toContain('/api/v3/projects/p1/generate/stream')
  })

  it('SSE flow: started + stage_start/done + done -> generated state with completed stage', async () => {
    installFetchMock({ status: STATUS_EMPTY })
    const Wrapper = makeWrapper()
    render(
      <Wrapper>
        <ProjectDetail />
      </Wrapper>,
    )
    await waitFor(() => screen.getByTestId('empty-canvas-state'))
    fireEvent.click(within(screen.getByTestId('workspace-toolbar')).getByRole('button', { name: 'Gerar Mapa' }))
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0))
    const es = FakeEventSource.instances[0]

    act(() => {
      es.emit({ event_type: 'started', stage: null, message: '' })
      es.emit({ event_type: 'stage_start', stage: 'voronoi', message: '' })
      es.emit({ event_type: 'stage_done', stage: 'voronoi', message: '' })
    })
    expect(useRunStore.getState().completedStages).toContain('voronoi')
    expect(useRunStore.getState().state).toBe('generating')

    act(() => {
      es.emit({ event_type: 'done', stage: null, message: 'all done' })
    })
    expect(useRunStore.getState().state).toBe('generated')
    expect(es.closed).toBe(true)
  })

  it('SSE error event renders ErrorCanvasCallout; retry re-POSTs /generate', async () => {
    const fetchMock = installFetchMock({ status: STATUS_EMPTY })
    const Wrapper = makeWrapper()
    render(
      <Wrapper>
        <ProjectDetail />
      </Wrapper>,
    )
    await waitFor(() => screen.getByTestId('empty-canvas-state'))
    fireEvent.click(within(screen.getByTestId('workspace-toolbar')).getByRole('button', { name: 'Gerar Mapa' }))
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0))
    const es = FakeEventSource.instances[0]

    act(() => {
      es.emit({
        event_type: 'error',
        stage: 'voronoi',
        message: 'PipelineError: KD-tree empty',
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('error-canvas-callout')).toBeInTheDocument()
    })
    expect(screen.getByText(/Falha no estágio: voronoi/)).toBeInTheDocument()

    const callsBefore = fetchMock.mock.calls.filter((c) => String(c[0]).endsWith('/generate')).length
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    await waitFor(() => {
      const callsAfter = fetchMock.mock.calls.filter((c) => String(c[0]).endsWith('/generate')).length
      expect(callsAfter).toBe(callsBefore + 1)
    })
  })

  it('renders CanvasViewer when status=generated and territory_metadata.json present', async () => {
    installFetchMock({ status: STATUS_GENERATED })
    const Wrapper = makeWrapper()
    render(
      <Wrapper>
        <ProjectDetail />
      </Wrapper>,
    )
    await waitFor(() => {
      expect(screen.getByTestId('canvas-viewer')).toBeInTheDocument()
    })
    const viewer = screen.getByTestId('canvas-viewer')
    expect(viewer.getAttribute('data-project-id')).toBe('p1')
    expect(viewer.getAttribute('data-cache-version')).toBe(PROJECT_FIXTURE.updated_at)
  })

  it('on unmount, EventSource.close() is called', async () => {
    installFetchMock({ status: STATUS_EMPTY })
    const Wrapper = makeWrapper()
    const { unmount } = render(
      <Wrapper>
        <ProjectDetail />
      </Wrapper>,
    )
    await waitFor(() => screen.getByTestId('empty-canvas-state'))
    fireEvent.click(within(screen.getByTestId('workspace-toolbar')).getByRole('button', { name: 'Gerar Mapa' }))
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0))
    const es = FakeEventSource.instances[0]
    expect(es.closed).toBe(false)
    unmount()
    expect(es.closed).toBe(true)
  })

  it('ProjectDetail.tsx file is < 280 LOC (vs 697 baseline)', () => {
    const file = resolve(__dirname, '../../../pages/ProjectDetail.tsx')
    const lineCount = readFileSync(file, 'utf8').split('\n').length
    expect(lineCount).toBeLessThan(280)
  })

  it('ProjectDetail.tsx contains zero references to deleted v1 modules', () => {
    const file = resolve(__dirname, '../../../pages/ProjectDetail.tsx')
    const src = readFileSync(file, 'utf8')
    const forbidden = [
      'useEditorStore',
      'usePipelineStore',
      'useResearchStore',
      'useValidationStore',
      'useProjectStore',
      'EditToolbar',
      'SplitTool',
      'VertexHandlesLayer',
      'TerritoryEditor',
      'TerrainBadgesLayer',
      'SaveStatusIndicator',
      'ResearchDialog',
      'AssignmentEditor',
      'CodexViewer',
      'Stepper',
      'StepCard',
      'ProviderEffortPicker',
      'TerrainDataSection',
      'BaronyGranularitySlider',
    ]
    for (const sym of forbidden) {
      expect(src).not.toContain(sym)
    }
  })

  it('ProjectDetail wires EventSource to /generate/stream and useRunStore (sanity)', () => {
    const file = resolve(__dirname, '../../../pages/ProjectDetail.tsx')
    const src = readFileSync(file, 'utf8')
    expect(src).toContain('/api/v3/projects/')
    expect(src).toMatch(/useRunStore/)
    expect(src).toMatch(/useGenerateStream/)
  })

  // Sanity: PIPELINE_STAGES is what RunLogPanel renders against
  it('PIPELINE_STAGES has 11 entries', () => {
    expect(PIPELINE_STAGES).toHaveLength(11)
  })
})
