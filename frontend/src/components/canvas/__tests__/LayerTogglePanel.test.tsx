import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { act } from 'react'
import { LayerTogglePanel } from '../LayerTogglePanel'
import { useUIStore } from '../../../stores/uiStore'

vi.mock('@radix-ui/themes', () => ({
  Card: ({ children, variant, style }: React.PropsWithChildren<{ variant?: string; style?: React.CSSProperties }>) => (
    <div data-testid="layer-card" data-variant={variant} style={style}>{children}</div>
  ),
  Flex: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  Text: ({ children }: React.PropsWithChildren) => <span>{children}</span>,
  Checkbox: ({ checked, onCheckedChange }: { checked?: boolean; onCheckedChange?: (v: boolean) => void }) => (
    <input type="checkbox" checked={checked} onChange={(e) => onCheckedChange?.(e.target.checked)} />
  ),
}))

const DEFAULT_VISIBILITY = { terrain: true, territories: true, borders: true, capitals: true, labels: false }

describe('LayerTogglePanel', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryId: null,
      layerVisibility: { ...DEFAULT_VISIBILITY },
      select: useUIStore.getState().select,
      toggleLayer: useUIStore.getState().toggleLayer,
    })
  })

  it('renders 5 layer rows in the correct order', () => {
    render(<LayerTogglePanel />)
    expect(screen.getByText('Terrain')).toBeTruthy()
    expect(screen.getByText('Territories')).toBeTruthy()
    expect(screen.getByText('Borders')).toBeTruthy()
    expect(screen.getByText('Capitals')).toBeTruthy()
    expect(screen.getByText('Labels')).toBeTruthy()
    expect(screen.getAllByRole('checkbox').length).toBe(5)
  })

  it('default D-09 state: terrain/territories/borders/capitals ON, labels OFF', () => {
    render(<LayerTogglePanel />)
    const boxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
    expect(boxes[0].checked).toBe(true)  // terrain
    expect(boxes[1].checked).toBe(true)  // territories
    expect(boxes[2].checked).toBe(true)  // borders
    expect(boxes[3].checked).toBe(true)  // capitals
    expect(boxes[4].checked).toBe(false) // labels
  })

  it('clicking Labels checkbox toggles store', () => {
    render(<LayerTogglePanel />)
    const boxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
    act(() => { fireEvent.click(boxes[4]) })
    expect(useUIStore.getState().layerVisibility.labels).toBe(true)
  })

  it('Card has variant="surface" at absolute position top:12 left:12 z-index:10', () => {
    render(<LayerTogglePanel />)
    const card = screen.getByTestId('layer-card')
    expect(card.getAttribute('data-variant')).toBe('surface')
    expect(card.style.position).toBe('absolute')
    expect(card.style.top).toBe('12px')
    expect(card.style.left).toBe('12px')
    expect(Number(card.style.zIndex)).toBe(10)
  })

  it('header text reads "Layers"', () => {
    render(<LayerTogglePanel />)
    expect(screen.getByText('Layers')).toBeTruthy()
  })
})
