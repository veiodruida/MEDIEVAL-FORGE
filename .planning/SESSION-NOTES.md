# Notas de Sessão — 2026-04-24

## Objetivo

Executar a Fase 04 (`canvas-editing-basic`) — especificamente o Plano 10, último gap de fechamento pendente, e conduzir o ciclo completo de verificação, revisão de código e registro de testes.

---

## O que foi feito

### Plano 04-10 — Fechar gap SC1 modo explícito de salvamento

**Problema:** Após um `Ctrl+S` no modo de salvamento explícito, o cache do TanStack Query não era invalidado. O canvas ficava congelado na geometria pré-edição mesmo após o arquivo `territories.geojson` ser atualizado em disco. Os modos `auto` e `per_op` já funcionavam (Plano 09).

**Solução:** Modificação cirúrgica em `frontend/src/hooks/useUndoShortcut.ts`:
- Adicionado `useQueryClient` do TanStack Query
- O handler do `Ctrl+S` agora aguarda `await manualSave()` e invalida os dois query keys (`['territories-geojson', projectId]` e `['territory-metadata', projectId]`) somente em caso de sucesso
- Erro é capturado defensivamente — sem invalidação em caso de falha
- `persistence.ts` não foi tocado (mantido livre de contexto React)

**Gap secundário descoberto na verificação:** O arquivo `useUndoShortcut.test.ts` não tinha `QueryClientProvider` em seus 5 `renderHook`, causando erro `No QueryClient set`. Corrigido adicionando factory `createWrapper()` com `QueryClientProvider` em todos os chamadas.

---

## Resultados dos testes

### Frontend — 52 testes ✓

| Arquivo de teste | Testes | Status |
|---|---|---|
| `useUndoShortcut.test.ts` | 5 | ✓ Passou |
| `CapitalDrag.test.tsx` | 4 | ✓ Passou |
| `DecorationsLayer.test.tsx` | 9 | ✓ Passou |
| `SplitTool.test.tsx` | 4 | ✓ Passou |
| `useRubberBandSelection.test.ts` | 5 | ✓ Passou |
| `persistence.test.ts` | 8 | ✓ Passou |
| `validation.test.ts` | 7 | ✓ Passou |
| `useEditorStore.test.ts` | 4 | ✓ Passou |
| `useProjectStore.test.ts` | 5 | ✓ Passou |
| **Total** | **52** | **✓ 100%** |

### Backend — 16 testes ✓

| Arquivo de teste | Testes | Status |
|---|---|---|
| `test_voronoi.py` | 9 | ✓ Passou |
| `test_edit_api.py` | 7 | ✓ Passou |
| **Total** | **16** | **✓ 100%** |

### Regressão — Testes de fases anteriores

- **Fase 01 + 02**: 51/53 testes passaram
- **2 falhas pré-existentes** em `ResearchDialog.test.tsx` — confirmadas como anteriores à Fase 04 via `git stash` — não são regressões desta fase

---

## Revisão de código (04-REVIEW.md)

**0 críticos · 7 avisos · 6 informativos**

Principais avisos a endereçar em fases futuras:
- **WR-01** `useProjectStore.ts:91-109` — função `diff` pode criar chaves `undefined` em undo/redo após split (zombies no mapa de territórios)
- **WR-02** `CanvasViewer.tsx:412-454` — duplo `endTransaction` possível no path de commit do vertex-edit
- **WR-03** `voronoi.py:259-278` — `split_territory` descarta silenciosamente polígonos além dos 2 primeiros (perda de dados em polígonos côncavos)
- **WR-04** `edit.py:151-163` — key `{id}_b` hard-coded; dividir o mesmo território duas vezes sobrescreve silenciosamente
- **WR-05** `useUndoShortcut.ts:45-62` — invalidação ocorre mesmo quando `manualSave` falhou (divergência visual silenciosa)
- **WR-06** `validation.ts:119-127` — bias epsilon `1e-12` pertuba denominador já garantido não-nulo

---

## Status de verificação

**Automatizada:** 5/5 critérios de sucesso verificados, 6/6 IDs de requisito cobertos (EDIT-01 a EDIT-04, EDIT-07, EDIT-08)

**Humana pendente (04-HUMAN-UAT.md):** 5 itens visuais/runtime não verificáveis por inspeção de código:
1. Arrastar capital atualiza canvas em < 500ms (modo auto/per_op)
2. Arrastar vértice refletido imediatamente no canvas
3. Resultado de merge visível imediatamente
4. Ctrl+Z desfaz drag de capital como passo composto único
5. Ctrl+S no modo explícito atualiza canvas sem reload

---

## Commits desta sessão

| Hash | Mensagem |
|---|---|
| `dd30f3e` | feat(04-10): wire queryClient.invalidateQueries into Ctrl+S handler |
| `fbc7784` | docs(04-10): create SUMMARY.md |
| `24d41da` | test(04-10): add QueryClientProvider wrapper to useUndoShortcut tests |
| `e55dd69` | test(04): persist human verification items as UAT |

---

## Próximos passos

Antes de avançar para a Fase 05:
- Testar manualmente os 5 itens de UAT no app rodando
- Confirmar "aprovado" para marcar a Fase 04 como completa
- Considerar `/gsd-code-review-fix 04` para endereçar os 7 avisos do REVIEW.md
