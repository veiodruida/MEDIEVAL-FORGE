---
quick_id: 260428-l0l
phase: quick
plan: l0l
subsystem: backend/codex-pipeline
tags: [codex, llm, schema, sse, alembic]
type: execute
mode: quick
wave: 1
depends_on: []
status: complete
date: 2026-04-28
master_plan: C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md
master_etapa: 9 (Codex schema + runner + endpoint)
next_etapa: 10 (Codex viewer frontend — tabs por categoria, render markdown)
---

# Quick 260428-l0l — Etapa 9: Codex Schema + Runner + Endpoint

## One-liner

Codex narrative pipeline: 12-category Pydantic schema (`CodexResult`), cache-aware async runner mirroring `run_research`, SSE + cached + prompt endpoints under `/api/projects/{id}/codex`, plus Alembic 0003 creating `codex_cache`.

## Files Changed

### Created (8)

| File | Lines |
|------|-------|
| `backend/medieval_forge/services/codex_cache.py` | 80 |
| `backend/medieval_forge/services/codex_runner.py` | 152 |
| `backend/medieval_forge/api/codex.py` | 169 |
| `alembic/versions/0003_create_codex_cache.py` | 31 |
| `backend/tests/services/test_codex_schema.py` | 113 |
| `backend/tests/services/test_codex_prompt.py` | 75 |
| `backend/tests/services/test_codex_runner.py` | 294 |
| `backend/tests/api/test_codex_endpoints.py` | 184 |

### Modified (3)

| File | Change |
|------|--------|
| `backend/medieval_forge/services/llm/schemas.py` | +`CodexEntity`, `CodexCategory`, 12 category subclasses, `CodexResult` (≈100 lines) |
| `backend/medieval_forge/services/llm/prompt.py` | +`SYSTEM_INSTRUCTIONS_CODEX`, `EXAMPLE_OUTPUT_CODEX`, `RULES_CODEX`, `build_codex_prompt` (≈170 lines) |
| `backend/medieval_forge/models.py` | +`CodexCache` ORM (19 lines) |
| `backend/medieval_forge/main.py` | +`codex_router` import + `include_router(codex_router, prefix="/api")` |

## Test Count Delta

| Task | RED | Suite after GREEN |
|------|-----|-------------------|
| Task 1 (schema + prompt) | 8 failing | 250 → 258 (+8) |
| Task 2 (codex_runner) | 5 failing | 258 → 263 (+5) |
| Task 3 (endpoints) | 4 failing | 263 → 267 (+4) |
| **Total** | **17 new** | **250 → 267 (+17)** |

(Master plan estimated ~12; the +5 overrun is the descriptive split per memory feedback — 5 schema + 3 prompt + 5 runner + 4 endpoint.)

Frontend suite untouched: 191/191 (no frontend changes this etapa, verified by inspection — only backend files modified).

## Commit Hashes

| # | Type | Hash | Message |
|---|------|------|---------|
| 1 | RED  | `5cabf3d` | test(quick-260428-l0l-01): add 8 failing tests for CodexResult schema + build_codex_prompt |
| 2 | GREEN | `7675c1c` | feat(quick-260428-l0l-01): CodexResult schema + build_codex_prompt + CodexCache model + 0003 migration |
| 3 | RED  | `e306d23` | test(quick-260428-l0l-02): add 5 failing tests for codex_runner SSE producer |
| 4 | GREEN | `4bf44dd` | feat(quick-260428-l0l-02): codex_runner.run_codex with cache + retry + SSE |
| 5 | RED  | `dd884cc` | test(quick-260428-l0l-03): add 4 failing tests for /codex endpoints |
| 6 | GREEN | `87b2f3f` | feat(quick-260428-l0l-03): /codex SSE + cached + prompt endpoints; wire router |

## Alembic Verification

```
$ alembic heads
0003 (head)
```

Migration `0003_create_codex_cache.py` applies cleanly on top of `0002` and is the active head. The 0003 migration mirrors the `models.py::CodexCache` shape one-to-one (PK `cache_key_hash`, JSON `payload`, +nullable `focus_sections`).

## Schema Notes

- `CodexResult` is composed of 12 distinct subclasses of `CodexCategory` (`CodexCurrency`, `CodexAttributes`, …, `CodexEvents`) instead of plain aliases. Pydantic v2 still treats them as separate types so error messages reference the precise category name. All inherit `model_config = ConfigDict(extra="forbid")` from `CodexCategory`, enforcing the "no unknown keys" contract requested in the master plan.
- `CodexEntity` requires `id`, `name`, `description` (markdown). `description` is a free-form string so the LLM can emit `**bold**`, `_italics_`, lists, etc.
- `compute_codex_cache_key` formula: `SHA-256("{country_qid}:{period_start}:{period_end}:{provider}:{model}:codex:{focus_csv}")`. The literal `:codex:` segment makes Codex keys disjoint from Research keys even when other components match.

## Runner Notes

- `run_codex` defaults `task_type="codex_genealogy"`, which routes via `model_routing.resolve_model` → high-effort tier (Claude Opus 4.7, GPT-4-turbo, Gemini 2.5 Pro, qwen2.5:32b). Callers pass `effort_override` when they need a cheaper run.
- `_ValidatingWrapper` from `research_runner` is intentionally NOT reused — Etapa 9 has no cross-ref validator yet (Etapa 10+ may add references like "marriage points to existing person"). `extra='forbid'` is the only validation, applied automatically by `run_with_retry`.
- Pitfall 6 honored: every code path (unknown provider, missing project, model-routing failure, validation retry exhaustion, RuntimeError mid-research) lands in the `finally` block which puts `None` on the queue.

## Endpoints Wired

| Verb | Path | Behavior |
|------|------|----------|
| POST | `/api/projects/{id}/codex` | StreamingResponse SSE (text/event-stream); query: `provider`, `force_refresh`, `focus` (csv) |
| GET  | `/api/projects/{id}/codex/cached` | JSON payload or 404; query: `provider`, `model?`, `focus?` |
| GET  | `/api/projects/{id}/codex/prompt` | JSON `{"prompt": "..."}` for the manual paste flow |

`main.py` includes `codex_router` directly after `research_router` (consistent with the master plan's "Codex parallels Research" architecture).

## Deviations from Plan

### Auto-fixed

**1. [Rule 3 — Blocking] Provided `app.state.credentials` in endpoint test fixture**

- **Found during:** Task 3 RED → GREEN transition.
- **Issue:** `resolve_credentials("claude", app_state)` returns `None` when `app_state.credentials` is missing, which would cause the SSE stream to emit `ERROR: no credentials for claude` instead of the happy-path RESULT/DONE chunks the test expects.
- **Fix:** The `async_client` fixture now sets `app.state.credentials = {"claude": {"api_key": "test-key"}}` before yielding. Mirrors the pattern in `test_codex_runner.py`'s `_AppState` stub.
- **Files modified:** `backend/tests/api/test_codex_endpoints.py` (added one line in the fixture before the AsyncClient context manager).
- **Commit:** `dd884cc` (RED) — fixture was correct from the first commit.

No plan-architecture changes required.

## Self-Check

- `backend/medieval_forge/services/llm/schemas.py` — FOUND (CodexResult class present)
- `backend/medieval_forge/services/llm/prompt.py` — FOUND (build_codex_prompt present)
- `backend/medieval_forge/models.py` — FOUND (CodexCache class present)
- `backend/medieval_forge/services/codex_cache.py` — FOUND
- `backend/medieval_forge/services/codex_runner.py` — FOUND
- `backend/medieval_forge/api/codex.py` — FOUND
- `alembic/versions/0003_create_codex_cache.py` — FOUND, head=0003
- `backend/medieval_forge/main.py` — FOUND (codex_router include present)
- 6 commits — FOUND: 5cabf3d, 7675c1c, e306d23, 4bf44dd, dd884cc, 87b2f3f
- Backend pytest 267/267 passing
- Alembic head = 0003

## Self-Check: PASSED

## Pointer

- **Master plan:** `C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md` § Etapa 9
- **Next etapa:** 10 — Codex viewer frontend (tabs por categoria, render markdown via react-markdown)
