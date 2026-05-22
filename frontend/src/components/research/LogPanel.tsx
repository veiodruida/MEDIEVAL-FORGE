/**
 * Collapsible log panel rendered inside ResearchDialog.
 *
 * UAT 2026-05-22 — the user reported "Não consigo ver o andamento da pesquisa
 * e ver o que o modelo anda a fazer". This panel solves it by polling the
 * server log endpoints (llamacpp/ollama) every 2s and rendering the trailing
 * 200 lines in a monospace, autoscrolled <pre> element.
 *
 * Visibility is opt-in via the disclosure header so the dialog stays compact
 * for users who don't care about server-side noise.
 */
import { useEffect, useRef, useState } from 'react'
import { Box, Flex, Text } from '@radix-ui/themes'
import { useLlamacppLogs, useOllamaLogs } from '../../api/useServerLogs'

export interface LogPanelProps {
  /** Active provider — drives which subprocess log endpoint we poll. */
  provider: string
  /** When false, queries idle and panel collapses to its header. */
  enabled: boolean
  /**
   * UAT 2026-05-22 — auto-open the disclosure while a research stream is
   * active so users see what the server is doing without an extra click.
   * Once toggled manually by the user the explicit state wins.
   */
  autoOpen?: boolean
}

const LOG_BOX_STYLE: React.CSSProperties = {
  background: '#0d0f12',
  color: '#d4d4d8',
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

export function LogPanel({ provider, enabled, autoOpen = false }: LogPanelProps) {
  // Default open while a run is happening so the user sees the model's
  // chatter without an extra click. Persists across re-renders.
  const [open, setOpen] = useState(false)
  const [userToggled, setUserToggled] = useState(false)

  // When `autoOpen` flips true (research stream starts) and the user hasn't
  // yet expressed a preference this session, expand the disclosure. We do
  // NOT auto-collapse — once the user has the panel open we trust them.
  useEffect(() => {
    if (autoOpen && !userToggled && !open) {
      setOpen(true)
    }
  }, [autoOpen, userToggled, open])

  const showLlamacpp = enabled && open && provider === 'llamacpp'
  const showOllama = enabled && open && provider === 'ollama'

  const llamacpp = useLlamacppLogs(showLlamacpp)
  const ollama = useOllamaLogs(showOllama)

  const lines =
    provider === 'llamacpp'
      ? llamacpp.data?.lines ?? []
      : provider === 'ollama'
      ? ollama.data?.lines ?? []
      : []

  const preRef = useRef<HTMLPreElement>(null)
  useEffect(() => {
    if (!open) return
    const el = preRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [open, lines.length])

  if (provider === 'claude') {
    // Claude runs on Anthropic's servers — no local subprocess to tail.
    return null
  }

  const label =
    provider === 'llamacpp'
      ? 'Logs do llama-server'
      : provider === 'ollama'
      ? 'Logs do ollama serve'
      : 'Logs do servidor'

  return (
    <Box data-testid="server-log-panel">
      <Flex
        align="center"
        gap="2"
        onClick={() => {
          setUserToggled(true)
          setOpen((v) => !v)
        }}
        style={{ cursor: 'pointer', userSelect: 'none' }}
        data-testid="server-log-panel-toggle"
      >
        <Text size="2" weight="medium">
          {open ? '▾' : '▸'} {label}
        </Text>
        {open && lines.length > 0 && (
          <Text size="1" color="gray">
            ({lines.length} linha{lines.length === 1 ? '' : 's'})
          </Text>
        )}
      </Flex>
      {open && (
        <Box mt="2">
          <pre ref={preRef} style={LOG_BOX_STYLE} data-testid="server-log-output">
            {lines.length === 0
              ? '(sem saída — servidor inativo ou ainda inicializando)'
              : lines.join('\n')}
          </pre>
        </Box>
      )}
    </Box>
  )
}
