/**
 * Phase 08 Plan 13 — EditToolPalette tests (GAP-C closure, UX-01).
 * TDD RED → GREEN: verifies that the palette renders 6 tool buttons bound to
 * useEditorStore.activeTool/selectTool. All 6 data-testids must appear in DOM.
 *
 * State is reset before each test to prevent zundo subscription leaks.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Theme } from '@radix-ui/themes';
import type { ReactNode } from 'react';
import { EditToolPalette } from '../EditToolPalette';
import { useEditorStore } from '../../../stores/useEditorStore';

function wrap(node: ReactNode) {
  return <Theme>{node}</Theme>;
}

describe('Phase 08 — EditToolPalette (GAP-C, UX-01)', () => {
  beforeEach(() => {
    // Reset editor store to clean state before each test
    useEditorStore.setState({
      activeTool: null,
      vertices: {},
      editLog: [],
    });
  });

  // ── 1. All 6 testids render in the DOM ──────────────────────────────────────
  it('renders all 6 tool buttons: V, A, D, S, M, Esc', () => {
    render(wrap(<EditToolPalette />));

    expect(screen.getByTestId('edit-tool-v')).toBeInTheDocument();
    expect(screen.getByTestId('edit-tool-a')).toBeInTheDocument();
    expect(screen.getByTestId('edit-tool-d')).toBeInTheDocument();
    expect(screen.getByTestId('edit-tool-s')).toBeInTheDocument();
    expect(screen.getByTestId('edit-tool-m')).toBeInTheDocument();
    expect(screen.getByTestId('edit-tool-esc')).toBeInTheDocument();
  });

  // ── 2. palette container renders ───────────────────────────────────────────
  it('renders the palette container with data-testid="edit-tool-palette"', () => {
    render(wrap(<EditToolPalette />));
    expect(screen.getByTestId('edit-tool-palette')).toBeInTheDocument();
  });

  // ── 3. Active tool is visually highlighted ──────────────────────────────────
  it('when activeTool="A" the A button has aria-pressed=true; others aria-pressed=false', () => {
    useEditorStore.setState({ activeTool: 'A' });
    render(wrap(<EditToolPalette />));

    const btnA = screen.getByTestId('edit-tool-a');
    expect(btnA).toHaveAttribute('aria-pressed', 'true');

    // All other tool buttons must be inactive
    for (const id of ['edit-tool-v', 'edit-tool-d', 'edit-tool-s', 'edit-tool-m']) {
      expect(screen.getByTestId(id)).toHaveAttribute('aria-pressed', 'false');
    }
  });

  // ── 4. Clicking a tool button calls selectTool with that tool ───────────────
  it('clicking the M button calls useEditorStore.selectTool("M")', () => {
    const selectTool = vi.spyOn(useEditorStore.getState(), 'selectTool');
    render(wrap(<EditToolPalette />));

    fireEvent.click(screen.getByTestId('edit-tool-m'));
    expect(selectTool).toHaveBeenCalledWith('M');
  });

  // ── 5. Clicking Esc calls selectTool(null) ──────────────────────────────────
  it('clicking the Esc button calls useEditorStore.selectTool(null)', () => {
    const selectTool = vi.spyOn(useEditorStore.getState(), 'selectTool');
    render(wrap(<EditToolPalette />));

    fireEvent.click(screen.getByTestId('edit-tool-esc'));
    expect(selectTool).toHaveBeenCalledWith(null);
  });

  // ── 6. Store-driven active state: activeTool='S' makes S button active ──────
  it('when activeTool="S" the S button is aria-pressed=true (store-driven, no local state)', () => {
    useEditorStore.setState({ activeTool: 'S' });
    render(wrap(<EditToolPalette />));

    expect(screen.getByTestId('edit-tool-s')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('edit-tool-v')).toHaveAttribute('aria-pressed', 'false');
  });

  // ── 7. Esc button is never in "active" state (it is a momentary cancel) ─────
  it('Esc button always shows aria-pressed=false, even when activeTool changes', () => {
    useEditorStore.setState({ activeTool: 'V' });
    render(wrap(<EditToolPalette />));

    expect(screen.getByTestId('edit-tool-esc')).toHaveAttribute('aria-pressed', 'false');
  });

  // ── 8. Keyboard selectTool updates are reflected in palette ─────────────────
  it('after store.selectTool("V") is called externally, V button becomes active', () => {
    const { rerender } = render(wrap(<EditToolPalette />));

    // Simulate keyboard shortcut setting activeTool
    useEditorStore.setState({ activeTool: 'V' });
    rerender(wrap(<EditToolPalette />));

    expect(screen.getByTestId('edit-tool-v')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('edit-tool-a')).toHaveAttribute('aria-pressed', 'false');
  });
});
