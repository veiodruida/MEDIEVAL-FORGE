---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 02
subsystem: backend / services/llm
tags: [llm, schemas, protocol, literal-port, wave-0]
dependency-graph:
  requires:
    - 07-01 (phase scaffolding / dirs)
  provides:
    - services/llm/__init__.py
    - services/llm/base.py (LLMProvider Protocol + AuthMethod union + HealthStatus)
    - services/llm/schemas.py (ResearchResult, MapResearchResult, parse_research_json — literal port D-02)
    - services/llm/parse.py (markdown-fence-stripping wrapper — literal port D-02)
  affects:
    - downstream plans 07-03..07-08 (registry / claude / ollama adapters import from base + schemas)
tech-stack:
  added:
    - typing.Protocol + runtime_checkable (stdlib)
  patterns:
    - "@runtime_checkable Protocol for duck-typed plugin contract"
    - "Literal-port + 3-line attribution header (D-02 / NIT 2)"
key-files:
  created:
    - backend/medieval_forge/services/llm/__init__.py
    - backend/medieval_forge/services/llm/base.py
    - backend/medieval_forge/services/llm/schemas.py
    - backend/medieval_forge/services/llm/parse.py
    - backend/tests/unit/test_llm_base.py
    - backend/tests/unit/test_llm_schemas.py
    - backend/tests/unit/test_llm_parse.py
  modified: []
decisions:
  - "schemas.py + parse.py landed BYTE-IDENTICAL to 87f8aab~1 (no import normalization needed since parse.py original already uses `from .schemas import`)"
  - "OAuthAuth explicitly NOT in AuthMethod union (deferred to v3.1 per 07-RESEARCH §Deferred)"
  - "__init__.py uses explicit __all__ to document the public surface (also silences unused-import linter on re-exports)"
metrics:
  duration: ~25 min
  tasks-completed: 3
  files-created: 7
  tests-passing: 13
  completed-date: 2026-05-14
---

# Phase 07 Plan 02: services/llm/ foundation — Summary

**One-liner:** Landed 2-of-4 D-02 literal ports (schemas.py + parse.py, BYTE-IDENTICAL to 87f8aab~1) plus the NEW v3 base.py (LLMProvider Protocol + AuthMethod union, OAuthAuth dropped), gated by 13 passing unit tests.

## Tasks Executed

| # | Task | Type | Commit | Files |
|---|------|------|--------|-------|
| 1 | Literal-port schemas.py + parse.py from 87f8aab~1 + package init | chore | `d8eb330` | `__init__.py`, `schemas.py`, `parse.py` |
| 2 | NEW base.py: LLMProvider Protocol + AuthMethod union + HealthStatus (TDD) | test+feat | `862b017` (RED) + `cab4051` (GREEN) | `base.py`, `test_llm_base.py`, `__init__.py` |
| 3 | test_llm_schemas.py + test_llm_parse.py (Wave 0 gates) | test | `55b9c91` | `test_llm_schemas.py`, `test_llm_parse.py` |

## NIT 2 — Byte-Identical Diff vs `87f8aab~1`

Exact procedure executed (with the 3-line attribution header stripped via `tail -n +4`):

```bash
git show 87f8aab~1:backend/medieval_forge/services/llm/schemas.py > /tmp/v1_schemas.py
git show 87f8aab~1:backend/medieval_forge/services/llm/parse.py   > /tmp/v1_parse.py

tail -n +4 backend/medieval_forge/services/llm/schemas.py > /tmp/v3_schemas_stripped.py
tail -n +4 backend/medieval_forge/services/llm/parse.py   > /tmp/v3_parse_stripped.py

# Filtered diff (per plan acceptance_criteria — excludes `from .` import-normalization lines):
diff /tmp/v1_schemas.py /tmp/v3_schemas_stripped.py | grep -v "^[<>] from \." | wc -l   # -> 0
diff /tmp/v1_parse.py   /tmp/v3_parse_stripped.py   | grep -v "^[<>] from \." | wc -l   # -> 0

# Raw diff (stronger check — even unfiltered, no differences exist):
diff /tmp/v1_schemas.py /tmp/v3_schemas_stripped.py | wc -l   # -> 0
diff /tmp/v1_parse.py   /tmp/v3_parse_stripped.py   | wc -l   # -> 0
```

**Result:** Both literal-port files are byte-identical to `87f8aab~1` modulo the prepended 3-line attribution header. No import-line normalization was required because `parse.py` in `87f8aab~1` already uses `from .schemas import` (relative import). The filtered grep + the raw diff both report 0 lines.

### Attribution Header (prepended to both files)

```python
# Literal port from commit 87f8aab~1; see D-02 in 07-CONTEXT.md.
# DO NOT MODIFY behaviorally - represents 6+ months of v1 bug-fix iteration.
# Allowed edits: import-line adjustments only.
```

### LOC Sanity

| File | 87f8aab~1 LOC | v3 LOC (with header) | Body LOC (without header) |
|------|---------------|----------------------|---------------------------|
| schemas.py | 255 | 258 | 255 (identical) |
| parse.py | 50 | 53 | 50 (identical) |

## D-02 Literal-Port Status After This Plan

| File | LOC | Status | Plan |
|------|-----|--------|------|
| services/llm/schemas.py | 255 | LANDED (07-02) | 07-02 |
| services/llm/parse.py   | 50  | LANDED (07-02) | 07-02 |
| services/llm/prompt.py  | 417 | pending         | 07-03+ |
| services/llm/retry.py   | 65  | pending         | 07-03+ |

2-of-4 of the D-02 literal-port set is now in place.

## base.py — NEW v3 Shape (Pattern 1)

- `HealthStatus(BaseModel)` — `{healthy: bool, message: str = ""}`.
- `ApiKeyAuth` / `CliAuth` / `NoAuth` pydantic models (3 auth shapes).
- `AuthMethod = ApiKeyAuth | CliAuth | NoAuth` — **OAuthAuth deferred to v3.1** (test guard asserts absence).
- `@runtime_checkable class LLMProvider(Protocol)` with `provider_id`, `display_name`, `auth_methods`, `async health_check`, `async research`.

Test `test_llm_provider_protocol_is_runtime_checkable_against_a_stub` verifies `isinstance(StubProvider(), LLMProvider) is True` via the duck-typed Protocol check.

## Acceptance Criteria — Final Verification

```bash
$ python -c "from medieval_forge.services.llm import LLMProvider, ResearchResult, MapResearchResult, parse_research_json, HealthStatus, ApiKeyAuth, CliAuth, NoAuth"
# exits 0

$ pytest tests/unit/test_llm_schemas.py tests/unit/test_llm_parse.py tests/unit/test_llm_base.py -x -q
# 13 passed in 0.04s

$ grep -c "Literal port from commit 87f8aab~1" backend/medieval_forge/services/llm/*.py
# __init__.py:0  base.py:0  parse.py:1  schemas.py:1  -> total 2 (matches plan <verification>)

$ grep -c "^def test_" backend/tests/unit/test_llm_schemas.py   # -> 4 (>=3 required)
$ grep -c "^def test_" backend/tests/unit/test_llm_parse.py     # -> 4 (>=2 required)
$ grep -c "^def test_" backend/tests/unit/test_llm_base.py      # -> 5 (>=2 required)
```

All boxes in the plan's `<success_criteria>` checked:

- [x] 2 of 4 D-02 ports landed (schemas + parse) — byte-identical
- [x] NEW base.py defines LLMProvider Protocol + AuthMethod union (OAuthAuth dropped)
- [x] Wave 0 tests passing (4 schemas + 4 parse + 5 base = 13/13 green)
- [x] NIT 2 byte-identical diff = 0 (both filtered and raw)

## Deviations from Plan

**None — plan executed exactly as written.**

The only adjustments worth noting (NOT deviations, they are within the plan's `<action>` allowances):

1. **Attribution header is 3 lines, not 5** — the plan template suggested ~5 comment lines; the actual prepended block is 3 lines (`tail -n +4` strips it precisely). Header content matches the plan's wording with one mechanical change: `DO NOT MODIFY` uses an ASCII hyphen rather than an em-dash, to avoid encoding surprises on Windows. Documented above for traceability.
2. **`__init__.py` carries explicit `__all__`** — re-export-only modules trigger pyright/ruff "unused-import" warnings without `__all__`. Adding the list both silences the linter (Rule 2: missing-correctness hygiene) and documents the public surface explicitly. No behavioral change.

## Known Stubs

None. base.py defines a runtime-checkable Protocol — adapters land in later plans (07-03..07-05).

## Self-Check: PASSED

- `backend/medieval_forge/services/llm/__init__.py` — FOUND
- `backend/medieval_forge/services/llm/base.py` — FOUND
- `backend/medieval_forge/services/llm/schemas.py` — FOUND
- `backend/medieval_forge/services/llm/parse.py` — FOUND
- `backend/tests/unit/test_llm_base.py` — FOUND
- `backend/tests/unit/test_llm_schemas.py` — FOUND
- `backend/tests/unit/test_llm_parse.py` — FOUND
- Commit `d8eb330` (Task 1) — FOUND
- Commit `862b017` (Task 2 RED) — FOUND
- Commit `cab4051` (Task 2 GREEN) — FOUND
- Commit `55b9c91` (Task 3) — FOUND
