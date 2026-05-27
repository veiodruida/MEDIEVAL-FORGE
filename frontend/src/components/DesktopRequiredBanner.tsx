/**
 * DesktopRequiredBanner — UA-gated desktop-required notification.
 *
 * Phase 08 D-36: desktop-only editor. Touch-primary devices (tablet/mobile)
 * see a non-dismissible amber Radix Callout directing them to a desktop browser.
 *
 * UA detection (UI-SPEC §Notes #8 verbatim):
 *   navigator.maxTouchPoints > 0 && !window.matchMedia('(pointer: fine)').matches
 *
 * This covers:
 *   - Touch-only phones/tablets: maxTouchPoints > 0, pointer:fine=false → SHOW
 *   - Desktop with mouse: maxTouchPoints=0 → HIDE
 *   - Hybrid (Surface Pro, iPad+mouse): maxTouchPoints > 0 but pointer:fine=true → HIDE
 *   - SSR / no window: return false → HIDE
 */
import React from 'react';
import { Callout } from '@radix-ui/themes';

/**
 * Returns true when the UA is touch-primary and lacks a fine pointer (mouse).
 * Exported for unit-test access.
 */
export function isDesktopRequired(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    navigator.maxTouchPoints > 0 &&
    !window.matchMedia('(pointer: fine)').matches
  );
}

/**
 * Renders an amber, non-dismissible Radix Callout when running on a touch-primary UA.
 * Returns null on desktop (no DOM nodes added).
 */
export const DesktopRequiredBanner: React.FC = () => {
  if (!isDesktopRequired()) return null;
  return (
    <Callout.Root color="amber" role="alert" style={{ borderRadius: 0 }}>
      <Callout.Text>
        O editor de vértices requer um dispositivo com mouse. Acesse pelo desktop.
      </Callout.Text>
    </Callout.Root>
  );
};
