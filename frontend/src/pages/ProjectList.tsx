import { Link } from 'react-router-dom'
import { Box, Button, Card, Flex, Heading, Text } from '@radix-ui/themes'
import { useDeleteProject, useProjects } from '../api/client'

export function ProjectList() {
  const { data, isLoading, error } = useProjects()
  const del = useDeleteProject()

  return (
    <Box p="6">
      <Flex justify="between" align="center" mb="4">
        <Heading>Projects</Heading>
        <Link to="/projects/new">
          <Button>New project</Button>
        </Link>
      </Flex>
      {isLoading && <Text>Loading…</Text>}
      {error && <Text color="red">{(error as Error).message}</Text>}
      {data && data.length === 0 && <Text color="gray">No projects yet.</Text>}
      <Flex direction="column" gap="3">
        {data?.map((p) => (
          <Card key={p.id}>
            <Flex justify="between" align="center">
              <Box>
                <Heading size="3">{p.name}</Heading>
                <Text size="2" color="gray">
                  {p.country_qid} · {p.period_start}–{p.period_end} · {p.status}
                </Text>
              </Box>
              <Flex gap="2">
                <Link to={`/projects/${p.id}`}>
                  <Button variant="soft">Open</Button>
                </Link>
                <Button
                  color="red"
                  variant="soft"
                  onClick={() => {
                    if (window.confirm(`Delete project "${p.name}"?`)) {
                      del.mutate(p.id)
                    }
                  }}
                >
                  Delete
                </Button>
              </Flex>
            </Flex>
          </Card>
        ))}
      </Flex>
    </Box>
  )
}
