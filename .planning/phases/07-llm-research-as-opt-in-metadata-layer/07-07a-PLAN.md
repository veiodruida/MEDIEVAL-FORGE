---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 07a
type: execute
wave: 3
depends_on: [01, 04, 05, 06]
files_modified:
  - backend/medieval_forge/services/research/cache.py
  - backend/medieval_forge/services/research/__init__.py
  - backend/tests/unit/test_research_cache.py
autonomous: true
requirements:
  - V3-LLM-OPT-IN
must_haves:
  truths:
    - "services/research/cache.py implements SHA-256 cache key derivation with canonical normalization (lowercase + strip whitespace per Pitfall 6) AND key includes all 5 components: country_qid + period_label + provider + model + prompt_version"
    - "Cache hit short-circuits the LLM call; force_refresh=True bypasses cache; cache key collision across periods prevented (Pitfall 6 — 'q29|868 ad|claude|...' canonical form)"
  artifacts:
    - path: "backend/medieval_forge/services/research/cache.py"
      provides: "SHA-256 cache key + SQLite read/write backed by research_cache table"
      contains: "def cache_key"
    - path: "backend/tests/unit/test_research_cache.py"
      provides: "Wave 0 gate — cache key derivation + hit/miss/force-refresh"
      contains: "test_cache_key_sha256_normalizes_case_and_whitespace"
  key_links:
    - from: "backend/medieval_forge/services/research/cache.py"
      to: "backend/medieval_forge/models.py:ResearchCache"
      via: "select(ResearchCache).where(ResearchCache.cache_key == key)"
      pattern: "from \\.\\.models import ResearchCache"
---

<objective>
Land the SQLite-backed research cache (D-11). Pre-split from former Plan 07 (now 07a + 07b) per checker WARNING 1 (file count borderline). 07a covers cache.py + tests; 07b covers runner + endpoints.

Purpose: D-11 cache; Pitfall 6 (cache key normalization). RESEARCH §Example 2 specifies exact code.

Output:
- backend/medieval_forge/services/research/cache.py
- backend/medieval_forge/services/research/__init__.py (extended)
- backend/tests/unit/test_research_cache.py

Filename note: `07-07a-PLAN.md` deviates from strict `{NN}` convention to honor checker WARNING 1 (split). Subsequent split is 07b.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@CLAUDE.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-CONTEXT.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md
@backend/medieval_forge/models.py
@backend/medieval_forge/services/credential_store.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: services/research/cache.py + test_research_cache.py — SHA-256 cache with canonical normalization</name>
  <files>
    backend/medieval_forge/services/research/cache.py
    backend/medieval_forge/services/research/__init__.py
    backend/tests/unit/test_research_cache.py
  </files>
  <read_first>
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Example 2 (cache_key derivation)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pitfall 6 (cache key collision across periods — canonical form lowercase + strip)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-CONTEXT.md (D-11 — table shape; D-24 carried — re-ingestion does NOT invalidate)
    - backend/medieval_forge/models.py (ResearchCache from Plan 01)
    - backend/medieval_forge/services/credential_store.py (Plan 01 — pattern reference for async DB CRUD)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-VALIDATION.md (Wave 0 — test_research_cache.py)
  </read_first>
  <behavior>
    - Test 1: `test_cache_key_sha256_normalizes_case_and_whitespace` — `cache_key("Q29", "868 AD", "Claude", "claude-sonnet-4-6", prompt_version="v1") == cache_key("q29", "868 ad", "Claude", "claude-sonnet-4-6", prompt_version="v1")` (case insensitive on country + period; provider + model case preserved per RESEARCH §Example 2)
    - Test 2: `test_cache_key_returns_64_char_hex_string` — assert SHA-256 hex length is 64.
    - Test 3: `test_cache_key_includes_prompt_version_to_prevent_stale_after_prompt_change` — different prompt_version → different cache key.
    - Test 4: `test_cache_hit_returns_payload_without_calling_provider` — store a payload then look it up; assert returns the same dict.
    - Test 5: `test_force_refresh_overwrites_cache_entry_on_success` — store then re-store via force-refresh path; assert new payload replaces old.
    - Test 6: `test_cache_miss_returns_none_for_unknown_key` — fresh DB, lookup returns None.
  </behavior>
  <action>
    1. Create `backend/medieval_forge/services/research/cache.py`:

       ```python
       """SQLite-backed research cache (D-11).

       Key derivation per RESEARCH §Example 2 + §Pitfall 6: canonical form is
       `{country_qid_lower}|{period_label_strip_lower}|{provider}|{model}|{prompt_version}`.
       SHA-256 hex digest gives a fixed-width 64-char key.

       Re-ingestion does NOT invalidate the cache (D-24 carried from v1).
       Force-refresh checkbox in UI dialog bypasses cache.
       """
       from __future__ import annotations

       import hashlib
       import json

       from sqlalchemy import select
       from sqlalchemy.ext.asyncio import AsyncSession

       from ..models import ResearchCache as ResearchCacheModel

       # Bump this when prompt.py changes meaningfully — prevents stale cache hits.
       PROMPT_VERSION = "v1"


       def cache_key(
           country_qid: str,
           period_label: str,
           provider: str,
           model: str,
           prompt_version: str = PROMPT_VERSION,
       ) -> str:
           """Derive a deterministic SHA-256 cache key.

           Normalizes country_qid + period_label to lowercase + stripped (Pitfall 6).
           Provider + model + prompt_version case is preserved.
           """
           canonical = (
               f"{country_qid.strip().lower()}|"
               f"{period_label.strip().lower()}|"
               f"{provider}|"
               f"{model}|"
               f"{prompt_version}"
           )
           return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


       async def cache_get(session: AsyncSession, key: str) -> dict | None:
           row = await session.scalar(
               select(ResearchCacheModel).where(ResearchCacheModel.cache_key == key)
           )
           if row is None:
               return None
           return json.loads(row.payload) if isinstance(row.payload, str) else row.payload


       async def cache_put(
           session: AsyncSession,
           key: str,
           payload: dict,
           provider: str,
           model: str,
       ) -> None:
           existing = await session.scalar(
               select(ResearchCacheModel).where(ResearchCacheModel.cache_key == key)
           )
           if existing:
               existing.payload = payload
               existing.provider = provider
               existing.model = model
           else:
               session.add(ResearchCacheModel(
                   cache_key=key, payload=payload, provider=provider, model=model
               ))
           await session.commit()
       ```

    2. UPDATE `backend/medieval_forge/services/research/__init__.py`:

       ```python
       from .overlay import merge_overlay, load_overlay_if_exists, ResearchOverlay, CondadoOverlayEntry, _ZIP_BOUND_FIELDS
       from .matcher import build_pipeline_condado_list, llm_output_to_overlay
       from .cache import cache_key, cache_get, cache_put, PROMPT_VERSION
       ```

    3. Create `backend/tests/unit/test_research_cache.py` with the 6 cases. Use in-memory aiosqlite fixture (same pattern as Plan 01 test_credential_store.py). Explicit numeric fixtures.
  </action>
  <acceptance_criteria>
    - File `backend/medieval_forge/services/research/cache.py` EXISTS
    - `grep -n "def cache_key" backend/medieval_forge/services/research/cache.py` returns 1 match
    - `grep -n "hashlib.sha256" backend/medieval_forge/services/research/cache.py` returns 1 match
    - `grep -n "country_qid" backend/medieval_forge/services/research/cache.py` returns ≥1 match
    - `grep -n "period_label" backend/medieval_forge/services/research/cache.py` returns ≥1 match
    - `grep -n "provider" backend/medieval_forge/services/research/cache.py` returns ≥1 match
    - `grep -n "model" backend/medieval_forge/services/research/cache.py` returns ≥1 match
    - `grep -n "prompt_version" backend/medieval_forge/services/research/cache.py` returns ≥1 match
    - `grep -n "strip().lower()" backend/medieval_forge/services/research/cache.py` returns ≥2 matches
    - File `backend/tests/unit/test_research_cache.py` EXISTS with ≥6 test functions
    - `cd backend && pytest tests/unit/test_research_cache.py -x -q` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && pytest tests/unit/test_research_cache.py -x -q</automated>
  </verify>
  <done>Cache lands with 5-component key + canonical normalization; Wave 0 gate flips green.</done>
</task>

</tasks>

<context_anchors>
- **D-11** (cache table)
- **D-24 carried** (re-ingestion does NOT invalidate cache)
- **RESEARCH §Example 2** (cache_key code)
- **RESEARCH §Pitfall 6** (cache key normalization)
- **VALIDATION.md row 07-XX-CACHE**
</context_anchors>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DB read/write → cache | Untrusted prompt input flows into key derivation (normalized via strip+lower) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-07a-01 | Information Disclosure | Cache poisoning across providers | mitigate | cache_key includes provider + model + prompt_version (5 components total). Acceptance: grep list verifies all 5. |
| T-07-07a-02 | Tampering | Cache key collision via case/whitespace | mitigate | Canonical strip().lower() on country + period; Test 1 enforces. |

</threat_model>

<verification>
- `cd backend && pytest tests/unit/test_research_cache.py -x -q` exits 0
- `cd backend && python -c "from medieval_forge.services.research import cache_key, cache_get, cache_put"` exits 0
</verification>

<success_criteria>
- 5-component cache key with canonical normalization
- Hit/miss/force-refresh semantics verified via tests
- Plan 07b runner can import cache_key/cache_get/cache_put
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-07a-SUMMARY.md` per the standard template.
</output>
