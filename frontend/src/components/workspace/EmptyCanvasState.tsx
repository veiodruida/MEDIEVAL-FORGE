import { Box, Button, Flex, Heading, Text } from '@radix-ui/themes'
import { MagicWandIcon } from '@radix-ui/react-icons'

export interface EmptyCanvasStateProps {
  country: string
  period: string
  onGenerate: () => void
}

/**
 * D-05 empty state — centered vertical stack with icon, headings, CTA.
 * Shown when status='created' and no artifacts exist.
 */
export function EmptyCanvasState({ country, period, onGenerate }: EmptyCanvasStateProps) {
  return (
    <Box
      data-testid="empty-canvas-state"
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Flex direction="column" align="center" gap="4">
        <MagicWandIcon width={48} height={48} style={{ color: 'var(--gray-9)' }} />
        <Heading size="3" weight="bold">
          Gerar mapa medieval para {country} {period}
        </Heading>
        <Text size="2" color="gray">
          Nenhum mapa gerado. Clique em 'Gerar Mapa' para iniciar.
        </Text>
        <Button color="blue" variant="solid" size="3" onClick={onGenerate}>
          Gerar Mapa
        </Button>
      </Flex>
    </Box>
  )
}
