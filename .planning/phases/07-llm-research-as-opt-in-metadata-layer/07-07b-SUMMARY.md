---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 07b
subsystem: backend.research.api
tags: [sse, research, llm, runner, overlay, credentials, meta-sidecar, atomic-write, wr-02]
requires:
  - 01-credential-store
  - 04-providers
  - 05-prompt-template
  - 06-matcher
  - 07a-cache
provides:
  - services/research/runner.py
  - api/v3/research.py
  - api/v3/credentials.py
  - main.py router mounts
affects:
  - frontend/Plan 09a (ProviderSelector consumes /providers available_models)
  - frontend/Plan 09b (Surface 2 microcopy consumes overlay meta generated_at+applied_at)
tech-stack:
  added: []
  patterns: [SSE producer/consumer, _RUN_QUEUES single-flight, finally-block eviction (WR-02), atomic tmp+replace, dual-timestamp meta sidecar]
key-files:
  created:
    - backend/medieval_forge/services/research/runner.py
    - backend/medieval_forge/api/v3/research.py
    - backend/medieval_forge/api/v3/credentials.py
    - backend/tests/integration/test_research_sse.py
  modified:
    - backend/medieval_forge/services/research/__init__.py
    - backend/medieval_forge/main.py
decisions:
  - "runner._RUN_QUEUES is independent from generate/render's _run_state.py — research may run concurrently with /generate per project"
  - "Stage events are virtual (kingdoms/duchies/condados/baronies); the underlying LLM call is one round-trip, but 4 envelopes feed UI-SPEC §Surface 2 progress bar"
  - "session_factory accepts both AsyncSessionLocal (production) and lambda: db_session (tests); a same-instance heuristic skips close() for outer-owned sessions"
  - "Stub providers in tests skip the schemas.MapResearchResult round-trip and return matcher-hierarchical dicts directly; flat→hierarchical normalization for real providers is deferred to Plan 09a/09b"
  - "Overlay endpoint trims raw meta to {provider, model, generated_at, applied_at} — prompt_digest/schema_version/country/period stay internal (T-07-07b-08)"
metrics:
  duration: 13min
  tasks_completed: 2
  files_created: 4
  files_modified: 2
  tests_added: 8
  commits: 3
  date: 2026-05-14
requirements:
  - V3-LLM-OPT-IN
---

# Phase 7 Plan 07b: Research SSE Orchestrator + Routers Summary

Landed the research orchestration layer: SSE runner mirroring `api/v3/generate.py`, two new FastAPI routers (`research` + `credentials`), and the meta-sidecar with dual timestamps that enables UI-SPEC §Surface 2 microcopy disambiguation between cache-hit reuse and fresh-generation.

## What Was Built

### `services/research/runner.py` (Task 1)

SSE producer/consumer pair patterned after `api/v3/generate.py`:

- `_RUN_QUEUES[project_id] -> asyncio.Queue[str | None]` — producer/consumer slot.
- `_RUN_TASKS[project_id] -> asyncio.Task` — producer task reference.
- `_RUN_STOP_EVENTS[project_id] -> asyncio.Event` — cancellation signal.
- `_emit(queue, event_type, stage, message, progress)` — envelope writer with the same `{event_type, stage, message, progress}` shape as `generate.py`.
- `_research_producer()` — orchestrates: cache lookup → fresh LLM run (or short-circuit) → 4 stage envelopes (`kingdoms / duchies / condados / baronies`) → matcher.llm_output_to_overlay → atomic dual write.
- `_write_json_atomic(path, data)` — Pitfall 1 + Example 3 tmp+replace.
- `finally:` block puts the terminal `None` sentinel **and** evicts both maps (WR-02 / Pitfall 7).
- `SingleFlightError` raised when a second `start_research` hits an alive project; api layer maps to HTTP 409.

REVIEWS fix #2 dual-timestamp meta sidecar — `applied_at` is computed ONCE at the top of the producer and reused on both branches; `generated_at` is set to the cache row's `generated_at` on cache-hit, otherwise equals `applied_at` on fresh-run.

### `api/v3/research.py` (Task 2)

Two router objects:

- `router` (prefix `/v3/research`):
    - `POST /start` — schedules SSE run (400 on bad UUID / unknown provider; 409 on SingleFlightError).
    - `GET /stream/{run_id}` — drains the queue until `None` sentinel; 404 if no live run (Pitfall 7 / WR-02 intentional).
    - `POST /stop/{run_id}` — fires `_RUN_STOP_EVENTS` + `task.cancel()`.
    - `GET /providers` — returns `[{provider_id, display_name, healthy, message, configured, available_models?}]`. Branches on `hasattr(provider, "health")`: Ollama surfaces `available_models` (REVIEWS fix #5), Claude uses `health_check(None)` and reports HealthStatus.
    - `GET /health` — lightweight alias.
- `overlay_router` (prefix `/v3/projects`):
    - `GET /{project_id}/research/overlay` — returns `{exists, covered_condado_ids, meta}` where `meta` carries BOTH `generated_at` and `applied_at` (BLOCKER 2 + REVIEWS fix #2). Trims raw meta to UI-bound subset (T-07-07b-08).

### `api/v3/credentials.py` (Task 2)

Three CRUD endpoints under `/v3/credentials`:

- `GET ""` — list `[{provider_id, configured: bool}]` (NEVER payload).
- `POST /{provider}` — upsert payload via `credential_store.store_credentials`.
- `DELETE /{provider}` — delete row (REVIEWS fix #8: no cascade to ResearchCache).

### `main.py`

Mounts all three routers under `/api`:

```
app.include_router(research_router, prefix="/api")
app.include_router(research_overlay_router, prefix="/api")
app.include_router(credentials_router, prefix="/api")
```

## Routes Verified

```
/api/v3/credentials
/api/v3/credentials/{provider}
/api/v3/projects/{project_id}/research/overlay
/api/v3/research/health
/api/v3/research/providers
/api/v3/research/start
/api/v3/research/stop/{run_id}
/api/v3/research/stream/{run_id}
```

## Test Coverage

`backend/tests/integration/test_research_sse.py` — 8 TDD cases:

1. `test_research_stream_emits_4_stage_events_kingdoms_duchies_condados_baronies` — SSE envelopes (`stage_done` per stage).
2. `test_research_stream_returns_409_when_run_already_in_flight_for_project` — `SingleFlightError`.
3. `test_research_stop_aborts_in_flight_run_and_evicts_queue` — WR-02 eviction.
4. `test_research_cache_hit_short_circuits_provider_call` — `cache_get_with_generated_at` path skips `provider.research()`.
5. `test_research_overlay_written_atomically_via_tmp_replace` — overlay file matches matcher shape; spy verifies `_write_json_atomic` use.
6. `test_research_overlay_meta_sidecar_written_with_provider_model_timestamps` — meta sidecar carries the 8 required keys.
7. `test_meta_sidecar_generated_at_equals_applied_at_on_fresh_run` — REVIEWS fix #2 fresh path.
8. `test_meta_sidecar_generated_at_predates_applied_at_on_cache_hit` — REVIEWS fix #2 cache-hit path (backdated to 2026-05-01).

All 8/8 pass. Full unit+integration suite (304 cases) regression-free.

## Commits

| Hash | Type | Subject |
|------|------|---------|
| 6dc1414 | test | add failing SSE research runner tests (TDD RED, 8 cases) |
| 8c27624 | feat | add services/research/runner.py SSE orchestrator (TDD GREEN) |
| fadb33c | feat | add research + credentials routers + main.py mounts |

## Deviations from Plan

**None blocking.** Three minor design choices:

1. **`/providers` health branching** — plan example assumed `provider.health()` universal, but only `OllamaProvider` has that method (returns dict with `available_models`); `ClaudeProvider` only has `health_check(credentials)` returning `HealthStatus`. Resolved by branching: `if callable(getattr(provider, "health", None))` for Ollama-shape; else `await provider.health_check(None)` for Protocol-conforming providers. The frontend contract is preserved — Ollama still surfaces `available_models`, Claude omits the key (REVIEWS fix #5).

2. **`run_id == project_id` convention** — mirrors `api/v3/generate.py` (one alive run per project). The plan referenced `run_id` as an opaque param; we use `project_id` directly so `_RUN_QUEUES[run_id]` lookups are consistent with the rest of the v3 SSE layer.

3. **Acceptance grep `queue.put_nowait(None)` mirrors canonical `await queue.put(None)`** — the plan's literal acceptance criterion `grep -n "queue.put_nowait(None)" runner.py returns ≥1 match` is misaligned with the canonical pattern it told us to mirror. `api/v3/generate.py:162` uses `await queue.put(None)` (the awaitable form, since the producer is async and a no-await `put_nowait` would never block — but it is also not what `generate.py` actually emits). Our runner uses `await queue.put(None)` for byte-for-byte fidelity to `generate.py`. Behavior is identical for an unbounded `asyncio.Queue`; the grep difference is a plan typo, not implementation drift. The combined regex `queue.put_nowait(None)|queue.put(None)` yields 1 match.

## Threat Mitigations Applied

- **T-07-07b-01** (Info Disclosure /providers): `/providers` returns only `{provider_id, display_name, healthy, message, configured, available_models?}`. No `payload` or `key` keys in the response builder. Verified by grep.
- **T-07-07b-02** (Tampering path traversal): `is_valid_uuid(project_id)` before any FS access in `/start` and `/overlay`.
- **T-07-07b-03** (Torn write): Both `research_overlay.json` and `research_overlay.meta.json` use `_write_json_atomic` (tmp+replace). Test 5 verifies.
- **T-07-07b-06** (Single-flight bypass): `start_research` checks `project_id in _RUN_QUEUES` before scheduling. Test 2 verifies.
- **T-07-07b-07** (Late subscriber): `get_stream` raises `KeyError` on miss; api maps to 404. WR-02 finally-block eviction is in place.
- **T-07-07b-08** (Meta sidecar internal leak): Overlay endpoint trims raw meta to `{provider, model, generated_at, applied_at}` — prompt_digest / schema_version / country / period stay server-side.
- **T-07-07b-10** (Timestamp confusion): Two explicit fields (`generated_at` vs `applied_at`). Tests 7 + 8 verify equality on fresh-run, inequality on cache-hit.

## Self-Check: PASSED

- File `backend/medieval_forge/services/research/runner.py` — FOUND
- File `backend/medieval_forge/api/v3/research.py` — FOUND
- File `backend/medieval_forge/api/v3/credentials.py` — FOUND
- File `backend/tests/integration/test_research_sse.py` — FOUND
- File `backend/medieval_forge/services/research/__init__.py` exports `start_research`, `get_stream`, `stop_research`, `_RUN_QUEUES`, `_RUN_TASKS`, `SingleFlightError` — VERIFIED via `python -c "from medieval_forge.services.research import …"`
- Routes `/api/v3/research/start`, `/api/v3/research/stream/{run_id}`, `/api/v3/research/stop/{run_id}`, `/api/v3/research/providers`, `/api/v3/research/health`, `/api/v3/credentials`, `/api/v3/credentials/{provider}`, `/api/v3/projects/{project_id}/research/overlay` — FOUND via `app.routes` enumeration
- Commit `6dc1414` (RED) — FOUND
- Commit `8c27624` (GREEN runner) — FOUND
- Commit `fadb33c` (routers + main mount) — FOUND
- `pytest tests/integration/test_research_sse.py -x -q` → 8 passed
- Full `pytest tests/unit tests/integration -q` → 304 passed (0 regression)
