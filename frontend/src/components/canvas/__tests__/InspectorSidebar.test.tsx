import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { InspectorSidebar } from '../InspectorSidebar'
import { useUIStore } from '../../../stores/uiStore'
import type {
  TerritoryMetadata,
  TerritoryRender,
} from '../../../hooks/useCanvasArtifacts'

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

const PROJECT = {
  name: 'Reconquista 868',
  country_qid: 'Q29',
  period_start: 868,
  period_end: 900,
}

function wrap(node: React.ReactNode) {
  return <Theme>{node}</Theme>
}

describe('InspectorSidebar — project overview (no selection)', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryId: null,
      layerVisibility: {
        terrain: true,
        territories: true,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('renders "Project overview" heading and 4 hierarchy stat labels', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} project={PROJECT} />),
    )
    expect(screen.getByText('Project overview')).toBeInTheDocument()
    expect(screen.getByText('Kingdoms')).toBeInTheDocument()
    expect(screen.getByText('Duchies')).toBeInTheDocument()
    expect(screen.getByText('Condados')).toBeInTheDocument()
    expect(screen.getByText('Baronies')).toBeInTheDocument()
  })

  it('renders project name, country, and period in summary state', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} project={PROJECT} />),
    )
    expect(screen.getByText('Reconquista 868')).toBeInTheDocument()
    expect(screen.getByText(/Q29/)).toBeInTheDocument()
    expect(screen.getByText(/868/)).toBeInTheDocument()
    expect(screen.getByText(/900/)).toBeInTheDocument()
  })
})

describe('InspectorSidebar — territory detail (D-06.3 capital sentinel)', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryId: 'C_CORUNA',
      layerVisibility: {
        terrain: true,
        territories: true,
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
          project={PROJECT}
        />,
      ),
    )
    expect(screen.getByText('A Coruña')).toBeInTheDocument()
    expect(screen.queryByText('No capital assigned')).toBeNull()
  })

  it('renders "No capital assigned" when capital_name is absent (D-06.3 sentinel)', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} project={PROJECT} />),
    )
    expect(screen.getByText('No capital assigned')).toBeInTheDocument()
  })

  it('renders "No capital assigned" when capital_name is empty/whitespace', () => {
    const metaEmpty: TerritoryMetadata = {
      ...META,
      condados: [{ ...META.condados[0], capital_name: '   ' }, META.condados[1]] as never,
    }
    render(
      wrap(<InspectorSidebar metadata={metaEmpty} territories={TERRITORIES} project={PROJECT} />),
    )
    expect(screen.getByText('No capital assigned')).toBeInTheDocument()
  })

  it('heading shows selected territory name', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} project={PROJECT} />),
    )
    // Two places could show "Coruña" (heading + Path:); use role to disambiguate
    expect(screen.getByRole('heading', { name: /Coruña/ })).toBeInTheDocument()
  })

  it('renders 4 labeled group rows: Path, Area, Centroid, Capital, Adjacent territories', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} project={PROJECT} />),
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
      selectedTerritoryId: 'C_CORUNA',
      layerVisibility: {
        terrain: true,
        territories: true,
        borders: true,
        capitals: true,
        labels: false,
      },
    })
  })

  it('renders a chip for each neighbor and dispatches select(neighborId) on click', () => {
    render(
      wrap(<InspectorSidebar metadata={META} territories={TERRITORIES} project={PROJECT} />),
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
          project={PROJECT}
        />,
      ),
    )
    expect(screen.getByText('No adjacent territories')).toBeInTheDocument()
  })
})
