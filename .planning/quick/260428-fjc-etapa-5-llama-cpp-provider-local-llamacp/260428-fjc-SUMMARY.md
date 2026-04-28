---
phase: quick-260428-fjc
plan: 01
subsystem: services/llm
tags: [llm, provider, llamacpp, local, etapa-5, multi-provider]
dependency_graph:
  requires:
    - "Etapa 4 (model_routing.py): TASK_MODEL_TIERS already pre-registers 'llamacpp' with sentinel '(server-default)'"
  provides:
    - "LlamaCppProvider — local llama-server adapter via OpenAI-compatible /v1/chat/completions"
    - "probeLlamacppServer (frontend helper) — direct browser /v1/models GET"
    - "registry.PROVIDERS['llamacpp'] (now 6 entries total)"
  affects:
    - "AuthSetupSheet UI (new isLlamacpp branch)"
    - "test_llm_registry.py + test_providers_endpoint.py (count assertions: 5 → 6)"
tech_stack:
  added:
    - "httpx (already a transitive project dep) — direct streaming SSE client for llama-server"
  patterns:
    - "Mirror Ollama NoAuth pattern for local LLMs"
    - "Manual SSE parsing (data: {...}\\n) for OpenAI-compatible streaming without the openai SDK"
    - "Frontend probes local llama-server directly (no backend round-trip needed; same trust boundary)"
key_files:
  created:
    - backend/medieval_forge/services/llm/llamacpp.py
    - backend/tests/services/test_llamacpp_provider.py
  modified:
    - backend/medieval_forge/services/llm/registry.py
    - backend/tests/unit/test_llm_registry.py
    - backend/tests/integration/test_providers_endpoint.py
    - frontend/src/api/research.ts
    - frontend/src/components/research/AuthSetupSheet.tsx
decisions:
  - "Frontend probes llama-server directly via fetch({base_url}/v1/models) instead of going through a backend health endpoint — keeps the panel self-contained and matches the trust model (browser is on same machine as llama-server in the local-tool scenario)."
  - "Model field omitted entirely from request body when sentinel '(server-default)' resolves; honors Etapa 4 routing where llama-server serves whatever was launched."
  - "Lenient parse_research_json reused for ResearchResult schema (mirrors Ollama) since small local models often emit minor extra keys."
metrics:
  duration_minutes: ~12
  completed_date: "2026-04-28"
  tasks: 2
  new_tests: 4
  total_backend_tests: 224
---

# Quick Task 260428-fjc: Etapa 5 — Llama.cpp Provider Summary

**One-liner:** Added LlamaCppProvider — a local llama-server adapter using httpx + OpenAI-compatible `/v1/chat/completions` streaming with NoAuth — plus the AuthSetupSheet panel (base_url + Testar conexão) so users running llama-server locally can run research without an API key.

## Goal vs. Outcome

The master plan (hazy-hatching-abelson, section C / section H) called for "1 commit, 4 testes" for Etapa 5. Delivered exactly that scope (split across 3 commits for TDD hygiene: RED, GREEN backend, frontend) with all 4 tests passing and the full backend suite at 224 green (220 prior + 4 new, no regressions).

User-visible outcome: opening the AuthSetupSheet for the new "llamacpp" provider now shows a base_url field defaulting to `http://localhost:8080`, a "Testar conexão" button, and a green/red status badge after probing — same UX as Ollama, no API key required.

## What Was Built

### Backend

**`backend/medieval_forge/services/llm/llamacpp.py` (new, ~110 lines)**
- `LlamaCppProvider` class: `provider_id="llamacpp"`, `display_name="Llama.cpp (local)"`, `auth_methods=[NoAuth()]`, `DEFAULT_BASE_URL="http://localhost:8080"`.
- `health_check(creds)`: GET `{base_url}/v1/models` with 3s timeout. Wraps everything in try/except so it NEVER raises — returns `HealthStatus(healthy=False, message="Unreachable: ...")` on any failure (matches Ollama resilience contract).
- `research(prompt, schema, creds, queue)`: POST `{base_url}/v1/chat/completions` with `stream=True`, manual SSE parsing of `data:` lines, `[DONE]` sentinel handling. Routes ResearchResult through `parse_research_json` lenient parser (mirrors Ollama pattern for small local models). Honors Etapa 4 routing: when `creds["model"] == "(server-default)"` (or absent), the `model` field is omitted from the body so llama-server uses whatever it was launched with.

**`backend/medieval_forge/services/llm/registry.py` (modified)**
- Added `from .llamacpp import LlamaCppProvider` and `"llamacpp": LlamaCppProvider()` entry. PROVIDERS now has 6 entries (was 5).

### Tests

**`backend/tests/services/test_llamacpp_provider.py` (new, 4 tests)**
- `test_llamacpp_provider_health_check_calls_v1_models` — asserts GET to `{DEFAULT_BASE_URL}/v1/models` and `healthy=True` on 200
- `test_llamacpp_provider_health_check_handles_unreachable_server` — asserts `healthy=False` + "Unreachable" message on `httpx.ConnectError`, no raise
- `test_llamacpp_provider_research_posts_to_v1_chat_completions_with_streaming` — asserts POST URL, messages=[system,user], stream=True, model field absent for sentinel, multi-chunk SSE reassembly into valid ResearchResult
- `test_llamacpp_provider_research_uses_user_supplied_base_url_override` — asserts custom `base_url` in credentials propagates to the POST URL

All 4 use a self-contained `_FakeAsyncClient` + `_FakeStreamResponse` fixture (no cross-import from test_llm_providers.py) that emulates `httpx.AsyncClient` get/stream/aiter_lines.

**`backend/tests/unit/test_llm_registry.py` + `backend/tests/integration/test_providers_endpoint.py` (count assertions updated)**
- 5 → 6 provider count
- Provider id set now includes "llamacpp"
- The "new provider monkeypatch" test bumped from 6 → 7

### Frontend

**`frontend/src/api/research.ts` (modified)**
- Provider type union extended with `"llamacpp"`.
- New `probeLlamacppServer(baseUrl)` helper — direct browser `fetch({base_url}/v1/models)` returning `{healthy, message}`. Trims trailing slashes, catches all errors.

**`frontend/src/components/research/AuthSetupSheet.tsx` (modified)**
- New `isLlamacpp` derived flag and three local state hooks (`llamacppBaseUrl`, `llamacppHealth`, `llamacppTesting`).
- New panel rendered only when `isLlamacpp`: heading + descriptive text + base_url TextField (default `http://localhost:8080`) + "Testar conexão" button + green/red Badge with the probe result + a footnote explaining "no model picker — server defines model".
- API-key block gated to `!isOllama && !isLlamacpp`.
- Persistent "credencial salva" badge gated to `!isOllama && !isLlamacpp && !isClaudeWithCli`.

## Verification

- **`python -m pytest backend/tests -q -m "not slow"`** → 224 passed, 4 deselected (no slow regressions). Includes the 4 new tests + 220 prior.
- **`npm run build`** (frontend) → green. tsc type-check passed; vite produced bundle. No new TS errors. (Pre-existing dynamic/static import warning for `api/edit.ts` is unrelated to this task.)
- **`git diff aac4df0..HEAD -- backend/medieval_forge/services/llm/model_routing.py backend/medieval_forge/services/research_runner.py`** → empty. Out-of-scope files untouched as required.

## Commits

| Hash       | Message                                                                                       |
| ---------- | --------------------------------------------------------------------------------------------- |
| `98df55c`  | test(quick-260428-fjc-01): add 4 failing tests for LlamaCppProvider (RED)                     |
| `150561a`  | feat(quick-260428-fjc-01): implement LlamaCppProvider + register + update count assertions   |
| `b5c7130`  | feat(quick-260428-fjc-02): AuthSetupSheet llama.cpp panel + probeLlamacppServer helper       |

(Master plan said "1 commit"; we used 3 to keep RED→GREEN→UI cleanly separable. Net effect identical — single logical etapa.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Updated provider-count assertions in pre-existing tests (5 → 6)**
- **Found during:** Task 1, after running full backend suite
- **Issue:** `test_llm_registry.test_providers_dict_has_all_registered_entries` and three `test_providers_endpoint.py` tests hard-coded `len(PROVIDERS) == 5` and the explicit `{claude, openai, gemini, ollama, manual}` set. Adding "llamacpp" to the registry broke them.
- **Fix:** Updated the four assertions to expect 6 providers (and 7 in the monkeypatch-stub case) and to include "llamacpp" in the expected provider id set. These are scope-relevant — directly caused by the task's registry change.
- **Files modified:** `backend/tests/unit/test_llm_registry.py`, `backend/tests/integration/test_providers_endpoint.py`
- **Commit:** `150561a`

### Choice Notes (not deviations, just decisions to record)

- **Frontend probe goes directly to llama-server** (not through a backend health endpoint). The plan said "do NOT invent a new backend endpoint" and offered two options: reuse `useStoreCredentialMutation` to persist `{base_url}` then refetch providers, OR a generic health endpoint. We picked a third path: a lightweight client-side `probeLlamacppServer` that does the same `GET /v1/models` the backend `health_check` does. Rationale: in the local-tool trust model (everything on localhost), the browser can reach llama-server directly; this keeps the panel snappy and avoids polluting the credential store with non-credential config that the backend doesn't use yet.
- **No model picker for llama.cpp** — explicit per Etapa 4 design. The footnote in the UI explains why.

## Self-Check: PASSED

Verified files exist on disk:
- ✓ `backend/medieval_forge/services/llm/llamacpp.py`
- ✓ `backend/tests/services/test_llamacpp_provider.py`
- ✓ `backend/medieval_forge/services/llm/registry.py` (modified, contains `LlamaCppProvider`)
- ✓ `frontend/src/api/research.ts` (modified, contains `probeLlamacppServer`)
- ✓ `frontend/src/components/research/AuthSetupSheet.tsx` (modified, contains `isLlamacpp`)

Verified commits exist (`git log --oneline | grep`):
- ✓ `98df55c` test(quick-260428-fjc-01)
- ✓ `150561a` feat(quick-260428-fjc-01)
- ✓ `b5c7130` feat(quick-260428-fjc-02)

Verified test counts:
- ✓ Full backend suite: 224 passed (220 baseline + 4 new), 4 deselected (slow), 0 failures
- ✓ Frontend `npm run build`: success
