# Etapa 13: OSM Retry Infinito + URLs Actualizadas — Research

**Researched:** 2026-04-28
**Domain:** Overpass API mirrors, FastAPI SSE cancellation, AbortController pattern
**Confidence:** HIGH (mirrors verified via OSM wiki; SSE patterns verified via FastAPI official discussion; call chain verified from source)

---

## Summary

The current `ingest_osm.py` has a 3-endpoint list that includes one deprecated/redirected mirror (`overpass.openstreetmap.ru`) and tries each endpoint only once before failing. The task is to: (1) update the endpoint list with verified live mirrors, (2) change `_post_query` to loop infinitely through all mirrors until client disconnects, and (3) add a "Parar ingestão" button that aborts the SSE stream from the frontend.

**Primary recommendation:** Backend — infinite `while True` loop cycling through endpoints with `asyncio.wait_for` timeout + check a `stop_event` (`asyncio.Event`) that gets set when the generator's `finally` block fires (client disconnect). Frontend — expose a `stop()` function from `useIngestStream` that calls `abortController.abort()`, which closes the underlying fetch stream.

---

## 1. Verified Overpass Public Mirrors (2026)

Source: OSM Wiki `/wiki/Overpass_API#Public_Overpass_API_instances` fetched 2026-04-28. [VERIFIED: wiki.openstreetmap.org]

| Endpoint | Operator | Status (April 2026) | Notes |
|----------|----------|---------------------|-------|
| `https://overpass-api.de/api/interpreter` | FOSSGIS | LIVE | Main instance; 10k req/day limit guideline |
| `https://overpass.kumi.systems/api/interpreter` | Private.coffee | LIVE | Same infra as private.coffee; no rate limit |
| `https://overpass.private.coffee/api/interpreter` | Private.coffee | LIVE — user-confirmed | No rate limit; same cluster as kumi.systems |
| `https://maps.mail.ru/osm/tools/overpass/api/interpreter` | VK Maps | SUSPENDED since 2026-03-16 | Remove from list |
| `https://overpass.openstreetmap.ru/api/interpreter` | (Russia) | UNRELIABLE/DOWN | Current list already bad; remove |

**Recommended list (3 live global instances):**

```python
OVERPASS_ENDPOINTS: list[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
```

Note: `kumi.systems` and `private.coffee` are the same physical cluster — including both provides a different URL string for log visibility but they share capacity. This is acceptable for a local tool where endpoint diversity matters less than having verified-live URLs. [VERIFIED: overpass.kumi.systems resolves to Private.coffee]

---

## 2. Backend: Infinite Retry Loop + Client Disconnect Stop Signal

### How FastAPI SSE disconnect propagation works

FastAPI's `StreamingResponse` uses Starlette. When the HTTP client closes the connection:

- The ASGI server (uvicorn) will **cancel the response generator coroutine** by raising `asyncio.CancelledError` or `GeneratorExit` inside the `async for` / `yield` machinery.
- **Crucially:** This cancellation propagates to the `_sse_generator` async generator when uvicorn tries to yield the next chunk and the socket is gone. The `finally` block in `_sse_generator` IS reliably called. [VERIFIED: FastAPI discussions #3766, #8805]
- However, if the generator is blocked inside `await queue.get()` waiting for the producer task, the cancellation may not fire until the next `yield`. To make disconnect detection fast, the producer task must be stoppable.

### Pattern: stop_event + asyncio.Event

The cleanest pattern for "infinite retry until disconnected":

```python
# In _sse_generator — set stop_event in finally so the producer knows to exit
stop_event: asyncio.Event = asyncio.Event()
task = asyncio.create_task(
    run_ingest(..., stop_event=stop_event)
)
try:
    while True:
        msg = await queue.get()
        if msg is None:
            break
        yield msg
except (asyncio.CancelledError, GeneratorExit):
    pass
finally:
    stop_event.set()  # Signal producer to stop
    if not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
```

The producer (`run_ingest` → `_post_query`) checks `stop_event.is_set()` at the top of each retry iteration:

```python
async def _post_query_infinite(
    query: str,
    queue: asyncio.Queue[str | None],
    stop_event: asyncio.Event,
    client_factory,
) -> dict[str, Any]:
    attempt = 0
    while not stop_event.is_set():
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        attempt += 1
        await queue.put(f"data: [Tentativa {attempt}] {endpoint} — aguardando resposta...\n\n")
        try:
            async with _factory() as client:
                resp = await asyncio.wait_for(
                    client.post(endpoint, data={"data": query}, ...),
                    timeout=_TIMEOUT_S,
                )
                retryable = {406, 408, 429, 502, 503, 504}
                if resp.status_code >= 500 or resp.status_code in retryable:
                    wait = min(30, 5 * attempt)
                    await queue.put(
                        f"data: [Tentativa {attempt}] retornou {resp.status_code}. "
                        f"Aguardando {wait}s...\n\n"
                    )
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
        except asyncio.TimeoutError:
            await queue.put(f"data: [Tentativa {attempt}] Timeout em {endpoint}. Tentando próximo...\n\n")
            continue
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            await queue.put(
                f"data: [Tentativa {attempt}] Falha de rede ({exc.__class__.__name__}) em {endpoint}. "
                f"Tentando próximo...\n\n"
            )
            continue
    # stop_event was set — user clicked "Parar"
    raise asyncio.CancelledError("ingest stopped by user")
```

**Key: use `asyncio.wait_for` wrapping the httpx call** instead of httpx's built-in timeout. This ensures the timeout raises `asyncio.TimeoutError` which the loop can catch cleanly. With httpx timeout alone, the `asyncio.CancelledError` from disconnect can get swallowed inside httpx internals on some versions.

**Backoff:** Use bounded exponential backoff (`min(30, 5 * attempt)` seconds) between retries on the same endpoint cycle. This prevents hammering mirrors when all are down. [ASSUMED — specific backoff values are a discretion choice]

### Verified call chain (from source)

`ingest_runner.py` — `run_ingest()` signature confirmed: [VERIFIED: source read]

```python
async def run_ingest(
    project_id, source, country, queue, db_session_factory=None,
    bbox=None, clip_iso_codes=None,
) -> None:
```

It calls `ingest_osm.fetch_municipalities(country, queue, bbox=bbox, clip_iso_codes=clip_iso_codes)`.

`stop_event` must be added to:
1. `_sse_generator` (creates it, sets it in `finally`, passes to `run_ingest`)
2. `run_ingest` signature (new kwarg `stop_event: asyncio.Event | None = None`)
3. `ingest_osm.fetch_municipalities` (new kwarg `stop_event: asyncio.Event | None = None`)
4. `_post_query_infinite` (consumes it in the `while` check)

Using `asyncio.Event | None = None` with a fallback `stop_event = stop_event or asyncio.Event()` inside `_post_query_infinite` keeps all call sites backward-compatible and all existing tests passing without changes.

---

## 3. Frontend: AbortController + "Parar" Button

### Current state

`useIngestStream` in `client.ts` uses a raw `fetch` + `ReadableStream` reader loop. There is no abort path — `start()` runs until stream ends or error. The `IngestStreamHandle` type only exposes `{ lines, start, isStreaming, error }`.

### Pattern: AbortController ref

```typescript
export interface IngestStreamHandle {
  lines: string[]
  start: (source: 'wikidata' | 'osm') => Promise<void>
  stop: () => void          // NEW
  isStreaming: boolean
  error: Error | null
}

export function useIngestStream(projectId: string | undefined): IngestStreamHandle {
  const qc = useQueryClient()
  const [lines, setLines] = useState<string[]>([])
  const [isStreaming, setStreaming] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const abortRef = useRef<AbortController | null>(null)  // NEW

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const start = useCallback(
    async (source: 'wikidata' | 'osm') => {
      if (!projectId) return
      const controller = new AbortController()    // NEW
      abortRef.current = controller               // NEW
      setLines([])
      setError(null)
      setStreaming(true)
      try {
        const res = await fetch(
          `/api/projects/${projectId}/ingest?source=${source}`,
          { method: 'POST', signal: controller.signal },  // NEW
        )
        // ... existing reader loop unchanged ...
      } catch (e) {
        // AbortError is not a real error — user clicked "Parar"
        if ((e as Error).name !== 'AbortError') {
          setError(e as Error)
        }
      } finally {
        setStreaming(false)
        abortRef.current = null                           // NEW
        qc.invalidateQueries({ queryKey: ['projects', projectId] })
        qc.invalidateQueries({ queryKey: ['projects'] })
      }
    },
    [projectId, qc],
  )

  return { lines, start, stop, isStreaming, error }
}
```

When `controller.abort()` is called:
- The `fetch()` rejects with `AbortError` if still connecting, OR
- The `reader.read()` inside the while loop rejects with `AbortError`, exiting the stream.
- On the backend, the HTTP connection closes → uvicorn detects disconnect → `finally` in `_sse_generator` fires → `stop_event.set()` → producer loop exits cleanly.

[VERIFIED: AbortController + fetch is the standard Web API pattern; MDN/WHATWG spec]

### ProjectDetail.tsx changes

In `renderStepContent()`, case 1 (OSM step), add the stop button next to the existing OSM button:

```tsx
<Button
  onClick={() => ingest.start('osm')}
  disabled={ingest.isStreaming}
>
  {ingest.isStreaming ? 'Ingerindo…' : '1. OSM com polígonos (recomendado)'}
</Button>

{ingest.isStreaming && (
  <Button
    color="red"
    variant="soft"
    onClick={() => ingest.stop()}
  >
    Parar ingestão
  </Button>
)}
```

The `ingest.stop` reference is new — `useIngestStream` return type must be updated first (TypeScript will enforce this at all call sites).

---

## 4. SSE Message Format for Retry Progress

Current format: `data: Tentando endpoint: {url}...\n\n`

Recommended format with attempt number prefix:

```
[Tentativa 1] overpass-api.de — aguardando resposta...
[Tentativa 1] overpass-api.de — retornou 504. Aguardando 5s...
[Tentativa 2] overpass.private.coffee — aguardando resposta...
[Tentativa 2] overpass.private.coffee — sucesso (287 elementos).
```

The `[Tentativa N]` prefix makes it scannable in the `<pre>` log panel. The existing `setLines` in `useIngestStream` strips the `data: ` prefix, so lines render as plain text — the bracket format works without any frontend changes beyond adding the stop button.

---

## 5. Files to Change

| File | Change |
|------|--------|
| `backend/medieval_forge/services/ingest_osm.py` | Update `OVERPASS_ENDPOINTS` list; rename `_post_query` → `_post_query_infinite`; add `stop_event: asyncio.Event \| None` param; change to `while not stop_event.is_set()` loop |
| `backend/medieval_forge/api/ingest.py` | Create `stop_event` in `_sse_generator`; pass to `run_ingest`; set in `finally` |
| `backend/medieval_forge/services/ingest_runner.py` | Add `stop_event: asyncio.Event \| None = None` to `run_ingest`; thread to `fetch_municipalities` |
| `backend/medieval_forge/services/ingest_osm.py` | Add `stop_event` to `fetch_municipalities` signature; thread to `_post_query_infinite` |
| `frontend/src/api/client.ts` | Add `abortRef`, `stop()` to `useIngestStream`; update `IngestStreamHandle` type |
| `frontend/src/pages/ProjectDetail.tsx` | Add "Parar ingestão" button when `isStreaming=true` |

---

## Common Pitfalls

### Pitfall 1: httpx timeout vs asyncio.wait_for inside infinite loop
**What goes wrong:** httpx's `timeout=` config raises `httpx.TimeoutException`, which is caught and the loop continues. But if `asyncio.CancelledError` arrives during the httpx request (from disconnect), it can get swallowed inside httpx's internals.
**How to avoid:** Wrap the `client.post(...)` call with `asyncio.wait_for(..., timeout=_TIMEOUT_S)` and let httpx have no internal timeout, OR keep httpx timeout but also check `stop_event.is_set()` immediately after the exception handler.

### Pitfall 2: kumi.systems = private.coffee same cluster
**What goes wrong:** Both endpoints failing simultaneously because they share infra — looks like 2 different failures but it's actually one outage.
**How to avoid:** Log endpoint hostname clearly. In practice acceptable for a local tool since the cycle will just try `overpass-api.de` next.

### Pitfall 3: AbortError treated as real error
**What goes wrong:** User clicks "Parar", `AbortError` propagates to the `catch` block, `setError` fires, and a red "Erro: AbortError" message appears in the UI.
**How to avoid:** `if ((e as Error).name !== 'AbortError') setError(e as Error)` — already shown in the pattern above.

### Pitfall 4: IngestStreamHandle type mismatch
**What goes wrong:** `stop` added to the return value of `useIngestStream` but consumers (ProjectDetail) destructure only the old fields — TypeScript won't error, but the stop function won't be available without explicit destructuring.
**How to avoid:** Update `IngestStreamHandle` interface first; TypeScript will flag any call sites that haven't destructured `stop`.

### Pitfall 5: Existing tests pass `_post_query` by name
**What goes wrong:** Renaming `_post_query` to `_post_query_infinite` breaks any test that monkeypatches or imports it directly.
**How to avoid:** Search test files for `_post_query` references before renaming; update or keep an alias.

---

## Assumptions Log

| # | Claim | Risk if Wrong |
|---|-------|---------------|
| A1 | Backoff of `min(30, 5 * attempt)` seconds between retries is acceptable UX | If too slow, reduce to `min(10, 2 * attempt)` |

All other claims verified from source or official docs.

---

## Sources

- [OSM Wiki — Public Overpass API Instances](https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances) — verified 2026-04-28
- [Private.coffee Overpass](https://overpass.private.coffee) — user-confirmed functional
- [overpass.kumi.systems](https://overpass.kumi.systems) — same infra as private.coffee
- [FastAPI Discussion #8805 — client disconnect](https://github.com/fastapi/fastapi/discussions/8805) — CancelledError propagation behaviour
- [FastAPI Discussion #7572 — stop streaming on disconnect](https://github.com/fastapi/fastapi/discussions/7572) — finalizer pattern
- MDN Web Docs — AbortController (standard Web API, HIGH confidence)
- `backend/medieval_forge/services/ingest_runner.py` — call chain verified from source
- `backend/medieval_forge/api/ingest.py` — `_sse_generator` structure verified from source
