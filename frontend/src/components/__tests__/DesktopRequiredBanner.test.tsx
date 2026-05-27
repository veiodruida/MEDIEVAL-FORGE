/**
 * Phase 08 Plan 05 — DesktopRequiredBanner tests (Task 2).
 * REQ-IDs: UX-02 (D-36 Desktop-only)
 *
 * Tests UA detection + Radix Callout banner rendering.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

// ── mock Radix UI Themes Callout ──────────────────────────────────────────────
vi.mock('@radix-ui/themes', () => {
  const React = require('react');
  return {
    Callout: {
      Root: ({ children, color, role, ...rest }: {
        children?: React.ReactNode;
        color?: string;
        role?: string;
        [key: string]: unknown;
      }) =>
        React.createElement('div', {
          'data-testid': 'callout-root',
          'data-color': color,
          role,
          ...rest,
        }, children),
      Text: ({ children }: { children?: React.ReactNode }) =>
        React.createElement('span', { 'data-testid': 'callout-text' }, children),
    },
  };
});

import { isDesktopRequired, DesktopRequiredBanner } from '../DesktopRequiredBanner';

// Helper to set navigator.maxTouchPoints
function setTouchPoints(n: number) {
  Object.defineProperty(navigator, 'maxTouchPoints', {
    configurable: true,
    value: n,
  });
}

// Helper to mock matchMedia
function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => {
  // Reset to desktop default: no touch, pointer:fine
  setTouchPoints(0);
  mockMatchMedia(true); // pointer:fine matches
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('isDesktopRequired()', () => {
  it('returns true when maxTouchPoints > 0 AND matchMedia pointer:fine does NOT match (touch-primary UA)', () => {
    setTouchPoints(1);
    mockMatchMedia(false); // pointer:fine doesn't match → touch-primary
    expect(isDesktopRequired()).toBe(true);
  });

  it('returns false when maxTouchPoints is 0 (desktop, no touch)', () => {
    setTouchPoints(0);
    mockMatchMedia(false);
    expect(isDesktopRequired()).toBe(false);
  });

  it('returns false when matchMedia pointer:fine matches (fine pointer = mouse)', () => {
    setTouchPoints(5); // has touch
    mockMatchMedia(true); // but pointer:fine also matches → hybrid, treat as desktop
    expect(isDesktopRequired()).toBe(false);
  });
});

describe('DesktopRequiredBanner', () => {
  it('renders Radix Callout color="amber" when isDesktopRequired() is true', () => {
    setTouchPoints(1);
    mockMatchMedia(false); // touch-primary
    render(<DesktopRequiredBanner />);
    const callout = screen.getByTestId('callout-root');
    expect(callout).toBeTruthy();
    expect(callout.getAttribute('data-color')).toBe('amber');
  });

  it('renders nothing when isDesktopRequired() is false', () => {
    setTouchPoints(0);
    mockMatchMedia(true); // desktop
    render(<DesktopRequiredBanner />);
    expect(screen.queryByTestId('callout-root')).toBeNull();
  });

  it('banner message contains actionable desktop redirect text', () => {
    setTouchPoints(1);
    mockMatchMedia(false);
    render(<DesktopRequiredBanner />);
    const text = screen.getByTestId('callout-text');
    expect(text.textContent?.toLowerCase()).toMatch(/desktop|mouse/i);
  });

  it('has role="alert" (non-dismissible notification)', () => {
    setTouchPoints(1);
    mockMatchMedia(false);
    render(<DesktopRequiredBanner />);
    const callout = screen.getByTestId('callout-root');
    expect(callout.getAttribute('role')).toBe('alert');
  });
});
