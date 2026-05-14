import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InspectorSidebar } from '../InspectorSidebar'
import { useUIStore } from '../../../stores/uiStore'
import type {
  BaronyRender,
  TerritoryMetadata,
  TerritoryRender,
} from '../../../hooks/useCanvasArtifacts'

// Plan 07-09b — mock useResearchOverlay so tests can assert microcopy variants
// without booting a real fetch chain. The default `useResearchOverlayMock` is
// reassigned per-suite via `vi.hoisted`.
const { useResearchOverlayMock } = vi.hoisted(() => ({
  useResearchOverlayMock: vi.fn(),
}))
vi.mock('../../../api/useResearchOverlay', () => ({
  useResearchOverlay: (...args: unknown[]) => useResearchOverlayMock(...args),
}))

// Plan 07-09b — silence ResearchDialog internals so InspectorSidebar tests
// stay focused on the trigger / microcopy / badge / reopen behavior.
vi.mock('../../research/ResearchDialog', () => ({
  ResearchDialog: ({ open, initialForceRefresh }: { open: boolean; initialForceRefresh?: boolean }) =>
    open ? (
      <div
        data-testid="research-dialog-mock"
        data-force-refresh={initialForceRefresh ? 'true' : 'false'}
      />
    ) : null,
}))

const META: TerritoryMetadata = {
  region: 'iberia',
  map_size: [2000, 1600],
  bounds: { lon_min: -10, lon_max: 0, lat_min: 40, lat_max: 50 },
  kingdoms: { K_LEON: 'Reino de León' },
  duchies: { D_GALICIA: { kingdom: 'K_LEON', name: 'Ducado de Galicia' } },
  condados: [
    {
      id: 'C_CORUNA',
      name: 'Coruña',
      lon: -8.41,
      lat: 43.37,
      duchy: 'D_GALICIA',
      kingdom: 'K_LEON',
      pixel_center: [100, 100],
      pixel_count: 1000,
      baronies: ['B_BETANZOS', 'B_CORUNA'],
      neighbors: ['C_LUGO', 'C_BETANZOS'],
    },
    {
      id: 'C_LUGO',
      name: 'Lugo',
      lon: -7.55,
      lat: 43.01,
      duchy: 'D_GALICIA',
      kingdom: 'K_LEON',
      pixel_center: [200, 100],
      pixel_count: 800,
      baronies: ['B_LUGO'],
      neighbors: ['C_CORUNA'],
    },
  ],
  baronies: [
    { name: 'B_BETANZOS', condado_idx: 0, duchy: 'D_GALICIA', pixel_count: 500 },
    { name: 'B_CORUNA', condado_idx: 0, duchy: 'D_GALICIA', pixel_count: 500 },
    { name: 'B_LUGO', condado_idx: 1, duchy: 'D_GALICIA', pixel_count: 800 },
  ],
}

const TERRITORIES: TerritoryRender[] = [
  {
    id: 'C_CORUNA',
    name: 'Coruña',
    points: [0, 0, 10, 0, 10, 10, 0, 10],
    neighbors: ['C_LUGO', 'C_BETANZOS'],
  },
  {
    id: 'C_LUGO',
    name: 'Lugo',
    points: [10, 0, 20, 0, 20, 10, 10, 10],
    neighbors: ['C_CORUNA'],
  },
]

// D-03 (Phase 04.1): default BaronyRender fixture used by every InspectorSidebar
// render call so the new `baronies` prop is satisfied. The dedicated barony-mode
// describe block at the bottom of the file supplies its own per-test variant.
const BARONIES: BaronyRender[] = [
  {
    id: 'B_BETANZOS',
    name: 'B_BETANZOS',
    condado_id: 'C_CORUNA',
    fill: '#aabbcc',
    points: [0, 0, 5, 0, 5, 5, 0, 5],
    centroid: [-8.213, 43.282],
  },
  {
    id: 'B_CORUNA',
    name: 'B_CORUNA',
    condado_id: 'C_CORUNA',
    fill: '#bbccdd',
    points: [5, 0, 10, 0, 10, 5, 5, 5],
    centroid: [-8.412, 43.371],
  },
  {
    id: 'B_LUGO',
    name: 'B_LUGO',
    condado_id: 'C_LUGO',
    fill: '#ccddee',
    points: [10, 0, 20, 0, 20, 10, 10, 10],
    centroid: [-7.554, 43.012],
  },
]

const PROJECT = {
  id: 'proj-1',
  name: 'Reconquista 868',
  country_qid: 'Q29',
  period_start: 868,
  period_end: 900,
  status: 'generated',
}

function makeQc() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  })
}

function wrap(node: React.ReactNode) {
  return (
    <QueryClientProvider client={makeQc()}>
      <Theme>{node}</Theme>
    </QueryClientProvider>
  )
}

// Default overlay: no research applied. Each Plan 07-09b suite overrides
// per-test via `useResearchOverlayMock.mockReturnValue(...)`.
beforeEach(() => {
  useResearchOverlayMock.mockReturnValue({
    data: { exists: false, covered_condado_ids: [], meta: null },
  })
})

describe('InspectorSidebar — placeholder (D-16, no selection)', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: [],
      selectedTerritoryId: null,
      selectedBaronyId: null,
      layerVisibility: {
        condados: true,
        baronies: false,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('renders the PT-BR placeholder when selection is empty', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.getByText('Clique num território para ver detalhes')).toBeInTheDocument()
  })

  it('does NOT render the project-overview hierarchy when selection is empty (replaced by D-16)', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.queryByText('Project overview')).toBeNull()
    expect(screen.queryByText('Kingdoms')).toBeNull()
  })
})

describe('InspectorSidebar — multi-select (D-17, length >= 2)', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: ['C_CORUNA', 'C_LUGO'],
      selectedTerritoryId: 'C_CORUNA',
      selectedBaronyId: null,
      layerVisibility: {
        condados: true,
        baronies: false,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('dispatches MultiSelectInspector when 2+ territories are selected', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.getByText('2 condados selecionados')).toBeInTheDocument()
    // Single-select copy must NOT appear
    expect(screen.queryByText('Path:')).toBeNull()
    expect(screen.queryByText('Centroid')).toBeNull()
  })
})

describe('InspectorSidebar — territory detail (D-06.3 capital sentinel)', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: ['C_CORUNA'],
      selectedTerritoryId: 'C_CORUNA',
      selectedBaronyId: null,
      layerVisibility: {
        condados: true,
        baronies: false,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('renders the capital city name when capital_name is present (D-06.3 positive)', () => {
    const metaWithCapital: TerritoryMetadata = {
      ...META,
      condados: [{ ...META.condados[0], capital_name: 'A Coruña' }, META.condados[1]] as never,
    }
    render(
      wrap(
        <InspectorSidebar
          metadata={metaWithCapital}
          territories={TERRITORIES}
          baronies={BARONIES}
          project={PROJECT}
        />,
      ),
    )
    expect(screen.getByText('A Coruña')).toBeInTheDocument()
    expect(screen.queryByText('No capital assigned')).toBeNull()
  })

  it('falls back to condado name when capital_name is absent', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    // condado name "Coruña" is used as fallback capital display (not sentinel text)
    expect(screen.queryByText('No capital assigned')).toBeNull()
  })

  it('falls back to condado name when capital_name is empty/whitespace', () => {
    const metaEmpty: TerritoryMetadata = {
      ...META,
      condados: [{ ...META.condados[0], capital_name: '   ' }, META.condados[1]] as never,
    }
    render(
      wrap(<InspectorSidebar metadata={metaEmpty} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.queryByText('No capital assigned')).toBeNull()
  })

  it('heading shows selected territory name', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    // Two places could show "Coruña" (heading + Path:); use role to disambiguate
    expect(screen.getByRole('heading', { name: /Coruña/ })).toBeInTheDocument()
  })

  it('renders 4 labeled group rows: Path, Area, Centroid, Capital, Adjacent territories', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.getByText(/Path:/)).toBeInTheDocument()
    expect(screen.getByText(/Area/)).toBeInTheDocument()
    expect(screen.getByText('Centroid')).toBeInTheDocument()
    expect(screen.getByText('Capital')).toBeInTheDocument()
    expect(screen.getByText('Adjacent territories')).toBeInTheDocument()
  })
})

describe('InspectorSidebar — neighbor chips', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: ['C_CORUNA'],
      selectedTerritoryId: 'C_CORUNA',
      selectedBaronyId: null,
      layerVisibility: {
        condados: true,
        baronies: false,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('renders a chip for each neighbor and dispatches select(neighborId) on click', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    const lugoChip = screen.getByTestId('neighbor-chip-C_LUGO')
    expect(lugoChip).toBeInTheDocument()
    fireEvent.click(lugoChip)
    expect(useUIStore.getState().selectedTerritoryId).toBe('C_LUGO')
  })

  it('shows "No adjacent territories" when neighbors is empty', () => {
    const metaNoNeighbors: TerritoryMetadata = {
      ...META,
      condados: [
        { ...META.condados[0], neighbors: [] },
        META.condados[1],
      ],
    }
    render(
      wrap(
        <InspectorSidebar
          metadata={metaNoNeighbors}
          territories={TERRITORIES}
          baronies={BARONIES}
          project={PROJECT}
        />,
      ),
    )
    expect(screen.getByText('No adjacent territories')).toBeInTheDocument()
  })
})

// D-03 (Phase 04.1): barony historical discoverability panel.
// Five test cases mandated by 04.1-04-PLAN.md Task 2 <behavior>:
//   1. existing hierarchy badges still render (regression guard)
//   2. source coordinate row renders to 3-decimal precision
//   3. source file label renders literal 'inicio/territory_data_v3.py'
//   4. collapsible 'Sobre o método' PT-BR explainer is present
//   5. fallback '—' placeholder when BaronyRender.centroid is undefined
describe('InspectorSidebar — barony historical discoverability (D-03)', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: [],
      selectedTerritoryId: null,
      selectedBaronyId: 'B_BETANZOS',
      layerVisibility: {
        condados: true,
        baronies: true,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('test_barony_panel_renders_existing_hierarchy_badges_unchanged', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    // Heading shows barony name; 4 hierarchy badges present
    expect(screen.getByRole('heading', { name: /B_BETANZOS/ })).toBeInTheDocument()
    expect(screen.getByText(/Kingdom: Reino de León/)).toBeInTheDocument()
    expect(screen.getByText(/Duchy: Ducado de Galicia/)).toBeInTheDocument()
    expect(screen.getByText(/Condado: Coruña/)).toBeInTheDocument()
    expect(screen.getByText('Barony')).toBeInTheDocument()
  })

  it('test_barony_panel_renders_source_coordinate_to_three_decimals', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    // BARONIES[0].centroid = [-8.213, 43.282] -> displayed as "lat, lon" = "43.282, -8.213"
    const coordEl = screen.getByTestId('barony-source-coord')
    expect(coordEl).toBeInTheDocument()
    expect(coordEl).toHaveTextContent('43.282, -8.213')
    expect(screen.getByText('Coordenada de origem')).toBeInTheDocument()
  })

  it('test_barony_panel_renders_source_file_label_inicio_territory_data_v3_py', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    const fileEl = screen.getByTestId('barony-source-file')
    expect(fileEl).toBeInTheDocument()
    expect(fileEl).toHaveTextContent('inicio/territory_data_v3.py')
    expect(screen.getByText('Origem dos dados')).toBeInTheDocument()
    // Must NOT be a clickable link (D-03 spec — read-only label)
    expect(fileEl.tagName.toLowerCase()).not.toBe('a')
  })

  it('test_barony_panel_renders_collapsible_sobre_o_metodo_explainer_in_pt_br', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    const details = screen.getByTestId('barony-method-explainer')
    expect(details).toBeInTheDocument()
    expect(details.tagName.toLowerCase()).toBe('details')
    // Summary copy
    expect(screen.getByText('Sobre o método')).toBeInTheDocument()
    // PT-BR explainer sentence is in the DOM even when <details> is collapsed
    expect(
      screen.getByText(/As baronias são geradas por Voronoi a partir de centroides históricos/),
    ).toBeInTheDocument()
  })

  it('test_barony_panel_renders_pesquisa_aplicada_badge_when_overlay_covers_parent_condado', () => {
    useResearchOverlayMock.mockReturnValue({
      data: {
        exists: true,
        covered_condado_ids: ['C_CORUNA'],
        meta: {
          provider: 'claude',
          model: 'claude-sonnet-4-6',
          generated_at: '2026-05-14T12:30:00Z',
          applied_at: '2026-05-14T12:30:00Z',
        },
      },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    // Badge text appears for the barony's parent condado C_CORUNA.
    expect(screen.getAllByText('Pesquisa aplicada').length).toBeGreaterThanOrEqual(1)
  })

  it('test_barony_panel_atualizar_pesquisa_link_opens_dialog_with_force_refresh', () => {
    useResearchOverlayMock.mockReturnValue({
      data: {
        exists: true,
        covered_condado_ids: ['C_CORUNA'],
        meta: {
          provider: 'claude',
          model: 'claude-sonnet-4-6',
          generated_at: '2026-05-14T12:30:00Z',
          applied_at: '2026-05-14T12:30:00Z',
        },
      },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    const reopen = screen.getAllByText('Atualizar pesquisa')[0]
    fireEvent.click(reopen)
    const dialog = screen.getByTestId('research-dialog-mock')
    expect(dialog).toBeInTheDocument()
    expect(dialog.getAttribute('data-force-refresh')).toBe('true')
  })

  it('test_barony_panel_falls_back_to_dash_when_centroid_missing', () => {
    // Override the barony fixture: same name selected, but centroid omitted
    const baroniesNoCentroid: BaronyRender[] = [
      {
        id: 'B_BETANZOS',
        name: 'B_BETANZOS',
        condado_id: 'C_CORUNA',
        fill: '#aabbcc',
        points: [0, 0, 5, 0, 5, 5, 0, 5],
        // centroid intentionally omitted (older artifacts on disk pre-Phase 04.1)
      },
    ]
    render(
      wrap(
        <InspectorSidebar
          metadata={META}
          territories={TERRITORIES}
          baronies={baroniesNoCentroid}
          project={PROJECT}
        />,
      ),
    )
    const coordEl = screen.getByTestId('barony-source-coord')
    expect(coordEl).toHaveTextContent('—')
    // No NaN, no "undefined" leak
    expect(coordEl.textContent).not.toContain('undefined')
    expect(coordEl.textContent).not.toContain('NaN')
  })
})

// Plan 07-09b — Research trigger + dual-timestamp microcopy + badges.
// UI-SPEC §Surface 2; REVIEWS fix #2 (generated_at vs applied_at).
describe('InspectorSidebar — Plan 07-09b research trigger (placeholder mode)', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: [],
      selectedTerritoryId: null,
      selectedBaronyId: null,
      layerVisibility: {
        condados: true,
        baronies: false,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('placeholder mode renders the "Pesquisar metadados históricos" trigger button', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    const btn = screen.getByRole('button', { name: /Pesquisar metadados históricos/ })
    expect(btn).toBeInTheDocument()
  })

  it('trigger is disabled and shows the gating tooltip when project.status !== "generated"', () => {
    render(
      wrap(
        <InspectorSidebar
          metadata={META}
          territories={TERRITORIES}
          baronies={BARONIES}
          project={{ ...PROJECT, status: 'pending' }}
        />,
      ),
    )
    const btn = screen.getByRole('button', { name: /Pesquisar metadados históricos/ })
    expect((btn as HTMLButtonElement).disabled).toBe(true)
    // Tooltip body is asserted via the wrapper data-* attribute (Radix Tooltip
    // mounts in a portal lazily; we expose the body via data-tooltip-body so
    // the assertion does not need pointer events).
    expect(screen.getByTestId('research-trigger-tooltip').getAttribute('data-tooltip-body'))
      .toBe('Gere o mapa antes de pesquisar metadados.')
  })

  it('clicking the trigger opens the ResearchDialog without force-refresh pre-checked', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    fireEvent.click(screen.getByRole('button', { name: /Pesquisar metadados históricos/ }))
    const dialog = screen.getByTestId('research-dialog-mock')
    expect(dialog).toBeInTheDocument()
    expect(dialog.getAttribute('data-force-refresh')).toBe('false')
  })

  it('REVIEWS fix #2 — renders SINGLE-LINE microcopy when generated_at === applied_at (fresh run)', () => {
    useResearchOverlayMock.mockReturnValue({
      data: {
        exists: true,
        covered_condado_ids: ['C_CORUNA'],
        meta: {
          provider: 'claude',
          model: 'claude-sonnet-4-6',
          generated_at: '2026-05-14T12:30:00Z',
          applied_at: '2026-05-14T12:30:00Z',
        },
      },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    // Single-line microcopy contains "Última pesquisa:" with provider/model/date.
    const line = screen.getByText((content) =>
      content.startsWith('Última pesquisa:') &&
      content.includes('claude') &&
      content.includes('claude-sonnet-4-6') &&
      content.includes('2026-05-14'),
    )
    expect(line).toBeInTheDocument()
    // Two-line variant MUST NOT appear.
    expect(screen.queryByText((c) => c.startsWith('Pesquisa gerada:'))).toBeNull()
    expect(screen.queryByText((c) => c.startsWith('· aplicada:'))).toBeNull()
  })

  it('REVIEWS fix #2 — renders TWO-LINE microcopy when generated_at differs from applied_at (cache hit)', () => {
    useResearchOverlayMock.mockReturnValue({
      data: {
        exists: true,
        covered_condado_ids: ['C_CORUNA'],
        meta: {
          provider: 'claude',
          model: 'claude-sonnet-4-6',
          generated_at: '2026-05-01T12:00:00Z',
          applied_at: '2026-05-14T15:00:00Z',
        },
      },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.getByText((c) => c.startsWith('Pesquisa gerada:'))).toBeInTheDocument()
    expect(screen.getByText((c) => c.startsWith('· aplicada:'))).toBeInTheDocument()
    // Single-line variant must NOT appear.
    expect(screen.queryByText((c) => c.startsWith('Última pesquisa:'))).toBeNull()
  })

  it('microcopy is ABSENT when overlay.meta is null', () => {
    useResearchOverlayMock.mockReturnValue({
      data: { exists: false, covered_condado_ids: [], meta: null },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.queryByText((c) => c.startsWith('Última pesquisa:'))).toBeNull()
    expect(screen.queryByText((c) => c.startsWith('Pesquisa gerada:'))).toBeNull()
  })
})

describe('InspectorSidebar — Plan 07-09b condado-mode research badge', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: ['C_CORUNA'],
      selectedTerritoryId: 'C_CORUNA',
      selectedBaronyId: null,
      layerVisibility: {
        condados: true,
        baronies: false,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('condado mode renders "Pesquisa aplicada" badge when overlay covers the condado id', () => {
    useResearchOverlayMock.mockReturnValue({
      data: {
        exists: true,
        covered_condado_ids: ['C_CORUNA'],
        meta: {
          provider: 'claude',
          model: 'claude-sonnet-4-6',
          generated_at: '2026-05-14T12:30:00Z',
          applied_at: '2026-05-14T12:30:00Z',
        },
      },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.getByText('Pesquisa aplicada')).toBeInTheDocument()
  })

  it('clicking "Atualizar pesquisa" reopens the dialog with force-refresh pre-checked', () => {
    useResearchOverlayMock.mockReturnValue({
      data: {
        exists: true,
        covered_condado_ids: ['C_CORUNA'],
        meta: {
          provider: 'claude',
          model: 'claude-sonnet-4-6',
          generated_at: '2026-05-14T12:30:00Z',
          applied_at: '2026-05-14T12:30:00Z',
        },
      },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    const reopen = screen.getByText('Atualizar pesquisa')
    fireEvent.click(reopen)
    const dialog = screen.getByTestId('research-dialog-mock')
    expect(dialog).toBeInTheDocument()
    expect(dialog.getAttribute('data-force-refresh')).toBe('true')
  })

  it('badge is HIDDEN when overlay does not cover the condado id', () => {
    useResearchOverlayMock.mockReturnValue({
      data: {
        exists: true,
        covered_condado_ids: ['C_OTHER'],
        meta: {
          provider: 'claude',
          model: 'claude-sonnet-4-6',
          generated_at: '2026-05-14T12:30:00Z',
          applied_at: '2026-05-14T12:30:00Z',
        },
      },
    })
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} baronies={BARONIES} project={PROJECT} />),
    )
    expect(screen.queryByText('Pesquisa aplicada')).toBeNull()
  })
})
