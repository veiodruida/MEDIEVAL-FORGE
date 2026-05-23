/**
 * Live model output pane (UAT 2026-05-22).
 *
 * Reads the `modelOutput` accumulator from useResearchStream and renders the
 * model's raw tokens as they arrive. Distinct from LogPanel (server-side
 * stdout); this is the actual JSON the LLM is producing.
 *
 * Auto-scrolls to the bottom on every update so the cursor follows the
 * latest token without manual scrolling.
 */
import { useEffect, useRef, useState } from 'react'
import { Box, Flex, Text } from '@radix-ui/themes'

const OUTPUT_BOX_STYLE: React.CSSProperties = {
  background: '#0d0f12',
  color: '#a7f3d0',
  border: '1px solid var(--gray-6)',
  borderRadius: '6px',
  padding: '8px 10px',
  fontFamily:
    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
  fontSize: '11px',
  lineHeight: '1.45',
  maxHeight: '220px',
  minHeight: '120px',
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}

export interface ModelOutputPanelProps {
  /** Accumulated model output text from useResearchStream.state.modelOutput. */
  text: string
  /** When true, the panel renders even before any token arrives. */
  active: boolean
  /**
   * UAT 2026-05-23 — provider heartbeat message (PT-BR) shown while the
   * model is loading / processing the prompt and no token has arrived yet.
   * Cleared by useResearchStream once the first token lands.
   */
  progressMessage?: string
}

export function ModelOutputPanel({ text, active, progressMessage }: ModelOutputPanelProps) {
  const [open, setOpen] = useState(true)
  const preRef = useRef<HTMLPreElement>(null)

  // UAT 2026-05-23 — client-side elapsed counter so the user has a live
  // signal even if the backend heartbeat is delayed (slow first probe on
  // a cold local model, or a transient SSE buffering hiccup somewhere
  // along the proxy chain). Resets every time the panel transitions from
  // inactive to active.
  const [elapsedMs, setElapsedMs] = useState(0)
  useEffect(() => {
    if (!active || text) {
      setElapsedMs(0)
      return
    }
    const start = Date.now()
    setElapsedMs(0)
    const id = window.setInterval(() => {
      setElapsedMs(Date.now() - start)
    }, 250)
    return () => window.clearInterval(id)
  }, [active, text])

  useEffect(() => {
    if (!open) return
    const el = preRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [open, text])

  if (!active && !text) {
    return null
  }

  const placeholder = (() => {
    if (text) return text
    const seconds = Math.floor(elapsedMs / 1000)
    const tail = `Aguardando primeiro token… (${seconds}s)`
    if (progressMessage) {
      return `${progressMessage}\n${tail}`
    }
    return tail
  })()

  return (
    <Box data-testid="model-output-panel">
      <Flex
        align="center"
        gap="2"
        onClick={() => setOpen((v) => !v)}
        style={{ cursor: 'pointer', userSelect: 'none' }}
        data-testid="model-output-panel-toggle"
      >
        <Text size="2" weight="medium">
          {open ? '▾' : '▸'} Saída do modelo
        </Text>
        <Text size="1" color="gray">
          {text
            ? `(${text.length} caractere${text.length === 1 ? '' : 's'})`
            : `(aguardando · ${Math.floor(elapsedMs / 1000)}s)`}
        </Text>
      </Flex>
      {open && (
        <Box mt="2">
          <pre ref={preRef} style={OUTPUT_BOX_STYLE} data-testid="model-output-text">
            {placeholder}
          </pre>
        </Box>
      )}
    </Box>
  )
}
