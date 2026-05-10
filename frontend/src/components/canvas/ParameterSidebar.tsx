import { useCallback } from 'react'
import { Box, Flex, ScrollArea, Separator, Text } from '@radix-ui/themes'
import { SliderCard } from './SliderCard'
import { StageViewToggle } from './StageViewToggle'
import {
  usePipelineParams,
  diffOverrides,
  type SliderKey,
} from '../../stores/usePipelineParams'
import { useRunStore } from '../../stores/useRunStore'
import { useRenderStream } from '../../api/useRenderStream'
import { postRender, postRenderCancel } from '../../api/render'
import { useDebouncedCallback } from 'use-debounce'

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

  const dispatchRender = useCallback(async () => {
    const { values, lastRendered, stageView } = usePipelineParams.getState()
    const diff = diffOverrides(values, lastRendered)
    if (Object.keys(diff).length === 0) return
    // Latest-wins (D-07): cancel in-flight, close SSE, then POST + subscribe.
    renderStream.close()
    await postRenderCancel(projectId).catch(() => {})
    try {
      const { run_id } = await postRender(projectId, diff, stageView)
      useRunStore.getState().startRender(run_id)
      usePipelineParams.getState().markRendered(values)
      renderStream.subscribe(projectId)
    } catch (e) {
      const msg = (e as Error).message
      useRunStore.getState().finish('error', msg)
    }
  }, [projectId, renderStream])

  const debouncedRender = useDebouncedCallback(dispatchRender, 250)

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
