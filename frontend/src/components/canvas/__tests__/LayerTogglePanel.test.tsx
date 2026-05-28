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
  Tooltip: ({ children, content }: React.PropsWithChildren<{ content?: React.ReactNode }>) => (
    <div data-testid="tooltip" data-content={typeof content === 'string' ? content : ''}>{children}</div>
  ),
  // Phase 08 Plan 08 (pre-existing): Separator needed by LayerTogglePanel
  Separator: () => <hr />,
  // Phase 08 Plan 16: Switch + Heading + RadioGroup + Badge + Button (used by LandmaskEditorHeader via LayerTogglePanel)
  Switch: ({ checked, onCheckedChange, 'data-testid': testId }: { checked?: boolean; onCheckedChange?: (v: boolean) => void; 'data-testid'?: string }) => (
    <input type="checkbox" data-testid={testId ?? 'switch'} checked={checked ?? false} onChange={(e) => onCheckedChange?.(e.target.checked)} />
  ),
  Heading: ({ children }: React.PropsWithChildren) => <h2>{children}</h2>,
  Box: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  Badge: ({ children }: React.PropsWithChildren) => <span>{children}</span>,
  Button: ({ children, onClick }: React.PropsWithChildren<{ onClick?: () => void }>) => (
    <button onClick={onClick}>{children}</button>
  ),
  RadioGroup: {
    Root: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    Item: ({ children }: React.PropsWithChildren) => <label><input type="radio" />{children}</label>,
  },
}))

// Phase 03: 'terrain' layer removed (Plan 03-05). 5 layers remain:
// condados / baronies / borders / capitals / labels.
const DEFAULT_VISIBILITY = {
  condados: true,
  baronies: false,
  borders: true,
  capitals: true,
  labels: false,
}

describe('LayerTogglePanel', () => {
  beforeEach(() => {
    useUIStore.setState({
      selectedTerritoryIds: [],
      selectedTerritoryId: null,
      layerVisibility: { ...DEFAULT_VISIBILITY },
    })
  })

  it('renders 5 layer rows in the correct order (Phase 03: terrain removed)', () => {
    render(<LayerTogglePanel />)
    expect(screen.getByText('Condados')).toBeTruthy()
    expect(screen.getByText('Baronias')).toBeTruthy()
    expect(screen.getByText('Fronteiras')).toBeTruthy()
    expect(screen.getByText('Capitais')).toBeTruthy()
    expect(screen.getByText('Nomes')).toBeTruthy()
    // Phase 08 Plan 16: 6 checkboxes total — 5 layer toggles + 1 landmask-edit-toggle (Switch)
    expect(screen.getAllByRole('checkbox').length).toBe(6)
  })

  it('does NOT render the Terreno (terrain) row', () => {
    render(<LayerTogglePanel />)
    expect(screen.queryByText('Terreno')).toBeNull()
  })

  it('default state: condados/borders/capitals ON, baronies/labels OFF', () => {
    render(<LayerTogglePanel />)
    const boxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
    expect(boxes[0].checked).toBe(true)  // condados
    expect(boxes[1].checked).toBe(false) // baronies
    expect(boxes[2].checked).toBe(true)  // borders
    expect(boxes[3].checked).toBe(true)  // capitals
    expect(boxes[4].checked).toBe(false) // labels
  })

  it('clicking Nomes (labels) checkbox toggles store', () => {
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

  it('header text reads "Camadas"', () => {
    render(<LayerTogglePanel />)
    expect(screen.getByText('Camadas')).toBeTruthy()
  })
})
