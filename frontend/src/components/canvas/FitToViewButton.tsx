import { Button } from '@radix-ui/themes'

interface FitToViewButtonProps {
  onFit: () => void
}

/**
 * Bottom-right "Fit to view" button. Positioned absolutely inside the canvas
 * container (CanvasViewer wraps in a position:relative div). minHeight:44
 * keeps the tap target accessible per WCAG AA.
 *
 * Position note: moved from bottom-left to bottom-right on 2026-04-23 because
 * the LegendCard (added by quick-task 260420-hkr) also sits at bottom-left
 * and was covering the Fit button. Bottom-right keeps the button visible and
 * outside the LayerTogglePanel (top-left) / InspectorSidebar (right pane) /
 * LegendCard (bottom-left) regions.
 */
export function FitToViewButton({ onFit }: FitToViewButtonProps) {
  return (
    <div
      data-testid="fit-to-view-wrapper"
      style={{
        position: 'absolute',
        bottom: '12px',
        right: '12px',
        zIndex: 10,
      }}
    >
      <Button
        variant="solid"
        onClick={onFit}
        style={{ minHeight: '44px', cursor: 'pointer' }}
      >
        Fit to view
      </Button>
    </div>
  )
}
