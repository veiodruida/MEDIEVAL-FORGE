---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 07a
subsystem: services/research
tags: [llm, cache, sqlite, sha256, prompt-digest, schema-version]
requires:
  - 07-01 (ResearchCache SQLAlchemy model with generated_at column)
  - 07-03 (services/llm/prompt.py — source of PROMPT_TEMPLATE)
  - 07-04 (provider registry — string-keyed provider names)
  - 07-05 (overlay sidecar for downstream Plan 07b consumer)
  - 07-06 (matcher condado_id contract for cache_key consumers)
provides:
  - cache_key (7-component SHA-256 derivation)
  - cache_get / cache_get_with_generated_at / cache_put
  - PROMPT_DIGEST (auto-computed; replaces manual PROMPT_VERSION)
  - SCHEMA_VERSION (constant; bump-on-migration)
affects:
  - backend/medieval_forge/services/llm/prompt.py (PROMPT_TEMPLATE added)
  - backend/medieval_forge/services/research/__init__.py (exports extended)
tech-stack:
  added: [hashlib (SHA-256), sqlalchemy.ext.asyncio (AsyncSession)]
  patterns:
    - "content-addressable cache key (no FK cascade, outlives credentials)"
    - "canonical normalization (strip+lower on country + period)"
    - "import-time digest derivation (auto-invalidate on template edit)"
key-files:
  created:
    - backend/medieval_forge/services/research/cache.py
    - backend/tests/unit/test_research_cache.py
  modified:
    - backend/medieval_forge/services/research/__init__.py
    - backend/medieval_forge/services/llm/prompt.py
decisions:
  - "PROMPT_DIGEST replaces manual PROMPT_VERSION discipline (REVIEWS soft Codex)"
  - "condado_ids_digest sorted-then-hashed for order-insensitive matching (REVIEWS fix #4 Codex)"
  - "SCHEMA_VERSION literal-int constant (not enum) — single source of truth (REVIEWS fix #4 Qwen3)"
  - "Cache outlives credentials by design — content-addressable, no FK (REVIEWS fix #8)"
  - "generated_at NOT auto-bumped on cache_put overwrite — preserves original-generation semantics; runner explicitly assigns on force-refresh"
metrics:
  completed: 2026-05-14
  duration: ~30min
  tasks: 1
  commits: 5
  files_created: 2
  files_modified: 2
  tests_added: 10
  tests_passing: 10
requirements: [V3-LLM-OPT-IN]
---

# Phase 07 Plan 07a: services/research/cache.py Summary

**One-liner:** SQLite-backed research cache with 7-component SHA-256 key
(country_qid + period_label + provider + model + PROMPT_DIGEST +
SCHEMA_VERSION + condado_ids_digest), auto-invalidating on prompt-template
edits and content-addressable so cache rows outlive credentials.

## What landed

### `backend/medieval_forge/services/research/cache.py` (NEW)

- `cache_key(country_qid, period_label, provider, model, condado_ids,
  prompt_digest=PROMPT_DIGEST, schema_version=SCHEMA_VERSION) -> str`
  - Canonical form: `{country_qid.strip().lower()}|{period_label.strip().lower()}|{provider}|{model}|{prompt_digest}|{schema_version}|{condado_ids_digest}`
  - Returns a 64-char SHA-256 hex digest.
- `_condado_ids_digest(condado_ids) -> str` (16-hex-char prefix of
  `sha256(",".join(sorted(condado_ids)))`).
- `cache_get(session, key) -> dict | None` — miss returns None.
- `cache_get_with_generated_at(session, key) -> tuple[dict, datetime] | None`
  — used by Plan 07b runner to populate `meta.json::generated_at`.
- `cache_put(session, key, payload, provider, model)` — upsert. `generated_at`
  NOT auto-bumped on overwrite (semantics: original-generation timestamp;
  force-refresh path is responsible for explicit reassignment in Plan 07b).
- `PROMPT_DIGEST: str = sha256(PROMPT_TEMPLATE)[:8]` — auto-computed at
  import time.
- `SCHEMA_VERSION: int = 1` — bump on semantic field changes.
- `PROMPT_VERSION: str = PROMPT_DIGEST` — back-compat alias for legacy callers.

### `backend/medieval_forge/services/research/__init__.py` (EXTENDED)

Added to `__all__`: `PROMPT_DIGEST`, `PROMPT_VERSION`, `SCHEMA_VERSION`,
`cache_get`, `cache_get_with_generated_at`, `cache_key`, `cache_put`.
Existing exports (`merge_overlay`, `build_pipeline_condado_list`,
`llm_output_to_overlay`, `_ZIP_BOUND_FIELDS`, etc.) preserved verbatim.

### `backend/medieval_forge/services/llm/prompt.py` (MODIFIED — Rule 3)

Added a single derived constant:

```python
PROMPT_TEMPLATE: str = SYSTEM_INSTRUCTIONS + EXAMPLE_OUTPUT + RULES
```

Non-behavioral. The literal-port prompt.py file's `build_research_prompt`,
`build_map_research_prompt`, and `build_codex_prompt` functions are untouched.

### `backend/tests/unit/test_research_cache.py` (NEW)

10 unit tests, all explicit fixtures, no hidden magic (per project memory
`feedback-tests-descriptive`):

| # | Test | What it gates |
|---|------|---------------|
| 1 | `test_cache_key_sha256_normalizes_case_and_whitespace` | Pitfall 6: canonical strip+lower; condado_ids order-insensitive |
| 2 | `test_cache_key_returns_64_char_hex_string` | SHA-256 hex contract |
| 3 | `test_cache_key_includes_prompt_digest_so_prompt_template_edit_invalidates` | REVIEWS soft Codex |
| 4 | `test_cache_key_differs_when_condado_ids_differ_even_with_same_country_and_period` | REVIEWS fix #4 Codex |
| 5 | `test_cache_key_includes_schema_version_to_force_miss_on_schema_migration` | REVIEWS fix #4 Qwen3 |
| 6 | `test_cache_hit_returns_payload_without_calling_provider` | Hit path |
| 7 | `test_force_refresh_overwrites_cache_entry_on_success` | Force-refresh path |
| 8 | `test_cache_miss_returns_none_for_unknown_key` | Miss path |
| 9 | `test_research_cache_row_uses_generated_at_column_not_created_at` | REVIEWS fix #2 |
| 10 | `test_cache_row_outlives_credential_row_deletion` | REVIEWS fix #8 |

## Verification

```bash
cd backend && pytest tests/unit/test_research_cache.py -x -q
# 10 passed in 0.56s

cd backend && python -c "from medieval_forge.services.research import \
  cache_key, cache_get, cache_get_with_generated_at, cache_put, \
  PROMPT_DIGEST, SCHEMA_VERSION; print(PROMPT_DIGEST, SCHEMA_VERSION)"
# e35139f3 1   (post Rule 1 fix — see Deviations §3)

# Smoke test no regression across research + LLM + credential packages
cd backend && pytest tests/unit/test_research_cache.py \
  tests/unit/test_credential_store.py \
  tests/unit/test_matcher.py \
  tests/unit/test_overlay_merge.py \
  tests/unit/test_llm_schemas.py \
  tests/unit/test_llm_parse.py \
  tests/unit/test_llm_sanitize.py -q
# 44 passed in 0.77s
```

## Commits

| Hash | Type | Message |
|------|------|---------|
| `eab04fd` | test | TDD RED — failing test_research_cache.py (10 cases) |
| `e1708eb` | feat | Add PROMPT_TEMPLATE constant to llm/prompt.py (Rule 3) |
| `e6c799c` | feat | Add services/research/cache.py (TDD GREEN) |
| `5b01a80` | docs | Initial SUMMARY.md |
| `10c2d42` | fix  | PROMPT_TEMPLATE covers all 3 prompt builders (Rule 1) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 – Blocking] Added `PROMPT_TEMPLATE` constant to `services/llm/prompt.py`**

- **Found during:** Task 1 GREEN-phase implementation (advisor flagged before writing).
- **Issue:** Plan instructs `from ..llm.prompt import PROMPT_TEMPLATE`, but
  `prompt.py` (Plan 07-03 literal-port file) only exports `SYSTEM_INSTRUCTIONS`,
  `EXAMPLE_OUTPUT`, `RULES`, and the `build_*_prompt` functions. There is no
  `PROMPT_TEMPLATE` constant to import.
- **Fix:** Added `PROMPT_TEMPLATE: str = SYSTEM_INSTRUCTIONS + EXAMPLE_OUTPUT + RULES`
  to `prompt.py` (single derived constant, no behavioral change). The literal-port
  banner is honored — `build_research_prompt`, `build_map_research_prompt`, and
  `build_codex_prompt` are byte-identical.
- **Files modified:** `backend/medieval_forge/services/llm/prompt.py`
- **Commit:** `e1708eb`

**2. [Rule 3 – Blocking] Import path needed `from ...models` (3 dots) not `from ..models` (2 dots)**

- **Found during:** First pytest run after writing GREEN code.
- **Issue:** Plan's action code shows `from ..models import ResearchCache as ResearchCacheModel`
  and `from ..llm.prompt import PROMPT_TEMPLATE`. But `cache.py` lives in
  `services/research/`, so `..` resolves to `services/` (where there is no
  `models.py`). The model lives one level higher at `medieval_forge/models.py`.
- **Fix:** Used `from ...services.llm.prompt import PROMPT_TEMPLATE` and
  `from ...models import ResearchCache as ResearchCacheModel` (3-dot relative).
- **Files modified:** `backend/medieval_forge/services/research/cache.py`
- **Commit:** `e6c799c`

**3. [Rule 1 – Bug] PROMPT_TEMPLATE under-covered prompt builders (silent cache-staleness)**

- **Found during:** Post-implementation advisor review.
- **Issue:** Initial `PROMPT_TEMPLATE = SYSTEM_INSTRUCTIONS + EXAMPLE_OUTPUT + RULES`
  covered ONLY the legacy `build_research_prompt`. But `services/llm/__init__.py`
  exports `build_map_research_prompt` (Etapa 6 baronies-aware flow — the one
  Plan 07b runner reaches through the matcher), and `build_codex_prompt` (Plan
  09a/09b). Edits to `RULES_MAP`, `EXAMPLE_OUTPUT_MAP`, `SYSTEM_INSTRUCTIONS_CODEX`,
  `EXAMPLE_OUTPUT_CODEX`, or `RULES_CODEX` would NOT bump `PROMPT_DIGEST`,
  silently leaving cached payloads stale and breaking the REVIEWS-soft-Codex
  contract ("any prompt edit auto-invalidates the cache").
- **Fix:** `PROMPT_TEMPLATE` now concatenates all 8 static prompt blocks across
  all 3 builders. Order is deterministic at import time; digest stability
  preserved. PROMPT_DIGEST changed from `0f13a2e6` → `e35139f3`.
- **Files modified:** `backend/medieval_forge/services/llm/prompt.py`
- **Commit:** `10c2d42`
- **Note:** since no production cache rows exist yet (Plan 07b runner not yet
  online), this digest change is a one-time invalidation with zero user impact.
- **Commit:** `e6c799c`

## Authentication Gates

None.

## Plan Acceptance Criteria — all met

- File `services/research/cache.py` EXISTS — yes
- `def cache_key` returns 1 match — yes
- `hashlib.sha256` ≥3 matches — yes (3)
- `PROMPT_DIGEST` ≥3 matches — yes (7)
- `SCHEMA_VERSION` ≥3 matches — yes (4)
- `SCHEMA_VERSION: int = 1` returns 1 match — yes
- `_condado_ids_digest` ≥2 matches — yes (2)
- `country_qid` ≥1 match — yes (5)
- `period_label` ≥1 match — yes (5)
- `condado_ids` ≥3 matches — yes (7)
- `strip().lower()` ≥2 matches — yes (2)
- `generated_at` ≥2 matches — yes (8)
- `cache_get_with_generated_at` ≥1 match — yes (1)
- test_research_cache.py EXISTS with ≥10 test functions — yes (10)
- All 5 REVIEWS-fix-tagged test names present — yes
- `pytest tests/unit/test_research_cache.py -x -q` exits 0 — yes (10 passed)

## Threat Model Status

All 5 `mitigate` dispositions implemented and asserted by tests:

| Threat ID | Mitigation | Test |
|-----------|-----------|------|
| T-07-07a-01 | provider+model+PROMPT_DIGEST+SCHEMA_VERSION+condado_ids_digest in key | Tests 1,3,4,5 |
| T-07-07a-02 | strip().lower() canonical form | Test 1 |
| T-07-07a-03 | condado_ids_digest in key | Test 4 |
| T-07-07a-04 | SCHEMA_VERSION in key | Test 5 |
| T-07-07a-05 | PROMPT_DIGEST auto-computed at import | Test 3 |

T-07-07a-06 (information disclosure via orphaned cache) is the accepted-risk
disposition; Test 10 asserts the intentional behavior.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or
trust-boundary schema changes introduced. Cache reads/writes happen entirely
within the existing SQLite session boundary established by Plan 01.

## Self-Check: PASSED

- `backend/medieval_forge/services/research/cache.py` — FOUND
- `backend/tests/unit/test_research_cache.py` — FOUND
- `backend/medieval_forge/services/research/__init__.py` extends exports — FOUND
- `backend/medieval_forge/services/llm/prompt.py` `PROMPT_TEMPLATE` constant — FOUND
- Commit `eab04fd` — FOUND
- Commit `e1708eb` — FOUND
- Commit `e6c799c` — FOUND
- `pytest tests/unit/test_research_cache.py -x -q` — 10 passed
- `python -c "from medieval_forge.services.research import cache_key, ..."` — exits 0
