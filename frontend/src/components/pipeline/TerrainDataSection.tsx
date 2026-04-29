import { useState } from 'react'
import * as Collapsible from '@radix-ui/react-collapsible'
import { Badge, Box, Button, Card, Flex, Heading, ScrollArea, SegmentedControl, Text } from '@radix-ui/themes'
import { StepCard } from './StepCard'
import { useTerrainStepStream, type TerrainStep, type TerrainStepStatus } from '../../api/useTerrainStepStream'

const BADGE_COLOR: Record<TerrainStepStatus, 'gray' | 'blue' | 'green' | 'red'> = {
  pendente: 'gray',
  rodando: 'blue',
  pronto: 'green',
  erro: 'red',
}

function StatusBadge({ status }: { status: TerrainStepStatus }) {
  return <Badge color={BADGE_COLOR[status]}>{status}</Badge>
}

interface StepRowProps {
  title: string
  description: string
  step: TerrainStep
  handle: ReturnType<typeof useTerrainStepStream>
  extraControls?: React.ReactNode
  onStart: () => void
}

function StepRow({ title, description, handle, extraControls, onStart }: StepRowProps) {
  const running = handle.status === 'rodando'
  return (
    <StepCard
      title={title}
      description={description}
      footer={
        <Flex gap="2" align="center">
          <StatusBadge status={handle.status} />
          {extraControls}
          {running ? (
            <Button color="red" variant="soft" onClick={() => handle.stop()}>
              Parar ingestão
            </Button>
          ) : (
            <Button onClick={onStart}>Executar</Button>
          )}
        </Flex>
      }
    >
      <Text size="2" color="gray">
        {handle.error ? `Erro: ${handle.error.message}` : null}
      </Text>
    </StepCard>
  )
}

export function TerrainDataSection({ projectId }: { projectId: string }) {
  const overpass = useTerrainStepStream(projectId, 'overpass')
  const hydrosheds = useTerrainStepStream(projectId, 'hydrosheds')
  const dem = useTerrainStepStream(projectId, 'dem')
  const ridges = useTerrainStepStream(projectId, 'ridges')
  const [sensitivity, setSensitivity] = useState<'low' | 'med' | 'high'>('med')

  const all = [overpass, hydrosheds, dem, ridges]
  const completed = all.filter((s) => s.status === 'pronto').length

  // D-27: shared log = currently-active (rodando) step's lines, OR last-finished if none rodando.
  const active = all.find((s) => s.status === 'rodando')
  const sharedLog = active ? active.lines : (all.find((s) => s.lines.length > 0)?.lines ?? [])

  return (
    // Pitfall 8: outermost wrapper is <Card> from @radix-ui/themes to avoid Tailwind v4 transparency bug
    <Card mb="4">
      <Collapsible.Root defaultOpen={false}>
        <Collapsible.Trigger asChild>
          <Flex
            justify="between"
            align="center"
            style={{ cursor: 'pointer' }}
            role="button"
            aria-label="Expandir Terrain Data"
          >
            <Heading size="3">Terrain Data</Heading>
            <Badge color="gray">{completed}/4 datasets prontos</Badge>
          </Flex>
        </Collapsible.Trigger>
        <Collapsible.Content>
          <Box mt="3">
            <StepRow
              title="Overpass terrain"
              description="Rios, picos, costa e freguesias via OSM Overpass."
              step="overpass"
              handle={overpass}
              onStart={() => overpass.start()}
            />
            <StepRow
              title="HydroSHEDS basins"
              description="Bacias hidrográficas lv6 (vendored, CC-BY)."
              step="hydrosheds"
              handle={hydrosheds}
              onStart={() => hydrosheds.start()}
            />
            <StepRow
              title="DEM (Copernicus)"
              description="Mosaic Copernicus DSM 90m do bbox do projeto."
              step="dem"
              handle={dem}
              onStart={() => dem.start()}
            />
            <StepRow
              title="Ridges (derive)"
              description="Cumeadas derivadas do DEM via slope+curvatura."
              step="ridges"
              handle={ridges}
              extraControls={
                <SegmentedControl.Root
                  data-testid="ridge-sensitivity-slider"
                  value={sensitivity}
                  onValueChange={(v) => setSensitivity(v as 'low' | 'med' | 'high')}
                >
                  <SegmentedControl.Item value="low">low</SegmentedControl.Item>
                  <SegmentedControl.Item value="med">med</SegmentedControl.Item>
                  <SegmentedControl.Item value="high">high</SegmentedControl.Item>
                </SegmentedControl.Root>
              }
              onStart={() => ridges.start({ sensitivity })}
            />
            <Box mt="3">
              <Heading size="2" mb="2">
                Log
              </Heading>
              <Card data-testid="terrain-shared-log">
                <ScrollArea style={{ height: 200 }}>
                  <Box p="2" style={{ fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap' }}>
                    {sharedLog.length === 0 ? (
                      <Text color="gray">Nenhuma execução iniciada.</Text>
                    ) : (
                      sharedLog.map((l, i) => <div key={i}>{l}</div>)
                    )}
                  </Box>
                </ScrollArea>
              </Card>
            </Box>
          </Box>
        </Collapsible.Content>
      </Collapsible.Root>
    </Card>
  )
}
