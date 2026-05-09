# Phase 03: Read-only canvas redesign - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 03-read-only-canvas-redesign
**Areas discussed:** Layout do shell, Disparo + progresso pipeline, Estados (vazio/loading/erro), Reuso vs strip de canvas existente, Escopo deleção v1, Inspector + interação click, Servir artefatos pipeline, Roteamento multi-projeto

---

## Layout do shell

### Q1: Estilo geral do workspace single-canvas

| Option | Description | Selected |
|--------|-------------|----------|
| Mapbox-like (Recommended) | Canvas full-bleed; chrome flutuante (toolbar fina topo, FitToView/zoom canto, layer panel canto sup. dir.) | ✓ |
| Figma-like | Canvas centro; sidebars esquerda+direita fixas; densidade alta de UI | |
| Hybrid (canvas + inspector fixo) | Canvas full-bleed exceto inspector direita colapsável; layers/legend flutuantes | |

### Q2: Inspector posição

| Option | Description | Selected |
|--------|-------------|----------|
| Sidebar direita colapsável (Recommended) | Painel ~320px com toggle. Padrão Figma/Mapbox Studio | ✓ |
| Flutuante draggable | Card móvel; pode ocupar mapa | |
| Drawer bottom | Desliza de baixo; mobile-feel | |
| Sempre visível sem colapso | Sidebar fixa permanente | |

### Q3: Toolbar topo

| Option | Description | Selected |
|--------|-------------|----------|
| Mínima | Nome + status + Generate | |
| Completa (Recommended) | Nome + status + Generate + Export ZIP + breadcrumb back | ✓ |
| Sem toolbar | Só chrome flutuante | |

### Q4: LayerTogglePanel + LegendCard posicionamento

| Option | Description | Selected |
|--------|-------------|----------|
| Ambos canto sup. esq. (Recommended) | Empilhados; padrão Mapbox | ✓ |
| Layer esq. + Legend dir. | Distribuído | |
| Ambos dentro do inspector | Centraliza chrome | |
| Layer flutuante + Legend canto inferior | Mapbox-classic | |

---

## Disparo + progresso pipeline

### Q1: Como user dispara pipeline após criar projeto

| Option | Description | Selected |
|--------|-------------|----------|
| Botão único "Generate Map" (Recommended) | Toolbar dispara ingest+generate em sequência (state interno: ingesting → generating → generated) | ✓ |
| Dois botões separados (Ingest, Generate) | User clica Ingest → espera → Generate | |
| Auto-run ao abrir projeto sem artefatos | Sem botão; auto-detecta | |
| Botão + Re-run depois | Generate inicial; depois Re-generate | |

### Q2: Feedback de progresso durante run

| Option | Description | Selected |
|--------|-------------|----------|
| Toolbar status badge + log inline (Recommended) | Status no badge + log expandível clicável | ✓ |
| Modal dedicado de progresso | Bloqueia interação | |
| Toast notifications | Pequenos toasts canto inferior dir. | |
| Status bar inferior + badge toolbar | Barra fina abaixo do canvas | |

### Q3: Endpoint backend para invocar Phase 01 run_pipeline()

| Option | Description | Selected |
|--------|-------------|----------|
| POST /api/v3/projects/{id}/generate + SSE GET (Recommended) | POST inicia, GET SSE streama estágios; espelha Phase 02 D-14 | ✓ |
| POST sync (sem SSE) | Bloqueia até terminar | |
| WebSocket bidirecional | Overkill p/ run único | |
| Combo /ingest + /generate em /run | Endpoint atômico | |

### Q4: Cancelamento de run em andamento

| Option | Description | Selected |
|--------|-------------|----------|
| Sem cancel (Recommended) | Pipeline rápido (~10s); cancel é complexidade extra | ✓ |
| Botão cancel + per-stage stop_event | Mirror ingest_terrain/runner.py | |
| Cancel só do ingest | Cancela só a parte cara (OSM) | |

---

## Estados (vazio/loading/erro)

### Q1: Estado VAZIO — projeto recém-criado, sem ingest nem generate

| Option | Description | Selected |
|--------|-------------|----------|
| Canvas com onboarding (Recommended) | Placeholder com ícone + "Gerar mapa medieval para [país] [período]" + CTA grande | ✓ |
| Canvas vazio + toolbar Generate piscando | Mais discreto | |
| Modal de boas-vindas obrigatório | Fricção alta | |

### Q2: Estado INGESTING — dados sendo baixados do OSM

| Option | Description | Selected |
|--------|-------------|----------|
| Canvas placeholder + log no badge (Recommended) | Silhueta país cinza + status badge SSE | ✓ |
| Spinner full-canvas | Bloqueia canvas | |
| Canvas mostra dataset bruto progressivo | Karpathy: hipotético | |

### Q3: Estado GENERATING — pipeline Phase 01 rodando

| Option | Description | Selected |
|--------|-------------|----------|
| Canvas placeholder + lista estágios SSE (Recommended) | Lista expandível dos 11 estágios DAG + ✓ por evento | ✓ |
| Só progress bar percentual | Perde transparência | |
| Render parcial dos estágios anteriores | Phase 04 features | |

### Q4: Estado ERRO — pipeline falhou meio do caminho

| Option | Description | Selected |
|--------|-------------|----------|
| Banner de erro + log + botão Retry (Recommended) | Callout vermelho topo, status badge vermelho, UI continua funcional | ✓ |
| Modal de erro bloqueante | Agressivo | |
| Toast + estado anterior preservado | Toast discreto | |

---

## Reuso vs strip de canvas existente

### Q1: CanvasViewer + 5 layers Konva existentes

| Option | Description | Selected |
|--------|-------------|----------|
| Reusar AS-IS (Recommended) | Designados read-only-friendly em v1; ajustar só hidratação | ✓ |
| Reescrever do zero | Custa muito; perde testes | |
| Reusar + audit + simplificação limitada | Risco scope creep | |

### Q2: Componentes EDIT-only (EditToolbar, SplitTool, VertexHandlesLayer, SelectionFloatingToolbar, ValidationBadgesLayer, useRubberBandSelection, useEditKeyboardMap)

| Option | Description | Selected |
|--------|-------------|----------|
| Apagar todos (Recommended) | Phase 03 read-only; Phase 04 traz sliders, não vertex edit. ~1500 linhas + testes saem | ✓ |
| Manter como dead-import | Viola D-V3-04 | |
| Mover para subdir /edit/ desativado | Sinaliza deprecation | |

### Q3: TerritoryEditor.tsx (341 linhas, página dedicada de edit)

| Option | Description | Selected |
|--------|-------------|----------|
| Apagar (Recommended) | Phase 04 não precisa de página dedicada | ✓ |
| Manter rota /editor até Phase 04 | Risco import dangling | |

### Q4: Hooks (useUndoShortcut, useBeforeUnloadGuard, useEditKeyboardMap)

| Option | Description | Selected |
|--------|-------------|----------|
| Apagar todos (read-only não tem unsaved state) (Recommended) | Phase 03 não tem nada para salvar/desfazer | ✓ |
| Manter useUndoShortcut p/ Phase 04 | Risco dead import | |
| Apagar useBeforeUnloadGuard + useEditKeyboardMap; manter useUndoShortcut | Surgical | |

---

## Escopo deleção v1

### Q1: Stepper UI (Stepper.tsx, StepCard.tsx, ProviderEffortPicker, BaronyGranularitySlider, TerrainDataSection, components/pipeline/*)

| Option | Description | Selected |
|--------|-------------|----------|
| Apagar tudo + usePipelineStore (Recommended) | ~1k linhas + testes + store saem | ✓ |
| Apagar stepper components, manter usePipelineStore | Store fica zumbi | |
| Mover tudo para /_archive/ até Phase 04 | Custa import maintenance | |

### Q2: Backend v1 (legacy /ingest + ingest_runner + ingest_wikidata + api/generate)

| Option | Description | Selected |
|--------|-------------|----------|
| Apagar tudo (Recommended) | Phase 02 D-15 deferiu; /api/v3/.../ingest substitui | ✓ |
| Apagar Wikidata; manter ingest_runner como library | Audit cuidadoso | |
| Apagar só endpoints v1; manter services/ | Viola D-V3-04 | |

### Q3: components/research/, components/codex/, useResearchStore, useCodexStream, api/research.ts, api/codex.ts (LLM v1)

| Option | Description | Selected |
|--------|-------------|----------|
| Apagar tudo agora; Phase 07 reescreve (Recommended) | Reescrita do zero é mais limpa que adapt v1; D-V3-04 vence | ✓ |
| Apagar UI; manter services + stores | Compromisso | |
| Manter tudo (Phase 07 reusa per ROADMAP) | Risco dead code | |
| Mover para /v1-archive/ | Ritual mais alto | |

### Q4: AssignmentEditor + useEditorStore + useValidationStore

| Option | Description | Selected |
|--------|-------------|----------|
| Apagar tudo — Phase 03 read-only (Recommended) | Sem edit UI = sem stores de edit | ✓ |
| Apagar UI; manter useValidationStore para Phase 06 | Risco até lá | |

---

## Inspector + interação click

### Q1: Que metadata o Inspector mostra ao clicar num condado

| Option | Description | Selected |
|--------|-------------|----------|
| Tudo de territory_metadata.json (Recommended) | id, name, kingdom, duchy, capital, pixel_count, lon/lat, baronies, neighbors | ✓ |
| Mínimo: id + name + kingdom + duchy | Card compacto | |
| Categoriza por seção (header, hierarchy, geometry, baronies) | Bom UX, mais código | |
| Card de seleção + tab "Detalhes" | Tabs sobram (layers/legend já no canto) | |

### Q2: Hover sobre território — feedback visual

| Option | Description | Selected |
|--------|-------------|----------|
| Outline sutil + tooltip nome (Recommended) | Outline cinza claro + tooltip; click → outline dourado | ✓ |
| Só cursor change | Menos descobrível | |
| Outline + Inspector preview ao hover | Atrapalha leitura | |

### Q3: Click em água/oceano (fora de qualquer território)

| Option | Description | Selected |
|--------|-------------|----------|
| Deselect (limpa Inspector) (Recommended) | Padrão Figma/Mapbox | ✓ |
| Não faz nada; mantém seleção | Inspeção continuada | |
| Click água = colapsa Inspector | Pode confundir | |

### Q4: Múltipla seleção (Shift+click vários condados)

| Option | Description | Selected |
|--------|-------------|----------|
| Sem multi-seleção (Recommended) | Karpathy: hipotético | |
| Shift+click + Inspector mostra agregado | Multi-select com inspector mostrando totais | ✓ |
| Rubber-band (drag select) | Edit-only; será deletado | |

**Notes (Q4):** User picked the non-recommended option. Justification accepted because (a) read-only inspection is within phase scope, (b) `InteractionLayer` already supports multi-outline rendering, (c) `useRubberBandSelection` is being deleted (D-10) so shift+click is the only multi-select mechanism that survives.

---

## Servir artefatos pipeline

### Q1: Como frontend acessa os 12 arquivos Unity gerados

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI StaticFiles mount em /api/v3/projects/{id}/artifacts/* (Recommended) | URLs previsíveis, cache HTTP nativo, sem código de leitura | ✓ |
| Endpoint dedicado por arquivo | Mais código; cache manual | |
| Reusar pattern v1 /preview/ | Acoplamento ao layout v1 | |
| Endpoint único /artifacts retorna ZIP | Caro; sem lazy loading | |

### Q2: Cache-busting quando pipeline re-gera

| Option | Description | Selected |
|--------|-------------|----------|
| Query param ?v={updated_at} (Recommended) | Pattern v1 já testado em CanvasViewer.cacheVersion | ✓ |
| Filenames com hash | Renaming logic + manifest | |
| ETag + max-age=0 | Re-fetch sempre | |

### Q3: Acesso Cross-Origin / autenticação (PRIMEIRA RESPOSTA — REVERTIDA)

| Option | Description | Selected |
|--------|-------------|----------|
| Sem auth (local-only) (Recommended) | v3 é local web tool por design | |
| Auth header obrigatório | Para hosting remoto futuro | ✓ (revertido) |

**First answer:** "Auth header obrigatório" — flagged by Claude as conflict with PROJECT.md "local web tool" + Phase 01/02 endpoints having no auth. `api/auth.py` audited and confirmed to be LLM credential storage only, not endpoint protection.

### Q3-reconcile: Auth para artifacts — quer mesmo introduzir agora ou foi engano?

| Option | Description | Selected |
|--------|-------------|----------|
| Sem auth (alinhado com v3 local-only) | Reverter para opção recomendada | ✓ |
| Manter auth obrigatório | Adiciona scope significativo | |
| Defer auth para backlog | Anota v3.1 | |

### Q4: Validar existência dos 12 arquivos antes do canvas hidratar

| Option | Description | Selected |
|--------|-------------|----------|
| GET /api/v3/projects/{id}/status retorna manifest (Recommended) | Frontend decide qual estado mostrar | ✓ |
| 404 condicional na hidratação | Ruído de log | |
| Endpoint manifest dedicado | Phase 06 owna export-gate manifest | |

---

## Roteamento multi-projeto

### Q1: Estrutura de rotas

| Option | Description | Selected |
|--------|-------------|----------|
| Manter /projects + /projects/:id (Recommended) | Estrutura atual; mínima mudança | ✓ |
| Workspace unificado /workspace/:id com sidebar projetos | Viola Mapbox-like full-bleed (D-01) | |
| Lista + detalhe + botão de switch rápido | Compromisso | |

### Q2: ProjectList.tsx (64 linhas) e ProjectNew.tsx (254 linhas)

| Option | Description | Selected |
|--------|-------------|----------|
| Manter ambas as-is (Recommended) | Nenhuma depende de stepper | ✓ |
| Refresh visual para combinar com Mapbox-like | Scope creep | |
| Apagar ProjectNew; criação vira modal in-list | Reescreve form | |

### Q3: Botão "Voltar" da toolbar leva para

| Option | Description | Selected |
|--------|-------------|----------|
| /projects (lista) (Recommended) | Padrão; breadcrumb explícito | ✓ |
| Browser back | navigate(-1); pode levar a lugar errado | |

---

## Claude's Discretion

Items deferred to the planner (CONTEXT.md "Claude's Discretion" section):
- Tailwind v4 vs Radix Themes split for the workspace shell
- Tooltip implementation (Radix vs Konva-text overlay)
- Status badge animation/format (pulse, percent bar, text-only)
- SSE event envelope shape (mirror Phase 02 vs stricter envelope)
- Run state location (new useRunStore vs derived from TanStack Query)
- Empty-state visual icon (Lucide vs Radix vs custom SVG)
- How much of useCanvasArtifacts needs change beyond URL prefix swap
- Whether api/auth.py + services/credential_store.py survive the D-13 purge
- Run-id generation strategy (uuid4 vs project_id+timestamp)

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section:
- Cancel of in-flight runs (Phase 04)
- Partial render of intermediate stages (Phase 04)
- Param studio sliders + live re-render (Phase 04)
- Compound undo for slider changes (Phase 04)
- DEM/HydroSHEDS terrain wire-up (Phase 06 / v3.1)
- Region YAML loader (Phase 05)
- Schema validation on artifact serve (Phase 06)
- LLM research dialog rewrite (Phase 07)
- Edit territory geometry / paint-brush mountains (out of v3 per PROJECT.md)
- Auth + remote hosting (backlog v3.1)
- Multi-language UI (out of v3 per PROJECT.md)
- Manifest dedicated endpoint (Phase 06 export gate)
- Map switcher / multi-project sidebar (v3.1 polish)
- Visual refresh of ProjectList and ProjectNew (v3.1 polish)
