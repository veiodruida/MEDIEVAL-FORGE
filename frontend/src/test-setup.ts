import '@testing-library/jest-dom/vitest'

// jsdom does not implement ResizeObserver (used by Radix ScrollArea and several
// other Radix primitives). Provide a minimal stub so components that mount it
// during tests don't crash. Real behavior is covered by Playwright e2e.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).ResizeObserver = ResizeObserverStub
}
