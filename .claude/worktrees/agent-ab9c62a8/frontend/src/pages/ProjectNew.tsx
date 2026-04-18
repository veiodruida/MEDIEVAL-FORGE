import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Button, Callout, Flex, Heading, Text, TextField } from '@radix-ui/themes'
import { useCreateProject, usePresets, type Preset } from '../api/client'

// Lista de países individuais para o autocomplete (além dos presets de região)
const COUNTRIES_EXTRA = [
  { label: 'Portugal', country: 'Portugal', country_qid: 'Q45', bbox: { lon_min: -9.5, lat_min: 36.9, lon_max: -6.2, lat_max: 42.2 }, period_example: [868, 1640] as [number, number] },
  { label: 'Espanha', country: 'Espanha', country_qid: 'Q29', bbox: { lon_min: -9.3, lat_min: 35.9, lon_max: 4.3, lat_max: 43.8 }, period_example: [711, 1492] as [number, number] },
  { label: 'França', country: 'França', country_qid: 'Q142', bbox: { lon_min: -5.1, lat_min: 41.3, lon_max: 9.6, lat_max: 51.1 }, period_example: [843, 1453] as [number, number] },
  { label: 'Inglaterra', country: 'Q145', country_qid: 'Q145', bbox: { lon_min: -5.7, lat_min: 49.9, lon_max: 1.8, lat_max: 55.8 }, period_example: [1066, 1485] as [number, number] },
  { label: 'Itália', country: 'Itália', country_qid: 'Q38', bbox: { lon_min: 6.6, lat_min: 36.6, lon_max: 18.5, lat_max: 47.1 }, period_example: [476, 1454] as [number, number] },
  { label: 'Alemanha', country: 'Alemanha', country_qid: 'Q183', bbox: { lon_min: 5.9, lat_min: 47.3, lon_max: 15.0, lat_max: 55.1 }, period_example: [962, 1356] as [number, number] },
  { label: 'Polonia', country: 'Q36', country_qid: 'Q36', bbox: { lon_min: 14.1, lat_min: 49.0, lon_max: 24.1, lat_max: 54.8 }, period_example: [966, 1410] as [number, number] },
  { label: 'Hungria', country: 'Q28', country_qid: 'Q28', bbox: { lon_min: 16.1, lat_min: 45.7, lon_max: 22.9, lat_max: 48.6 }, period_example: [895, 1526] as [number, number] },
  { label: 'Marrocos', country: 'Q1028', country_qid: 'Q1028', bbox: { lon_min: -13.2, lat_min: 27.6, lon_max: -1.0, lat_max: 35.9 }, period_example: [788, 1492] as [number, number] },
  { label: 'Brasil', country: 'Brasil', country_qid: 'Q155', bbox: { lon_min: -74.0, lat_min: -33.8, lon_max: -34.8, lat_max: 5.3 }, period_example: [1500, 1822] as [number, number] },
]

interface BboxForm { lon_min: string; lat_min: string; lon_max: string; lat_max: string }

export function ProjectNew() {
  const navigate = useNavigate()
  const create = useCreateProject()
  const { data: serverPresets } = usePresets()

  // Combinar presets do servidor com países extra para o autocomplete
  const allOptions: Preset[] = [
    ...(serverPresets || []),
    ...COUNTRIES_EXTRA.filter(
      (c) => !(serverPresets || []).some((p) => p.country_qid === c.country_qid && p.label === c.label)
    ),
  ]

  const [search, setSearch] = useState('')
  const [selectedPreset, setSelectedPreset] = useState<Preset | null>(null)
  const [showDropdown, setShowDropdown] = useState(false)
  const [customCountry, setCustomCountry] = useState('')
  const [period_start, setPeriodStart] = useState(868)
  const [period_end, setPeriodEnd] = useState(1492)
  const [name, setName] = useState('')
  const [bbox, setBbox] = useState<BboxForm>({ lon_min: '', lat_min: '', lon_max: '', lat_max: '' })
  const searchRef = useRef<HTMLDivElement>(null)

  const filtered = search.length >= 2
    ? allOptions.filter((o) => o.label.toLowerCase().includes(search.toLowerCase()))
    : allOptions

  const applyPreset = (p: Preset) => {
    setSelectedPreset(p)
    setSearch(p.label)
    setShowDropdown(false)
    setPeriodStart(p.period_example[0])
    setPeriodEnd(p.period_example[1])
    setBbox({
      lon_min: String(p.bbox.lon_min),
      lat_min: String(p.bbox.lat_min),
      lon_max: String(p.bbox.lon_max),
      lat_max: String(p.bbox.lat_max),
    })
  }

  const clearPreset = () => {
    setSelectedPreset(null)
    setSearch('')
    setCustomCountry('')
  }

  // Fechar dropdown ao clicar fora
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const effectiveCountry = selectedPreset ? selectedPreset.country : customCountry

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!effectiveCountry) { alert('Selecione um país ou região.'); return }
    const toFloat = (v: string) => (v.trim() === '' ? null : Number(v))
    const created = await create.mutateAsync({
      name,
      country_qid: effectiveCountry,
      period_start: Number(period_start),
      period_end: Number(period_end),
      bbox_lon_min: toFloat(bbox.lon_min),
      bbox_lat_min: toFloat(bbox.lat_min),
      bbox_lon_max: toFloat(bbox.lon_max),
      bbox_lat_max: toFloat(bbox.lat_max),
    })
    navigate(`/projects/${created.id}`)
  }

  return (
    <Box p="6" style={{ maxWidth: 700 }}>
      <Heading mb="1">Novo Projeto de Mapa</Heading>
      <Text size="2" color="gray" as="p" mb="4">
        Crie um projeto para gerar mapas medievais históricos com dados geográficos reais.
      </Text>

      <form onSubmit={submit}>
        <Flex direction="column" gap="4">

          {/* Nome */}
          <Box>
            <Text as="label" size="2" weight="medium">Nome do projeto</Text>
            <TextField.Root value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Ex: Reconquista 868 AD" required />
          </Box>

          {/* Busca de país/região */}
          <Box>
            <Text as="label" size="2" weight="medium">País ou região</Text>
            <Text size="1" color="gray" as="p" mb="1">
              Escreva para filtrar (ex: "Portugal", "Iberia", "Balcãs") ou selecione da lista.
              Selecionar preenche a bounding box e o período automaticamente.
            </Text>
            <Box ref={searchRef} style={{ position: 'relative' }}>
              {selectedPreset ? (
                <Flex align="center" gap="2" style={{
                  border: '1px solid var(--green-7)', borderRadius: 6, padding: '6px 10px',
                  background: 'var(--green-1)',
                }}>
                  <Text size="2" style={{ flex: 1 }}>{selectedPreset.label}</Text>
                  <Button size="1" variant="ghost" color="red" type="button" onClick={clearPreset}>✕ Mudar</Button>
                </Flex>
              ) : (
                <>
                  <TextField.Root
                    value={search}
                    onChange={(e) => { setSearch(e.target.value); setShowDropdown(true) }}
                    onFocus={() => setShowDropdown(true)}
                    placeholder="Pesquisar país ou região…"
                  />
                  {showDropdown && filtered.length > 0 && (
                    <Box style={{
                      position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 99,
                      background: 'white', border: '1px solid var(--gray-6)', borderRadius: 6,
                      boxShadow: '0 4px 12px rgba(0,0,0,0.12)', maxHeight: 260, overflow: 'auto',
                    }}>
                      {filtered.map((p) => (
                        <Box key={p.label}
                          style={{ padding: '8px 12px', cursor: 'pointer' }}
                          onMouseDown={() => applyPreset(p)}
                          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--gray-2)')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                        >
                          <Text size="2">{p.label}</Text>
                          <Text size="1" color="gray" as="p">
                            {p.bbox.lon_min}…{p.bbox.lon_max} lon · {p.period_example[0]}–{p.period_example[1]} AD
                          </Text>
                        </Box>
                      ))}
                    </Box>
                  )}
                </>
              )}

              {/* Campo de país manual se não encontrou na lista */}
              {!selectedPreset && search.length > 2 && filtered.length === 0 && (
                <Box mt="2">
                  <Text size="1" color="gray">País não encontrado na lista. Pode escrever um código QID ou ISO:</Text>
                  <TextField.Root value={customCountry}
                    onChange={(e) => setCustomCountry(e.target.value)}
                    placeholder="Ex: Q45 ou PT" />
                </Box>
              )}
            </Box>
          </Box>

          {/* Período */}
          <Box>
            <Text as="label" size="2" weight="medium">Período histórico</Text>
            <Flex gap="3" mt="1">
              <Box style={{ flex: 1 }}>
                <Text as="label" size="1" color="gray">Ano de início</Text>
                <TextField.Root type="number" value={period_start}
                  onChange={(e) => setPeriodStart(Number(e.target.value))} required />
              </Box>
              <Box style={{ flex: 1 }}>
                <Text as="label" size="1" color="gray">Ano de fim</Text>
                <TextField.Root type="number" value={period_end}
                  onChange={(e) => setPeriodEnd(Number(e.target.value))} required />
              </Box>
            </Flex>
          </Box>

          {/* Bounding Box */}
          <Box>
            <Flex justify="between" align="baseline" mb="1">
              <Text as="label" size="2" weight="medium">Área do mapa — Bounding Box</Text>
              <a
                href={
                  bbox.lat_min && bbox.lon_min && bbox.lat_max && bbox.lon_max
                    ? `https://bboxfinder.com/#${bbox.lat_min},${bbox.lon_min},${bbox.lat_max},${bbox.lon_max}`
                    : 'https://bboxfinder.com'
                }
                target="_blank" rel="noreferrer"
                style={{ fontSize: 12, color: 'var(--accent-9)' }}>
                Consultar no bboxfinder.com ↗
              </a>
            </Flex>
            {selectedPreset ? (
              <Callout.Root size="1" color="green" mb="2">
                <Callout.Text>Preenchida automaticamente pelo preset "{selectedPreset.label}".</Callout.Text>
              </Callout.Root>
            ) : (
              <Callout.Root size="1" mb="2">
                <Callout.Text>
                  Selecione um país/região acima para preencher automaticamente,
                  ou use o link bboxfinder.com para desenhar a área no mapa.
                  Lon = horizontal (negativo = Oeste) · Lat = vertical (negativo = Sul).
                </Callout.Text>
              </Callout.Root>
            )}
            <Flex gap="2" wrap="wrap">
              {([
                { key: 'lon_min', label: 'Lon Mín (Oeste)', ex: '-9.5' },
                { key: 'lat_min', label: 'Lat Mín (Sul)',   ex: '36.9' },
                { key: 'lon_max', label: 'Lon Máx (Leste)', ex: '-6.2' },
                { key: 'lat_max', label: 'Lat Máx (Norte)', ex: '42.2' },
              ] as const).map(({ key, label, ex }) => (
                <Box key={key} style={{ flex: 1, minWidth: 140 }}>
                  <Text as="label" size="1" color="gray">{label}</Text>
                  <TextField.Root placeholder={ex} value={bbox[key]}
                    onChange={(e) => setBbox((b) => ({ ...b, [key]: e.target.value }))}
                    type="number" step="0.01" />
                </Box>
              ))}
            </Flex>
          </Box>

          {create.error && <Text color="red" size="2">{(create.error as Error).message}</Text>}

          <Flex gap="2" mt="2">
            <Button type="submit" disabled={create.isPending || !effectiveCountry}>
              {create.isPending ? 'Criando…' : 'Criar projeto'}
            </Button>
            <Button variant="soft" type="button" onClick={() => navigate('/projects')}>Cancelar</Button>
          </Flex>
        </Flex>
      </form>
    </Box>
  )
}
