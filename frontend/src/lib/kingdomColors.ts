/**
 * Kingdom color palette — 20 visually distinct, saturated hex colors.
 * Jewel tones + distinct hues designed to read over the muted terrain base.
 * These fills are set directly on Konva shape `fill` props — NOT Radix tokens.
 */
export const KINGDOM_PALETTE: readonly string[] = [
  '#c0392b', '#2980b9', '#27ae60', '#8e44ad', '#f39c12',
  '#16a085', '#d35400', '#2c3e50', '#c2185b', '#00897b',
  '#7b1fa2', '#388e3c', '#f57c00', '#1976d2', '#5d4037',
  '#00695c', '#ad1457', '#283593', '#bf360c', '#4527a0',
] as const

/**
 * Returns the palette color for a kingdom.
 *
 * @param kingdomId - The kingdom identifier (used as fallback hash seed).
 * @param indexInDict - Non-negative integer index of the kingdom in its
 *   ordered list. When valid, selects color by index (mod palette length)
 *   so the mapping is stable and predictable. When negative, NaN, or
 *   non-finite, falls back to a deterministic char-code hash of `kingdomId`.
 */
export function kingdomColorFor(kingdomId: string, indexInDict: number): string {
  const len = KINGDOM_PALETTE.length
  if (Number.isFinite(indexInDict) && indexInDict >= 0) {
    return KINGDOM_PALETTE[Math.floor(indexInDict) % len]
  }
  // Deterministic fallback: sum of char codes mod palette length.
  let hash = 0
  for (let i = 0; i < kingdomId.length; i++) {
    hash += kingdomId.charCodeAt(i)
  }
  return KINGDOM_PALETTE[hash % len]
}
