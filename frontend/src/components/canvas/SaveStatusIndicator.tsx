import { Badge } from '@radix-ui/themes'
import { useSaveStatus } from '../../services/persistence'

/**
 * SaveStatusIndicator (D-07) — header badge reflecting current save status.
 *
 * Status strings per UI-SPEC §Copywriting Contract:
 *   saved   → "Salvo ✓"       (green)
 *   saving  → "Salvando…"     (gray)
 *   unsaved → "Alterações não salvas" (amber)
 */
export function SaveStatusIndicator() {
  const status = useSaveStatus()
  if (status === 'saved') {
    return (
      <Badge color="green" variant="soft">
        Salvo ✓
      </Badge>
    )
  }
  if (status === 'saving') {
    return (
      <Badge color="gray" variant="soft">
        Salvando…
      </Badge>
    )
  }
  return (
    <Badge color="amber" variant="soft">
      Alterações não salvas
    </Badge>
  )
}
