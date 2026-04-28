---
phase: quick-260428-f9x
plan: 01
subsystem: backend/llm
tags: [llm, routing, etapa-4, hazy-hatching-abelson]
requires:
  - quick-260428-ewx (Etapa 3 — schemas split)
provides:
  - medieval_forge.services.llm.model_routing.resolve_model
  - medieval_forge.services.llm.model_routing.TASK_MODEL_TIERS
  - medieval_forge.services.llm.model_routing.TASK_DEFAULT_EFFORT
  - run_research(task_type=..., effort_override=...) optional routing
affects:
  - backend/medieval_forge/services/research_runner.py
tech_stack:
  added: []
  patterns:
    - "Static-table routing: provider × effort → model_id"
    - "Sentinel '(server-default)' for self-hosted llamacpp"
    - "Additive kwargs at end of signature for backward-compat"
key_files:
  created:
    - backend/medieval_forge/services/llm/model_routing.py
    - backend/tests/unit/test_llm_routing.py
  modified:
    - backend/medieval_forge/services/research_runner.py
decisions:
  - Routing layer is a pure-function module with module-level constants (no class, no state)
  - ValueError (not KeyError) for unknown provider/task/effort — clearer message contract
  - llamacpp uses a sentinel string rather than None so callers can log/cache uniformly
  - task_type/effort_override added at END of run_research signature; legacy callers untouched
metrics:
  duration: ~10 min
  completed: 2026-04-28
  tasks: 2
  commits:
    - af691f0 feat(quick-260428-f9x-01): add model_routing module + 4 unit tests
    - 883f5eb feat(quick-260428-f9x-02): integrate resolve_model into research_runner
---

# Quick Task 260428-f9x: Etapa 4 — Model Routing Multi-Modelo Summary

**One-liner:** Adds a (provider, task, effort) → model_id routing layer with per-task default effort tiers, integrated additively into `research_runner` so any future caller (codex_runner, UI effort picker, llamacpp) can route freely without touching the legacy default-model path.

## What was built

### Task 1 — `model_routing.py` + tests (TDD)

- **`backend/medieval_forge/services/llm/model_routing.py`** (new, ~75 lines):
  - `TASK_MODEL_TIERS` — 5 providers (claude/openai/gemini/ollama/llamacpp) × 3 effort tiers (low/medium/high). Values copied verbatim from master plan B.1.
  - `TASK_DEFAULT_EFFORT` — 8 known tasks mapped to their default effort tier (validate_barony_assignments=low, map_research_full=high, codex_genealogy=high, codex_population_economy=low, etc.). From master plan B.2.
  - `resolve_model(provider_id, task, effort_override=None) -> str` — pure function. `effort_override` wins over the task default. Unknown provider/task/effort raise `ValueError` with the offending value embedded in the message.
- **`backend/tests/unit/test_llm_routing.py`** (new, 4 tests, ~70 lines) — descriptive names per project convention:
  - `test_task_default_effort_resolves_correct_model_for_claude_provider_when_no_override`
  - `test_user_override_effort_takes_precedence_over_task_default_effort`
  - `test_llamacpp_provider_returns_server_default_marker_for_any_effort_tier`
  - `test_resolve_model_raises_clear_error_for_unknown_provider_id`

Commit: `af691f0`

### Task 2 — `research_runner.py` integration

- Added import: `from .llm.model_routing import resolve_model`.
- Extended `run_research` signature ADDITIVELY with two optional kwargs at the end: `task_type: str | None = None`, `effort_override: str | None = None`.
- After the existing ollama-override block, added a guarded routing block: when `task_type is not None`, `model = resolve_model(provider_id, task_type, effort_override)`; `ValueError` is surfaced as an SSE `data: ERROR: ...` line and the function returns cleanly (sentinel still emitted in `finally`).
- When `task_type is None`, the legacy `PROVIDER_DEFAULT_MODEL` path is unchanged — every existing caller (and all 216 prior tests) keeps the previous behavior bit-for-bit.
- Updated docstring to describe the new optional params.

Commit: `883f5eb`

## Test counts

| Run | Result |
| --- | --- |
| Before Task 1 (baseline) | 216 passed |
| `tests/unit/test_llm_routing.py` after GREEN | 4 passed |
| Full suite after Task 1 | 220 passed (216 + 4) |
| Full suite after Task 2 | 220 passed — zero regressions |

Command used: `python -m pytest backend/tests -q -m "not slow"`.

## Confirmation: legacy paths untouched

- `PROVIDER_DEFAULT_MODEL` dict still exists and is still consulted on every call.
- Ollama session-credentials override still applies before the new routing block.
- Cache key (`compute_cache_key`) still receives whatever `model` was resolved — no change to cache schema.
- All 216 pre-existing tests continue to pass without modification.
- New `task_type` / `effort_override` kwargs default to `None`, so positional and keyword callers in the existing codebase compile and behave identically.

## Smoke checks

```
$ python -c "from medieval_forge.services.llm.model_routing import resolve_model; print(resolve_model('claude', 'map_research_full'))"
claude-opus-4-7

$ python -c "from medieval_forge.services.llm.model_routing import resolve_model; print(resolve_model('llamacpp', 'codex_genealogy', 'low'))"
(server-default)
```

Both match plan `<verification>` expectations.

## Deviations from plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were needed.

## Self-Check: PASSED

- Created `backend/medieval_forge/services/llm/model_routing.py` — FOUND
- Created `backend/tests/unit/test_llm_routing.py` — FOUND
- Modified `backend/medieval_forge/services/research_runner.py` — FOUND (in HEAD)
- Commit `af691f0` (Task 1) — FOUND in `git log`
- Commit `883f5eb` (Task 2) — FOUND in `git log`
- Full suite reports 220 passed, 0 failed
