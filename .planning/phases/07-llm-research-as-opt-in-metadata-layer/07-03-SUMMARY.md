---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 03
subsystem: services/llm
tags: [llm, retry, prompt, registry, literal-port, D-02, D-05, pitfall-9]
requires:
  - 07-02 (services/llm/base.py + schemas.py + parse.py)
provides:
  - run_with_retry (3-retry validation loop with PT-BR progress)
  - build_map_research_prompt (LITERAL PORT, 417 LOC)
  - PROVIDERS registry skeleton (deferred-population)
  - ResearchValidationError exception type
affects:
  - 07-04 (claude.py + ollama.py will call register())
  - 07-07b (v3 runner consumes run_with_retry + queue events)
  - 07-09a (useResearchStream dual-shape decision — see WARNING 3 verdict below)
tech-stack:
  added: []
  patterns:
    - "Import-time plugin registration (RESEARCH §Pattern 2)"
    - "Self-correcting LLM retry loop with error-in-prompt feedback"
key-files:
  created:
    - backend/medieval_forge/services/llm/retry.py
    - backend/medieval_forge/services/llm/prompt.py
    - backend/medieval_forge/services/llm/registry.py
    - backend/tests/unit/test_llm_retry.py
  modified:
    - backend/medieval_forge/services/llm/__init__.py
decisions:
  - "D-02 literal-port preserved verbatim with 2-line attribution header on retry.py + prompt.py"
  - "WARNING 3 verdict (a): retry.py writes to asyncio.Queue → dual-shape SSE tolerance in Plan 09a JUSTIFIED"
  - "Registry deferred-population: PROVIDERS == {} at Plan 03 end; Plan 04 fills both slots"
  - "Pitfall 9: PT-BR 'Tentativa N/M' progress strings kept verbatim (not translated)"
metrics:
  duration_minutes: ~15
  completed: 2026-05-14
  tasks: 3
  files: 5
  commits: 3
---

# Phase 07 Plan 03: services/llm retry + prompt + registry Summary

One-liner: literal-ported v1 `retry.py` (65 LOC) + `prompt.py` (417 LOC) with attribution
headers, added deferred-population `registry.py` skeleton, and landed Wave 0
`test_llm_retry.py` (3 async cases). WARNING 3 emission verdict resolved to **(a)**.

## Tasks Completed

| # | Name                                                     | Commit    | Files                                                                                                                 |
| - | -------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------- |
| 1 | Literal-port retry.py + prompt.py + WARNING 3 verdict    | `f4da0b6` | `services/llm/retry.py`, `services/llm/prompt.py`, `services/llm/__init__.py`                                         |
| 2 | Wave 0 test_llm_retry.py (3 cases)                       | `fb879ab` | `backend/tests/unit/test_llm_retry.py`                                                                                |
| 3 | registry.py skeleton with deferred-population PROVIDERS  | `a788827` | `services/llm/registry.py`, `services/llm/__init__.py`                                                                |

## Verification Results

- `python -c "from medieval_forge.services.llm import LLMProvider, PROVIDERS, register, get, list_providers, ResearchResult, MapResearchResult, parse_research_json, run_with_retry, build_map_research_prompt"` → exits 0 (full export surface importable).
- `pytest tests/unit/test_llm_retry.py tests/unit/test_llm_schemas.py tests/unit/test_llm_parse.py tests/unit/test_llm_base.py -x -q` → **16 passed in 0.06s**.
- `grep -c "Literal port from commit 87f8aab~1" services/llm/{retry,prompt,schemas,parse}.py` → 1 match each (4 total).
- `wc -l services/llm/retry.py` → 67 lines (65 body + 2 attribution); `prompt.py` → 419 lines (417 body + 2 attribution).
- `grep -n "Tentativa" services/llm/retry.py` → line 57 (Pitfall 9 PT-BR preserved).
- `grep -n "def build_map_research_prompt" services/llm/prompt.py` → line 171.
- `python -c "from medieval_forge.services.llm import PROVIDERS, register, get, list_providers; assert PROVIDERS == {}; assert list_providers() == []"` → exits 0.

## WARNING 3 — retry.py emission verdict

**Verdict: (a) — retry.py writes to queue.** Dual-shape SSE tolerance in Plan 09a's
`useResearchStream` is **JUSTIFIED**. Keep the dual-shape parser.

Grep evidence (run against the literal-ported file at HEAD):

```
$ grep -nE "yield|queue\.put|event_emit|send|asyncio\.Queue|\.write\(" backend/medieval_forge/services/llm/retry.py
33:    queue: asyncio.Queue[str | None] | None = None,
57:                await queue.put(
```

Line 57 calls `await queue.put(f"data: Tentativa {attempt}/{max_retries}: ...")` —
this is a **raw SSE-frame string** emitted directly to the stream (note the
`data: ` prefix and `\n\n` terminator). It is NOT a structured envelope. The v3
runner (Plan 07b) will additionally emit structured `event_type: "retry"` envelopes
on top of, not instead of, these raw frames.

**Consequence for Plan 09a:** `useResearchStream` MUST accept both shapes:
1. Raw `data: ...` SSE frames (legacy v1 path, emitted by retry.py directly).
2. Structured `{event_type, ...}` JSON envelopes (new v3 path, emitted by the runner).

The dual-shape parser stays as currently designed. Plan 09a executor: do not
simplify away the legacy branch.

## Deviations from Plan

None — plan executed exactly as written. Three tasks, three atomic commits, no
Rule 1/2/3 auto-fixes, no Rule 4 architectural escalations, no auth gates.

## Pitfall 9 Compliance

retry.py emits PT-BR `"Tentativa {attempt}/{max_retries}: {last_error}"` strings —
left UNTRANSLATED per Pitfall 9 (these strings are what the v1 UI surfaces to the
Game Designer; touching them breaks visual parity). Test 3 in `test_llm_retry.py`
explicitly asserts `"Tentativa 1/3"` appears on the queue.

## Threat Flags

None — all surfaces introduced are internal to services/llm and the threat model
(T-07-03-01..04) is already mitigated by the literal port itself (3-retry hard
cap, deferred PROVIDERS population).

## Self-Check: PASSED

- FOUND: `backend/medieval_forge/services/llm/retry.py`
- FOUND: `backend/medieval_forge/services/llm/prompt.py`
- FOUND: `backend/medieval_forge/services/llm/registry.py`
- FOUND: `backend/tests/unit/test_llm_retry.py`
- FOUND commit: `f4da0b6` (chore(07-03): literal-port retry.py + prompt.py)
- FOUND commit: `fb879ab` (test(07-03): Wave 0 test_llm_retry.py)
- FOUND commit: `a788827` (feat(07-03): registry.py skeleton)
