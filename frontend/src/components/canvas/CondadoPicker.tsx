/**
 * CondadoPicker — Radix Select dropdown for assigning a condado at carve time (D-26).
 * Phase 08.3 Plan 09.
 *
 * Props:
 *   condados         — list of condado options (id + name + idx + duchy_id + kingdom_id)
 *   value            — currently selected condado_idx (null = parent default / unset)
 *   parentCondadoIdx — the parent barony's condado_idx, shown in the default-option label
 *   onChange         — fires with { condado_idx, duchy_id, kingdom_id } when a real condado
 *                      is chosen, or null when the "Herdar do pai" (inherit) option is selected.
 *                      The picked values include the CHOSEN condado's transitive duchy/kingdom
 *                      (D-26 transitive hierarchy) — never the parent's.
 *
 * DOM: CondadoPicker is a Radix `Select` (DOM element). It CANNOT render inside
 * PenDrawLayer's Konva tree (react-konva rejects DOM children in <Layer>). It is
 * hosted in the CanvasViewer DOM overlay alongside the action bar (see CanvasViewer.tsx).
 *
 * Radix Select sentinel: @radix-ui/themes Select.Item throws on value="". The "Herdar do pai"
 * default option uses the sentinel value "inherit" which maps to null in onChange.
 *
 * De-duplication: callers must de-dupe condados by id before passing them. The picker
 * renders one item per entry in the condados array.
 */

import React from 'react'
import { Select, Text } from '@radix-ui/themes'

// ── Types exported for consumer + tests ──────────────────────────────────────

export interface CondadoPickerCondado {
  id: string
  name: string
  idx: number
  duchy_id?: string
  kingdom_id?: string
}

export interface CondadoPickerValue {
  condado_idx: number
  duchy_id: string
  kingdom_id: string
}

export interface CondadoPickerProps {
  /** List of condado options (de-duped by id from effectiveTerritories). */
  condados: CondadoPickerCondado[]
  /** Currently selected condado_idx; null = unset / inherit from parent. */
  value: number | null
  /** Parent barony's condado_idx — used in the default-option label. */
  parentCondadoIdx: number
  /** Fires with the chosen condado's own hierarchy, or null for parent default. */
  onChange: (sel: CondadoPickerValue | null) => void
}

const INHERIT_SENTINEL = 'inherit'

/**
 * Pure helper: converts the raw Radix Select string value to a CondadoPickerValue
 * (or null for the inherit sentinel / unknown idx).
 * Exported for unit testing (jsdom Radix Select portal isolation).
 *
 * D-26 transitive: the returned duchy_id/kingdom_id come from the CHOSEN condado,
 * never inherited from the parent.
 */
export function computePickerChange(
  raw: string,
  condados: CondadoPickerCondado[],
): CondadoPickerValue | null {
  if (raw === INHERIT_SENTINEL) return null
  const idx = parseInt(raw, 10)
  if (isNaN(idx)) return null
  const chosen = condados.find((c) => c.idx === idx)
  if (!chosen) return null
  return {
    condado_idx: chosen.idx,
    duchy_id: chosen.duchy_id ?? '',
    kingdom_id: chosen.kingdom_id ?? '',
  }
}

export const CondadoPicker: React.FC<CondadoPickerProps> = ({
  condados,
  value,
  parentCondadoIdx,
  onChange,
}) => {
  // Map value (number | null) → Radix string value
  const selectValue = value === null ? INHERIT_SENTINEL : String(value)

  // Find the parent condado name for the default label (best-effort).
  const parentCondado = condados.find((c) => c.idx === parentCondadoIdx)
  const parentLabel = parentCondado ? `${parentCondado.name} (idx ${parentCondadoIdx})` : `Condado ${parentCondadoIdx}`

  const handleValueChange = (raw: string) => {
    onChange(computePickerChange(raw, condados))
  }

  return (
    <Select.Root value={selectValue} onValueChange={handleValueChange} size="1">
      <Select.Trigger
        data-testid="condado-picker"
        style={{ minWidth: 180 }}
      />
      <Select.Content>
        {/* Default / inherit option — value must be non-empty (Radix throws on "") */}
        <Select.Item value={INHERIT_SENTINEL} data-testid="condado-option-inherit">
          <Text size="1">Herdar do pai ({parentLabel})</Text>
        </Select.Item>
        <Select.Separator />
        {/* One item per condado; de-dupe by id is caller's responsibility */}
        {condados.map((c) => (
          <Select.Item
            key={c.id}
            value={String(c.idx)}
            data-testid={`condado-option-${c.idx}`}
          >
            <Text size="1">{c.name} (idx {c.idx})</Text>
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}

export default CondadoPicker
