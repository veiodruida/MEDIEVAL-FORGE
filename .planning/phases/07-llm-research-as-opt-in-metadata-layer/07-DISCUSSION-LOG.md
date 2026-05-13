# Phase 07: LLM research as opt-in metadata layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or
> execution agents. Decisions are captured in `07-CONTEXT.md`; this log
> preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 07-llm-research-as-opt-in-metadata-layer
**Areas discussed:** Interpretação SC #3, Onde mescla overlay, Escopo
providers day 1, Persistência credenciais, UI gatilho + diálogo, Absorver
pendência Phase 06, Cache research

---

## Interpretação SC #3

ROADMAP SC #3 says LLM modules "are reused (moved into `v3/` namespace)"
but Phase 03 deleted them in commit `87f8aab` and PROJECT.md D-V3-04
prohibits namespace transitional shims.

### Q1: Como interpretar 'módulos reusados'?

| Option | Description | Selected |
|--------|-------------|----------|
| (c) Sidecar-first do zero | Define `research_overlay.json` contract first, then build minimum provider plumbing. Treats "reusados" as "design reused, not code". v1-archive becomes design reference. | ✓ |
| (a) Restaurar literal via git | `git checkout 87f8aab` + rename to `v3/`. Highest fidelity to SC #3 text. Resuscitates 350+ LOC with revoked dependencies. | |
| (b) Reescrever c/ v1-archive como template | Middle ground: v1-archive defines architecture, but code rewritten under v3 patterns. | |

**User's choice:** (c) Sidecar-first do zero
**Notes:** Aligns with Karpathy (don't resuscitate deleted code). v1-archive
03-CONTEXT.md / 03-RESEARCH.md become design templates only.

### Q2: Quais artefatos do 87f8aab puxar literais?

| Option | Description | Selected |
|--------|-------------|----------|
| prompt.py | 417 LOC, multiple bug-fix iterations | ✓ (after clarification) |
| schemas.py | 255 LOC Pydantic + lenient parser | ✓ (after clarification) |
| retry.py + parse.py | 3-retry loop + lenient JSON parser | ✓ (after clarification) |
| Reescrever tudo do zero | No literal copies; pure conceptual reuse | (initial multi-select misclick) |

**User's choice:** Option A — copy `prompt.py` + `schemas.py` + `retry.py`
+ `parse.py` literais; adjust only imports. Final answer after follow-up
disambiguation (multi-select had returned 4 contradictory options; user
confirmed Option A as intent).
**Notes:** These 4 files are stateless / pure (no `app.state.credentials`,
no `LLMCredential` coupling, no OAuth state). Represent weeks of bug-fix
iteration not worth repeating.

---

## Onde mescla overlay

### Q1: Onde research_overlay.json funde com pipeline?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-zip merge em territory_metadata.json | Overlay sidecar in project_dir; export merges into zip. Frontend/Unity see merged territory_metadata.json. Zero schema change to 12-file contract. | ✓ |
| 13º arquivo no zip | research_overlay.json ships as file 13. Breaks EXPORT_FILE_CONTRACT, requires Unity loader update. | |
| Overlay fora do zip (sidecar do projeto) | Frontend fetches separately; Unity ignores. Breaks SC #2 "territories show historical names" if interpreted as "in the Unity game". | |

**User's choice:** Pre-zip merge em territory_metadata.json
**Notes:** Preserves 12-file `EXPORT_FILE_CONTRACT` (Phase 05 Plan 05-15).
Unity loader unchanged. MANIFEST gains `research_overlay_applied` flag.

### Q2: Quando overlay aterrissa em territory_metadata.json?

| Option | Description | Selected |
|--------|-------------|----------|
| No export endpoint, não-destrutivo | Pipeline writes raw output untouched; overlay sits as sidecar; build_unity_zip merges in-memory before zipping; frontend uses merged-serving endpoint. | ✓ |
| Logo após research run | Research_runner overwrites territory_metadata.json directly. Loses idempotency; re-run without overlay would overwrite historical names. | |
| Merge em ambos lados, separadamente | Export merges at zip-time; frontend merges via separate fetch. Two merge paths, divergence risk. | |

**User's choice:** No export endpoint, não-destrutivo
**Notes:** Pipeline determinism preserved. Re-running pipeline always
produces byte-identical raw output. D-12 parity test enforces this.

---

## Escopo providers day 1

### Q1: Quais providers entregar no Phase 07 day 1?

| Option | Description | Selected |
|--------|-------------|----------|
| MVP: Claude + Ollama | Frontier + CLI piggyback + zero-cost local. Plugin registry in place. OpenAI/Gemini → v3.1 backlog. | ✓ |
| MVP enxuto: só Ollama | Zero credential code. Risk: PT-BR + JSON mode quality inferior. | |
| All-4 paridade v1 | Claude + OpenAI + Gemini + Ollama. ~1.5k LOC, multiplies edge cases. | |
| Claude + OpenAI | Two cloud frontier providers. No zero-cost option. | |

**User's choice:** MVP Claude + Ollama
**Notes:** Plugin registry pattern from v1 preserved. Adding OpenAI later
= one file + one line.

---

## Persistência credenciais

### Q1: Como persistir credenciais LLM?

| Option | Description | Selected |
|--------|-------------|----------|
| DB SQLite, herdar reversão do v1 | Table `llm_credentials` in `~/.medieval-forge/medieval_forge.db`. Survives restart. Matches gh/git model. | ✓ |
| Session-mem only | `app.state.credentials` volatile dict. Safer (zero disk) but high friction. | |
| Só env vars + CLI piggyback (sem dialog/DB) | Zero credential storage code. UX poor (configure shell first). | |

**User's choice:** DB SQLite, herdar reversão do v1
**Notes:** v1 originally session-memory, reverted after user push.
Phase 07 inherits the reversal (session-2026-04-21-phase3-execute.md
line 66).

### Q2: Ordem de resolução de credencial Claude?

| Option | Description | Selected |
|--------|-------------|----------|
| CLI piggyback > DB > env > dialog | Maximize zero-setup if user has claude-code installed. v1 chain. | ✓ |
| env > DB > CLI > dialog | Env-first for CI-friendly explicit override. | |
| DB > env > dialog (sem CLI piggyback) | No CLI auto-discovery; simpler cross-platform but Claude Code users type key twice. | |

**User's choice:** CLI piggyback > DB > env > dialog paste

---

## UI gatilho + diálogo

### Q1: Onde mora o gatilho 'Run research'?

| Option | Description | Selected |
|--------|-------------|----------|
| Botão na InspectorSidebar modo placeholder + projeto | Adds button to project-summary mode (D-16 from Phase 03). Inspector of selected territory shows merged names + "Pesquisa aplicada" badge. | ✓ |
| Card flutuante no canvas | Always-visible Research card alongside Slider/Legend cards. Occupies permanent real-estate. | |
| Item no ParameterSidebar | Add Research section below Pipeline Params. Risk: research is orthogonal to geometric params; mixing confuses. | |

**User's choice:** InspectorSidebar placeholder/project-summary mode

### Q2: Como é o diálogo de research?

| Option | Description | Selected |
|--------|-------------|----------|
| Radix Dialog modal + SSE stream interno | Modal blocks canvas; field set (country auto, period, provider, model); SSE renders progress inside modal. | ✓ |
| Sheet lateral c/ SSE | Side drawer; lets user see map during stream. More layout coexistence work. | |
| Modal mínimo + status na sidebar | Modal captures inputs and closes; status badge persists on InspectorSidebar. Less dialog, more discrete. | |

**User's choice:** Radix Dialog modal + SSE stream interno

---

## Absorver pendência Phase 06

### Q1: Phase 07 absorve a UI swap deferida da Phase 06?

| Option | Description | Selected |
|--------|-------------|----------|
| Sim, absorve no Phase 07 | No 06.1 in roadmap; Export button broken today; Phase 07 already touches frontend; SC #1 ("project without API key exports successfully") requires functional Export. | ✓ |
| Cria Phase 06.1 separada | Inserts 06.1 between 06 and 07. Phase 07 stays lean. Adds single-task phase. | |
| Defere p/ v3.1 | Neither 06.1 nor 07 carries. Export button stays broken / hidden. Breaks Phase 07 SC #1. | |

**User's choice:** Sim, absorve no Phase 07
**Notes:** Sub-scope (per D-10): swap Export button to v3 endpoint;
render the 422 envelope (5 stable codes from Phase 06 D-08) in a Radix
modal with PT-BR strings per code; optional dry-run preview link.

---

## Cache research

### Q1: Como cachear resultado de research?

| Option | Description | Selected |
|--------|-------------|----------|
| Tabela SQLite, chave (country, period, provider, model) | Same DB as llm_credentials. v1 design. "Force refresh" bypass. Re-ingestion does NOT invalidate. | ✓ |
| Arquivo JSON em project_dir/ | Per-project cache, no DB schema. Rigid (no cross-project reuse). | |
| Sem cache (cada run fresh) | Always pays LLM cost. Worst UX. | |

**User's choice:** SQLite research_cache table, key
`(country_qid, period_label, provider, model)` SHA-256 hashed

---

## Claude's Discretion

Captured in `07-CONTEXT.md` `<decisions>` § Claude's Discretion. Items 1-10
cover: credential encoding, CLI piggyback path discovery, Anthropic SDK
version, Ollama SDK vs raw httpx, SSE format, migration mechanism, Pydantic
schema field shape, error-code i18n keys, dialog styling, plugin registry
import vs lazy.

## Deferred Ideas

Captured in `07-CONTEXT.md` `<deferred>`. Highlights: OpenAI/Gemini
providers (v3.1), Anthropic OAuth (indefinite), drag-and-drop reassignment,
automatic provider fallback, multi-turn refinement, token usage UI, manual
overlay editing UI, region-key promotion, at-rest credential encryption,
chunked SSE for large outputs.
