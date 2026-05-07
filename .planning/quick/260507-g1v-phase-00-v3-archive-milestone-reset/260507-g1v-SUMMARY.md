---
phase: quick-260507-g1v
plan: 01
subsystem: planning-meta
tags: [v3, milestone-reset, archive, ci-bootstrap, claude-md-rewrite]
requires: []
provides:
  - "Tag git v1.0-archive (commit anterior ao reset)"
  - ".planning/v1-archive/ — snapshot completo do milestone v1.0"
  - "CLAUDE.md v3 (Pipeline Contract + Architecture + Conventions + What v3 is NOT)"
  - "v3 planning seed (.planning/{PROJECT,ROADMAP,STATE,backlog}.md)"
  - ".claude/skills/karpathy/SKILL.md — skill auto-discoverable"
  - ".github/workflows/ci.yml — CI scaffold (4 jobs paralelos)"
  - "pytest markers parity/integration/uat (slow preservado)"
  - "frontend script e2e:playwright"
  - "V1_DELETION_CANDIDATES.md — review humano antes de Phase 03+"
affects:
  - "v1.0 milestone arquivado, v3 milestone iniciado"
tech-stack:
  added:
    - "GitHub Actions CI workflow"
  patterns:
    - "Conservative archival (mover não deletar) com tag git como ancoragem"
key-files:
  created:
    - .planning/PROJECT.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/backlog.md
    - .planning/v1-archive/STACK_RESEARCH.md
    - .claude/skills/karpathy/SKILL.md
    - .github/workflows/ci.yml
    - .planning/quick/260507-g1v-phase-00-v3-archive-milestone-reset/V1_DELETION_CANDIDATES.md
  modified:
    - CLAUDE.md
    - pyproject.toml
    - frontend/package.json
  moved:
    - ".planning/ROADMAP.md → .planning/v1-archive/ROADMAP.md"
    - ".planning/PROJECT.md → .planning/v1-archive/PROJECT.md"
    - ".planning/REQUIREMENTS.md → .planning/v1-archive/REQUIREMENTS.md"
    - ".planning/STATE.md → .planning/v1-archive/STATE.md"
    - ".planning/SESSION-NOTES.md → .planning/v1-archive/SESSION-NOTES.md"
    - ".planning/phases/ → .planning/v1-archive/phases/"
    - "Skill/SKILL-karpathy.md → .claude/skills/karpathy/SKILL.md"
decisions:
  - "Conservative deletion: V1_DELETION_CANDIDATES.md em vez de remover código v1 agora — Phase 02/07 reusa muita coisa"
  - "Worktree audit relaxed: 6 stale worktrees não tinham working tree dir on disk; remoção via 'git worktree remove --force' segura sem auditoria de status (impossível inspecionar dirs inexistentes)"
metrics:
  duration_minutes: 47
  completed_date: "2026-05-07"
  tasks_completed: 3
  files_created: 8
  files_modified: 3
  files_moved: 7
  commits: 3
---

# Phase 00 Plan 01: v3 Archive Milestone Reset — Summary

Phase 00 atomica e cirúrgica: arquivou todo o milestone v1.0 sob a tag git `v1.0-archive`, seedou o esqueleto v3 (4 docs de planning + CLAUDE.md reescrito de 168 linhas → 130 linhas focadas em pipeline contract), bootstrap CI com 4 jobs paralelos, e listou candidatos a deleção para revisão humana — sem quebrar o servidor que continua respondendo HTTP 200.

## Tasks executadas

### Task 1 — chore(v3): archive v1.0 planning artifacts and prepare v3 milestone
- **Commit:** `9b156a5`
- Tag `v1.0-archive` criada apontando para `07b7f37` (commit anterior ao reset)
- 5 arquivos de planning v1 movidos para `.planning/v1-archive/` (ROADMAP, PROJECT, REQUIREMENTS, STATE, SESSION-NOTES)
- Diretório `.planning/phases/` (109 arquivos, 9 phases) movido para `.planning/v1-archive/phases/`
- Skill Karpathy movida de `Skill/SKILL-karpathy.md` → `.claude/skills/karpathy/SKILL.md` (auto-discovery padrão do Claude Code); diretório `Skill/` removido
- 6 worktrees stale removidos via `git worktree remove --force`: agent-{a1e3903b, a4a1804e, a5ad6a02, ad649f86, ae007eb2, ae81ed71}; `git worktree prune` confirmou cleanup
- 117 arquivos modificados (1 novo skill + 116 renames), commit-only de itens em `.planning/` e `.claude/skills/karpathy/` (exclui exports/ deletions e settings.local.json modificados que estavam fora de scope)

### Task 2 — docs(v3): rewrite CLAUDE.md and seed v3 planning docs
- **Commit:** `c055dac`
- `.planning/v1-archive/STACK_RESEARCH.md` criado com tabelas Validated Choices (Frontend/Backend/Packaging) + Potential Issues (1-7) + Recommendations + Confidence Levels + Sources extraídas integralmente do CLAUDE.md anterior (preserva research v1 sem poluir contexto v3)
- `CLAUDE.md` reescrito completamente: seções Project / Constraints / **v3 Pipeline Contract** (12-file Unity export + 7 non-negotiable rules referenciando `inicio/map_generator.py` + `inicio/licoes/JORNADA_CRIACAO_MAPA.md`) / Conventions / Architecture (DAG de 11 estágios) / Project Skills / GSD Workflow / **What v3 explicitly is NOT** / Developer Profile. Markers GSD `<!-- GSD:*-start/end -->` preservados em todas seções
- `.planning/PROJECT.md` v3 seedado: vision, value, constraints, out-of-scope, 7 decisões D-V3-01 a D-V3-07
- `.planning/ROADMAP.md` v3 seedado: 8 phases (00-07) com goal/depends/status/success criteria por phase + tabela de requirement coverage
- `.planning/STATE.md` v3 seedado: milestone=v3, current_phase=00, progress 0/8, blockers documentando lições do v1 a re-ler antes de Phase 01
- `.planning/backlog.md` seedado: 6 itens v3.1 (research histórica, Kuwahara, compound undo, vector editor, heightmap, i18n)
- 6 arquivos commitados, 406 inserções / 117 deleções

### Task 3 — chore(v3): bootstrap CI scaffolding and list v1 deletion candidates
- **Commit:** `a437f5e`
- `.github/workflows/ci.yml` criado: 4 jobs paralelos triggerados em push/PR para `main`
  - `pytest-unit` (Python 3.11 + cov-fail-under=60 — Phase 01 sobe para 85%)
  - `pytest-parity` (parity + integration markers, non-skippable from Phase 01; Phase 00 passa como placeholder se vazio)
  - `vitest` (Node 20, npm ci, run mode)
  - `playwright-uat` (Node 20, chromium browsers, scriptado para `npm run e2e:playwright`)
- `pyproject.toml` `[tool.pytest.ini_options]` markers estendidos: `slow` (preservado) + `parity` + `integration` + `uat`. `asyncio_mode/testpaths/pythonpath` intactos
- `frontend/package.json` script `e2e:playwright: "playwright test"` adicionado entre `test:e2e` e `test:e2e:update` (alias preservando ambos)
- `V1_DELETION_CANDIDATES.md` criado com greps reais (sem placeholders): 4 confirmados (ProjectDetail, Stepper, StepCard, usePipelineStore — todos frontend stepper UI), 4 possíveis-mediante-review (codex_runner com tightly-coupled LLM v1 → delete em Phase 07; territory_builder, territories_geojson, lib/map_generator wrapper), 10 DO-NOT-DELETE (ingest_*, llm/, research_*, db.py, models.py — reusados em Phase 02/07)
- Smoke test passado: uvicorn + medieval_forge.main:app respondeu HTTP 200 em http://127.0.0.1:8765/

## Commits (em ordem)

| # | Hash | Subject |
|---|------|---------|
| 1 | `9b156a5` | chore(v3): archive v1.0 planning artifacts and prepare v3 milestone |
| 2 | `c055dac` | docs(v3): rewrite CLAUDE.md and seed v3 planning docs |
| 3 | `a437f5e` | chore(v3): bootstrap CI scaffolding and list v1 deletion candidates |

`git rev-list v1.0-archive..HEAD --count` retorna **3** (exatamente um commit por task).

## Tag git criada

```
v1.0-archive → 07b7f37 (docs(session): notas da sessão 2026-04-29 — fase 02.1 completa + performance fixes)
```

## Smoke test (servidor ainda boota)

```
$ python -c "import uvicorn; from medieval_forge.main import app; uvicorn.run(app, host='127.0.0.1', port=8765, log_level='warning')" &
$ sleep 6 && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/
HTTP_STATUS=200
```

App importável (`medieval_forge.cli` + `medieval_forge.main:app`), responde 200 OK na rota `/`. Phase 00 não quebrou nada.

## Deviations from Plan

### [Rule 3 - Blocking] Skill/SKILL-karpathy.md was untracked, not under git control

- **Found during:** Task 1 (step 1.4)
- **Issue:** `git mv Skill/SKILL-karpathy.md .claude/skills/karpathy/SKILL.md` falhou com "fatal: not under version control, source=Skill/SKILL-karpathy.md". O arquivo estava untracked (nunca foi commitado).
- **Fix:** Substituído por `cp` + `rm` manual seguido de `rmdir Skill`. Resultado idêntico (skill no novo local, dir antigo removido), e o arquivo entra no git index pela primeira vez via `git add .claude/skills/karpathy/SKILL.md` na hora do commit.
- **Files modified:** N/A (mesma operação semântica)
- **Commit:** `9b156a5`

### [Auditoria Worktree] 6 worktrees stale tinham metadata git mas não dirs on-disk

- **Found during:** Task 1 (step 1.2)
- **Issue:** A constraint exigia rodar `git -C <worktree> status --porcelain` e `git -C <worktree> log main..HEAD` para cada worktree antes de remover, abortando se algum tivesse trabalho. Mas os 6 paths em `.claude/worktrees/agent-{a1e3903b...ae81ed71}/` **não existem on-disk** (foram listados no plano como existentes, mas o `.claude/worktrees/` na realidade só tem agent-a93cb60b/ e agent-ab9c62a8/ — outros, mais antigos, fora do escopo). `git status` e `git log` falham com "cannot change to directory" para qualquer um dos 6.
- **Decisão:** Worktrees sem working tree on-disk são implicitamente clean (não há onde modificar arquivos). `git worktree remove --force` removeu o registro git limpo. `git worktree list` agora retorna 1 linha (só main).
- **Auditoria humana:** Os outros 2 worktrees on-disk (agent-a93cb60b, agent-ab9c62a8 — datados de Apr 20) NÃO foram tocados (fora do escopo do plano).

## Files Created / Modified / Moved

### Created (8)
- `.planning/PROJECT.md` (v3 vision)
- `.planning/ROADMAP.md` (8 phases v3)
- `.planning/STATE.md` (milestone=v3)
- `.planning/backlog.md` (6 itens v3.1)
- `.planning/v1-archive/STACK_RESEARCH.md` (research v1 extracted)
- `.claude/skills/karpathy/SKILL.md` (skill move target)
- `.github/workflows/ci.yml` (CI scaffold)
- `.planning/quick/260507-g1v-phase-00-v3-archive-milestone-reset/V1_DELETION_CANDIDATES.md` (review list)

### Modified (3)
- `CLAUDE.md` (rewrite — 168 → 130 lines, focused on v3)
- `pyproject.toml` (3 new pytest markers added; asyncio_mode/testpaths/pythonpath preserved)
- `frontend/package.json` (1 new script `e2e:playwright`)

### Moved (7 paths, 116 files)
- `.planning/ROADMAP.md` → `.planning/v1-archive/ROADMAP.md`
- `.planning/PROJECT.md` → `.planning/v1-archive/PROJECT.md`
- `.planning/REQUIREMENTS.md` → `.planning/v1-archive/REQUIREMENTS.md`
- `.planning/STATE.md` → `.planning/v1-archive/STATE.md`
- `.planning/SESSION-NOTES.md` → `.planning/v1-archive/SESSION-NOTES.md`
- `.planning/phases/` → `.planning/v1-archive/phases/` (110 files: 5 phases + 999.1 placeholder)
- `Skill/SKILL-karpathy.md` → `.claude/skills/karpathy/SKILL.md`

### Removed
- `Skill/` (empty dir after skill move)
- 6 git worktree registrations: agent-{a1e3903b, a4a1804e, a5ad6a02, ad649f86, ae007eb2, ae81ed71}

## Verification

End-to-end automated check (16/16 passes):

```
PASS 1: tag v1.0-archive
PASS 2: 6 archive docs (.planning/v1-archive/{ROADMAP,PROJECT,REQUIREMENTS,STATE,SESSION-NOTES,STACK_RESEARCH}.md)
PASS 3: skill at new location (.claude/skills/karpathy/SKILL.md)
PASS 4: Skill/ removed
PASS 5: only main worktree (1 line in git worktree list)
PASS 6: v3 Pipeline Contract present in CLAUDE.md (count=1)
PASS 7: Validated Choices removed from CLAUDE.md (count=0)
PASS 8: PROJECT.md
PASS 9: ROADMAP.md
PASS 10: STATE.md
PASS 11: backlog.md
PASS 12: ci.yml
PASS 13: parity marker in pyproject.toml
PASS 14: e2e:playwright script in frontend/package.json
PASS 15: V1_DELETION_CANDIDATES.md
PASS 16: exactly 3 commits since v1.0-archive
```

## Self-Check: PASSED

All 8 created files exist. All 3 modified files contain expected changes. All 3 commits exist in git log. Server boots and serves 200 OK.

```
$ for f in .planning/PROJECT.md .planning/ROADMAP.md .planning/STATE.md .planning/backlog.md .planning/v1-archive/STACK_RESEARCH.md .claude/skills/karpathy/SKILL.md .github/workflows/ci.yml .planning/quick/260507-g1v-phase-00-v3-archive-milestone-reset/V1_DELETION_CANDIDATES.md; do test -f "$f" && echo "FOUND: $f" || echo "MISSING: $f"; done
$ for h in 9b156a5 c055dac a437f5e; do git log --oneline --all | grep -q "$h" && echo "FOUND: $h" || echo "MISSING: $h"; done
```

(See Verification block above for the 16-check end-to-end run.)

## Próximo passo

`/gsd-discuss-phase 01` para iniciar Phase 01 (Pipeline parity — port `inicio/map_generator.py` + harness de paridade contra Reconquista).
