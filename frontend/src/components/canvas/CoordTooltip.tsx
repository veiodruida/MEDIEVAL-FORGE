/**
 * CoordTooltip — DOM overlay showing (lat, lon) in 6-decimal monospace.
 *
 * D-33: drag tooltip follows cursor, shows float 6 decimals.
 * UI-SPEC §Notes #5: DOM div, NOT Radix Tooltip (no DOM anchor on Konva canvas).
 * position:fixed so cursor coordinates from Stage.getPointerPosition() — which
 * are viewport-relative — map directly to the overlay position without any
 * transform gymnastics.
 */
import React from 'react';

interface CoordTooltipProps {
  lat: number;
  lon: number;
  cursorX: number;
  cursorY: number;
  visible: boolean;
}

export const CoordTooltip: React.FC<CoordTooltipProps> = ({
  lat,
  lon,
  cursorX,
  cursorY,
  visible,
}) => {
  if (!visible) return null;
  return (
    <div
      style={{
        position: 'fixed',
        left: cursorX + 12,
        top: cursorY + 12,
        pointerEvents: 'none',
        zIndex: 60,
        fontFamily: 'ui-monospace, monospace',
        fontSize: '11px',
        background: 'var(--color-panel-solid)',
        padding: '4px 8px',
        borderRadius: 4,
        border: '1px solid var(--gray-6)',
        whiteSpace: 'nowrap',
      }}
    >
      lat: {lat.toFixed(6)}&nbsp;&nbsp;lon: {lon.toFixed(6)}
    </div>
  );
};
