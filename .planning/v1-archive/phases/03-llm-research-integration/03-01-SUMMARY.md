---
phase: 03
plan: 01
status: complete
completed_date: 2026-04-21
duration_minutes: 35
tasks_completed: 3
tasks_total: 3
files_created: 8
files_modified: 2
commits:
  - 9566be8: pyproject.toml updated with LLM SDK dependencies + test files scaffolded (RED)
  - 7111138: plan files restored
  - 2d2538e: base.py + schemas.py + __init__.py created (GREEN Task 2)
  - edc1d66: implement run_with_retry + ResearchValidationError
  - cb219e1: implement 4 provider adapters + registry (GREEN)
subsystem: services/llm
tags: [llm, multi-provider, adapter, protocol, pydantic, registry, retry]
key_files:
  created:
    - backend/medieval_forge/services/llm/base.py
    - backend/medieval_forge/services/llm/schemas.py
    - backend/medieval_forge/services/llm/claude.py
    - backend/medieval_forge/services/llm/openai.py
    - backend/medieval_forge/services/llm/gemini.py
    - backend/medieval_forge/services/llm/ollama.py
    - backend/medieval_forge/services/llm/retry.py
    - backend/medieval_forge/services/llm/registry.py
  modified:
    - backend/medieval_forge/services/llm/__init__.py
    - backend/pyproject.toml
decisions:
  - Used google-genai (google.genai) NOT google.generativeai per RESEARCH.md Pitfall 2
  - ClaudeProvider uses tool_use JSON mode (submit_research tool) for structured output
  - OllamaProvider uses format='json' with stream=False (blocking) per test contract
  - All providers receive credentials dict; never log key material (T-3-A2 mitigation)
requirements_closed: [RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-06, RESEARCH-07, RESEARCH-09]
---

# Phase 3 Plan 01: LLM Adapter Layer Summary

**One-liner:** Multi-provider LLM adapter layer with Protocol, 4 adapters (Claude/OpenAI/Gemini/Ollama), Pydantic ResearchResult schema, and 3-retry validation loop.

## Objective

Build the `services/llm/` package: Protocol, registry, Pydantic schemas, four provider adapters, and the shared 3-retry validation loop. This is the foundational technical layer consumed by Phase 3 Plans 02-05.

## What Was Built

| File | Purpose |
|------|---------|
| `base.py` | `LLMProvider` Protocol (`@runtime_checkable`), `AuthMethod` tagged union (ApiKeyAuth/OAuthAuth/CliAuth/NoAuth), `HealthStatus` |
| `schemas.py` | `ResearchResult`, `CondadoAssignment`, `Barony` Pydantic models with `extra="forbid"` mirroring `territory_data_v3.py` |
| `retry.py` | `run_with_retry(provider, prompt, schema, credentials, queue, max_retries=3)` — appends error to prompt on failure, emits SSE progress to queue, raises `ResearchValidationError` after exhaustion |
| `claude.py` | `ClaudeProvider` — `AsyncAnthropic.messages.stream` with `tool_use` JSON mode (`submit_research` tool), model `claude-sonnet-4-6` |
| `openai.py` | `OpenAIProvider` — `AsyncOpenAI.chat.completions.create` with `response_format=json_schema`, `stream=True`, model `gpt-4o` |
| `gemini.py` | `GeminiProvider` — `google.genai.Client().aio.models.generate_content` with `response_mime_type="application/json"`, model `gemini-2.0-flash` |
| `ollama.py` | `OllamaProvider` — `ollama.AsyncClient.chat` with `format="json"`, `stream=False`, model `qwen2.5:7b`, host `http://localhost:11434` |
| `registry.py` | `PROVIDERS: dict[str, LLMProvider]` — 4 entries; new provider = one file + one line here |
| `__init__.py` | Exports `PROVIDERS`, `run_with_retry`, `ResearchValidationError` alongside all Protocol/schema types |

## Test Results

All 16 unit tests passed (16 passed in 15.46s):

- `tests/unit/test_llm_registry.py` — 3 passed (registry contract, Protocol compliance, async methods)
- `tests/unit/test_llm_schemas.py` — 4 passed (valid payload, extra fields rejected, nested rejection, required fields)
- `tests/unit/test_llm_retry.py` — 4 passed (success, error appending, max retries, queue progress)
- `tests/services/test_llm_providers.py` — 5 passed (per-provider mocked SDK tests + health_check)

## Patterns Established for Downstream Plans

**Provider call signature** (consumed by `api/research.py`, Plan 03):
```python
result = await provider.research(prompt, ResearchResult, credentials, queue)
```

**Queue message format** (SSE, mirrors `ingest_runner.py`):
```
data: <message text>\n\n
```

**Extension pattern** (RESEARCH-09):
- Create `backend/medieval_forge/services/llm/mistral.py` with a `MistralProvider` class
- Add `"mistral": MistralProvider()` to `registry.py`
- No other files change

## SDK Shape Deviations from RESEARCH.md

None — all 5 assumptions (A1-A5) held exactly as specified. Mocks matched production call shapes without adjustment.

## Deviations from Plan

None — plan executed exactly as written. The continuation agent resumed from Task 3 (GREEN phase) after retry.py was committed separately; all other implementation proceeded per spec.

## Security Notes (Threat Model)

- **T-3-A1 (mitigated):** `extra="forbid"` on all 3 Pydantic models enforced; retry loop catches `ValidationError` and re-prompts.
- **T-3-A2 (mitigated):** Providers receive `credentials` dict only; no key material logged — providers only emit `provider_id`/model in SSE messages.
- **T-3-A3 (accepted):** SDK default timeouts apply; SSE producer cancellation is Plan 03's responsibility.

## Self-Check: PASSED

All key files verified present and committed:
- `backend/medieval_forge/services/llm/claude.py` — commit cb219e1
- `backend/medieval_forge/services/llm/openai.py` — commit cb219e1
- `backend/medieval_forge/services/llm/gemini.py` — commit cb219e1
- `backend/medieval_forge/services/llm/ollama.py` — commit cb219e1
- `backend/medieval_forge/services/llm/registry.py` — commit cb219e1
- `backend/medieval_forge/services/llm/retry.py` — commit edc1d66
