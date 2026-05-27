/**
 * Phase 08 Plan 05 — useKeyboardShortcuts Phase-08 extension tests (Task 2).
 * REQ-IDs: UX-01 (D-32 keyboard shortcuts), UNDO-01 (D-25 undo/redo)
 *
 * Tests V/A/D/S/M/Esc tool shortcuts + Ctrl+Z/Ctrl+Shift+Z undo/redo +
 * Delete key deleteVertices + editable-element guard.
 * All shortcuts active only when canvas has focus (document.activeElement not
 * an INPUT/TEXTAREA/SELECT).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { fireEvent } from '@testing-library/dom';

// ── mock spies ────────────────────────────────────────────────────────────────
const mockSelectTool = vi.fn();
const mockDeleteVertices = vi.fn();
const mockUndo = vi.fn();
const mockRedo = vi.fn();

// Mock the entire useEditorStore module with a factory that exposes getState + temporal
vi.mock('../../stores/useEditorStore', () => {
  // The mock useEditorStore is a function (for selector usage) AND has static methods
  const store = Object.assign(
    (selector: (s: unknown) => unknown) =>
      selector({
        selectedVertexIds: ['v1', 'v2'],
        activeTool: null,
      }),
    {
      getState: () => ({
        selectTool: mockSelectTool,
        deleteVertices: mockDeleteVertices,
        selectedVertexIds: ['v1', 'v2'],
        activeTool: null,
      }),
      temporal: {
        getState: () => ({
          undo: mockUndo,
          redo: mockRedo,
          clear: vi.fn(),
          pastStates: [],
          futureStates: [],
        }),
        subscribe: vi.fn(() => () => {}),
      },
    },
  );
  return { useEditorStore: store };
});

// ── mock useUIStore ───────────────────────────────────────────────────────────
const mockClearSelection = vi.fn();
vi.mock('../../stores/uiStore', () => ({
  useUIStore: {
    getState: () => ({
      select: mockClearSelection,
    }),
  },
}));

import { useKeyboardShortcuts } from '../useKeyboardShortcuts';

// Helper: simulate keydown on window
function pressKey(key: string, opts: Partial<KeyboardEventInit> = {}) {
  fireEvent.keyDown(window, { key, ...opts });
}

// Helper: make document.activeElement point to an input
function focusInput(): HTMLInputElement {
  const input = document.createElement('input');
  document.body.appendChild(input);
  input.focus();
  return input;
}

function focusBody() {
  (document.activeElement as HTMLElement | null)?.blur?.();
}

beforeEach(() => {
  vi.clearAllMocks();
  focusBody();
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.querySelectorAll('input').forEach((el) => el.remove());
});

describe('useKeyboardShortcuts — Phase 08 tool shortcuts', () => {
  it('V key calls selectTool("V")', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('v');
    expect(mockSelectTool).toHaveBeenCalledWith('V');
  });

  it('A key calls selectTool("A")', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('a');
    expect(mockSelectTool).toHaveBeenCalledWith('A');
  });

  it('D key calls selectTool("D")', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('d');
    expect(mockSelectTool).toHaveBeenCalledWith('D');
  });

  it('S key calls selectTool("S")', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('s');
    expect(mockSelectTool).toHaveBeenCalledWith('S');
  });

  it('M key calls selectTool("M")', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('m');
    expect(mockSelectTool).toHaveBeenCalledWith('M');
  });

  it('Esc key calls selectTool(null) when an editor tool is active', async () => {
    // Esc dismisses the active editor tool (not the territory selection) when
    // activeTool !== null. Override getState to simulate an active tool.
    const { useEditorStore } = await import('../../stores/useEditorStore');
    const originalGetState = useEditorStore.getState;
    useEditorStore.getState = () => ({
      ...originalGetState(),
      activeTool: 'V' as const,
      selectTool: mockSelectTool,
    });
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('Escape');
    expect(mockSelectTool).toHaveBeenCalledWith(null);
    useEditorStore.getState = originalGetState;
  });
});

describe('useKeyboardShortcuts — undo/redo', () => {
  it('Ctrl+Z calls temporal.getState().undo()', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('z', { ctrlKey: true });
    expect(mockUndo).toHaveBeenCalledTimes(1);
  });

  it('Ctrl+Shift+Z calls temporal.getState().redo()', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('z', { ctrlKey: true, shiftKey: true });
    expect(mockRedo).toHaveBeenCalledTimes(1);
  });
});

describe('useKeyboardShortcuts — Delete key', () => {
  it('Delete with selectedVertexIds calls deleteVertices as single undoable op', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    pressKey('Delete');
    expect(mockDeleteVertices).toHaveBeenCalledWith(['v1', 'v2']);
  });
});

describe('useKeyboardShortcuts — editable-element guard', () => {
  it('shortcuts are inactive when document.activeElement is an INPUT', () => {
    renderHook(() => useKeyboardShortcuts(() => {}));
    const input = focusInput();
    pressKey('v');
    expect(mockSelectTool).not.toHaveBeenCalled();
    input.remove();
  });
});
