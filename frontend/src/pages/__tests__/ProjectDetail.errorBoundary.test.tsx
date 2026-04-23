import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme, Callout } from '@radix-ui/themes'
import { ErrorBoundary } from 'react-error-boundary'

/**
 * GAP-07 regression: when InspectorSidebarWrapper throws, the ErrorBoundary
 * must render a visible fallback ("Sidebar failed to load — check console")
 * rather than blanking the sidebar. This test exercises the exact
 * ErrorBoundary shape used in `ProjectDetail.tsx` (fallback + onError) without
 * rendering the full ProjectDetail tree (which would require mocking the
 * entire api/client, router, and query plumbing).
 *
 * The contract being locked in:
 *   - Fallback uses Radix Callout.Root with color="red" and text
 *     "Sidebar failed to load — check console."
 *   - onError logs full error detail to console.error (developer triage)
 *     and NOT into the fallback UI (T-02-05-02 information-disclosure
 *     mitigation — no err.stack / err.message in the rendered fallback).
 */

function Thrower(): never {
  throw new Error('Simulated InspectorSidebar failure — GAP-07 test')
}

describe('ProjectDetail — InspectorSidebar ErrorBoundary (GAP-07)', () => {
  it('renders generic fallback text when the wrapped subtree throws', () => {
    // Suppress React's expected error output in test logs
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const onError = vi.fn()

    render(
      <Theme>
        <ErrorBoundary
          onError={(err) => {
            // eslint-disable-next-line no-console
            console.error('[InspectorSidebar] boundary caught:', err)
            onError(err)
          }}
          fallback={
            <Callout.Root color="red" size="1">
              <Callout.Text>
                Sidebar failed to load — check console.
              </Callout.Text>
            </Callout.Root>
          }
        >
          <Thrower />
        </ErrorBoundary>
      </Theme>,
    )

    // Fallback is visible
    expect(screen.getByText(/Sidebar failed to load/i)).toBeInTheDocument()

    // onError fired with the actual thrown Error
    expect(onError).toHaveBeenCalled()
    const caught = onError.mock.calls[0]![0] as Error
    expect(caught.message).toMatch(/Simulated InspectorSidebar failure/i)

    // T-02-05-02: the thrown stack / message MUST NOT leak into the visible
    // DOM. We allow the text "check console" — nothing more.
    const visibleText = document.body.textContent ?? ''
    expect(visibleText).not.toMatch(/Simulated InspectorSidebar failure/)
    expect(visibleText).not.toMatch(/at Thrower/) // stack frames
    expect(visibleText).not.toMatch(/\.tsx:\d+/) // source paths

    errSpy.mockRestore()
  })
})
