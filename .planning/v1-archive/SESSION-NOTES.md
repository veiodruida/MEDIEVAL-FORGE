# Notas de Sessão — 2026-04-26

## Objetivo

Fechar todos os bugs órfãos documentados na UAT round 2 da Fase 04 (`04-HUMAN-UAT.md`, linhas 175-179) antes de avançar para a próxima fase.

---

## O que foi feito

### 5 bugs órfãos fechados (todos via `/gsd-quick`)

| # | Bug | Quick ID | Root cause | Commit |
|---|-----|----------|------------|--------|
| 2 | 13 condados presentes em `territory_metadata.json` ausentes de `territories.geojson` | `260426-pcy` | H1: `emit_territories_from_disk` silenciosamente ignorava entradas do `colors.json` quando `original_condados=None` — convertido para fail-loud + soft-assert log em `build_territories_geojson` | `7057539` |
| 4 | "Gerar mapa" usava research stale de 4 condados em vez do cache rico de 91 do DB | `260426-q3v` | `api/generate.py` aceitava o body cegamente sem consultar `ResearchCache` — novo `services/territory_builder.py` aplica cache-first; `force_body_territory_data` como escape hatch | `e6bf168` |
| 1 | vertex-handles endpoint com `target=12` retornava todos os 287 vértices | `260426-qc0` | `decimate_polygon` em `voronoi.py` usava busca binária de tolerância Douglas-Peucker com range `0–1` que colapsa polígonos em escala de grau (lon/lat) — reescrito como curvature-weighted stride sampler independente de escala | `2637aea` |
| 3 | `recalc_neighbors` não recortava células Voronoi na máscara de terra | `260426-qlo` | Sem clip após mover capital → células no oceano — `load_land_mask_and_bbox()` adicionado em `voronoi.py`, `move_capital` em `edit.py` passando land mask + bbox; `pixel_polygon_to_lonlat` promovido a público | `98dd090` |
| 5 | `project.updated_at` não era atualizado nos endpoints de edição | `260426-qvu` | `api/edit.py` nunca bumpava o campo — novo `services/project_meta.py` com `touch_project(session, project_id)` chamado em 5 endpoints na mesma transação | `0df5187` |

---

## Gap arquitetural remanescente (Fase 04 T4)

**Ctrl+Z compound undo** continua falhando — o listener dispara e `temporal.undo()` reverte o store em memória, mas o disco mantém o estado pós-edição. O canvas refetch do disco → estado não revertido. Requer endpoint de inverse-operation no backend (ex: re-chamar `move_capital` com posição anterior) ou undo log persistente. **Não é um bug de implementação — é uma lacuna arquitetural.** Escopo: nova fase ou sub-fase dedicada.

---

## Novos artefatos criados

| Arquivo | Propósito |
|---------|-----------|
| `scripts/diagnose_orphans.py` | Diagnóstico one-shot que compara metadata vs geojson vs lookup PNG por projeto |
| `backend/medieval_forge/services/territory_builder.py` | Monta `territory_data` a partir do `ResearchCache` (cache-first) |
| `backend/medieval_forge/services/project_meta.py` | Helper `touch_project()` — bump `updated_at` transacional |
| `backend/tests/services/test_territories_geojson_consistency.py` | Regression: `set(metadata.id) ⊆ set(geojson.id)` |
| `backend/tests/services/test_territory_builder.py` | 7 testes do territory_builder |
| `backend/tests/api/test_generate_uses_cached_research.py` | 4 testes de regressão do cache-first |

---

## Próximos passos para amanhã

### Opção A — Avançar para Fase 05

A Fase 04 está funcionalmente completa (4/5 SC aprovados na UAT round 2; T4 é gap arquitetural documentado, não bloqueador). Para fechar formalmente:

1. `/gsd-audit-milestone` — auditar se todos os requisitos da Fase 04 estão cobertos
2. Marcar Fase 04 como `complete` no ROADMAP.md
3. `/gsd-plan-phase 05` — iniciar planejamento da próxima fase (verificar ROADMAP.md para o scope)

### Opção B — Planear o undo arquitetural

Se o Ctrl+Z compound undo for prioritário:

1. `/gsd-add-phase` — adicionar fase de undo-log / inverse-op ao roadmap
2. `/gsd-discuss-phase` → `/gsd-plan-phase` na nova fase

### Opção C — Code review fix dos avisos da Fase 04

7 avisos de qualidade documentados em `04-REVIEW.md` (WR-01 a WR-06). Se quiser limpar antes de avançar:

1. `/gsd-code-review-fix 04` — aplica fixes automáticos nos avisos do REVIEW.md

---

## Estado do repo ao fim da sessão

- Branch: `main`
- Commits desta sessão: 19 commits (5 bugs × ~4 commits cada)
- Testes: todos os testes em scope passando
- Working tree: limpo (excepto `territory_iberia.json` — modificação não relacionada, não commitada)
