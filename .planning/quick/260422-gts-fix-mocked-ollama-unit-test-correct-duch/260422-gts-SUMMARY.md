---
phase: quick-260422-gts
plan: 01
subsystem: backend/tests
tags: [test, llm, ollama, fix]
dependency_graph:
  requires: []
  provides: [passing LLM provider unit tests]
  affects: [backend/tests/services/test_llm_providers.py]
tech_stack:
  added: []
  patterns: [mocked async client, grammar-constrained format assertion]
key_files:
  modified:
    - backend/tests/services/test_llm_providers.py
decisions:
  - Gemini test assertion corrected to assert response_schema is None — production intentionally omits it due to Gemini API rejecting additionalProperties from Pydantic dict fields
metrics:
  duration: 10m
  completed: "2026-04-22"
  tasks_completed: 2
  files_modified: 1
---

# Quick Task 260422-gts: Fix Mocked Ollama Unit Test + Correct Duchy Shape Summary

**One-liner:** Fixed _VALID_PAYLOAD duchies dict shape (list -> Duchy model) and updated Ollama format assertion from `"json"` string to grammar-constrained schema dict check.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix _VALID_PAYLOAD duchies shape | 81353e0 | backend/tests/services/test_llm_providers.py |
| 2 | Update Ollama format assertion to grammar-constrained schema | 81353e0 | backend/tests/services/test_llm_providers.py |

## Verification

```
cd backend && pytest tests/services/test_llm_providers.py -v
```

Result: **5 passed** in 0.44s.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Gemini test: response_schema assertion was asserting wrong value**
- **Found during:** Task 2 (running full test suite)
- **Issue:** `test_gemini_provider_uses_response_mime_type_application_json` asserted `config.response_schema is ResearchResult`, but the production code intentionally does NOT set `response_schema` (documented in gemini.py: Gemini API rejects `additionalProperties` which Pydantic emits for `dict[str, X]` fields).
- **Fix:** Updated assertion to `assert config.response_schema is None` with explanatory comment.
- **Files modified:** backend/tests/services/test_llm_providers.py
- **Commit:** 81353e0

## Self-Check: PASSED

- backend/tests/services/test_llm_providers.py: FOUND
- Commit 81353e0: FOUND
- 5 tests passing: CONFIRMED
