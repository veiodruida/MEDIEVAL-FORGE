/**
 * Phase 08.2 Plan 03 — Task 3
 * Visibility matrix tests for BezierApplyControls (Apply Edits group in WorkspaceToolbar).
 *
 * UI-SPEC §"Visibility and enable state matrix" (294-303):
 *   - Bézier mode inactive → group hidden
 *   - Bézier mode active, manual, editLog empty → Switch visible/OFF, Apply visible/disabled, Badge hidden
 *   - Bézier mode active, manual, editLog non-empty → Switch visible/OFF, Apply visible/enabled, Badge hidden
 *   - Bézier mode active, auto-immediate → Switch visible/ON, Apply hidden, Badge visible
 *   - Any mode, isRunning → Apply disabled (manual) or Hidden (auto)
 *   - Click Apply calls handleApplyEdits
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { WorkspaceToolbar } from '../WorkspaceToolbar'
import { useEditorStore } from '../../../stores/useEditorStore'
import type { Project } from '../../../api/client'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../../components/editor/BranchPicker', () => ({
  BranchPicker: () => null,
}))
vi.mock('../../../components/editor/EditorSyncBridge', () => ({
  EditorSyncBridge: () => null,
}))

// Mock useBezierApply so tests don't need a network layer
const mockHandleApplyEdits = vi.fn().mockResolvedValue(undefined)
vi.mock('../../../hooks/useBezierApply', () => ({
  useBezierApply: () => ({
    handleApplyEdits: mockHandleApplyEdits,
    triggerAutoApply: vi.fn().mockResolvedValue(undefined),
  }),
  MAX_VERTEX_KEYS_FALLBACK: 40000,
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PROJECT: Project = {
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

const DEFAULT_PROPS = {
  project: PROJECT,
  runState: 'idle' as const,
  currentStage: null,
  hasArtifacts: false,
  onGenerate: vi.fn(),
  onExport: vi.fn(),
  statusBadgeOpen: false,
  onToggleStatusBadge: vi.fn(),
}

function wrap(node: ReactNode) {
  return (
    <MemoryRouter>
      <Theme>{node}</Theme>
    </MemoryRouter>
  )
}

function resetStore() {
  useEditorStore.setState({
    vertices: {},
    editLog: [],
    activeBranchId: 'branch-1',
    activeTool: null,
    activeTerritoryId: null,
    selectedVertexIds: [],
    landmaskMode: 'manual',
    editableLayer: 'baronies',
    editsSinceSnapshot: 0,
    undoLabels: [],
    redoLabels: [],
    bezierApplyMode: 'manual',
  })
  useEditorStore.temporal.getState().clear()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WorkspaceToolbar BezierApplyControls visibility matrix', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
    // Restore mock return after clearAllMocks
    mockHandleApplyEdits.mockResolvedValue(undefined)
  })

  it('Apply group is hidden when Bézier mode is inactive (no barony selected)', () => {
    // activeTerritoryId=null → Bézier mode inactive
    useEditorStore.setState({ editableLayer: 'baronies', activeTerritoryId: null, activeTool: 'V' })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    expect(screen.queryByTestId('bezier-apply-edits-btn')).toBeNull()
    expect(screen.queryByTestId('bezier-apply-auto-switch')).toBeNull()
  })

  it('Apply group is hidden when activeTool is not V', () => {
    useEditorStore.setState({
      editableLayer: 'baronies',
      activeTerritoryId: 'barony-1',
      activeTool: 'A',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    expect(screen.queryByTestId('bezier-apply-edits-btn')).toBeNull()
    expect(screen.queryByTestId('bezier-apply-auto-switch')).toBeNull()
  })

  it('Apply group is hidden when editableLayer is not baronies', () => {
    useEditorStore.setState({
      editableLayer: 'landmask',
      activeTerritoryId: 'barony-1',
      activeTool: 'V',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    expect(screen.queryByTestId('bezier-apply-edits-btn')).toBeNull()
    expect(screen.queryByTestId('bezier-apply-auto-switch')).toBeNull()
  })

  it('Bézier mode active, manual, editLog empty: Switch visible, Apply disabled, Badge hidden', () => {
    useEditorStore.setState({
      editableLayer: 'baronies',
      activeTerritoryId: 'barony-1',
      activeTool: 'V',
      editLog: [],
      bezierApplyMode: 'manual',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    // Switch must be visible
    expect(screen.getByTestId('bezier-apply-auto-switch')).toBeDefined()

    // Apply button visible but disabled
    const applyBtn = screen.getByTestId('bezier-apply-edits-btn')
    expect(applyBtn).toBeDefined()
    expect(applyBtn).toHaveProperty('disabled', true)

    // Badge hidden (no orange badge)
    expect(screen.queryByText('Modo auto: ~3-5s por edição')).toBeNull()
  })

  it('Bézier mode active, manual, editLog non-empty: Apply enabled', () => {
    useEditorStore.setState({
      editableLayer: 'baronies',
      activeTerritoryId: 'barony-1',
      activeTool: 'V',
      editLog: [{ op: 'move', ts: 1000, vertexIds: ['v1'], lat: 10, lon: 20 }],
      bezierApplyMode: 'manual',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    const applyBtn = screen.getByTestId('bezier-apply-edits-btn')
    expect(applyBtn).toHaveProperty('disabled', false)
  })

  it('Bézier mode active, auto-immediate: Switch ON, Apply hidden, Badge visible', () => {
    useEditorStore.setState({
      editableLayer: 'baronies',
      activeTerritoryId: 'barony-1',
      activeTool: 'V',
      editLog: [],
      bezierApplyMode: 'auto-immediate',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    // Switch should be checked (ON)
    const sw = screen.getByTestId('bezier-apply-auto-switch')
    expect(sw).toBeDefined()
    // Apply button hidden in auto mode
    expect(screen.queryByTestId('bezier-apply-edits-btn')).toBeNull()

    // Orange badge visible
    expect(screen.getByText('Modo auto: ~3-5s por edição')).toBeDefined()
  })

  it('Apply button disabled when isRunning (runState=rendering)', () => {
    useEditorStore.setState({
      editableLayer: 'baronies',
      activeTerritoryId: 'barony-1',
      activeTool: 'V',
      editLog: [{ op: 'move', ts: 1000, vertexIds: ['v1'], lat: 10, lon: 20 }],
      bezierApplyMode: 'manual',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} runState="rendering" />))

    const applyBtn = screen.getByTestId('bezier-apply-edits-btn')
    expect(applyBtn).toHaveProperty('disabled', true)
  })

  it('clicking Apply button calls handleApplyEdits', () => {
    useEditorStore.setState({
      editableLayer: 'baronies',
      activeTerritoryId: 'barony-1',
      activeTool: 'V',
      activeBranchId: 'branch-1',
      editLog: [{ op: 'move', ts: 1000, vertexIds: ['v1'], lat: 10, lon: 20 }],
      bezierApplyMode: 'manual',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    const applyBtn = screen.getByTestId('bezier-apply-edits-btn')
    fireEvent.click(applyBtn)

    expect(mockHandleApplyEdits).toHaveBeenCalled()
  })

  it('pt-BR copy strings are present: Aplicar edições, Auto-aplicar', () => {
    useEditorStore.setState({
      editableLayer: 'baronies',
      activeTerritoryId: 'barony-1',
      activeTool: 'V',
      editLog: [],
      bezierApplyMode: 'manual',
    })
    render(wrap(<WorkspaceToolbar {...DEFAULT_PROPS} />))

    expect(screen.getByText('Aplicar edições')).toBeDefined()
    expect(screen.getByText('Auto-aplicar')).toBeDefined()
  })
})
