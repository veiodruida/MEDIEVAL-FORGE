---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 04
subsystem: backend/services/llm
tags: [llm, providers, claude, ollama, auth-chain, registry, sanitize]
requires: [07-01, 07-02, 07-03]
provides:
  - services.llm.ClaudeProvider with D-07 auth chain + BLOCKER 1 401-retry
  - services.llm.OllamaProvider with D-13 defaults + REVIEWS fix #5 available_models
  - services.llm.escape_condado_name prompt-injection guard
  - services.llm.PROVIDERS populated with 2 entries at import time
affects:
  - Plan 07b (research runner) — consumes PROVIDERS + escape_condado_name
  - Plan 09a (frontend ProviderSelector) — consumes Ollama health().available_models
tech-stack:
  added: []
  patterns:
    - "tool_use API for guaranteed JSON from Claude (tool_choice forced)"
    - "format=schema for guaranteed JSON from Ollama"
    - "Import-time registry population (RESEARCH §Pattern 2)"
    - "Provider-level 401-retry with skip_cli (BLOCKER 1)"
key-files:
  created:
    - backend/medieval_forge/services/llm/claude.py
    - backend/medieval_forge/services/llm/ollama.py
    - backend/medieval_forge/services/llm/sanitize.py
    - backend/tests/integration/test_claude_auth_chain.py
    - backend/tests/unit/test_ollama_health.py
    - backend/tests/unit/test_llm_sanitize.py
    - backend/tests/unit/test_llm_registry.py
  modified:
    - backend/medieval_forge/services/llm/__init__.py
decisions:
  - D-07 auth chain (CLI → DB → env → dialog) implemented at provider level via _resolve_key(skip_cli)
  - BLOCKER 1 — 401-retry-with-skip_cli is owned by ClaudeProvider.research(), NOT the runner
  - D-13 default qwen2.5:7b shipped as constant; UI selects from available_models (REVIEWS fix #5)
  - sanitize.escape_condado_name called at CALLER boundary; prompt.py literal-port unchanged
metrics:
  duration_minutes: 18
  tasks_completed: 4
  files_created: 7
  files_modified: 1
  commits:
    - 72bdd90 feat(07-04): add ClaudeProvider with D-07 auth chain + BLOCKER 1 401-retry
    - 8e873a5 feat(07-04): add OllamaProvider with D-13 defaults + REVIEWS fix #5 available_models
    - d0f3666 feat(07-04): add sanitize.escape_condado_name prompt-injection guard
    - b8b864e feat(07-04): wire ClaudeProvider + OllamaProvider into registry at import time
  completed: 2026-05-14
---

# Phase 07 Plan 04: 2-Provider MVP (Claude + Ollama) + Registry Wiring Summary

## One-liner

Lands ClaudeProvider (AsyncAnthropic + tool_use + D-07 auth chain with BLOCKER 1 401-retry-with-skip_cli at provider level) and OllamaProvider (AsyncClient + format=schema + 3s health-check surfacing available_models per REVIEWS fix #5), plus an escape_condado_name prompt-injection guard, and registers both providers at package import so `services.llm.PROVIDERS` returns exactly 2 entries.

## Tasks Completed

| # | Task | Commit | Tests |
|---|------|--------|-------|
| 1 | ClaudeProvider + D-07 auth chain + BLOCKER 1 401-retry | 72bdd90 | 5 integration (@pytest.mark.anthropic) |
| 2 | OllamaProvider + D-13 defaults + available_models | 8e873a5 | 4 unit (health timeout/error/success) |
| 3 | sanitize.escape_condado_name prompt-injection guard | d0f3666 | 5 unit (tags/braces/unicode/empty/idempotence) |
| 4 | Registry wired — PROVIDERS == 2 at import time | b8b864e | 4 unit (size/sorted/get/sanitize-reexport) |

## Verification

```bash
cd backend && python -c "from medieval_forge.services.llm import PROVIDERS, escape_condado_name; assert len(PROVIDERS) == 2; assert set(PROVIDERS) == {'claude','ollama'}; print('ok')"
# -> ok

cd backend && pytest tests/unit/test_ollama_health.py tests/unit/test_llm_registry.py tests/unit/test_llm_sanitize.py -x -q
# -> 13 passed in 0.54s

cd backend && pytest -m anthropic tests/integration/test_claude_auth_chain.py -q
# -> 5 passed in 0.50s
```

Total: **18 tests passing (5 integration + 13 unit)**.

## Threat Mitigations Applied

| Threat ID | Mitigation | Evidence |
|-----------|------------|----------|
| T-07-04-01 | OAuth token expiry epoch-ms check | `expires_at_ms > time.time() * 1000` in `_read_claude_cli_token` |
| T-07-04-02 | No token leak via error message | `raise RuntimeError("No Claude credentials available (CLI/DB/env all empty).")` — no key value |
| T-07-04-04 | Command injection bound | `shell=False` (hardcoded argv `["claude", "auth", "status"]`); grep `shell=True` returns 0 |
| T-07-04-05 | CLI shell-out timeout | `timeout=3.0` on subprocess.run |
| T-07-04-06 | Ollama health-check timeout | `asyncio.wait_for(..., timeout=3.0)` on `/api/tags` |
| T-07-04-07 | Path traversal bound | Credential file paths derived from controlled env vars only |
| T-07-04-08 | No dynamic provider load | Direct class imports in `__init__.py`; no `importlib` |
| T-07-04-09 (BLOCKER 1) | 401-retry-with-skip_cli at provider level | `except anthropic.AuthenticationError` + `_resolve_key(skip_cli=True)` retry block; Test 2 + Test 5 |
| T-07-04-10 (REVIEWS soft Qwen3) | Prompt-injection guard at caller boundary | `escape_condado_name()` strips `</`, `{{`, `}}` |

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met. Test 5 of Task 1 uses `anthropic.AuthenticationError` propagation (`pytest.raises`) instead of a more specific `RuntimeError`, matching the implementation's "re-raise to caller" semantics. The plan's `done` clause says "ultimately raises (no third retry; chain exhausted)" — which the test asserts via `pytest.raises(anthropic.AuthenticationError)`.

## Open Items / Follow-ups for Plan 07b

- Runner MUST call `escape_condado_name` on every condado name BEFORE passing into `build_map_research_prompt` (REVIEWS soft Qwen3 contract).
- Runner MUST surface `Ollama.health()["available_models"]` in the `/api/v3/research/providers` response so the frontend ProviderSelector (Plan 09a) can pick a sensible default from the ordered preference list.
- Runner does NOT implement auth-chain logic for Claude — `ClaudeProvider.research()` owns the 401-retry. The runner just propagates exceptions.

## Self-Check: PASSED

- backend/medieval_forge/services/llm/claude.py — FOUND
- backend/medieval_forge/services/llm/ollama.py — FOUND
- backend/medieval_forge/services/llm/sanitize.py — FOUND
- backend/medieval_forge/services/llm/__init__.py — MODIFIED (register calls added)
- backend/tests/integration/test_claude_auth_chain.py — FOUND
- backend/tests/unit/test_ollama_health.py — FOUND
- backend/tests/unit/test_llm_sanitize.py — FOUND
- backend/tests/unit/test_llm_registry.py — FOUND
- commit 72bdd90 — FOUND
- commit 8e873a5 — FOUND
- commit d0f3666 — FOUND
- commit b8b864e — FOUND
