# Phase 8: border-vertex-editor — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or
> execution agents. Decisions are captured in CONTEXT.md — this log
> preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr
**Areas discussed:** Escopo de operações, Modelo de branching, Camadas editáveis + DAG, Undo + validação + UX, Performance / Telemetria / Touch / Recovery

---

## Escopo de operações

### Operações de vértice

| Option | Description | Selected |
|--------|-------------|----------|
| Mover vértice (drag) | Clássico SVG: arrasta handle | ✓ |
| Adicionar vértice | Click numa aresta cria novo vértice | ✓ |
| Deletar vértice | Selecionar + Delete/Backspace | ✓ |
| Simplify (Douglas-Peucker) | Slider de tolerância + botão | ✓ |

**User's choice:** All four. Maximum scope.

### Operações de polígono inteiro

| Option | Description | Selected |
|--------|-------------|----------|
| Split (corta polígono em 2) | Linha cruza polígono → 2 territórios | ✓ |
| Merge (funde 2 vizinhos) | Seleciona 2 adjacentes → 1 | ✓ |
| Mover território inteiro (translate) | Drag interior translada todos vértices | ✓ |
| Nenhuma — só edit de vértice (Recommended) | Scope mínimo | |

**User's choice:** Split + Merge + Translate. Overrode recommended minimum.

### Coastline / land mask

| Option | Description | Selected |
|--------|-------------|----------|
| Não — só baronias internas (Recommended) | Defer landmask | |
| Sim — land mask editável | Permite ajustar costa | ✓ |
| Coast read-only mas vértices costeiros de barony editáveis | Mid-ground | |

**User's choice:** Sim — landmask editável. Most aggressive scope.

### Hierarquia editável

| Option | Description | Selected |
|--------|-------------|----------|
| Só barony — condado/duchy re-derivados (Recommended) | Barony fonte de verdade | ✓ |
| Condado direto (move borda do condado) | Mais rápido p/ macro | |
| Ambos com tier toggle | Mais flex, mais bugs | |

**User's choice:** Recommended.

### Split — nomeação

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt modal pede nome + tier | Mais controle | |
| Auto: herda condado, nome = `<pai> (2)`, id = next free (Recommended) | Zero-friction | ✓ |
| Auto sem nome (vira 'unnamed') | Marca amarela | |

**User's choice:** Recommended.

### Merge — winner rule

| Option | Description | Selected |
|--------|-------------|----------|
| Primeiro selecionado vence (Recommended) | Regra simples | ✓ |
| Prompt escolhe qual vence | Mais cliques | |
| Bloqueia merge se condados pais diferentes | Conservador | |

**User's choice:** Recommended.

### Landmask re-clip cascade trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Manual: 'Apply landmask' button (Recommended) | Batch + cascade ao fim | |
| Auto-debounce 500ms | Custo alto | |
| Per-edit imediato | Inviável (10s/vértice) | |

**User's choice:** Other — "Definir duas opcoes, 1 manual e outro com edicao imediata". **Two-mode toggle** (manual + auto-immediate).

### Cap de vértices

| Option | Description | Selected |
|--------|-------------|----------|
| Sem cap mas warning >500 | Performance degrada | |
| Hard cap 1000 vért/barony (Recommended) | Protege render + lookup | ✓ |
| Sem cap, sem warning | Trust user | |

**User's choice:** Recommended.

---

## Modelo de branching

### Conceito de branch

| Option | Description | Selected |
|--------|-------------|----------|
| Branch nomeada estilo git (Recommended) | Manual create/switch/delete | |
| Snapshot auto a cada N edits | Timeline-based | |
| Fork-on-first-edit (implícita) | Main intocada | |
| Branch + snapshots (híbrido) | Mais poder | ✓ |

**User's choice:** Híbrido. Most powerful.

### Branch creation

| Option | Description | Selected |
|--------|-------------|----------|
| Botão explícito 'New branch from <atual>' (Recommended) | Zero magia | ✓ |
| Auto na primeira edição em main | Protege main | |
| Manual + auto na main | Híbrido | |

**User's choice:** Recommended.

### Branch storage

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot completo do GeoJSON + RegionConfig (Recommended) | Simples, sem replay | ✓ |
| Patch incremental sobre main | Disco menor; replay caro | |
| Patch + checkpoint a cada N | Híbrido | |

**User's choice:** Recommended.

### Branch picker UI

| Option | Description | Selected |
|--------|-------------|----------|
| Dropdown no toolbar (Recommended) | Padrão git client | ✓ |
| Painel dedicado sidebar | Custa real-estate | |
| Comando teclado + modal | Power-user only | |

**User's choice:** Recommended.

### Auto-snapshot frequency

| Option | Description | Selected |
|--------|-------------|----------|
| A cada N edits (ex: 25) (Recommended) | Previsível | ✓ |
| A cada N minutos de atividade | Time-based | |
| Só manual | Sem auto | |
| Antes de cada Generate/Re-render | Pre-cascade | |

**User's choice:** Recommended.

### Branch merge

| Option | Description | Selected |
|--------|-------------|----------|
| Não — branches isoladas (Recommended) | Copy-replace p/ promover | ✓ |
| Sim, copy-replace ('Copy <branch> → main') | Substitui main | |
| Merge geométrico 3-way | Complexo, defer | |

**User's choice:** Recommended (note: D-14 actually picks the copy-replace mechanic as the promotion path; this matches the recommended "no real merge" answer).

### Export source

| Option | Description | Selected |
|--------|-------------|----------|
| Branch ativa no momento do export (Recommended) | Manifesto inclui nome + timestamp | ✓ |
| Sempre main | Branches viram sandbox | |
| Modal pede escolha | +1 click | |

**User's choice:** Recommended.

### Delete main

| Option | Description | Selected |
|--------|-------------|----------|
| Não — main protegida (Recommended) | Botão delete desabilitado | ✓ |
| Sim, com confirmação | Reset total | |
| Sim, mas auto-promove outra a main | Invariante mantida | |

**User's choice:** Recommended.

---

## Camadas editáveis + DAG

### Artefato dos edits no pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| Sobrescrevem GeoJSON pós-merge (Recommended) | Downstream re-roda normal | ✓ |
| Patch overlay separado | Cache invalidation tricky | |
| Sobrescrevem pós-voronoi (antes cleanup) | Smooth deforma edits | |

**User's choice:** Recommended.

### Slider Phase 04 vs edits pendentes

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-snapshot pre-cascade + warning modal (Recommended) | DAG detecta + confirma | ✓ |
| Silenciosamente sobrescreve | Frustrante | |
| Bloqueia sliders enquanto há edits | Conservador | |
| Tenta replay sobre nova geometria | Quebra frequente | |

**User's choice:** Recommended.

### Stage 'manual_edit' no DAG

| Option | Description | Selected |
|--------|-------------|----------|
| Sim — entre merge e hierarchy (Recommended) | Honra Phase 04 contract | ✓ |
| Não — fora do DAG | Quebra D-V3-05 | |
| Edits viram parte do RegionConfig | Config enorme | |

**User's choice:** Recommended.

### Landmask cascade no DAG

| Option | Description | Selected |
|--------|-------------|----------|
| Sim — landmask invalidado dispara cascade total (Recommended) | KD-tree per país rebuild | ✓ |
| Apenas máscara extra sem re-Voronoi | Quebra hit detection | |

**User's choice:** Recommended.

### original_idx p/ baronias novas

| Option | Description | Selected |
|--------|-------------|----------|
| max(original_idx) + 1 dentro da branch (Recommended) | Sempre crescente | ✓ |
| UUID v4 | Unity shader quebra (int) | |
| Hash truncado p/ int32 | Colisão possível | |

**User's choice:** Recommended.

### Lookup PNG re-render

| Option | Description | Selected |
|--------|-------------|----------|
| render + lookup re-rodam após manual_edit (Recommended) | NEAREST mantido | ✓ |
| Preview-only no canvas, export final faz | Preview ≠ Unity | |
| Re-render incremental | Otimização complexa | |

**User's choice:** Recommended.

### Coast / border layer

| Option | Description | Selected |
|--------|-------------|----------|
| Coast = landmask boundary, editado como polígono único (Recommended) | Border PT/ES read-only separada | ✓ |
| Coast read-only; só border PT/ES editável | Conservador | |
| Coast e border PT/ES ambos editáveis | Quebra CLAUDE.md #3 | |

**User's choice:** Recommended.

### DAG cache scope

| Option | Description | Selected |
|--------|-------------|----------|
| Cache por (project_id, branch_id, stage, token) (Recommended) | Switch = cache hit | ✓ |
| Cache global; switch invalida tudo | Re-roda ~10s | |
| Cache só da branch ativa (LRU 2) | Compromisso | |

**User's choice:** Recommended.

---

## Undo + validação topológica + UX seleção

### Undo scope

| Option | Description | Selected |
|--------|-------------|----------|
| Sim — undo só de ops do editor (Recommended) | zundo wrap; sliders fora | ✓ |
| Sim — undo compound (edits + sliders + branch switch) | Cross-stage; complexo | |
| Não cabear ainda — snapshots fazem | Adia novamente | |

**User's choice:** Recommended.

### Topology validation

| Option | Description | Selected |
|--------|-------------|----------|
| Bloqueia self-intersect + gap; avisa duplicado (Recommended) | Shapely is_valid + touches | ✓ |
| Bloqueia TODAS (incl. sliver <0.001°) | Máximo rigor | |
| Só avisa, permite | Liberal | |

**User's choice:** Recommended.

### Auto-snap

| Option | Description | Selected |
|--------|-------------|----------|
| Snap vértice 5px + snap aresta (Recommended) | Hold Alt desliga | ✓ |
| Só snap a vértice | Gaps possíveis | |
| Sem snap | Manual livre | |

**User's choice:** Recommended.

### Selection UX

| Option | Description | Selected |
|--------|-------------|----------|
| Click + Shift-click + marquee drag (Recommended) | Padrão Figma | ✓ |
| Click único, sem multi-select | Repetitivo | |
| Click + lasso | Mais código | |

**User's choice:** Recommended.

### Shared edge visual

| Option | Description | Selected |
|--------|-------------|----------|
| Realce roxo + vértices em hover (Recommended) | Indica afetará vizinhos | ✓ |
| Sem realce | Confuso | |
| Aresta sempre destacada | Polui canvas | |

**User's choice:** Recommended.

### Shared vertex movement

| Option | Description | Selected |
|--------|-------------|----------|
| Sim, sempre (Recommended) | Topologia limpa | ✓ |
| Só move no ativo (gap → validação bloqueia) | Editor puro | |
| Hold Shift p/ só ativo | Flex; +1 atalho | |

**User's choice:** Recommended.

### Hotkeys

| Option | Description | Selected |
|--------|-------------|----------|
| V/A/D/S/M/Esc + Ctrl+Z/Y (Recommended) | Single-letter Figma-style | ✓ |
| Só Delete + Esc + Ctrl+Z/Y | Mínimo | |
| Tudo + custom rebind | Máximo | |

**User's choice:** Recommended.

### Coord readout

| Option | Description | Selected |
|--------|-------------|----------|
| (lat, lon) float 6 casas, tooltip flutuante (Recommended) | Game-Designer thinks geographic | ✓ |
| (x, y) pixel | Debug only | |
| Ambos lado-a-lado | Ruído | |

**User's choice:** Recommended.

---

## Performance / Telemetria / Touch / Recovery (rodada extra)

### Performance budget

| Option | Description | Selected |
|--------|-------------|----------|
| 60fps até ~5k vért + viewport culling (Recommended) | RAF batching 16ms | ✓ |
| 30fps sem culling | Konva render tudo | |
| 60fps + LOD por zoom | Handles só >1.5x | |

**User's choice:** Recommended.

### Telemetria

| Option | Description | Selected |
|--------|-------------|----------|
| Local-only SQLite (Recommended) | Tabela edit_events | ✓ |
| Sem telemetria | Mínimo | |
| Local + opt-in export bundle | User exporta on-demand | |

**User's choice:** Recommended.

### Mobile / touch

| Option | Description | Selected |
|--------|-------------|----------|
| Defer — desktop-only (Recommended) | Phase 8 = desktop | ✓ |
| Touch + pen básico | Pointer events roteados | |
| Touch full (pinch, tap-size, two-finger pan) | Custo alto | |

**User's choice:** Recommended.

### Persistência + recovery

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-save SQLite cada N edits + branch ativa em localStorage (Recommended) | Snapshot IS save | ✓ |
| Auto-save a cada drag-end | I/O cada drag = lag | |
| Só snapshot manual + localStorage dirty flag | User decide | |

**User's choice:** Recommended.

---

## Claude's Discretion

- Exact CSS for shared-edge / snap / invalid-drag visuals.
- Toolbar tool icons and help-panel layout.
- Whether `Apply landmask` button is filled or outlined.
- Branch-picker dropdown row metadata density.
- Intermediate coord precision (tooltip is 6 decimals; storage TBD).
- zundo `partialize` diff representation.

---

## Deferred Ideas (full list in CONTEXT.md `<deferred>`)

- 3-way geometric merge between branches
- Mobile/touch support
- LOD / zoom-gated handles
- Per-barony incremental lookup re-render
- Custom keybind rebinding UI
- Hierarchy-tier toggle (condado-direct edits)
- Cross-condado merge guardrail
- Telemetry opt-in export bundle
- LRU cache eviction beyond (latest, prior) per branch
