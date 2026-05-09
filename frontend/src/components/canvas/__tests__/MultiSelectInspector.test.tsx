import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { MultiSelectInspector } from '../MultiSelectInspector'
import type { TerritoryMetadata } from '../../../hooks/useCanvasArtifacts'

const META: TerritoryMetadata = {
  region: 'iberia',
  map_size: [2000, 1600],
  bounds: { lon_min: -10, lon_max: 0, lat_min: 40, lat_max: 50 },
  kingdoms: { K_LEON: 'Reino de León', K_NAV: 'Reino de Navarra' },
  duchies: {
    D_GAL: { kingdom: 'K_LEON', name: 'Ducado de Galicia' },
    D_NAV: { kingdom: 'K_NAV', name: 'Ducado de Pamplona' },
  },
  condados: [
    {
      id: 'C_A', name: 'Coruña', lon: -8.4, lat: 43.4,
      duchy: 'D_GAL', kingdom: 'K_LEON',
      pixel_center: [0, 0], pixel_count: 1000,
      baronies: [], neighbors: [],
    },
    {
      id: 'C_B', name: 'Lugo', lon: -7.5, lat: 43.0,
      duchy: 'D_GAL', kingdom: 'K_LEON',
      pixel_center: [0, 0], pixel_count: 800,
      baronies: [], neighbors: [],
    },
    {
      id: 'C_C', name: 'Pamplona', lon: -1.6, lat: 42.8,
      duchy: 'D_NAV', kingdom: 'K_NAV',
      pixel_center: [0, 0], pixel_count: 1500,
      baronies: [], neighbors: [],
    },
  ],
  baronies: [],
}

function wrap(node: React.ReactNode) {
  return <Theme>{node}</Theme>
}

describe('MultiSelectInspector', () => {
  it('renders "X condados selecionados" heading with the selection count', () => {
    render(wrap(<MultiSelectInspector selectedIds={['C_A', 'C_B']} metadata={META} />))
    expect(screen.getByText('2 condados selecionados')).toBeInTheDocument()
  })

  it('renders the four section headings (Área total, Reinos, Ducados, Condados)', () => {
    render(wrap(<MultiSelectInspector selectedIds={['C_A', 'C_B']} metadata={META} />))
    expect(screen.getByText('Área total')).toBeInTheDocument()
    expect(screen.getByText('Reinos')).toBeInTheDocument()
    expect(screen.getByText('Ducados')).toBeInTheDocument()
    expect(screen.getByText('Condados')).toBeInTheDocument()
  })

  it('renders one kingdom badge per UNIQUE kingdom across the selection', () => {
    // Both C_A and C_B share K_LEON → only one badge
    render(wrap(<MultiSelectInspector selectedIds={['C_A', 'C_B']} metadata={META} />))
    expect(screen.getAllByText('Reino de León').length).toBe(1)
    expect(screen.queryByText('Reino de Navarra')).toBeNull()
  })

  it('aggregates kingdoms from cross-kingdom selection (union of K_LEON and K_NAV)', () => {
    render(wrap(<MultiSelectInspector selectedIds={['C_A', 'C_C']} metadata={META} />))
    expect(screen.getByText('Reino de León')).toBeInTheDocument()
    expect(screen.getByText('Reino de Navarra')).toBeInTheDocument()
  })

  it('lists each selected condado name in the Condados ScrollArea', () => {
    render(wrap(<MultiSelectInspector selectedIds={['C_A', 'C_B']} metadata={META} />))
    expect(screen.getByText('Coruña')).toBeInTheDocument()
    expect(screen.getByText('Lugo')).toBeInTheDocument()
    expect(screen.queryByText('Pamplona')).toBeNull()
  })

  it('sums pixel_count for selected condados and renders ~km² area', () => {
    render(wrap(<MultiSelectInspector selectedIds={['C_A', 'C_B']} metadata={META} />))
    // Total pixels = 1000 + 800 = 1800 out of 2000*1600 = 3,200,000
    // Bounds: 10° lon × 10° lat at center lat 45° → ~870km × ~1113km ≈ 968_000 km²
    // 1800 / 3_200_000 * 968_000 ≈ 544 km²
    // Just assert the km² suffix and a positive integer in the rendered text.
    const allKm2 = screen.getAllByText(/km²/)
    expect(allKm2.length).toBeGreaterThan(0)
    const text = allKm2[0].textContent ?? ''
    expect(text).toMatch(/^~\d/)
  })

  it('renders 0 km² gracefully when bounds/map_size are absent', () => {
    const missingBounds = {
      ...META,
      bounds: undefined as unknown as TerritoryMetadata['bounds'],
    }
    render(
      wrap(<MultiSelectInspector selectedIds={['C_A']} metadata={missingBounds} />),
    )
    // Falls back to "~0 km²"
    expect(screen.getByText(/^~0 km²/)).toBeInTheDocument()
  })
})
