import { useEffect } from 'react'
import { useSaveStatus, useSaveStrategy } from '../services/persistence'

/**
 * useBeforeUnloadGuard (D-07, T-04-08-04) — browser navigation warning.
 *
 * Fires a browser confirmation dialog when:
 *   - save strategy is 'explicit', AND
 *   - save status is 'unsaved' (edits pending flush via Ctrl+S)
 *
 * This is the only protection against accidental data loss in explicit mode.
 * A crash before Ctrl+S flushes the snapshot will lose unsaved edits (by design —
 * the D-07 "Manual" contract). The beforeunload guard warns the user before close.
 */
export function useBeforeUnloadGuard() {
  const status = useSaveStatus()
  const strategy = useSaveStrategy()

  useEffect(() => {
    if (strategy !== 'explicit' || status !== 'unsaved') return

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      // Setting returnValue triggers the browser's built-in confirmation dialog.
      // The actual string is ignored by modern browsers (they show a generic message).
      e.returnValue = ''
    }

    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [status, strategy])
}
