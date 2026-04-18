import { Button } from '@radix-ui/themes'

interface FitToViewButtonProps {
  onFit: () => void
}

/**
 * Bottom-left "Fit to view" button. Positioned absolutely inside the canvas
 * container (CanvasViewer wraps in a position:relative div). minHeight:44
 * keeps the tap target accessible per WCAG AA.
 */
export function FitToViewButton({ onFit }: FitToViewButtonProps) {
  return (
    <div
      data-testid="fit-to-view-wrapper"
      style={{
        position: 'absolute',
        bottom: '12px',
        left: '12px',
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
