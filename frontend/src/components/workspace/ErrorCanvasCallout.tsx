import { Box, Button, Callout, Flex } from '@radix-ui/themes'
import { ExclamationTriangleIcon } from '@radix-ui/react-icons'
import type { PipelineStage } from '../../stores/useRunStore'

export interface ErrorCanvasCalloutProps {
  errorStage: PipelineStage | null
  errorMessage: string
  lastLogLine?: string | null
  onRetry: () => void
}

/**
 * D-08 error callout — top-of-canvas red Callout with stage name,
 * last log line, copyable error block, retry CTA.
 */
export function ErrorCanvasCallout({
  errorStage,
  errorMessage,
  lastLogLine,
  onRetry,
}: ErrorCanvasCalloutProps) {
  const handleCopy = () => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(errorMessage).catch(() => {})
    }
  }

  return (
    <Box data-testid="error-canvas-callout" p="3">
      <Callout.Root color="red" variant="surface">
        <Callout.Icon>
          <ExclamationTriangleIcon />
        </Callout.Icon>
        <Callout.Text>
          <strong>Falha no estágio: {errorStage ?? 'desconhecido'}</strong>
        </Callout.Text>
        {lastLogLine && (
          <Callout.Text>
            <span style={{ fontSize: 12, color: 'var(--gray-11)' }}>{lastLogLine}</span>
          </Callout.Text>
        )}
        <Callout.Text>
          <Box
            asChild
            style={{
              background: 'var(--red-3)',
              padding: '4px 8px',
              borderRadius: 4,
              fontFamily: 'monospace',
              fontSize: 12,
              display: 'block',
              wordBreak: 'break-word',
            }}
          >
            <code>{errorMessage}</code>
          </Box>
        </Callout.Text>
        <Flex gap="2" mt="2">
          <Button color="red" variant="soft" onClick={onRetry}>
            Tentar novamente
          </Button>
          <Button color="gray" variant="soft" onClick={handleCopy}>
            Copiar
          </Button>
        </Flex>
      </Callout.Root>
    </Box>
  )
}
