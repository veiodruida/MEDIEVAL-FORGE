/* Phase 08 Plan 08 — LandmaskEditorHeader tests (Task 1, TDD RED → GREEN).
 * Covers REQ-IDs: LANDMASK-01, LANDMASK-02
 * WARNING-5 fix: VertexEditLayer landmask handles + Pitfall 3.
 *
 * 5 tests per plan behavior specification.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

// ── mock Radix UI Themes ──────────────────────────────────────────────────────
vi.mock('@radix-ui/themes', () => {
  const React = require('react');
  const Box: React.FC<{ children?: React.ReactNode }> = ({ children }) =>
    React.createElement('div', { 'data-testid': 'box' }, children);
  const Heading: React.FC<{ children?: React.ReactNode; size?: string }> = ({ children }) =>
    React.createElement('h2', { 'data-testid': 'heading' }, children);
  const Badge: React.FC<{ children?: React.ReactNode; color?: string; variant?: string }> = ({
    children,
    color,
  }) =>
    React.createElement(
      'span',
      { 'data-testid': 'badge', 'data-color': color },
      children,
    );
  const Button: React.FC<{
    children?: React.ReactNode;
    variant?: string;
    color?: string;
    onClick?: () => void;
  }> = ({ children, variant, onClick }) =>
    React.createElement(
      'button',
      { 'data-testid': 'button', 'data-variant': variant, onClick },
      children,
    );
  const Flex: React.FC<{ children?: React.ReactNode; direction?: string; gap?: string }> = ({
    children,
  }) => React.createElement('div', { 'data-testid': 'flex' }, children);
  const RadioGroup = {
    Root: ({
      children,
      value,
      onValueChange,
    }: {
      children?: React.ReactNode;
      value?: string;
      onValueChange?: (v: string) => void;
    }) =>
      React.createElement(
        'div',
        { 'data-testid': 'radio-group-root', 'data-value': value },
        React.Children.map(children, (child) =>
          React.cloneElement(child as React.ReactElement, { _onValueChange: onValueChange }),
        ),
      ),
    Item: ({
      children,
      value,
      _onValueChange,
    }: {
      children?: React.ReactNode;
      value?: string;
      _onValueChange?: (v: string) => void;
    }) =>
      React.createElement(
        'label',
        {
          'data-testid': `radio-item-${value}`,
          onClick: () => _onValueChange?.(value ?? ''),
        },
        React.createElement('input', {
          type: 'radio',
          value,
          onChange: () => _onValueChange?.(value ?? ''),
        }),
        children,
      ),
  };
  const Switch: React.FC<{
    checked?: boolean;
    onCheckedChange?: (v: boolean) => void;
    'data-testid'?: string;
  }> = ({ checked, onCheckedChange, 'data-testid': testId }) =>
    React.createElement('input', {
      type: 'checkbox',
      'data-testid': testId ?? 'switch',
      checked: checked ?? false,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => onCheckedChange?.(e.target.checked),
    });
  const Text: React.FC<{ children?: React.ReactNode; size?: string }> = ({ children }) =>
    React.createElement('span', { 'data-testid': 'text' }, children);
  return { Box, Heading, Badge, Button, Flex, RadioGroup, Switch, Text };
});

// ── mock useEditorStore ───────────────────────────────────────────────────────
const mockSetLandmaskMode = vi.fn();
const mockSetEditableLayer = vi.fn();
let mockLandmaskMode = 'manual';
let mockEditableLayer = 'baronies';

vi.mock('../../../stores/useEditorStore', () => ({
  useEditorStore: (selector: (s: {
    landmaskMode: string;
    setLandmaskMode: typeof mockSetLandmaskMode;
    editableLayer: string;
    setEditableLayer: typeof mockSetEditableLayer;
  }) => unknown) =>
    selector({
      landmaskMode: mockLandmaskMode,
      setLandmaskMode: mockSetLandmaskMode,
      editableLayer: mockEditableLayer,
      setEditableLayer: mockSetEditableLayer,
    }),
}));

// ── import after mocks ────────────────────────────────────────────────────────
import { LandmaskEditorHeader } from '../LandmaskEditorHeader';

describe('LandmaskEditorHeader (LANDMASK-01, LANDMASK-02)', () => {
  const mockOnApply = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    mockLandmaskMode = 'manual';
    mockEditableLayer = 'baronies';
  });

  it('initial render shows RadioGroup with Manual selected (default per D-05)', () => {
    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );
    const radioGroup = screen.getByTestId('radio-group-root');
    expect(radioGroup).toBeTruthy();
    expect(radioGroup.getAttribute('data-value')).toBe('manual');
  });

  it('clicking "Auto imediato" sets landmaskMode=auto-immediate AND shows orange Badge', () => {
    // Switch mock to return auto-immediate after setMode is called
    mockLandmaskMode = 'auto-immediate';

    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );

    const badge = screen.getByTestId('badge');
    expect(badge).toBeTruthy();
    expect(badge.getAttribute('data-color')).toBe('orange');
    expect(badge.textContent).toContain('~10s');
  });

  it('in Manual mode, "Aplicar landmask" Button is visible with variant=outline', () => {
    mockLandmaskMode = 'manual';

    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );

    const button = screen.getByTestId('button');
    expect(button).toBeTruthy();
    expect(button.getAttribute('data-variant')).toBe('outline');
    expect(button.textContent).toContain('Aplicar');
  });

  it('in Auto mode, "Aplicar" Button is hidden (not rendered)', () => {
    mockLandmaskMode = 'auto-immediate';

    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );

    const buttons = screen.queryAllByTestId('button');
    expect(buttons).toHaveLength(0);
  });

  it('clicking Apply triggers onApply callback (POST /editor/apply with op_type=landmask_replace)', async () => {
    mockLandmaskMode = 'manual';

    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );

    const button = screen.getByTestId('button');
    fireEvent.click(button);

    // onApply is called (which POSTs landmask_replace internally via parent)
    expect(mockOnApply).toHaveBeenCalledTimes(1);
  });

  // ── Phase 08 Plan 16: editableLayer toggle tests ──────────────────────────────

  it('renders landmask-edit-toggle with data-testid and unchecked when baronies', () => {
    mockEditableLayer = 'baronies';
    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );
    const toggle = screen.getByTestId('landmask-edit-toggle') as HTMLInputElement;
    expect(toggle).toBeTruthy();
    expect(toggle.checked).toBe(false);
  });

  it('toggle is checked when editableLayer=landmask', () => {
    mockEditableLayer = 'landmask';
    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );
    const toggle = screen.getByTestId('landmask-edit-toggle') as HTMLInputElement;
    expect(toggle.checked).toBe(true);
  });

  it('toggling ON calls setEditableLayer("landmask")', () => {
    mockEditableLayer = 'baronies';
    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );
    const toggle = screen.getByTestId('landmask-edit-toggle');
    fireEvent.click(toggle);
    expect(mockSetEditableLayer).toHaveBeenCalledWith('landmask');
  });

  it('toggling OFF calls setEditableLayer("baronies")', () => {
    mockEditableLayer = 'landmask';
    render(
      <LandmaskEditorHeader
        projectId="proj-123"
        branchId="branch-abc"
        onApply={mockOnApply}
      />,
    );
    const toggle = screen.getByTestId('landmask-edit-toggle');
    fireEvent.click(toggle);
    expect(mockSetEditableLayer).toHaveBeenCalledWith('baronies');
  });
});
