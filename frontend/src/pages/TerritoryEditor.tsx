/**
 * Editor hierárquico da estrutura política do jogo.
 * Visualização em árvore: Reino → Ducado → Território → Baronia
 */
import { useState } from 'react'
import { Box, Button, Card, Flex, Text, TextField } from '@radix-ui/themes'

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface Barony { name: string; lon: string; lat: string }
interface Condado { id: string; name: string; lon: string; lat: string; duchy_id: string; baronies: Barony[] }
interface Duchy   { id: string; name: string; kingdom_id: string }
interface Kingdom { id: string; name: string }

export interface TerritoryData {
  kingdoms: Record<string, string>
  duchies:  Record<string, [string, string]>
  condados: Array<[string, string, number, number, string, Array<[string, number, number]>]>
}

interface Props { value: TerritoryData; onChange: (v: TerritoryData) => void }

// ─── Helpers ──────────────────────────────────────────────────────────────────

function slug(s: string) {
  return s.toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 20)
}

function fromData(d: TerritoryData) {
  return {
    kingdoms: Object.entries(d.kingdoms).map(([id, name]) => ({ id, name })),
    duchies:  Object.entries(d.duchies).map(([id, [kingdom_id, name]]) => ({ id, name, kingdom_id })),
    condados: d.condados.map(([id, name, lon, lat, duchy_id, bars]) => ({
      id, name, lon: String(lon), lat: String(lat), duchy_id,
      baronies: bars.map(([bn, bl, ba]) => ({ name: bn, lon: String(bl), lat: String(ba) })),
    })),
  }
}

function toData(kingdoms: Kingdom[], duchies: Duchy[], condados: Condado[]): TerritoryData {
  return {
    kingdoms: Object.fromEntries(kingdoms.map(k => [k.id, k.name])),
    duchies:  Object.fromEntries(duchies.map(d => [d.id, [d.kingdom_id, d.name] as [string, string]])),
    condados: condados.map(c => [
      c.id, c.name, parseFloat(c.lon)||0, parseFloat(c.lat)||0, c.duchy_id,
      c.baronies.map(b => [b.name, parseFloat(b.lon)||0, parseFloat(b.lat)||0] as [string,number,number]),
    ]),
  }
}

// ─── Sub-componentes ──────────────────────────────────────────────────────────

function InlineField({ label, value, onChange, type = 'text', width = 120 }: {
  label: string; value: string; onChange: (v: string) => void
  type?: 'text' | 'number'; width?: number
}) {
  return (
    <Box style={{ width }}>
      <Text size="1" color="gray">{label}</Text>
      <TextField.Root size="1" value={value} type={type} step={type === 'number' ? '0.01' : undefined}
        onChange={e => onChange(e.target.value)} />
    </Box>
  )
}

// ─── Componente principal ─────────────────────────────────────────────────────

export function TerritoryEditor({ value, onChange }: Props) {
  const init = fromData(value)
  const [kingdoms, setKingdoms] = useState<Kingdom[]>(init.kingdoms)
  const [duchies,  setDuchies]  = useState<Duchy[]>(init.duchies)
  const [condados, setCondados] = useState<Condado[]>(init.condados)

  // Estado de expansão da árvore
  const [openKingdoms, setOpenKingdoms] = useState<Set<string>>(new Set(init.kingdoms.map(k => k.id)))
  const [openDuchies,  setOpenDuchies]  = useState<Set<string>>(new Set(init.duchies.map(d => d.id)))
  const [openCondados, setOpenCondados] = useState<Set<string>>(new Set())
  const [showJson, setShowJson] = useState(false)

  const emit = (k: Kingdom[], d: Duchy[], c: Condado[]) => onChange(toData(k, d, c))

  const toggleSet = (set: Set<string>, id: string): Set<string> => {
    const next = new Set(set)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  }

  // ── Reinos ──────────────────────────────────────────────────────────────────
  const addKingdom = () => {
    const k: Kingdom = { id: `K_REINO${kingdoms.length+1}`, name: `Reino ${kingdoms.length+1}` }
    const next = [...kingdoms, k]
    setKingdoms(next); setOpenKingdoms(new Set([...openKingdoms, k.id])); emit(next, duchies, condados)
  }
  const updK = (i: number, f: keyof Kingdom, v: string) => {
    const next = kingdoms.map((k,j) => j===i ? {...k, [f]: f==='id' ? slug(v) : v} : k)
    setKingdoms(next); emit(next, duchies, condados)
  }
  const delK = (i: number) => {
    const next = kingdoms.filter((_,j) => j!==i)
    setKingdoms(next); emit(next, duchies, condados)
  }

  // ── Ducados ─────────────────────────────────────────────────────────────────
  const addDuchy = (kingdom_id: string) => {
    const d: Duchy = { id: `D_DUC${duchies.length+1}`, name: `Ducado ${duchies.length+1}`, kingdom_id }
    const next = [...duchies, d]
    setDuchies(next); setOpenDuchies(new Set([...openDuchies, d.id])); emit(kingdoms, next, condados)
  }
  const updD = (i: number, f: keyof Duchy, v: string) => {
    const next = duchies.map((d,j) => j===i ? {...d, [f]: f==='id' ? slug(v) : v} : d)
    setDuchies(next); emit(kingdoms, next, condados)
  }
  const delD = (i: number) => {
    const next = duchies.filter((_,j) => j!==i)
    setDuchies(next); emit(kingdoms, next, condados)
  }

  // ── Territórios ─────────────────────────────────────────────────────────────
  const addCondado = (duchy_id: string) => {
    const c: Condado = {
      id: `T_TER${condados.length+1}`, name: `Território ${condados.length+1}`,
      lon: '-8.0', lat: '40.0', duchy_id,
      baronies: [{ name: 'Baronia', lon: '-8.0', lat: '40.0' }],
    }
    const next = [...condados, c]
    setCondados(next); emit(kingdoms, duchies, next)
  }
  const updC = (i: number, f: keyof Condado, v: string) => {
    const next = condados.map((c,j) => j===i ? {...c, [f]: f==='id' ? slug(v) : v} : c)
    setCondados(next); emit(kingdoms, duchies, next)
  }
  const delC = (i: number) => {
    const next = condados.filter((_,j) => j!==i)
    setCondados(next); emit(kingdoms, duchies, next)
  }

  // ── Baronias ────────────────────────────────────────────────────────────────
  const addBarony = (ci: number) => {
    const c = condados[ci]
    const next = condados.map((x,j) => j===ci
      ? {...x, baronies: [...x.baronies, { name: 'Nova Baronia', lon: c.lon, lat: c.lat }]}
      : x)
    setCondados(next); emit(kingdoms, duchies, next)
  }
  const updB = (ci: number, bi: number, f: keyof Barony, v: string) => {
    const next = condados.map((c,j) => j===ci
      ? {...c, baronies: c.baronies.map((b,k) => k===bi ? {...b, [f]: v} : b)}
      : c)
    setCondados(next); emit(kingdoms, duchies, next)
  }
  const delB = (ci: number, bi: number) => {
    const next = condados.map((c,j) => j===ci
      ? {...c, baronies: c.baronies.filter((_,k) => k!==bi)}
      : c)
    setCondados(next); emit(kingdoms, duchies, next)
  }

  const INDENT_1 = 16

  return (
    <Box>
      {/* Legenda */}
      <Flex gap="3" mb="3" wrap="wrap">
        {[
          { icon: '👑', label: 'Reino — topo da hierarquia', color: 'var(--amber-9)' },
          { icon: '🏰', label: 'Ducado — agrupa territórios', color: 'var(--blue-9)' },
          { icon: '🗺️', label: 'Território — região jogável', color: 'var(--green-9)' },
          { icon: '⚔️', label: 'Baronia — sub-região', color: 'var(--gray-9)' },
        ].map(({ icon, label, color }) => (
          <Flex key={label} align="center" gap="1">
            <Text style={{ fontSize: 14 }}>{icon}</Text>
            <Text size="1" style={{ color }}>{label}</Text>
          </Flex>
        ))}
      </Flex>

      {/* Árvore */}
      <Flex direction="column" gap="2">
        {kingdoms.map((k, ki) => {
          const kDuchies = duchies.filter(d => d.kingdom_id === k.id)
          const isKOpen = openKingdoms.has(k.id)
          const kCondados = kDuchies.flatMap(d => condados.filter(c => c.duchy_id === d.id))

          return (
            <Card key={k.id} style={{ borderLeft: '3px solid var(--amber-7)' }}>
              {/* Reino */}
              <Flex align="center" gap="2" mb={isKOpen ? '2' : '0'}>
                <Button size="1" variant="ghost" onClick={() => setOpenKingdoms(toggleSet(openKingdoms, k.id))}>
                  {isKOpen ? '▼' : '▶'}
                </Button>
                <Text style={{ fontSize: 16 }}>👑</Text>
                <Box style={{ flex: 1 }}>
                  <InlineField label="Nome do Reino" value={k.name} onChange={v => updK(ki, 'name', v)} width={200} />
                </Box>
                <Box>
                  <InlineField label="ID" value={k.id} onChange={v => updK(ki, 'id', v)} width={120} />
                </Box>
                <Button size="1" color="amber" variant="soft"
                  style={{ marginTop: 16 }} onClick={() => addDuchy(k.id)}>
                  + Ducado
                </Button>
                <Button size="1" color="red" variant="ghost"
                  style={{ marginTop: 16 }} onClick={() => delK(ki)}>✕</Button>
              </Flex>

              {isKOpen && (
                <Flex direction="column" gap="2">
                  {kDuchies.length === 0 && (
                    <Text size="1" color="gray" style={{ paddingLeft: INDENT_1 }}>
                      Sem ducados. Clique "+ Ducado" para adicionar.
                    </Text>
                  )}

                  {kDuchies.map((d, _) => {
                    const di = duchies.indexOf(d)
                    const dCondados = condados.filter(c => c.duchy_id === d.id)
                    const isDOpen = openDuchies.has(d.id)

                    return (
                      <Box key={d.id} style={{ paddingLeft: INDENT_1 }}>
                        <Card style={{ borderLeft: '3px solid var(--blue-6)', background: 'var(--blue-1)' }}>
                          {/* Ducado */}
                          <Flex align="center" gap="2" mb={isDOpen ? '2' : '0'}>
                            <Button size="1" variant="ghost" onClick={() => setOpenDuchies(toggleSet(openDuchies, d.id))}>
                              {isDOpen ? '▼' : '▶'}
                            </Button>
                            <Text style={{ fontSize: 14 }}>🏰</Text>
                            <Box style={{ flex: 1 }}>
                              <InlineField label="Nome do Ducado" value={d.name}
                                onChange={v => updD(di, 'name', v)} width={180} />
                            </Box>
                            <Box>
                              <InlineField label="ID" value={d.id}
                                onChange={v => updD(di, 'id', v)} width={110} />
                            </Box>
                            <Button size="1" color="green" variant="soft"
                              style={{ marginTop: 16 }} onClick={() => addCondado(d.id)}>
                              + Território
                            </Button>
                            <Button size="1" color="red" variant="ghost"
                              style={{ marginTop: 16 }} onClick={() => delD(di)}>✕</Button>
                          </Flex>

                          {isDOpen && (
                            <Flex direction="column" gap="2">
                              {dCondados.length === 0 && (
                                <Text size="1" color="gray" style={{ paddingLeft: INDENT_1 }}>
                                  Sem territórios. Clique "+ Território".
                                </Text>
                              )}

                              {dCondados.map((c) => {
                                const ci = condados.indexOf(c)
                                const isCOpen = openCondados.has(c.id)

                                return (
                                  <Box key={c.id} style={{ paddingLeft: INDENT_1 }}>
                                    <Card style={{ borderLeft: '3px solid var(--green-6)', background: 'var(--green-1)' }}>
                                      {/* Território */}
                                      <Flex align="center" gap="2" mb={isCOpen ? '2' : '0'} wrap="wrap">
                                        <Button size="1" variant="ghost"
                                          onClick={() => setOpenCondados(toggleSet(openCondados, c.id))}>
                                          {isCOpen ? '▼' : `▶ ${c.baronies.length}⚔️`}
                                        </Button>
                                        <Text style={{ fontSize: 13 }}>🗺️</Text>
                                        <InlineField label="Nome" value={c.name}
                                          onChange={v => updC(ci, 'name', v)} width={150} />
                                        <InlineField label="ID" value={c.id}
                                          onChange={v => updC(ci, 'id', v)} width={100} />
                                        <InlineField label="Longitude" value={c.lon} type="number"
                                          onChange={v => updC(ci, 'lon', v)} width={90} />
                                        <InlineField label="Latitude" value={c.lat} type="number"
                                          onChange={v => updC(ci, 'lat', v)} width={90} />
                                        <Button size="1" color="red" variant="ghost"
                                          style={{ marginTop: 16 }} onClick={() => delC(ci)}>✕</Button>
                                      </Flex>

                                      {/* Baronias expandidas */}
                                      {isCOpen && (
                                        <Box style={{ paddingLeft: INDENT_1, borderTop: '1px solid var(--green-4)', paddingTop: 8 }}>
                                          <Flex justify="between" align="center" mb="1">
                                            <Text size="1" weight="medium">⚔️ Baronias</Text>
                                            <Button size="1" variant="soft" onClick={() => addBarony(ci)}>+ Baronia</Button>
                                          </Flex>
                                          <Flex direction="column" gap="1">
                                            {c.baronies.map((b, bi) => (
                                              <Flex key={bi} gap="2" align="center"
                                                style={{ paddingLeft: INDENT_1 }}>
                                                <Text size="1" color="gray" style={{ width: 12 }}>└</Text>
                                                <InlineField label="Nome" value={b.name}
                                                  onChange={v => updB(ci, bi, 'name', v)} width={140} />
                                                <InlineField label="Lon" value={b.lon} type="number"
                                                  onChange={v => updB(ci, bi, 'lon', v)} width={80} />
                                                <InlineField label="Lat" value={b.lat} type="number"
                                                  onChange={v => updB(ci, bi, 'lat', v)} width={80} />
                                                <Button size="1" color="red" variant="ghost"
                                                  style={{ marginTop: 16 }} onClick={() => delB(ci, bi)}>✕</Button>
                                              </Flex>
                                            ))}
                                          </Flex>
                                        </Box>
                                      )}
                                    </Card>
                                  </Box>
                                )
                              })}
                            </Flex>
                          )}
                        </Card>
                      </Box>
                    )
                  })}

                  {/* Estatísticas do reino */}
                  <Text size="1" color="gray" style={{ paddingLeft: INDENT_1 }}>
                    {kDuchies.length} ducado(s) · {kCondados.length} território(s) · {kCondados.reduce((s,c) => s+c.baronies.length, 0)} baronia(s)
                  </Text>
                </Flex>
              )}
            </Card>
          )
        })}
      </Flex>

      {/* Botões globais */}
      <Flex gap="2" mt="3" align="center">
        <Button variant="soft" onClick={addKingdom}>👑 + Adicionar Reino</Button>
        <Button size="1" variant="ghost" onClick={() => setShowJson(!showJson)}>
          {showJson ? '▲ Ocultar JSON' : '▼ Ver JSON gerado'}
        </Button>
      </Flex>

      {showJson && (
        <pre style={{ marginTop: 8, padding: 8, background: '#f5f5f5', borderRadius: 4,
          fontSize: 11, overflow: 'auto', maxHeight: 280 }}>
          {JSON.stringify(toData(kingdoms, duchies, condados), null, 2)}
        </pre>
      )}
    </Box>
  )
}
