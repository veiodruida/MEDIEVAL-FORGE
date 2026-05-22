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
}

export function ModelOutputPanel({ text, active }: ModelOutputPanelProps) {
  const [open, setOpen] = useState(true)
  const preRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (!open) return
    const el = preRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [open, text])

  if (!active && !text) {
    return null
  }

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
          ({text.length} caractere{text.length === 1 ? '' : 's'})
        </Text>
      </Flex>
      {open && (
        <Box mt="2">
          <pre ref={preRef} style={OUTPUT_BOX_STYLE} data-testid="model-output-text">
            {text || '(aguardando primeiro token…)'}
          </pre>
        </Box>
      )}
    </Box>
  )
}
