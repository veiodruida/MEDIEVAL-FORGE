/**
 * Phase 08.3 Plan 03 — EditToolPalette pen tool tests (PEN-CREATE-01).
 *
 * Verifies:
 *   T1: Pen tool button (testid edit-tool-p) renders with the correct tooltip
 *   T2: with disabledTools={['A','D','S','M']} those four buttons are disabled, V and P are not
 *   T3: disabledTools regression — S and M are enabled when disabledTools not set
 *   T4: Pen button clicking calls selectTool('P')
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

describe('Phase 08.3 — EditToolPalette pen tool (PEN-CREATE-01)', () => {
  beforeEach(() => {
    useEditorStore.setState({
      activeTool: null,
      vertices: {},
      editLog: [],
    });
  });

  // ── T1: Pen button renders with testid edit-tool-p and pen tooltip ───────────
  it('T1: renders pen tool button with testid edit-tool-p and pen tooltip aria-label', () => {
    render(wrap(<EditToolPalette />));

    const penBtn = screen.getByTestId('edit-tool-p');
    expect(penBtn).toBeInTheDocument();
    expect(penBtn).toHaveAttribute(
      'aria-label',
      'Caneta — desenhar contorno de baronato (P)',
    );
  });

  // ── T2: disabledTools=['A','D','S','M'] disables those four; V and P are not ─
  it('T2: with disabledTools={["A","D","S","M"]} those 4 are disabled; V and P remain enabled', () => {
    render(wrap(<EditToolPalette disabledTools={['A', 'D', 'S', 'M']} />));

    // A, D, S, M must be disabled
    expect(screen.getByTestId('edit-tool-a')).toBeDisabled();
    expect(screen.getByTestId('edit-tool-d')).toBeDisabled();
    expect(screen.getByTestId('edit-tool-s')).toBeDisabled();
    expect(screen.getByTestId('edit-tool-m')).toBeDisabled();

    // V and P must remain enabled
    expect(screen.getByTestId('edit-tool-v')).toBeEnabled();
    expect(screen.getByTestId('edit-tool-p')).toBeEnabled();
  });

  // ── T3: S and M are enabled when disabledTools not provided ─────────────────
  it('T3: without disabledTools, S and M buttons are enabled (Phase 08 regression)', () => {
    render(wrap(<EditToolPalette />));

    expect(screen.getByTestId('edit-tool-s')).toBeEnabled();
    expect(screen.getByTestId('edit-tool-m')).toBeEnabled();
    expect(screen.getByTestId('edit-tool-p')).toBeEnabled();
  });

  // ── T4: clicking Pen button calls selectTool('P') ────────────────────────────
  it('T4: clicking pen button calls selectTool("P")', () => {
    const selectTool = vi.spyOn(useEditorStore.getState(), 'selectTool');
    render(wrap(<EditToolPalette />));

    fireEvent.click(screen.getByTestId('edit-tool-p'));
    expect(selectTool).toHaveBeenCalledWith('P');
  });
});
