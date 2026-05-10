import { useEffect, useState } from 'react'
import { Card, Flex, IconButton, Slider, Text, Tooltip } from '@radix-ui/themes'
import { ResetIcon } from '@radix-ui/react-icons'
import {
  PARAM_BOUNDS,
  PARAM_DEFAULTS,
  usePipelineParams,
  type SliderKey,
} from '../../stores/usePipelineParams'

interface SliderCardProps {
  paramKey: SliderKey
  label: string
  /** Called after debounce expiry from the parent; triggers render dispatch. */
  onCommit: () => void
  /** Called by reset button — fires immediately, bypassing debounce. */
  onResetCommit: () => void
}

const FLASH_MS = 600

export function SliderCard({ paramKey, label, onCommit, onResetCommit }: SliderCardProps) {
  const value = usePipelineParams((s) => s.values[paramKey])
  const setValue = usePipelineParams((s) => s.setValue)
  const resetSlider = usePipelineParams((s) => s.resetSlider)
  const bounds = PARAM_BOUNDS[paramKey]
  const def = PARAM_DEFAULTS[paramKey]
  const [flash, setFlash] = useState(false)
  const [text, setText] = useState(String(value))

  useEffect(() => {
    setText(String(value))
  }, [value])

  const commitNumeric = (raw: string) => {
    const n = Number(raw)
    if (Number.isFinite(n) && n >= bounds.min && n <= bounds.max) {
      // Snap to step grid
      const stepped =
        Math.round((n - bounds.min) / bounds.step) * bounds.step + bounds.min
      const clamped = Math.min(bounds.max, Math.max(bounds.min, stepped))
      setValue(paramKey, clamped)
      onCommit()
    } else {
      setText(String(value)) // revert text to last valid
      setFlash(true)
      window.setTimeout(() => setFlash(false), FLASH_MS)
    }
  }

  const onReset = () => {
    resetSlider(paramKey)
    onResetCommit()
  }

  return (
    <Card variant="surface" data-testid={`slider-card-${paramKey}`}>
      <Flex direction="column" gap="3" p="3">
        <Flex justify="between" align="center">
          <Text size="2" weight="bold">
            {label}
          </Text>
          <Tooltip content="Redefinir para padrão">
            <IconButton
              size="1"
              variant="ghost"
              color="gray"
              onClick={onReset}
              aria-label={`Redefinir ${label}`}
            >
              <ResetIcon />
            </IconButton>
          </Tooltip>
        </Flex>

        <div style={{ position: 'relative', paddingTop: 4, paddingBottom: 8 }}>
          <Slider
            value={[value]}
            min={bounds.min}
            max={bounds.max}
            step={bounds.step}
            onValueChange={(v) => setValue(paramKey, v[0])}
            onValueCommit={() => onCommit()}
            data-testid={`slider-${paramKey}`}
          />
          {/* Default-tick marker: positioned at the percentage that maps to the default value */}
          <div
            data-testid={`tick-${paramKey}`}
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: 0,
              left: `${((def - bounds.min) / (bounds.max - bounds.min)) * 100}%`,
              width: 2,
              height: 8,
              background: 'var(--gray-9)',
            }}
          />
        </div>

        <Flex justify="between">
          <Text size="1" color="gray">
            {bounds.min}
          </Text>
          <Text size="1" color="gray">
            {bounds.max}
          </Text>
        </Flex>

        <Flex align="center" gap="2">
          <input
            type="number"
            value={text}
            min={bounds.min}
            max={bounds.max}
            step={bounds.step}
            onChange={(e) => setText(e.target.value)}
            onBlur={(e) => commitNumeric(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter')
                commitNumeric((e.target as HTMLInputElement).value)
            }}
            aria-label={`${label} value`}
            data-flash={flash ? 'true' : 'false'}
            style={{
              width: 80,
              padding: '4px 8px',
              border: `1px solid ${flash ? 'var(--red-9)' : 'var(--gray-7)'}`,
              borderRadius: 4,
              transition: 'border-color 200ms',
            }}
          />
          <Text size="1" color="gray">
            padrão: {def}
          </Text>
        </Flex>
      </Flex>
    </Card>
  )
}
