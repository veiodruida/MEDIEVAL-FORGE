import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Box, Button, Card, Flex, Heading, Text, TextField } from '@radix-ui/themes'
import { useProject, useUpdateProject, useIngestStream } from '../api/client'

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: project, isLoading, error } = useProject(id)
  const update = useUpdateProject(id || '')
  const ingest = useIngestStream(id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ name: '', period_start: 0, period_end: 0 })

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
          <Button disabled title="Will be wired by Plan 1.4 (map generation)">Generate (Plan 1.4)</Button>
          <Button disabled title="Will be wired by Plan 1.5 (Unity export)">Export ZIP (Plan 1.5)</Button>
        </Flex>
        {ingest.error && (
          <Text color="red" size="2">Ingest error: {ingest.error.message}</Text>
        )}
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
    </Box>
  )
}
