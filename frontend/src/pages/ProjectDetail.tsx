import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Box, Button, Card, Flex, Heading, Text, TextArea, TextField } from '@radix-ui/themes'
import { useProject, useUpdateProject, useIngestStream, useGenerate, useExport } from '../api/client'

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: project, isLoading, error } = useProject(id)
  const update = useUpdateProject(id || '')
  const ingest = useIngestStream(id)
  const generate = useGenerate(id)
  const exportZip = useExport(id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ name: '', period_start: 0, period_end: 0 })
  const [territoryJson, setTerritoryJson] = useState<string>(
    JSON.stringify(
      {
        kingdoms: { K_TEST: 'Test Kingdom' },
        duchies: { D_TEST: ['K_TEST', 'Test Duchy'] },
        condados: [
          ['C_NORTH', 'North', -3.0, 41.0, 'D_TEST', [['North Barony', -3.0, 41.0]]],
          ['C_SOUTH', 'South', -3.0, 39.0, 'D_TEST', [['South Barony', -3.0, 39.0]]],
        ],
      },
      null,
      2,
    ),
  )

  if (isLoading) return <Box p="6"><Text>Loading…</Text></Box>
  if (error) return <Box p="6"><Text color="red">{(error as Error).message}</Text></Box>
  if (!project) return null

  const startEdit = () => {
    setDraft({
      name: project.name,
      period_start: project.period_start,
      period_end: project.period_end,
    })
    setEditing(true)
  }

  const save = async () => {
    await update.mutateAsync({
      name: draft.name,
      period_start: Number(draft.period_start),
      period_end: Number(draft.period_end),
    })
    setEditing(false)
  }

  const handleGenerate = () => {
    try {
      const data = JSON.parse(territoryJson)
      generate.mutate(data)
    } catch (e) {
      alert(`territory_data JSON parse error: ${(e as Error).message}`)
    }
  }

  return (
    <Box p="6">
      <Flex justify="between" align="center" mb="4">
        <Heading>{project.name}</Heading>
        <Link to="/projects"><Button variant="soft">← All projects</Button></Link>
      </Flex>

      <Card mb="4">
        <Flex direction="column" gap="2">
          <Text><strong>ID:</strong> {project.id}</Text>
          <Text><strong>Country QID:</strong> {project.country_qid}</Text>
          <Text><strong>Period:</strong> {project.period_start}–{project.period_end}</Text>
          <Text><strong>Status:</strong> {project.status}</Text>
          <Text size="2" color="gray">Created {project.created_at}</Text>
          <Flex gap="2" mt="2">
            {!editing && <Button variant="soft" onClick={startEdit}>Edit</Button>}
          </Flex>
        </Flex>
      </Card>

      {editing && (
        <Card mb="4">
          <Heading size="3" mb="2">Edit project</Heading>
          <Flex direction="column" gap="2">
            <TextField.Root
              value={draft.name}
              onChange={(e) => setDraft((s) => ({ ...s, name: e.target.value }))}
            />
            <Flex gap="2">
              <TextField.Root
                type="number"
                value={draft.period_start}
                onChange={(e) => setDraft((s) => ({ ...s, period_start: Number(e.target.value) }))}
              />
              <TextField.Root
                type="number"
                value={draft.period_end}
                onChange={(e) => setDraft((s) => ({ ...s, period_end: Number(e.target.value) }))}
              />
            </Flex>
            <Flex gap="2">
              <Button onClick={save} disabled={update.isPending}>
                {update.isPending ? 'Saving…' : 'Save'}
              </Button>
              <Button variant="soft" onClick={() => setEditing(false)}>Cancel</Button>
            </Flex>
          </Flex>
        </Card>
      )}

      {/* Pipeline action surface (D-09 SSE log lives here). */}
      <Card>
        <Heading size="3" mb="2">Pipeline actions</Heading>
        <Flex gap="2" mb="3" wrap="wrap">
          <Button
            onClick={() => ingest.start('wikidata')}
            disabled={ingest.isStreaming}
          >
            {ingest.isStreaming ? 'Ingesting…' : 'Ingest from Wikidata'}
          </Button>
          <Button
            variant="soft"
            onClick={() => ingest.start('osm')}
            disabled={ingest.isStreaming}
          >
            Ingest from OSM
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={project.status === 'generating' || generate.isPending}
          >
            {project.status === 'generating' ? 'Generating…' : 'Generate'}
          </Button>
          <Button
            variant="soft"
            color="green"
            onClick={() => exportZip.mutate()}
            disabled={
              exportZip.isPending ||
              (project.status !== 'generated' && project.status !== 'exported')
            }
            title={
              project.status === 'generated' || project.status === 'exported'
                ? 'Build and download Unity ZIP'
                : 'Generate maps first (status must be generated or exported)'
            }
          >
            {exportZip.isPending ? 'Building ZIP…' : 'Export ZIP'}
          </Button>
        </Flex>
        {exportZip.error && (
          <Text color="red" size="2">Export error: {(exportZip.error as Error).message}</Text>
        )}
        {ingest.error && (
          <Text color="red" size="2">Ingest error: {ingest.error.message}</Text>
        )}

        {/* Territory data JSON input for generation */}
        <Box mb="3">
          <Text size="2" weight="medium">Territory data (JSON)</Text>
          <TextArea
            value={territoryJson}
            onChange={(e) => setTerritoryJson(e.target.value)}
            rows={10}
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          />
          {generate.error && (
            <Text color="red" size="2">
              Generate error: {(generate.error as Error).message}
            </Text>
          )}
          {project.status === 'error_generating' &&
            Boolean(project.generator_config?.last_error) && (
              <Text color="red" size="2">
                Last generation error: {String(project.generator_config?.last_error ?? '')}
              </Text>
            )}
        </Box>

        <Box>
          <Text size="2" color="gray">Ingestion log:</Text>
          <pre
            id="ingest-log"
            style={{
              marginTop: 4,
              padding: 8,
              background: '#f5f5f5',
              borderRadius: 4,
              maxHeight: 240,
              overflow: 'auto',
              fontSize: 12,
              whiteSpace: 'pre-wrap',
            }}
          >
            {ingest.lines.join('')}
          </pre>
        </Box>
      </Card>

      {/* Preview images — rendered when generation has completed or exported. */}
      {(project.status === 'generated' || project.status === 'exported') && (
        <Card mt="4">
          <Heading size="3" mb="2">Previews</Heading>
          <Flex gap="3" wrap="wrap">
            {(['territories.png', 'borders.png', 'terrain.png'] as const).map((fname) => (
              <Box key={fname}>
                <Text size="2" weight="medium">{fname}</Text>
                <img
                  src={`/api/projects/${project.id}/preview/${fname}`}
                  alt={fname}
                  style={{
                    display: 'block',
                    maxWidth: 360,
                    border: '1px solid #ddd',
                    borderRadius: 4,
                    marginTop: 4,
                  }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.opacity = '0.3'
                  }}
                />
              </Box>
            ))}
          </Flex>
        </Card>
      )}
    </Box>
  )
}
