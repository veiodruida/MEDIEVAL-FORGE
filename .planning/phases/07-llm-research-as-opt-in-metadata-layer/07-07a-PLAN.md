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
    - "services/research/cache.py implements SHA-256 cache key derivation with canonical normalization (lowercase + strip whitespace per Pitfall 6) AND key includes 7 components: country_qid + period_label + provider + model + prompt_version (PROMPT_DIGEST per REVIEWS soft codex) + schema_version (REVIEWS fix #4 Qwen3) + condado_ids_digest (REVIEWS fix #4 Codex)"
    - "Cache row column is `generated_at` (renamed from `created_at` per REVIEWS fix #2 — distinguishes original-generation time from runner-apply time)"
    - "SCHEMA_VERSION constant defined in services/research/cache.py (REVIEWS fix #4 — bump on semantic changes to cached fields)"
    - "PROMPT_DIGEST derived from sha256(PROMPT_TEMPLATE.encode())[:8] (REVIEWS soft codex — subsumes manual PROMPT_VERSION bumps)"
    - "Cache hit short-circuits the LLM call; force_refresh=True bypasses cache; cache key collision across periods prevented (Pitfall 6 — 'q29|868 ad|claude|...' canonical form)"
    - "Cache outlives credentials: deleting an LLMCredential row does NOT cascade-delete ResearchCache rows (REVIEWS fix #8 — cache rows remain valid for cache hits)"
  artifacts:
    - path: "backend/medieval_forge/services/research/cache.py"
      provides: "SHA-256 cache key (7 components) + SCHEMA_VERSION + PROMPT_DIGEST + SQLite read/write backed by research_cache table (generated_at column)"
      contains: "def cache_key"
    - path: "backend/tests/unit/test_research_cache.py"
      provides: "Wave 0 gate — cache key derivation + hit/miss/force-refresh + condado_ids_digest + schema_version + cache-outlives-credentials"
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

REVIEWS replan 2026-05-14 deltas:
- **Fix #2 (Codex)**: Rename ResearchCache row column `created_at` → `generated_at`. This is the original-LLM-generation timestamp. The "applied to project" timestamp (`applied_at`) lives in the overlay meta sidecar (Plan 07b), not in the cache table.
- **Fix #4 (Codex+Qwen3)**: Cache key gains `condado_ids_digest` + `schema_version`. Final key formula: `sha256(country_qid|period|provider|model|prompt_version|schema_version|condado_ids_digest)`. `SCHEMA_VERSION = 1` constant introduced; bumped on semantic field changes.
- **Fix #8 (Qwen3)**: Document that `credential_store.delete_credentials(provider)` does NOT cascade to ResearchCache. Cache rows outlive credentials. Add a test asserting this behavior.
- **Soft (Codex)**: Replace manual `PROMPT_VERSION = "v1"` with `PROMPT_DIGEST = sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()[:8]`. PROMPT_DIGEST is computed at import time from the literal-port prompt template; any prompt edit auto-invalidates the cache.

Filename note: `07-07a-PLAN.md` deviates from strict `{NN}` convention to honor checker WARNING 1 (split). Subsequent split is 07b.

Output:
- backend/medieval_forge/services/research/cache.py (7-component key + SCHEMA_VERSION + PROMPT_DIGEST + generated_at)
- backend/medieval_forge/services/research/__init__.py (extended)
- backend/tests/unit/test_research_cache.py (with cache-outlives-credentials test)
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
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md
@backend/medieval_forge/models.py
@backend/medieval_forge/services/credential_store.py
</context>

<dependency_note>
**REVIEWS fix #2 — `created_at` rename to `generated_at`**

Plan 01 created `ResearchCache.created_at` as a column. Plan 07a renames it to `generated_at`
to disambiguate from the overlay meta sidecar's `applied_at` (Plan 07b). The semantic is:

- `ResearchCache.generated_at` — when the LLM originally produced this payload (DB timestamp)
- `research_overlay.meta.json::generated_at` — copied from the cache row when applied
- `research_overlay.meta.json::applied_at` — when the runner wrote this overlay to the project

The UI microcopy (Plan 09b) reads both timestamps and renders them per REVIEWS fix #2 UX.

**Migration note**: since Plan 01 is in Wave 0 and Plan 07a is in Wave 3, the column-name
change must land in Plan 01's migration (Alembic 0006). Plan 01 has been updated to
specify `generated_at` directly — no second migration needed. If Plan 01 was already
executed before this replan landed, run `alembic downgrade -1 && alembic upgrade head`
after the Plan 01 file update.
</dependency_note>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: services/research/cache.py + test_research_cache.py — SHA-256 cache (7 components: + SCHEMA_VERSION + condado_ids_digest) + PROMPT_DIGEST + generated_at + cache-outlives-credentials test</name>
  <files>
    backend/medieval_forge/services/research/cache.py
    backend/medieval_forge/services/research/__init__.py
    backend/tests/unit/test_research_cache.py
  </files>
  <read_first>
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Example 2 (cache_key derivation)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pitfall 6 (cache key collision across periods — canonical form lowercase + strip)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-CONTEXT.md (D-11 — table shape; D-24 carried — re-ingestion does NOT invalidate)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md "Recommended Action Before Execution" #2, #4, #8 + soft codex on PROMPT_DIGEST
    - backend/medieval_forge/models.py (ResearchCache from Plan 01 — column renamed to `generated_at`)
    - backend/medieval_forge/services/credential_store.py (Plan 01 — pattern reference for async DB CRUD)
    - backend/medieval_forge/services/llm/prompt.py (Plan 03 literal port — source of PROMPT_TEMPLATE for PROMPT_DIGEST)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-VALIDATION.md (Wave 0 — test_research_cache.py)
  </read_first>
  <behavior>
    - Test 1: `test_cache_key_sha256_normalizes_case_and_whitespace` — `cache_key("Q29", "868 AD", "Claude", "claude-sonnet-4-6", condado_ids=["oviedo","leon"]) == cache_key("q29", "868 ad", "Claude", "claude-sonnet-4-6", condado_ids=["leon","oviedo"])` (case insensitive on country + period; provider + model case preserved; condado_ids sorted-then-hashed so order-insensitive)
    - Test 2: `test_cache_key_returns_64_char_hex_string` — assert SHA-256 hex length is 64.
    - Test 3: `test_cache_key_includes_prompt_digest_so_prompt_template_edit_invalidates` — patch `PROMPT_DIGEST` to a different value; assert different cache key.
    - Test 4 (REVIEWS fix #4 Codex): `test_cache_key_differs_when_condado_ids_differ_even_with_same_country_and_period` — Iberia 868 with condados {oviedo, leon, burgos} vs Iberia 868 with condados {sevilla, cordoba} produce DIFFERENT cache keys. This prevents stale cache reuse across incompatible region geometries.
    - Test 5 (REVIEWS fix #4 Qwen3): `test_cache_key_includes_schema_version_to_force_miss_on_schema_migration` — patch SCHEMA_VERSION 1→2; assert different cache key.
    - Test 6: `test_cache_hit_returns_payload_without_calling_provider` — store a payload then look it up; assert returns the same dict.
    - Test 7: `test_force_refresh_overwrites_cache_entry_on_success` — store then re-store via force-refresh path; assert new payload replaces old.
    - Test 8: `test_cache_miss_returns_none_for_unknown_key` — fresh DB, lookup returns None.
    - Test 9 (REVIEWS fix #2): `test_research_cache_row_uses_generated_at_column_not_created_at` — store a row; query the SQLAlchemy model attribute `generated_at` (not `created_at`); assert datetime returned.
    - Test 10 (REVIEWS fix #8 Qwen3): `test_cache_row_outlives_credential_row_deletion` — seed `LLMCredential(provider_id="claude", ...)`; seed `ResearchCache(cache_key="abc...", ...)`; call `credential_store.clear_credentials(session, "claude")`; then call `cache_get(session, "abc...")` — assert it STILL returns the cached payload. Cache outlives credentials.
  </behavior>
  <action>
    1. Create `backend/medieval_forge/services/research/cache.py`:

       ```python
       """SQLite-backed research cache (D-11).

       Key derivation per RESEARCH §Example 2 + §Pitfall 6 + REVIEWS fix #4: canonical form is
       `{country_qid_lower}|{period_label_strip_lower}|{provider}|{model}|{PROMPT_DIGEST}|{SCHEMA_VERSION}|{condado_ids_digest}`.
       SHA-256 hex digest gives a fixed-width 64-char key.

       REVIEWS fix #2: row column is `generated_at` (the original LLM-output timestamp).
       Plan 07b reads this and copies it into research_overlay.meta.json::generated_at;
       the runner-write timestamp lives in research_overlay.meta.json::applied_at instead.

       REVIEWS fix #4 Codex: cache key includes condado_ids_digest so two regions sharing
       country + period but different condado lists DO NOT share cached payloads.

       REVIEWS fix #4 Qwen3: cache key includes SCHEMA_VERSION constant. Bump on semantic
       changes to cached fields (e.g., if `historical_notes` semantics change). Forces a
       cache miss for all rows at the previous schema version.

       REVIEWS soft codex: PROMPT_DIGEST replaces manual PROMPT_VERSION discipline. It is
       a sha256 of the literal-port prompt.py template, computed at import time. Any edit
       to the template auto-invalidates the cache.

       REVIEWS fix #8 Qwen3: cache rows outlive credential rows. Deleting an LLMCredential
       row does NOT cascade-delete ResearchCache rows. The cache key is provider-string-keyed
       (not FK-keyed), so cache hits work even after credentials are rotated.

       Re-ingestion does NOT invalidate the cache (D-24 carried from v1).
       Force-refresh checkbox in UI dialog bypasses cache.
       """
       from __future__ import annotations

       import hashlib
       import json

       from sqlalchemy import select
       from sqlalchemy.ext.asyncio import AsyncSession

       from ..llm.prompt import PROMPT_TEMPLATE  # literal-port source (Plan 03)
       from ..models import ResearchCache as ResearchCacheModel

       # REVIEWS soft codex — PROMPT_DIGEST replaces manual PROMPT_VERSION.
       # Computed at import time from the literal-port prompt template; any edit forces a
       # cache miss. 8-hex-char prefix is enough to disambiguate prompt revisions while
       # keeping the canonical form short.
       PROMPT_DIGEST: str = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()[:8]

       # REVIEWS fix #4 Qwen3 — bump on semantic changes to cached fields
       # (e.g., historical_notes contract change, new required field). Forces cache miss
       # for all rows at the previous schema version.
       SCHEMA_VERSION: int = 1

       # Back-compat alias for legacy callers / tests still expecting PROMPT_VERSION.
       # New code MUST use PROMPT_DIGEST directly. Remove this alias in v3.1.
       PROMPT_VERSION: str = PROMPT_DIGEST


       def _condado_ids_digest(condado_ids: list[str]) -> str:
           """REVIEWS fix #4 Codex — order-insensitive hash of the condado-id list.

           Sorting guarantees Iberia 868 with {oviedo,leon} and {leon,oviedo} share a key.
           Truncate to 16 hex chars to keep the canonical form short.
           """
           joined = ",".join(sorted(condado_ids))
           return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


       def cache_key(
           country_qid: str,
           period_label: str,
           provider: str,
           model: str,
           condado_ids: list[str],
           prompt_digest: str = PROMPT_DIGEST,
           schema_version: int = SCHEMA_VERSION,
       ) -> str:
           """Derive a deterministic SHA-256 cache key.

           7 components: country_qid + period_label + provider + model + prompt_digest +
           schema_version + condado_ids_digest. Normalizes country_qid + period_label to
           lowercase + stripped (Pitfall 6). Provider + model case preserved.
           """
           canonical = (
               f"{country_qid.strip().lower()}|"
               f"{period_label.strip().lower()}|"
               f"{provider}|"
               f"{model}|"
               f"{prompt_digest}|"
               f"{schema_version}|"
               f"{_condado_ids_digest(condado_ids)}"
           )
           return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


       async def cache_get(session: AsyncSession, key: str) -> dict | None:
           row = await session.scalar(
               select(ResearchCacheModel).where(ResearchCacheModel.cache_key == key)
           )
           if row is None:
               return None
           return json.loads(row.payload) if isinstance(row.payload, str) else row.payload


       async def cache_get_with_generated_at(
           session: AsyncSession, key: str
       ) -> tuple[dict, "datetime"] | None:
           """REVIEWS fix #2 — used by Plan 07b runner to populate
           research_overlay.meta.json::generated_at on cache-hit path.
           """
           row = await session.scalar(
               select(ResearchCacheModel).where(ResearchCacheModel.cache_key == key)
           )
           if row is None:
               return None
           payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
           return payload, row.generated_at


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
               # generated_at NOT updated on overwrite: force-refresh resets the
               # generation timestamp via explicit assignment in the runner path.
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
       from .cache import cache_key, cache_get, cache_get_with_generated_at, cache_put, PROMPT_DIGEST, PROMPT_VERSION, SCHEMA_VERSION
       ```

    3. Create `backend/tests/unit/test_research_cache.py` with the 10 cases. Use in-memory aiosqlite fixture (same pattern as Plan 01 test_credential_store.py). Explicit numeric fixtures.

       Test 10 (REVIEWS fix #8) example:
       ```python
       @pytest.mark.asyncio
       async def test_cache_row_outlives_credential_row_deletion(session):
           # Seed credential + cache entries
           await store_credentials(session, "claude", {"key": "sk-ant-test", "type": "api_key"})
           key = cache_key("Q29", "868 AD", "claude", "claude-sonnet-4-6",
                          condado_ids=["oviedo", "leon"])
           await cache_put(session, key, {"condados": [{"id": "oviedo", "name": "Oviedo"}]},
                          provider="claude", model="claude-sonnet-4-6")
           # Delete credentials
           await clear_credentials(session, "claude")
           # Cache row STILL returns payload
           payload = await cache_get(session, key)
           assert payload is not None
           assert payload["condados"][0]["name"] == "Oviedo"
       ```
  </action>
  <acceptance_criteria>
    - File `backend/medieval_forge/services/research/cache.py` EXISTS
    - `grep -n "def cache_key" backend/medieval_forge/services/research/cache.py` returns 1 match
    - `grep -n "hashlib.sha256" backend/medieval_forge/services/research/cache.py` returns ≥3 matches (key + condado_ids_digest + PROMPT_DIGEST)
    - `grep -n "PROMPT_DIGEST" backend/medieval_forge/services/research/cache.py` returns ≥3 matches (REVIEWS soft codex)
    - `grep -n "SCHEMA_VERSION" backend/medieval_forge/services/research/cache.py` returns ≥3 matches (REVIEWS fix #4 Qwen3)
    - `grep -n "SCHEMA_VERSION: int = 1" backend/medieval_forge/services/research/cache.py` returns 1 match
    - `grep -n "_condado_ids_digest" backend/medieval_forge/services/research/cache.py` returns ≥2 matches (REVIEWS fix #4 Codex)
    - `grep -n "country_qid" backend/medieval_forge/services/research/cache.py` returns ≥1 match
    - `grep -n "period_label" backend/medieval_forge/services/research/cache.py` returns ≥1 match
    - `grep -n "condado_ids" backend/medieval_forge/services/research/cache.py` returns ≥3 matches
    - `grep -n "strip().lower()" backend/medieval_forge/services/research/cache.py` returns ≥2 matches
    - `grep -n "generated_at" backend/medieval_forge/services/research/cache.py` returns ≥2 matches (REVIEWS fix #2)
    - `grep -n "cache_get_with_generated_at" backend/medieval_forge/services/research/cache.py` returns ≥1 match (Plan 07b consumer)
    - File `backend/tests/unit/test_research_cache.py` EXISTS with ≥10 test functions
    - `grep -n "test_cache_key_differs_when_condado_ids_differ_even_with_same_country_and_period" backend/tests/unit/test_research_cache.py` returns 1 match (REVIEWS fix #4 Codex)
    - `grep -n "test_cache_key_includes_schema_version_to_force_miss_on_schema_migration" backend/tests/unit/test_research_cache.py` returns 1 match (REVIEWS fix #4 Qwen3)
    - `grep -n "test_cache_key_includes_prompt_digest_so_prompt_template_edit_invalidates" backend/tests/unit/test_research_cache.py` returns 1 match (REVIEWS soft codex)
    - `grep -n "test_research_cache_row_uses_generated_at_column_not_created_at" backend/tests/unit/test_research_cache.py` returns 1 match (REVIEWS fix #2)
    - `grep -n "test_cache_row_outlives_credential_row_deletion" backend/tests/unit/test_research_cache.py` returns 1 match (REVIEWS fix #8)
    - `cd backend && pytest tests/unit/test_research_cache.py -x -q` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && pytest tests/unit/test_research_cache.py -x -q</automated>
  </verify>
  <done>Cache lands with 7-component key (+ SCHEMA_VERSION + condado_ids_digest), PROMPT_DIGEST replaces manual PROMPT_VERSION, generated_at column wired, cache-outlives-credentials test asserts no FK cascade. Wave 0 gate flips green.</done>
</task>

</tasks>

<context_anchors>
- **D-11** (cache table)
- **D-24 carried** (re-ingestion does NOT invalidate cache)
- **RESEARCH §Example 2** (cache_key code)
- **RESEARCH §Pitfall 6** (cache key normalization)
- **VALIDATION.md row 07-XX-CACHE**
- **REVIEWS fix #2** (created_at → generated_at rename; applied_at lives in meta sidecar)
- **REVIEWS fix #4** (condado_ids_digest + schema_version added to cache key)
- **REVIEWS fix #8** (cache outlives credentials; no FK cascade)
- **REVIEWS soft codex** (PROMPT_DIGEST replaces manual PROMPT_VERSION)
</context_anchors>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DB read/write → cache | Untrusted prompt input flows into key derivation (normalized via strip+lower) |
| Credential delete → Cache row lifecycle | Independent lifecycles by design (REVIEWS fix #8) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-07a-01 | Information Disclosure | Cache poisoning across providers | mitigate | cache_key includes provider + model + PROMPT_DIGEST + SCHEMA_VERSION + condado_ids_digest (7 components total). Acceptance: grep list verifies all 7. |
| T-07-07a-02 | Tampering | Cache key collision via case/whitespace | mitigate | Canonical strip().lower() on country + period; Test 1 enforces. |
| T-07-07a-03 | Tampering | Stale cache after region-geometry change | mitigate | REVIEWS fix #4 Codex — condado_ids_digest in cache key. Test 4 asserts different condado lists ≠ same key. |
| T-07-07a-04 | Tampering | Stale cache after schema migration | mitigate | REVIEWS fix #4 Qwen3 — SCHEMA_VERSION in cache key. Test 5 asserts schema-version bump invalidates. |
| T-07-07a-05 | Tampering | Stale cache after prompt-template edit | mitigate | REVIEWS soft codex — PROMPT_DIGEST auto-computed from prompt.py at import time. Test 3 asserts digest change invalidates. |
| T-07-07a-06 | Information Disclosure | Credential deletion leaves orphaned cache | accept (REVIEWS fix #8) | Cache rows are NOT FK-linked to credentials and DO NOT cascade-delete. This is intentional: cache hits should work even after credentials rotate. Test 10 asserts the behavior. Concern is "orphaned cache" — accepted because cache rows are content-addressable (sha256 key) and cannot leak credentials. |

</threat_model>

<verification>
- `cd backend && pytest tests/unit/test_research_cache.py -x -q` exits 0
- `cd backend && python -c "from medieval_forge.services.research import cache_key, cache_get, cache_get_with_generated_at, cache_put, PROMPT_DIGEST, SCHEMA_VERSION"` exits 0
</verification>

<success_criteria>
- 7-component cache key with canonical normalization (REVIEWS fix #4)
- PROMPT_DIGEST replaces manual PROMPT_VERSION (REVIEWS soft codex)
- generated_at column wired (REVIEWS fix #2 prep for Plan 07b applied_at)
- Hit/miss/force-refresh semantics verified via tests
- Cache-outlives-credentials test locked in (REVIEWS fix #8)
- Plan 07b runner can import cache_key / cache_get / cache_get_with_generated_at / cache_put
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-07a-SUMMARY.md` per the standard template.
</output>
