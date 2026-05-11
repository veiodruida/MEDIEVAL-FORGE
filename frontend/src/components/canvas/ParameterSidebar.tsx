import { useCallback } from 'react'
import { Box, Flex, ScrollArea, Separator, Text } from '@radix-ui/themes'
import { SliderCard } from './SliderCard'
import { StageViewToggle } from './StageViewToggle'
import { usePipelineParams, type SliderKey } from '../../stores/usePipelineParams'
import { useRenderStream } from '../../api/useRenderStream'
import { useParameterStudioDispatch } from '../../hooks/useParameterStudioDispatch'

interface ParameterSidebarProps {
  projectId: string
}

const SIDEBAR_W = 320

const SLIDER_LABELS: Record<SliderKey, string> = {
  smooth_sigma: 'Suavização (σ)',
  median_passes: 'Passes Mediana',
  fragment_min_px: 'Fragmento mín. (px)',
  blob_merge_px: 'Fusão de blobs (px)',
}

export function ParameterSidebar({ projectId }: ParameterSidebarProps) {
  const sidebarOpen = usePipelineParams((s) => s.sidebarOpen)
  const renderStream = useRenderStream()

  // D-06 (Phase 04.1 WR-03): single canonical dispatch path.
  // useParameterStudioDispatch wraps the 250ms-debounced latest-wins sequence
  // + D-04 bounded RENDER_BUSY retry. We pass renderStream.subscribe via
  // onRenderStarted so the SSE consumer attaches once a run_id is returned.
  // useRenderStream.subscribe internally closes any prior EventSource — no
  // need for an explicit renderStream.close() here.
  const debouncedRender = useParameterStudioDispatch(projectId, (_runId) => {
    renderStream.subscribe(projectId)
  })

  // Reset bypasses debounce — flush() invokes the wrapped fn synchronously.
  const onResetCommit = useCallback(
    () => debouncedRender.flush(),
    [debouncedRender],
  )

  if (!sidebarOpen) return null

  const keys: SliderKey[] = [
    'smooth_sigma',
    'median_passes',
    'fragment_min_px',
    'blob_merge_px',
  ]

  return (
    <Box
      data-testid="parameter-sidebar"
      style={{
        width: SIDEBAR_W,
        height: '100%',
        overflow: 'hidden',
        borderRight: '1px solid var(--gray-6)',
        background: 'var(--color-panel-solid)',
      }}
    >
      <ScrollArea>
        <Flex direction="column" gap="4" p="4">
          <Text size="3" weight="bold">
            Parâmetros
          </Text>
          <StageViewToggle />
          <Separator size="4" />
          {keys.map((k) => (
            <SliderCard
              key={k}
              paramKey={k}
              label={SLIDER_LABELS[k]}
              onCommit={debouncedRender}
              onResetCommit={onResetCommit}
            />
          ))}
        </Flex>
      </ScrollArea>
    </Box>
  )
}
