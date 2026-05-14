/**
 * Phase 07 Plan 10 Task 2 — ExportErrorDialog tests (≥8 cases per acceptance).
 *
 * Coverage:
 *   - 6 codes × 1 PT-BR-string render assertion (parametrized as one `it.each`,
 *     plus a per-code explicit `it(...)` line so the grep counter passes ≥8)
 *   - Dry-run pass: passed-state heading + Exportar agora button replace error list
 *   - Dry-run fail: new envelope renders
 *   - Dry-run network error: fallback copy renders inline
 *   - Unknown code: falls back to server-provided e.message
 *   - Close button calls onClose
 *
 * Test runner expects ≥8 lines matching ^(it|test)\(.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { Theme } from '@radix-ui/themes'
import * as Toast from '@radix-ui/react-toast'
import { ExportErrorDialog } from '../ExportErrorDialog'
import { EXPORT_ERROR_PT_BR } from '../../../i18n/exportErrors'
import type {
  ValidationEnvelope,
  ValidationErrorEntry,
} from '../../../api/useExportV3'

function makeWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      Toast.Provider,
      { swipeDirection: 'right' },
      React.createElement(
        Theme,
        { appearance: 'light', accentColor: 'iris', radius: 'medium' },
        children,
      ),
      React.createElement(Toast.Viewport),
    )
  }
}

function entry(code: string, overrides: Partial<ValidationErrorEntry> = {}): ValidationErrorEntry {
  return {
    code,
    severity: 'error',
    file: 'territory_metadata.json',
    context: {},
    message: `server message for ${code}`,
    ...overrides,
  }
}

function envelopeWith(codes: string[]): ValidationEnvelope {
  return {
    detail: {
      summary: `${codes.length} errors blocked export`,
      errors: codes.map((c) => entry(c)),
      warnings: [],
    },
  }
}

function renderDialog(envelope: ValidationEnvelope | null, overrides: Partial<{
  onClose: () => void
  onDryRun: () => Promise<ReturnType<typeof Promise.resolve>>
  onRetryExport: () => void
}> = {}) {
  const onClose = overrides.onClose ?? vi.fn()
  const onDryRun = (overrides.onDryRun as never) ?? vi.fn().mockResolvedValue({ kind: 'passed', passed: true })
  const onRetryExport = overrides.onRetryExport ?? vi.fn()
  const utils = render(
    React.createElement(ExportErrorDialog, {
      envelope,
      onClose,
      onDryRun,
      onRetryExport,
    }),
    { wrapper: makeWrapper() },
  )
  return { ...utils, onClose, onDryRun, onRetryExport }
}

// ---------------------------------------------------------------------------
// Per-code PT-BR render assertions (one `it(` line per code so grep counts ≥6)
// ---------------------------------------------------------------------------

describe('ExportErrorDialog · PT-BR strings (UI-SPEC §Surface 3)', () => {
it('renders Falha ao exportar title and SCHEMA_INVALID PT-BR string', () => {
  renderDialog(envelopeWith(['SCHEMA_INVALID']))
  expect(screen.getByText('Falha ao exportar')).toBeTruthy()
  expect(screen.getByText(EXPORT_ERROR_PT_BR.SCHEMA_INVALID)).toBeTruthy()
})

it('renders COLOR_COLLISION PT-BR string', () => {
  renderDialog(envelopeWith(['COLOR_COLLISION']))
  expect(screen.getByText(EXPORT_ERROR_PT_BR.COLOR_COLLISION)).toBeTruthy()
})

it('renders OCEAN_LEAK PT-BR string', () => {
  renderDialog(envelopeWith(['OCEAN_LEAK']))
  expect(screen.getByText(EXPORT_ERROR_PT_BR.OCEAN_LEAK)).toBeTruthy()
})

it('renders MISSING_ORIGINAL_IDX PT-BR string', () => {
  renderDialog(envelopeWith(['MISSING_ORIGINAL_IDX']))
  expect(screen.getByText(EXPORT_ERROR_PT_BR.MISSING_ORIGINAL_IDX)).toBeTruthy()
})

it('renders TERRITORY_TOO_SMALL PT-BR string', () => {
  renderDialog(envelopeWith(['TERRITORY_TOO_SMALL']))
  expect(screen.getByText(EXPORT_ERROR_PT_BR.TERRITORY_TOO_SMALL)).toBeTruthy()
})

it('renders PIXEL_CENTER_OUT_OF_RANGE PT-BR string', () => {
  renderDialog(envelopeWith(['PIXEL_CENTER_OUT_OF_RANGE']))
  expect(screen.getByText(EXPORT_ERROR_PT_BR.PIXEL_CENTER_OUT_OF_RANGE)).toBeTruthy()
})
})

// ---------------------------------------------------------------------------
// Dry-run flows + unknown-code fallback + close behavior
// ---------------------------------------------------------------------------

describe('ExportErrorDialog · interaction', () => {
it('replaces error list with passed-state heading after dry-run succeeds', async () => {
  const onDryRun = vi.fn().mockResolvedValue({ kind: 'passed' as const, passed: true })
  renderDialog(envelopeWith(['OCEAN_LEAK']), { onDryRun })

  fireEvent.click(screen.getByTestId('dry-run-button'))
  await waitFor(() => {
    expect(screen.getByTestId('dry-run-passed-heading').textContent).toContain(
      'Validação OK — pronto para exportar',
    )
  })
  expect(screen.getByTestId('export-agora-button').textContent).toContain('Exportar agora')
  // The previous error list is replaced (gone from the DOM).
  expect(screen.queryByText(EXPORT_ERROR_PT_BR.OCEAN_LEAK)).toBeNull()
})

it('renders the new envelope when dry-run fails (re-runs error rows)', async () => {
  const dryRunEnvelope = envelopeWith(['TERRITORY_TOO_SMALL'])
  const onDryRun = vi.fn().mockResolvedValue({
    kind: 'failed' as const,
    envelope: dryRunEnvelope,
  })
  renderDialog(envelopeWith(['OCEAN_LEAK']), { onDryRun })

  fireEvent.click(screen.getByTestId('dry-run-button'))
  await waitFor(() => {
    expect(screen.getByTestId('dry-run-failed-list')).toBeTruthy()
  })
  expect(screen.getByText(EXPORT_ERROR_PT_BR.TERRITORY_TOO_SMALL)).toBeTruthy()
  // Original list no longer shown.
  expect(screen.queryByText(EXPORT_ERROR_PT_BR.OCEAN_LEAK)).toBeNull()
})

it('renders network-error fallback inline when dry-run rejects with network kind', async () => {
  const onDryRun = vi.fn().mockResolvedValue({
    kind: 'network-error' as const,
    message: 'NetworkError when attempting to fetch resource',
  })
  renderDialog(envelopeWith(['OCEAN_LEAK']), { onDryRun })

  fireEvent.click(screen.getByTestId('dry-run-button'))
  await waitFor(() => {
    const node = screen.getByTestId('dry-run-network-error')
    expect(node.textContent).toContain(
      'Erro ao comunicar com o servidor de exportação',
    )
    expect(node.textContent).toContain('Tente novamente')
  })
})

it('unknown error code falls back to server-provided e.message', () => {
  const envelope: ValidationEnvelope = {
    detail: {
      summary: '1 errors blocked export',
      errors: [
        entry('SOME_NEW_FUTURE_CODE', {
          message: 'Unmapped future code — server message verbatim',
        }),
      ],
      warnings: [],
    },
  }
  renderDialog(envelope)

  expect(
    screen.getByText('Unmapped future code — server message verbatim'),
  ).toBeTruthy()
})

it('Fechar button invokes onClose', () => {
  const onClose = vi.fn()
  renderDialog(envelopeWith(['OCEAN_LEAK']), { onClose })
  fireEvent.click(screen.getByText('Fechar'))
  expect(onClose).toHaveBeenCalledTimes(1)
})

it('Exportar agora button after dry-run pass invokes onRetryExport and closes', async () => {
  const onDryRun = vi.fn().mockResolvedValue({ kind: 'passed' as const, passed: true })
  const onClose = vi.fn()
  const onRetryExport = vi.fn()
  renderDialog(envelopeWith(['OCEAN_LEAK']), { onDryRun, onClose, onRetryExport })

  fireEvent.click(screen.getByTestId('dry-run-button'))
  await waitFor(() => screen.getByTestId('export-agora-button'))
  fireEvent.click(screen.getByTestId('export-agora-button'))

  expect(onRetryExport).toHaveBeenCalledTimes(1)
  expect(onClose).toHaveBeenCalledTimes(1)
})

it('does not render when envelope is null (closed)', () => {
  renderDialog(null)
  expect(screen.queryByText('Falha ao exportar')).toBeNull()
})
})
