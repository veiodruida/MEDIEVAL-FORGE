/**
 * Phase 07 Plan 10 Task 2 — ExportErrorDialog (Phase 06 absorption).
 *
 * Renders the D-08 422 envelope returned by POST /api/v3/projects/{id}/export
 * with PT-BR strings keyed by the 6 stable error codes (UI-SPEC §Surface 3).
 *
 * Visual contract (07-UI-SPEC §Surface 3 + 07-RESEARCH §Example 4):
 *  - Dialog title `Falha ao exportar`
 *  - Subtitle from envelope.detail.summary (verbatim)
 *  - Top-right `Validar antes de exportar` button (dry-run trigger)
 *  - One row per error: [<Badge color="red" variant="soft">{code}</Badge>]
 *    · <Text size="1" color="gray">{file}</Text>
 *    · <Text size="2">{EXPORT_ERROR_PT_BR[code] ?? message}</Text>
 *  - Footer: `Fechar` button; `Exportar agora` appears after a passing dry-run
 *
 * Unknown-code forward-compat: nullish-coalesce the i18n map onto server message.
 * React text children only — never inject raw HTML (T-07-10-01 XSS mitigation).
 */
import { useState } from 'react'
import { Dialog, Badge, Button, Flex, Heading, Text } from '@radix-ui/themes'
import { EXPORT_ERROR_PT_BR } from '../../i18n/exportErrors'
import type {
  ValidationEnvelope,
  ValidationErrorEntry,
} from '../../api/useExportV3'

const SUBTITLE_FALLBACK =
  'O pipeline gerou conteúdo que não atende ao contrato Unity. Corrija os problemas abaixo e tente novamente.'

const NETWORK_FALLBACK_PREFIX = 'Erro ao comunicar com o servidor de exportação:'

export interface ExportErrorDialogProps {
  /** D-08 envelope from the failed POST /export call. `null` → dialog closed. */
  envelope: ValidationEnvelope | null
  /** Closes the dialog (parent clears its `exportEnvelope` state). */
  onClose: () => void
  /**
   * Trigger the same mutation with `dryRun: true`. Returns the dry-run payload
   * (either a 200 `{dry_run, passed, errors, warnings}` or, on 422, the
   * ExportValidationError will already have been caught by the parent — we
   * receive the new envelope back as a rejected promise to render inline).
   */
  onDryRun: () => Promise<DryRunOutcome>
  /** Re-trigger the real export (closes the dialog and re-runs `handleExport`). */
  onRetryExport: () => void
}

export type DryRunOutcome =
  | { kind: 'passed'; passed: true }
  | { kind: 'failed'; envelope: ValidationEnvelope }
  | { kind: 'network-error'; message: string }

function renderRow(e: ValidationErrorEntry, index: number) {
  return (
    <Flex key={`${e.code}-${index}`} gap="2" align="center" wrap="wrap">
      <Badge color="red" variant="soft">{e.code}</Badge>
      {e.file && (
        <Text size="1" color="gray">
          {e.file}
        </Text>
      )}
      <Text size="2">{EXPORT_ERROR_PT_BR[e.code] ?? e.message}</Text>
    </Flex>
  )
}

export function ExportErrorDialog({
  envelope,
  onClose,
  onDryRun,
  onRetryExport,
}: ExportErrorDialogProps) {
  const [dryRunResult, setDryRunResult] = useState<DryRunOutcome | null>(null)
  const [dryRunBusy, setDryRunBusy] = useState(false)

  const open = envelope !== null

  function handleOpenChange(next: boolean) {
    if (!next) {
      setDryRunResult(null)
      setDryRunBusy(false)
      onClose()
    }
  }

  async function handleDryRunClick() {
    setDryRunBusy(true)
    try {
      const result = await onDryRun()
      setDryRunResult(result)
    } finally {
      setDryRunBusy(false)
    }
  }

  function handleExportAgora() {
    setDryRunResult(null)
    onClose()
    onRetryExport()
  }

  if (!envelope) return null

  const summary = envelope.detail?.summary || SUBTITLE_FALLBACK
  const initialErrors = envelope.detail?.errors ?? []
  const passedDryRun = dryRunResult?.kind === 'passed'
  const failedDryRun =
    dryRunResult?.kind === 'failed' ? dryRunResult.envelope.detail : null
  const dryRunNetworkError =
    dryRunResult?.kind === 'network-error' ? dryRunResult.message : null

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Content style={{ maxWidth: 560 }}>
        <Flex justify="between" align="start" gap="3">
          <Dialog.Title>Falha ao exportar</Dialog.Title>
          {!passedDryRun && (
            <Button
              variant="soft"
              size="2"
              onClick={handleDryRunClick}
              disabled={dryRunBusy}
              data-testid="dry-run-button"
            >
              Validar antes de exportar
            </Button>
          )}
        </Flex>

        {!passedDryRun && (
          <Dialog.Description>
            <Text size="2" color="gray">
              {summary}
            </Text>
          </Dialog.Description>
        )}
        {passedDryRun && (
          <Dialog.Description>
            <Text size="2" color="gray">
              Validação concluída com sucesso.
            </Text>
          </Dialog.Description>
        )}

        {passedDryRun ? (
          <Flex direction="column" gap="2" mt="3">
            <Heading size="3" color="green" data-testid="dry-run-passed-heading">
              Validação OK — pronto para exportar
            </Heading>
            <Text size="2">
              Nenhum problema encontrado. Clique em "Exportar agora" para baixar o
              ZIP.
            </Text>
          </Flex>
        ) : failedDryRun ? (
          <Flex direction="column" gap="2" mt="3" data-testid="dry-run-failed-list">
            {failedDryRun.errors.map((e, i) => renderRow(e, i))}
          </Flex>
        ) : dryRunNetworkError ? (
          <Text size="2" color="red" mt="3" data-testid="dry-run-network-error">
            {`${NETWORK_FALLBACK_PREFIX} ${dryRunNetworkError}. Tente novamente.`}
          </Text>
        ) : (
          <Flex direction="column" gap="2" mt="3" data-testid="export-error-list">
            {initialErrors.map((e, i) => renderRow(e, i))}
          </Flex>
        )}

        <Flex justify="end" gap="2" mt="4">
          <Button variant="soft" color="gray" onClick={onClose}>
            Fechar
          </Button>
          {passedDryRun && (
            <Button
              onClick={handleExportAgora}
              data-testid="export-agora-button"
            >
              Exportar agora
            </Button>
          )}
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  )
}
