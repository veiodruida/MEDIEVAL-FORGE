import { Link } from 'react-router-dom'
import { Box, Button, Card, Flex, Heading, Text } from '@radix-ui/themes'
import { useDeleteProject, useProjects } from '../api/client'

const STATUS_LABEL: Record<string, string> = {
  created: 'Criado',
  ingested: 'Dados ingeridos',
  generating: 'Gerando mapa…',
  generated: 'Mapa gerado',
  exported: 'Exportado',
  error_ingesting: 'Erro na ingestão',
  error_generating: 'Erro na geração',
}

export function ProjectList() {
  const { data, isLoading, error } = useProjects()
  const del = useDeleteProject()

  return (
    <Box p="6">
      <Flex justify="between" align="center" mb="4">
        <Heading>Projetos de Mapa</Heading>
        <Link to="/projects/new">
          <Button>+ Novo projeto</Button>
        </Link>
      </Flex>
      {isLoading && <Text>Carregando…</Text>}
      {error && <Text color="red">{(error as Error).message}</Text>}
      {data && data.length === 0 && (
        <Text color="gray">Nenhum projeto criado ainda. Clique em "Novo projeto" para começar.</Text>
      )}
      <Flex direction="column" gap="3">
        {data?.map((p) => (
          <Card key={p.id}>
            <Flex justify="between" align="center">
              <Box>
                <Heading size="3">{p.name}</Heading>
                <Text size="2" color="gray">
                  {p.country_qid} · {p.period_start}–{p.period_end} · {STATUS_LABEL[p.status] ?? p.status}
                </Text>
              </Box>
              <Flex gap="2">
                <Link to={`/projects/${p.id}`}>
                  <Button variant="soft">Abrir</Button>
                </Link>
                <Button
                  color="red"
                  variant="soft"
                  onClick={() => {
                    if (window.confirm(`Excluir o projeto "${p.name}"? Esta ação não pode ser desfeita.`)) {
                      del.mutate(p.id)
                    }
                  }}
                >
                  Excluir
                </Button>
              </Flex>
            </Flex>
          </Card>
        ))}
      </Flex>
    </Box>
  )
}
