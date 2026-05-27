/**
 * Phase 08 Plan 06a — VertexCapBadge tests.
 * REQ-IDs: EDIT-VERTEX-04, D-06 (cap 1000, warning at 500)
 *
 * Badge color/copy logic:
 *   count < 500: no badge rendered
 *   500 <= count < 1000: amber Badge "N vértices — simplificar recomendado"
 *   count == 1000: red Badge "Limite de 1000 vértices atingido"
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { VertexCapBadge } from '../VertexCapBadge';

describe('VertexCapBadge — count below warning threshold', () => {
  it('renders nothing when vertex count is 499 (below 500 threshold)', () => {
    const { container } = render(<VertexCapBadge count={499} max={1000} />);
    expect(container.firstElementChild).toBeNull();
  });

  it('renders nothing when vertex count is 0', () => {
    const { container } = render(<VertexCapBadge count={0} max={1000} />);
    expect(container.firstElementChild).toBeNull();
  });
});

describe('VertexCapBadge — warning state (amber at 500)', () => {
  it('renders amber Badge with vertex count text at exactly 500', () => {
    const { getByText } = render(<VertexCapBadge count={500} max={1000} />);
    const badge = getByText('500 vértices — simplificar recomendado');
    expect(badge).toBeTruthy();
  });

  it('renders amber Badge at 750 (mid-range warning)', () => {
    const { getByText } = render(<VertexCapBadge count={750} max={1000} />);
    expect(getByText('750 vértices — simplificar recomendado')).toBeTruthy();
  });

  it('renders amber Badge at 999 (just below cap)', () => {
    const { getByText } = render(<VertexCapBadge count={999} max={1000} />);
    expect(getByText('999 vértices — simplificar recomendado')).toBeTruthy();
  });
});

describe('VertexCapBadge — cap state (red at 1000)', () => {
  it('renders red Badge with cap text at exactly 1000 (hard cap D-06)', () => {
    const { getByText } = render(<VertexCapBadge count={1000} max={1000} />);
    expect(getByText('Limite de 1000 vértices atingido')).toBeTruthy();
  });

  it('renders red Badge (not amber) when count equals max', () => {
    const { container } = render(<VertexCapBadge count={1000} max={1000} />);
    // Should have exactly one badge element
    expect(container.firstElementChild).not.toBeNull();
    // Text must be the cap message, not the warning message
    expect(container.textContent).toContain('Limite de 1000 vértices atingido');
    expect(container.textContent).not.toContain('simplificar recomendado');
  });
});
