import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dialog,
  Select,
  TextField,
  Button,
  Flex,
  Box,
  Text,
} from '@radix-ui/themes'
import * as Toast from '@radix-ui/react-toast'
import { useRegions } from '../../api/useRegions'
import { useCreateV3Project } from '../../api/client'
import type { RegionInfo } from '../../types/region'

function formatBounds(r: RegionInfo): string {
  const { lon_min, lon_max, lat_min, lat_max } = r.bounds
  return `lon ${lon_min.toFixed(1)}…${lon_max.toFixed(1)} · lat ${lat_min.toFixed(1)}…${lat_max.toFixed(1)}`
}

function defaultRegionKey(regions: RegionInfo[] | undefined): string {
  if (!regions || regions.length === 0) return ''
  const iberia = regions.find((r) => r.key === 'iberia_868')
  if (iberia) return iberia.key
  const first = regions.find((r) => r.has_dataset)
  return first ? first.key : (regions[0]?.key ?? '')
}

export function NewProjectModal() {
  const navigate = useNavigate()
  const { data: regions, isLoading, isError, refetch } = useRegions()
  const create = useCreateV3Project()

  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [regionKey, setRegionKey] = useState('')
  const [nameError, setNameError] = useState('')
  const [toastOpen, setToastOpen] = useState(false)

  // Set default region key when regions load
  useEffect(() => {
    if (regions && regionKey === '') {
      setRegionKey(defaultRegionKey(regions))
    }
  }, [regions, regionKey])

  // Show error toast when region fetch fails
  useEffect(() => {
    if (isError) setToastOpen(true)
  }, [isError])

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      // Reset form state on close
      setName('')
      setRegionKey(defaultRegionKey(regions))
      setNameError('')
      create.reset()
    }
  }

  const trimmedName = name.trim()
  const selectedRegion = regions?.find((r) => r.key === regionKey)
  const nameValid = trimmedName.length >= 1 && trimmedName.length <= 64
  const regionValid = Boolean(selectedRegion?.has_dataset)
  const canSubmit = nameValid && regionValid

  function handleNameChange(e: React.ChangeEvent<HTMLInputElement>) {
    setName(e.target.value)
    setNameError('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!nameValid) {
      if (trimmedName.length === 0) setNameError('Informe um nome para o projeto.')
      else setNameError('O nome deve ter no máximo 64 caracteres.')
      return
    }
    if (!regionKey) return
    try {
      const result = await create.mutateAsync({ name: trimmedName, region_key: regionKey })
      setOpen(false)
      navigate(`/projects/${result.id}`)
    } catch {
      // error displayed inline via create.error
    }
  }

  const loadingText = 'Carregando regiões...'
  const submitLabel = create.isPending ? 'Criando...' : 'Criar projeto'

  return (
    <>
      <Dialog.Root open={open} onOpenChange={handleOpenChange}>
        {/* Trigger: data-testid on the Button itself; Dialog.Trigger renders it as-is */}
        <Dialog.Trigger>
          <Button data-testid="new-project-button">+ Novo projeto</Button>
        </Dialog.Trigger>

        <Dialog.Content
          data-testid="new-project-modal"
          style={{ maxWidth: 480 }}
        >
          <Dialog.Title>Novo projeto</Dialog.Title>

          <Dialog.Description>
            <Text size="2" color="gray">
              Escolha uma região para gerar o mapa. Iberia 868 é o padrão.
            </Text>
          </Dialog.Description>

          <form onSubmit={handleSubmit}>
            <Flex direction="column" gap="3" mt="4">

              {/* Nome do projeto */}
              <Box>
                <Text as="label" size="2" weight="medium" htmlFor="project-name-input">
                  Nome do projeto
                </Text>
                <Box mt="1">
                  <TextField.Root
                    id="project-name-input"
                    value={name}
                    onChange={handleNameChange}
                    placeholder="Ex.: Reconquista 868"
                    autoFocus
                  />
                </Box>
                {nameError && (
                  <Text size="1" color="red" mt="1" as="p">
                    {nameError}
                  </Text>
                )}
              </Box>

              {/* Região */}
              <Box>
                <Text as="label" size="2" weight="medium" htmlFor="region-select-trigger">
                  Região
                </Text>
                <Box mt="1">
                  <Select.Root
                    value={regionKey}
                    onValueChange={setRegionKey}
                    disabled={isLoading || isError}
                  >
                    <Select.Trigger
                      id="region-select-trigger"
                      data-testid="region-select"
                      placeholder={isLoading ? loadingText : 'Selecione uma região'}
                    />
                    <Select.Content>
                      {regions?.map((r) => (
                        <Select.Item
                          key={r.key}
                          value={r.key}
                          disabled={!r.has_dataset}
                        >
                          <Flex direction="column" gap="1">
                            <Text size="2">
                              {r.display_name}
                              {!r.has_dataset && (
                                <Text size="1" color="gray"> (sem dataset)</Text>
                              )}
                            </Text>
                            <Text size="1" color="gray">
                              {formatBounds(r)}
                            </Text>
                          </Flex>
                        </Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Root>
                </Box>
                {selectedRegion && !selectedRegion.has_dataset && (
                  <Text size="1" color="gray" mt="1" as="p">
                    Esta região ainda não tem inputs geográficos. Disponível em uma futura versão.
                  </Text>
                )}
              </Box>

              {/* Submission error */}
              {create.error && (
                <Text size="2" color="red">
                  Não foi possível criar o projeto: {(create.error as Error).message}
                </Text>
              )}

              {/* CTA row */}
              <Flex gap="2" justify="end" mt="2">
                <Button
                  type="button"
                  variant="soft"
                  onClick={() => handleOpenChange(false)}
                >
                  Cancelar
                </Button>
                <Button type="submit" disabled={!canSubmit || create.isPending}>
                  {submitLabel}
                </Button>
              </Flex>
            </Flex>
          </form>
        </Dialog.Content>
      </Dialog.Root>

      {/* Error toast for region fetch failure */}
      {/* 24h duration: long enough to span any plausible session; finite so Radix does not warn. */}
      <Toast.Root open={toastOpen} onOpenChange={setToastOpen} duration={1000 * 60 * 60 * 24}>
        <Toast.Title asChild>
          <Text size="2">
            Não foi possível carregar a lista de regiões. Tente novamente.
          </Text>
        </Toast.Title>
        <Toast.Action altText="Tentar novamente" asChild>
          <Button
            size="1"
            variant="soft"
            onClick={() => {
              refetch()
              setToastOpen(false)
            }}
          >
            Tentar novamente
          </Button>
        </Toast.Action>
      </Toast.Root>
    </>
  )
}
