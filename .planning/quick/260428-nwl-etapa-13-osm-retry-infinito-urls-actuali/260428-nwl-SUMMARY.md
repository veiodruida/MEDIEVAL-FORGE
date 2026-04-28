---
phase: quick-260428-nwl
plan: 01
subsystem: ingest
tags: [osm, retry, sse, abort, frontend, backend]
dependency_graph:
  requires: []
  provides: [osm-infinite-retry, stop-event-plumbing, abort-controller-stop]
  affects: [ingest_osm, ingest_runner, api/ingest, client.ts, ProjectDetail]
tech_stack:
  added: []
  patterns: [asyncio.Event stop_event, AbortController signal, SSE [Tentativa N] messages]
key_files:
  created:
    - backend/tests/services/test_ingest_osm.py
    - frontend/src/api/__tests__/useIngestStream.test.tsx
  modified:
    - backend/medieval_forge/services/ingest_osm.py
    - backend/medieval_forge/services/ingest_runner.py
    - backend/medieval_forge/api/ingest.py
    - frontend/src/api/client.ts
    - frontend/src/pages/ProjectDetail.tsx
decisions:
  - Kept _post_query function name unchanged (plan suggested optional rename to _post_query_infinite; kept for minimal churn and test compat)
  - Backoff uses min(30, 5*attempt) with asyncio.wait_for(stop_event.wait(), timeout=wait_s) so stop_event fires immediately even during sleep
  - asyncio.CancelledError caught BEFORE bare Exception in run_ingest so cancellation message differs from generic error
  - Test 4 uses distinct signal identity check instead of vi.spyOn(AbortController) — spying on native class constructor causes "cannot invoke without new" in vitest tinyspy
metrics:
  duration: ~25 min
  completed: 2026-04-28
  tasks_completed: 2
  tasks_total: 3
  files_changed: 7
  tests_added: 9
  tests_before_backend: 267
  tests_after_backend: 272
  tests_before_frontend: 222
  tests_after_frontend: 226
---

# Phase quick-260428-nwl Plan 01: Etapa 13 — OSM Infinite Retry + Parar Ingestão Summary

**One-liner:** OSM ingest now cycles 3 verified-live Overpass mirrors (private.coffee replaces dead openstreetmap.ru) in an infinite retry loop with stop_event cancellation plumbed end-to-end from frontend AbortController to backend asyncio.Event.

## What Was Built

### Endpoint List Update

`OVERPASS_ENDPOINTS` in `ingest_osm.py` now contains exactly:
- `https://overpass-api.de/api/interpreter`
- `https://overpass.private.coffee/api/interpreter`
- `https://overpass.kumi.systems/api/interpreter`

Removed: `overpass.openstreetmap.ru` (dead mirror).

### Backend — Infinite Retry Loop

`_post_query` rewritten from a single-pass for-loop to a `while not stop_event.is_set()` infinite loop:
- Cycles endpoints via `OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]`
- Emits `[Tentativa N] {endpoint} — aguardando resposta...` SSE message per attempt
- On 5xx/retryable: emits `[Tentativa N] {endpoint} retornou {status}. Aguardando {wait}s...`, sleeps `min(30, 5*attempt)` seconds using `asyncio.wait_for(stop_event.wait(), timeout=...)` (immediately interruptible by stop)
- On network error: emits `[Tentativa N] Falha de rede ...` and continues immediately
- On success: emits `[Tentativa N] {endpoint} — sucesso ({N} elementos).`
- When stop_event set: raises `asyncio.CancelledError("ingest stopped by user")`

### Backend — stop_event Plumbing

Stop event threaded from API layer to inner loop:
- `_post_query`: new `stop_event: asyncio.Event | None = None` keyword param (default creates never-set Event for backward compat)
- `fetch_municipalities`: new `stop_event` keyword param forwarded to `_post_query`
- `run_ingest` (ingest_runner.py): new `stop_event` param forwarded to `fetch_municipalities`; catches `asyncio.CancelledError` before bare `Exception` handler, emits "Cancelado pelo usuário."
- `_sse_generator` (api/ingest.py): creates `stop_event = asyncio.Event()` before task creation; finally block calls `stop_event.set()` BEFORE `task.cancel()` fallback

### Frontend — AbortController in useIngestStream

`client.ts` changes:
- `useRef<AbortController | null>` added (`abortRef`)
- `stop()` callback calls `abortRef.current?.abort()`
- `start()` creates `new AbortController()` at entry, assigns to `abortRef.current`, passes `signal: controller.signal` to `fetch()`
- `catch` block filters `AbortError`: only calls `setError` when `err.name !== 'AbortError'`
- `finally` block clears `abortRef.current = null` (GC + ensures next `start()` gets fresh controller)
- `IngestStreamHandle` interface: added `stop: () => void`

### Frontend — "Parar ingestão" Button

`ProjectDetail.tsx`, case 1 footer (OSM step):
```tsx
{ingest.isStreaming && (
  <Button color="red" variant="soft" onClick={() => ingest.stop()}>
    Parar ingestão
  </Button>
)}
```
Renders alongside the OSM CTA button only while `ingest.isStreaming` is true.

## Test Delta

| Suite | Before | After | Added |
|-------|--------|-------|-------|
| Backend (`pytest`) | 267 | 272 | 5 |
| Frontend (`vitest`) | 222 | 226 | 4 |

### New Backend Tests (backend/tests/services/test_ingest_osm.py)

1. `test_overpass_endpoints_are_three_live_mirrors` — validates endpoint list contents
2. `test_post_query_retries_past_three_endpoints_then_stops` — loop cycles past 3 until stop_event set
3. `test_post_query_honours_pre_set_stop_event` — pre-set event causes immediate CancelledError, 0 HTTP calls
4. `test_post_query_succeeds_on_second_attempt` — 504→200 path; SSE has [Tentativa 1] and [Tentativa 2]
5. `test_sse_generator_sets_stop_event_on_client_disconnect` — generator aclose() triggers stop_event.set()

### New Frontend Tests (frontend/src/api/__tests__/useIngestStream.test.tsx)

1. Returns object with `stop` function (type guard)
2. `stop()` while streaming: AbortError filtered, `error` stays null
3. After `stop()`, `isStreaming` = false; subsequent `start()` works
4. `start()` after `stop()` passes a fresh signal (distinct AbortSignal instances verified)

## Deviations from Plan

### Auto-fixed Issues

None — implementation matched plan exactly.

### Intentional Deviations

**1. Kept `_post_query` function name unchanged**
- Plan noted rename to `_post_query_infinite` was optional
- Kept original name to minimize churn and preserve any external test references

**2. Test 4 uses signal identity instead of AbortController spy**
- `vi.spyOn(globalThis, 'AbortController')` causes `TypeError: Class constructor cannot be invoked without 'new'` in vitest's tinyspy mock layer
- Instead: two fetch calls collect their signals; test verifies `signals[0] !== signals[1]` (distinct instances) and `signals[0].aborted === true` (old one was aborted, confirming a new controller was created for the second call)
- Test is semantically equivalent and arguably stronger (checks actual abort state)

## Known Stubs

None — all functionality is wired end-to-end.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary changes introduced.

## Self-Check

### Files Exist
- backend/tests/services/test_ingest_osm.py: FOUND
- frontend/src/api/__tests__/useIngestStream.test.tsx: FOUND
- backend/medieval_forge/services/ingest_osm.py: FOUND (modified)
- frontend/src/api/client.ts: FOUND (modified)
- frontend/src/pages/ProjectDetail.tsx: FOUND (modified)

### Commits
- 7afe815: test(quick-260428-nwl-01): RED backend tests
- 9759090: feat(quick-260428-nwl-01): GREEN backend implementation
- fca0f08: test(quick-260428-nwl-02): RED frontend tests
- 6978f84: feat(quick-260428-nwl-02): GREEN frontend implementation

## Self-Check: PASSED
