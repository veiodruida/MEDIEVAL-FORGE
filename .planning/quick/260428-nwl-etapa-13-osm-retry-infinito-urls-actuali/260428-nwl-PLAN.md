---
phase: quick-260428-nwl
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/ingest_osm.py
  - backend/medieval_forge/services/ingest_runner.py
  - backend/medieval_forge/api/ingest.py
  - frontend/src/api/client.ts
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
requirements:
  - QUICK-260428-NWL
must_haves:
  truths:
    - "OSM ingest cycles indefinitely through 3 verified-live Overpass mirrors instead of failing after one pass"
    - "User can click 'Parar ingestão' to abort the SSE stream cleanly (no error toast)"
    - "Each retry attempt streams an [Tentativa N] message naming the endpoint and outcome"
    - "Backend producer task exits within ~1s of client disconnect (no zombie tasks)"
  artifacts:
    - path: "backend/medieval_forge/services/ingest_osm.py"
      provides: "Updated OVERPASS_ENDPOINTS list (3 live mirrors); _post_query loops infinitely while stop_event not set"
      contains: "overpass.private.coffee"
    - path: "backend/medieval_forge/api/ingest.py"
      provides: "_sse_generator owns asyncio.Event stop_event; sets it in finally; passes through run_ingest"
      contains: "stop_event"
    - path: "frontend/src/api/client.ts"
      provides: "useIngestStream exposes stop(); IngestStreamHandle type updated; AbortController wired into fetch"
      contains: "AbortController"
    - path: "frontend/src/pages/ProjectDetail.tsx"
      provides: "'Parar ingestão' button rendered while ingest.isStreaming"
      contains: "Parar"
  key_links:
    - from: "frontend/src/api/client.ts"
      to: "backend SSE stream"
      via: "AbortController.signal on fetch — abort closes connection"
      pattern: "controller\\.abort"
    - from: "backend/medieval_forge/api/ingest.py finally block"
      to: "ingest_osm._post_query loop"
      via: "stop_event.set() propagated through run_ingest kwarg"
      pattern: "stop_event\\.set"
    - from: "backend/medieval_forge/services/ingest_osm.py"
      to: "Overpass mirrors"
      via: "while not stop_event.is_set(): cycle endpoints with backoff"
      pattern: "while not stop_event"
---

<objective>
Etapa 13 — substituir endpoint Overpass morto (`overpass.openstreetmap.ru`) pelas 3 instâncias verificadas live (overpass-api.de, private.coffee, kumi.systems), trocar o retry "uma passada" por loop infinito com backoff bounded, e adicionar botão "Parar ingestão" no frontend que aborta o SSE via AbortController.

Purpose: Hoje a ingestão OSM falha rapidamente quando os mirrors estão sobrecarregados (504/429 são comuns) e força o usuário a re-disparar manualmente. O loop infinito + botão Parar inverte o controle: a ingestão tenta para sempre até que o usuário decida parar OU um mirror responda com sucesso.

Output: OSM resiliente a outages temporários de mirrors, com cancelamento limpo end-to-end (frontend AbortController → backend stop_event → producer loop exit).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260428-nwl-etapa-13-osm-retry-infinito-urls-actuali/260428-nwl-RESEARCH.md
@backend/medieval_forge/services/ingest_osm.py
@backend/medieval_forge/services/ingest_runner.py
@backend/medieval_forge/api/ingest.py
@frontend/src/api/client.ts
@frontend/src/pages/ProjectDetail.tsx

<interfaces>
<!-- Existing contracts the executor must preserve -->

run_ingest signature (ingest_runner.py:38) — ADD stop_event kwarg:
```python
async def run_ingest(
    project_id: str,
    source: str,
    country: str,
    queue: asyncio.Queue[str | None],
    db_session_factory: async_sessionmaker | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    clip_iso_codes: list[str] | None = None,
    stop_event: asyncio.Event | None = None,   # NEW
) -> None
```

fetch_municipalities signature (ingest_osm.py:290) — ADD stop_event kwarg (keyword-only):
```python
async def fetch_municipalities(
    country_iso: str,
    queue: asyncio.Queue[str | None],
    *,
    bbox: ... = None,
    clip_iso_codes: ... = None,
    client_factory: ... = None,
    stop_event: asyncio.Event | None = None,   # NEW
) -> dict[str, Any]
```

IngestStreamHandle (client.ts:197) — ADD stop:
```typescript
export interface IngestStreamHandle {
  lines: string[]
  start: (source: 'wikidata' | 'osm') => Promise<void>
  stop: () => void              // NEW
  isStreaming: boolean
  error: Error | null
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Backend — infinite retry loop + stop_event plumbing</name>
  <files>
    backend/medieval_forge/services/ingest_osm.py,
    backend/medieval_forge/services/ingest_runner.py,
    backend/medieval_forge/api/ingest.py,
    backend/tests/services/test_ingest_osm.py
  </files>
  <behavior>
    - Test 1: OVERPASS_ENDPOINTS contains exactly the 3 live mirrors (overpass-api.de, overpass.private.coffee, overpass.kumi.systems) and does NOT contain overpass.openstreetmap.ru or maps.mail.ru.
    - Test 2: When all mirrors return 504, `_post_query` keeps cycling (attempt counter increments past 3) until `stop_event.is_set()` is true; then it raises asyncio.CancelledError.
    - Test 3: When stop_event is set BEFORE the first iteration, `_post_query` raises asyncio.CancelledError immediately without making any HTTP call.
    - Test 4: When the second attempt succeeds (mock 504 → 200), `_post_query` returns the JSON payload and pushes `[Tentativa 1]` and `[Tentativa 2]` SSE messages to the queue.
    - Test 5: On client disconnect (simulated via cancelling the StreamingResponse generator), `_sse_generator`'s finally block calls `stop_event.set()` and awaits the producer task to completion.
  </behavior>
  <action>
    Step 1 — `ingest_osm.py`:
    - Replace OVERPASS_ENDPOINTS (lines 33-38) with the 3 verified live endpoints (per RESEARCH §1):
      ```python
      OVERPASS_ENDPOINTS: list[str] = [
          "https://overpass-api.de/api/interpreter",
          "https://overpass.private.coffee/api/interpreter",
          "https://overpass.kumi.systems/api/interpreter",
      ]
      ```
    - Rewrite `_post_query` (lines 246-287) to loop infinitely while `stop_event` is not set, cycling endpoints via `OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]`. Add `stop_event: asyncio.Event | None = None` as new keyword-only param; default `stop_event = stop_event or asyncio.Event()` so existing callers without the kwarg still work (they get a never-set Event = infinite retry, which matches new desired behavior).
    - On retryable HTTP status (codes already in `retryable` set + `>= 500`): emit `data: [Tentativa N] {endpoint} retornou {status}. Aguardando {wait}s...\n\n`, sleep `min(30, 5 * attempt)` seconds via `await asyncio.sleep(...)` (which is cancellable), then `continue`.
    - On `httpx.TimeoutException | httpx.ConnectError`: emit `data: [Tentativa N] Falha de rede ({exc.__class__.__name__}) em {endpoint}. Tentando próximo...\n\n` and continue immediately (next endpoint in cycle, no extra sleep).
    - On success (2xx): emit `data: [Tentativa N] {endpoint} — sucesso ({len(payload['elements'])} elementos).\n\n` and return payload.
    - When loop exits because stop_event was set: `raise asyncio.CancelledError("ingest stopped by user")`.
    - Wrap the `client.post(...)` with `asyncio.wait_for(client.post(...), timeout=_TIMEOUT_S)` per RESEARCH Pitfall 1, so disconnect cancellation propagates cleanly. Catch `asyncio.TimeoutError` and treat as a retryable timeout (same as TimeoutException).
    - Update `fetch_municipalities` signature to accept `stop_event` keyword-only param and forward it to `_post_query` at line 327.

    Step 2 — `ingest_runner.py`:
    - Add `stop_event: asyncio.Event | None = None` to `run_ingest` signature (after `clip_iso_codes`).
    - Forward to `ingest_osm.fetch_municipalities` call (line 65-67): add `stop_event=stop_event`.
    - For wikidata branch leave unchanged (Wikidata path is fast-fail; stop_event not threaded there per scope).
    - In the outer `try/except`: catch `asyncio.CancelledError` separately BEFORE the bare `Exception` handler — emit `data: Cancelado pelo usuário.\n\n`, set status to `error_ingesting` (or a new "cancelled" state — use `error_ingesting` for now since DB schema lacks a cancelled state), then re-raise so the caller knows it was a cancellation. Actually: do NOT re-raise — the producer must still put None sentinel in finally. Just emit the cancelled message and let finally run.

    Step 3 — `api/ingest.py`:
    - In `_sse_generator` (lines 30-58): create `stop_event = asyncio.Event()` before `asyncio.create_task(...)`. Pass `stop_event=stop_event` to `run_ingest`.
    - In the `finally` block (lines 51-58): call `stop_event.set()` BEFORE the `task.cancel()` fallback. The set lets the producer exit gracefully (preferred); the cancel is the fallback if it ignored the event.

    Step 4 — Tests in `backend/tests/services/test_ingest_osm.py`:
    - Add the 5 tests above. Mock `client_factory` to return an httpx.MockTransport-backed AsyncClient that returns canned 504s then a 200, OR use a custom factory returning a stub client whose `.post` is an AsyncMock with `side_effect=[Mock(status_code=504,...), Mock(status_code=504,...), Mock(status_code=200,json=lambda:{...})]`.
    - For Test 3 (stop before first iter): pass a pre-set `asyncio.Event` and assert `pytest.raises(asyncio.CancelledError)` and that the mocked client was never called.
    - For Test 5 (disconnect propagation): use a fake queue and verify the integration via `_sse_generator`. May require a small async helper that consumes one message then raises `GeneratorExit` to simulate client disconnect.

    Per RESEARCH Pitfall 5: search test files for any direct reference to `_post_query` and update if signature changed. We are NOT renaming the function — keep name `_post_query` to minimize churn (RESEARCH suggested rename to `_post_query_infinite` but that's optional; keeping the name preserves test compat).
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/services/test_ingest_osm.py -x -v 2>&1 | tail -40</automated>
  </verify>
  <done>
    All 5 new tests pass. Existing ingest_osm tests still pass. OVERPASS_ENDPOINTS contains the 3 live mirrors. `_post_query` loops while `stop_event` is unset. `_sse_generator` calls `stop_event.set()` in finally.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Frontend — AbortController in useIngestStream + "Parar ingestão" button</name>
  <files>
    frontend/src/api/client.ts,
    frontend/src/pages/ProjectDetail.tsx,
    frontend/src/api/__tests__/useIngestStream.test.tsx
  </files>
  <behavior>
    - Test 1: `useIngestStream` returns an object with `stop` function (type guard).
    - Test 2: Calling `stop()` while streaming triggers `AbortController.abort()`, the fetch promise rejects with `AbortError`, and `setError` is NOT called (AbortError filtered out).
    - Test 3: After `stop()`, `isStreaming` becomes false and `abortRef` is reset to null so a subsequent `start()` works.
    - Test 4: `start()` after a previous `stop()` creates a NEW AbortController (no stale signal reused).
  </behavior>
  <action>
    Step 1 — `frontend/src/api/client.ts`:
    - Update import from 'react' (line 195): add `useRef`.
    - Update `IngestStreamHandle` interface (line 197): add `stop: () => void` between `start` and `isStreaming`.
    - Inside `useIngestStream`:
      - Add `const abortRef = useRef<AbortController | null>(null)` after the state hooks.
      - Add `const stop = useCallback(() => { abortRef.current?.abort() }, [])` before `start`.
      - In `start`: create `const controller = new AbortController()` at the very top, assign `abortRef.current = controller`. Pass `signal: controller.signal` in the `fetch(...)` init.
      - In the `catch (e)` block: filter AbortError — `if ((e as Error).name !== 'AbortError') setError(e as Error)` (per RESEARCH Pitfall 3).
      - In the `finally` block: set `abortRef.current = null` (allow GC + signal subsequent start gets a fresh controller).
    - Return value: include `stop` in the returned object.

    Step 2 — `frontend/src/pages/ProjectDetail.tsx`:
    - Find the OSM CTA in `renderStepContent()` case 1 (the "1. OSM com polígonos (recomendado)" Button). Identify the `ingest` handle from `useIngestStream(project?.id)` already in scope.
    - Render a sibling `<Button>` next to (or right below) the OSM button, conditional on `ingest.isStreaming`:
      ```tsx
      {ingest.isStreaming && (
        <Button color="red" variant="soft" onClick={() => ingest.stop()}>
          Parar ingestão
        </Button>
      )}
      ```
    - Use Radix Themes Button. Place inside the same Flex/Stack container that holds the OSM CTA so layout is consistent.

    Step 3 — Tests in `frontend/src/api/__tests__/useIngestStream.test.tsx`:
    - Use `@testing-library/react` `renderHook` + `act`.
    - Mock global `fetch` to return a `Response` with a `ReadableStream` body that pulls one chunk and then awaits indefinitely (so the test can call `stop()` mid-stream).
    - Test 2: `await act(() => result.current.start('osm'))` (don't await — just kick off), then `act(() => result.current.stop())`. Assert `result.current.error === null` and `result.current.isStreaming === false` (after microtask flush).
    - Test 4: After stop, call start again, assert a new `AbortController` instance was constructed (spy on `globalThis.AbortController`).
  </action>
  <verify>
    <automated>cd frontend && npm test -- --run src/api/__tests__/useIngestStream.test.tsx 2>&1 | tail -30</automated>
  </verify>
  <done>
    All 4 frontend tests pass. `useIngestStream` exposes `stop`. ProjectDetail shows the red "Parar ingestão" button only while streaming. Existing frontend tests still pass (`npm test -- --run` green).
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Manual smoke test — start OSM ingest, hit Parar mid-stream, restart</name>
  <what-built>
    OSM ingest now cycles 3 live Overpass mirrors infinitely with [Tentativa N] progress messages, and the UI has a "Parar ingestão" button that aborts the SSE cleanly.
  </what-built>
  <how-to-verify>
    1. `medieval-forge start` (or equivalent dev command) → open the app, create/open an Iberia project.
    2. Click "1. OSM com polígonos (recomendado)" — observe the log panel.
    3. Confirm the first message references one of the 3 new endpoints (overpass-api.de, overpass.private.coffee, or overpass.kumi.systems). NO mention of `openstreetmap.ru`.
    4. While `[Tentativa 1] ... aguardando resposta` is visible, click "Parar ingestão".
    5. Expected:
       - Button "Parar ingestão" disappears.
       - The OSM CTA becomes clickable again.
       - No red error toast / no "AbortError" message in the log panel.
       - Backend logs (terminal) show no traceback, just the producer task ending cleanly.
    6. Click OSM CTA again → confirm a fresh ingest starts (new [Tentativa 1] line).
    7. Let one full cycle complete OR force-stop again to confirm idempotency.
  </how-to-verify>
  <resume-signal>Type "approved" or describe issues observed (e.g., "AbortError shown", "stop button stuck", "wrong endpoint")</resume-signal>
</task>

</tasks>

<verification>
- All backend tests pass: `cd backend && python -m pytest tests/services/test_ingest_osm.py -x`
- Full backend suite still green: `cd backend && python -m pytest -x`
- All frontend tests pass: `cd frontend && npm test -- --run`
- Manual smoke test (Task 3) approved by user
- `OVERPASS_ENDPOINTS` contains exactly: overpass-api.de, overpass.private.coffee, overpass.kumi.systems
- `useIngestStream` return type includes `stop: () => void`
</verification>

<success_criteria>
- OSM ingest no longer fails after one pass through endpoints — cycles indefinitely until success or user abort
- "Parar ingestão" button visible only while ingest.isStreaming, aborts via AbortController, no error toast on abort
- Backend producer exits within ~1s of frontend abort (no zombie tasks, verified by absence of warning logs)
- Retry messages use `[Tentativa N] {endpoint} ...` format (scannable in `<pre>` log panel)
- Bounded backoff (`min(30, 5*attempt)` seconds) between cycles when all mirrors return 5xx
- Existing tests still pass (no regressions)
</success_criteria>

<output>
After completion, create `.planning/quick/260428-nwl-etapa-13-osm-retry-infinito-urls-actuali/260428-nwl-SUMMARY.md` with: endpoints changed, retry loop pattern, AbortController integration, test count delta, and any deviations from RESEARCH.md (e.g., kept `_post_query` name instead of renaming).
</output>
