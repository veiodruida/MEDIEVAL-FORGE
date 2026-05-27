/**
 * VertexCapBadge — Phase 08 D-06 vertex count badge.
 *
 * REQ-IDs: EDIT-VERTEX-04, D-06 (hard cap 1000, warning at 500)
 *
 * Badge color/copy logic (PLAN 08-06a interfaces):
 *   count < max/2:         no badge rendered
 *   max/2 <= count < max:  amber Badge "N vértices — simplificar recomendado"
 *   count >= max:          red Badge "Limite de N vértices atingido"
 */
import React from 'react';
import { Badge } from '@radix-ui/themes';

interface VertexCapBadgeProps {
  /** Current vertex count for the active barony. */
  count: number;
  /** Hard cap (D-06 default: 1000). Warning fires at max/2 (default: 500). */
  max: number;
}

export const VertexCapBadge: React.FC<VertexCapBadgeProps> = ({ count, max }) => {
  // Hard cap reached — red badge
  if (count >= max) {
    return (
      <Badge color="red" variant="soft">
        {`Limite de ${max} vértices atingido`}
      </Badge>
    );
  }

  // Warning threshold (max/2) reached — amber badge
  if (count >= max / 2) {
    return (
      <Badge color="amber" variant="soft">
        {`${count} vértices — simplificar recomendado`}
      </Badge>
    );
  }

  // Below warning threshold — render nothing
  return null;
};
