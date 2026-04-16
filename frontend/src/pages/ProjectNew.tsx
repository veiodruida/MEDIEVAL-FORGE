import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Button, Flex, Heading, Text, TextField } from '@radix-ui/themes'
import { useCreateProject } from '../api/client'

export function ProjectNew() {
  const navigate = useNavigate()
  const create = useCreateProject()
  const [form, setForm] = useState({
    name: '',
    country_qid: 'Q29',
    period_start: 868,
    period_end: 1492,
    bbox_lon_min: '',
    bbox_lon_max: '',
    bbox_lat_min: '',
    bbox_lat_max: '',
  })

  const update = (k: keyof typeof form, v: string) =>
    setForm((s) => ({ ...s, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const toFloat = (v: string) => (v === '' ? null : Number(v))
    const created = await create.mutateAsync({
      name: form.name,
      country_qid: form.country_qid,
      period_start: Number(form.period_start),
      period_end: Number(form.period_end),
      bbox_lon_min: toFloat(form.bbox_lon_min),
      bbox_lon_max: toFloat(form.bbox_lon_max),
      bbox_lat_min: toFloat(form.bbox_lat_min),
      bbox_lat_max: toFloat(form.bbox_lat_max),
    })
    navigate(`/projects/${created.id}`)
  }

  return (
    <Box p="6" style={{ maxWidth: 640 }}>
      <Heading mb="4">New project</Heading>
      <form onSubmit={submit}>
        <Flex direction="column" gap="3">
          <Box>
            <Text as="label" size="2" weight="medium">Name</Text>
            <TextField.Root
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              required
            />
          </Box>
          <Box>
            <Text as="label" size="2" weight="medium">
              Country (Wikidata QID, e.g. Q29 = Spain, Q142 = France)
            </Text>
            <TextField.Root
              value={form.country_qid}
              onChange={(e) => update('country_qid', e.target.value)}
              required
            />
          </Box>
          <Flex gap="3">
            <Box style={{ flex: 1 }}>
              <Text as="label" size="2" weight="medium">Period start (year)</Text>
              <TextField.Root
                type="number"
                value={form.period_start}
                onChange={(e) => update('period_start', e.target.value)}
                required
              />
            </Box>
            <Box style={{ flex: 1 }}>
              <Text as="label" size="2" weight="medium">Period end (year)</Text>
              <TextField.Root
                type="number"
                value={form.period_end}
                onChange={(e) => update('period_end', e.target.value)}
                required
              />
            </Box>
          </Flex>
          <Heading size="2" mt="2">Bounding box (optional)</Heading>
          <Flex gap="3">
            <TextField.Root placeholder="lon_min" value={form.bbox_lon_min} onChange={(e) => update('bbox_lon_min', e.target.value)} />
            <TextField.Root placeholder="lon_max" value={form.bbox_lon_max} onChange={(e) => update('bbox_lon_max', e.target.value)} />
            <TextField.Root placeholder="lat_min" value={form.bbox_lat_min} onChange={(e) => update('bbox_lat_min', e.target.value)} />
            <TextField.Root placeholder="lat_max" value={form.bbox_lat_max} onChange={(e) => update('bbox_lat_max', e.target.value)} />
          </Flex>
          {create.error && (
            <Text color="red">{(create.error as Error).message}</Text>
          )}
          <Flex gap="2" mt="2">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creating…' : 'Create project'}
            </Button>
          </Flex>
        </Flex>
      </form>
    </Box>
  )
}
