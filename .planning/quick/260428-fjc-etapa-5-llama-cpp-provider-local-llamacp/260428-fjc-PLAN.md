---
phase: quick-260428-fjc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/llm/llamacpp.py
  - backend/medieval_forge/services/llm/registry.py
  - backend/tests/services/test_llamacpp_provider.py
  - frontend/src/components/research/AuthSetupSheet.tsx
  - frontend/src/api/research.ts
autonomous: true
requirements:
  - quick-260428-fjc
must_haves:
  truths:
    - "registry.PROVIDERS contains key 'llamacpp' bound to a LlamaCppProvider instance"
    - "LlamaCppProvider.health_check(None) returns HealthStatus without raising; healthy reflects GET /v1/models reachability"
    - "LlamaCppProvider.research POSTs to {base_url}/v1/chat/completions with messages=[system,user] and stream=True; parses streamed JSON via parse_research_json"
    - "AuthSetupSheet shows a Llama.cpp panel (base_url input + 'Testar conexão' button + status badge) when sheetOpenForProvider==='llamacpp'"
    - "All 220 existing backend tests still pass after changes"
  artifacts:
    - path: "backend/medieval_forge/services/llm/llamacpp.py"
      provides: "LlamaCppProvider class (provider_id, display_name, auth_methods=[NoAuth()], DEFAULT_BASE_URL, health_check, research)"
    - path: "backend/medieval_forge/services/llm/registry.py"
      provides: "PROVIDERS dict with 'llamacpp' entry"
      contains: "LlamaCppProvider"
    - path: "backend/tests/services/test_llamacpp_provider.py"
      provides: "4 unit tests with mocked httpx (descriptive names per project convention)"
    - path: "frontend/src/components/research/AuthSetupSheet.tsx"
      provides: "isLlamacpp branch with base_url field + connection test + status badge"
  key_links:
    - from: "backend/medieval_forge/services/llm/registry.py"
      to: "backend/medieval_forge/services/llm/llamacpp.py"
      via: "from .llamacpp import LlamaCppProvider"
      pattern: "from \\.llamacpp import LlamaCppProvider"
    - from: "backend/medieval_forge/services/llm/llamacpp.py"
      to: "backend/medieval_forge/services/llm/schemas.py"
      via: "parse_research_json for ResearchResult validation"
      pattern: "parse_research_json"
    - from: "frontend/src/components/research/AuthSetupSheet.tsx"
      to: "POST /api/research/credentials (or health endpoint) with provider='llamacpp' + base_url"
      via: "useStoreCredentialMutation / health probe"
      pattern: "llamacpp"
---

<objective>
Etapa 5 of the multi-provider/multi-model expansion (master plan: hazy-hatching-abelson, section C, lines 209-252). Add Llama.cpp as a local LLM provider so users with a llama.cpp server running on localhost:8080 can run research without an API key — same UX as the existing Ollama path, but talking to llama.cpp's OpenAI-compatible /v1/chat/completions endpoint.

Purpose: Etapa 4 (model_routing) already pre-registered "llamacpp" with the sentinel "(server-default)" model id. This etapa supplies the actual provider implementation, registers it, tests it, and exposes it in the AuthSetupSheet UI.

Output:
- backend/medieval_forge/services/llm/llamacpp.py with LlamaCppProvider class
- registry entry "llamacpp": LlamaCppProvider()
- 4 mocked-httpx unit tests in backend/tests/services/test_llamacpp_provider.py
- Llama.cpp panel in AuthSetupSheet (base_url default http://localhost:8080, Testar conexão, status badge)

Out of scope (DO NOT touch): research_runner.py, model_routing.py — Etapa 4 already integrated routing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md
@backend/medieval_forge/services/llm/ollama.py
@backend/medieval_forge/services/llm/openai.py
@backend/medieval_forge/services/llm/registry.py
@backend/medieval_forge/services/llm/base.py
@backend/medieval_forge/services/llm/model_routing.py
@backend/medieval_forge/services/llm/schemas.py
@backend/tests/services/test_llm_providers.py
@frontend/src/components/research/AuthSetupSheet.tsx

<interfaces>
<!-- Key contracts already established in the codebase. The executor must conform exactly. -->

LLMProvider Protocol (backend/medieval_forge/services/llm/base.py):
```python
@runtime_checkable
class LLMProvider(Protocol):
    provider_id: str
    display_name: str
    auth_methods: list[AuthMethod]   # AuthMethod = ApiKeyAuth | OAuthAuth | CliAuth | NoAuth

    async def health_check(self, credentials: dict | None) -> HealthStatus: ...
    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel: ...

class HealthStatus(BaseModel):
    healthy: bool
    message: str = ""

class NoAuth(BaseModel):
    type: Literal["none"] = "none"
```

Schemas helper (backend/medieval_forge/services/llm/schemas.py):
```python
from .schemas import parse_research_json, ResearchResult
# Lenient parser — used by OllamaProvider for ResearchResult to tolerate
# small models adding extra top-level keys. Use the same path here.
```

Existing pattern for streaming OpenAI-compatible /v1/chat/completions
(backend/medieval_forge/services/llm/openai.py):
```python
stream = await client.chat.completions.create(
    model=...,
    messages=[{"role": "system", "content": SYSTEM_PROMPT},
              {"role": "user",   "content": prompt}],
    response_format={"type": "json_schema",
                     "json_schema": {"name": "research_result",
                                     "schema": schema.model_json_schema(),
                                     "strict": True}},
    stream=True,
)
chunks: list[str] = []
async for chunk in stream:
    delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
    if delta:
        chunks.append(delta)
        if queue is not None:
            await queue.put(f"data: {delta}\n\n")
return schema.model_validate_json("".join(chunks))
```

Etapa 4 already wired (DO NOT MODIFY — model_routing.py:24):
```python
"llamacpp": {"low": "(server-default)", "medium": "(server-default)", "high": "(server-default)"},
```
This means: llama.cpp does NOT receive a `model` field in the chat/completions
body when the resolver returns "(server-default)" — the local llama-server
serves whatever model it was launched with. Provider must omit `model` in
that case (or pass it through if a real model id was provided).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement LlamaCppProvider + register + 4 mocked unit tests</name>
  <files>
    backend/medieval_forge/services/llm/llamacpp.py,
    backend/medieval_forge/services/llm/registry.py,
    backend/tests/services/test_llamacpp_provider.py
  </files>
  <behavior>
    Test 1 — `test_llamacpp_provider_health_check_calls_v1_models`:
      Mock httpx.AsyncClient.get to return SimpleNamespace(status_code=200, json=lambda: {"data":[{"id":"llama-3"}]}).
      Call provider.health_check(None). Assert HealthStatus(healthy=True) and that the URL was f"{DEFAULT_BASE_URL}/v1/models".

    Test 2 — `test_llamacpp_provider_health_check_handles_unreachable_server`:
      Mock httpx.AsyncClient.get to raise httpx.ConnectError("refused").
      Call provider.health_check(None). Assert HealthStatus(healthy=False) and message contains "Unreachable" or the error text. Must not raise.

    Test 3 — `test_llamacpp_provider_research_posts_to_v1_chat_completions_with_streaming`:
      Mock httpx.AsyncClient.stream to yield SSE chunks whose `data:` lines contain a valid ResearchResult JSON split across 2-3 chunks. Call provider.research("prompt", ResearchResult, {"base_url":"http://localhost:8080"}, queue=None). Assert: result is ResearchResult instance with kingdoms/duchies/condados/baronies populated; the URL was POST f"{base_url}/v1/chat/completions"; the body contained messages=[system,user] and stream=True; when model resolves to "(server-default)" the body does NOT include a `model` key (or includes None — adapt to implementation choice but assert the test matches it).

    Test 4 — `test_llamacpp_provider_research_uses_user_supplied_base_url_override`:
      Mock httpx.AsyncClient.stream as in Test 3. Call provider.research("prompt", ResearchResult, {"base_url":"http://10.0.0.5:9090"}, queue=None). Assert request URL begins with "http://10.0.0.5:9090/v1/chat/completions" (proves base_url override path).
  </behavior>
  <action>
    1. RED — Create `backend/tests/services/test_llamacpp_provider.py` with the 4 tests above. Use the same descriptive-name + mocked-httpx style as `test_llm_providers.py`. Import _VALID_PAYLOAD/_VALID_JSON shape from inline definition (do NOT cross-import from test_llm_providers.py — keep tests self-contained). Run pytest; all 4 must fail with ImportError or AttributeError on `LlamaCppProvider`.

    2. GREEN — Create `backend/medieval_forge/services/llm/llamacpp.py`:
       ```python
       """LlamaCppProvider — local llama-server via OpenAI-compatible /v1/chat/completions."""
       from __future__ import annotations
       import asyncio, json
       import httpx
       from pydantic import BaseModel
       from .base import HealthStatus, NoAuth
       from .schemas import parse_research_json, ResearchResult

       DEFAULT_BASE_URL = "http://localhost:8080"
       SYSTEM_PROMPT = "You are a historical-research assistant. Return JSON matching the schema."

       class LlamaCppProvider:
           provider_id = "llamacpp"
           display_name = "Llama.cpp (local)"
           auth_methods = [NoAuth()]
           DEFAULT_BASE_URL = DEFAULT_BASE_URL

           async def health_check(self, credentials):
               base_url = (credentials or {}).get("base_url", DEFAULT_BASE_URL)
               try:
                   async with httpx.AsyncClient(timeout=3.0) as client:
                       r = await client.get(f"{base_url}/v1/models")
                       if r.status_code == 200:
                           return HealthStatus(healthy=True, message=f"Reachable at {base_url}")
                       return HealthStatus(healthy=False, message=f"HTTP {r.status_code}")
               except Exception as exc:
                   return HealthStatus(healthy=False, message=f"Unreachable: {exc}")

           async def research(self, prompt, schema, credentials, queue):
               base_url = (credentials or {}).get("base_url", DEFAULT_BASE_URL)
               model = (credentials or {}).get("model")  # may be None or "(server-default)"
               body = {
                   "messages": [
                       {"role": "system", "content": SYSTEM_PROMPT},
                       {"role": "user",   "content": prompt},
                   ],
                   "response_format": {"type": "json_object"},
                   "stream": True,
               }
               if model and model != "(server-default)":
                   body["model"] = model

               chunks: list[str] = []
               async with httpx.AsyncClient(timeout=None) as client:
                   async with client.stream("POST", f"{base_url}/v1/chat/completions", json=body) as resp:
                       resp.raise_for_status()
                       async for line in resp.aiter_lines():
                           if not line or not line.startswith("data:"):
                               continue
                           payload = line[len("data:"):].strip()
                           if payload == "[DONE]":
                               break
                           try:
                               obj = json.loads(payload)
                           except json.JSONDecodeError:
                               continue
                           delta = (obj.get("choices",[{}])[0].get("delta",{}) or {}).get("content","")
                           if delta:
                               chunks.append(delta)
                               if queue is not None:
                                   await queue.put(f"data: {delta}\n\n")
               content = "".join(chunks)
               if schema is ResearchResult:
                   return parse_research_json(content)
               return schema.model_validate_json(content)
       ```

    3. Register in `backend/medieval_forge/services/llm/registry.py`: add `from .llamacpp import LlamaCppProvider` and `"llamacpp": LlamaCppProvider(),` to PROVIDERS dict (keep existing entries). Do NOT touch model_routing.py.

    4. Run pytest. The 4 new tests must pass. Run the full backend suite to confirm no regression among the 220 existing tests.

    Notes for the executor:
    - Match Ollama's resilience: health_check must NEVER raise — wrap in try/except.
    - Use `httpx` (already a project dep transitively via FastAPI/anthropic). If not directly imported elsewhere in services/llm, this is fine — it's a standard dep.
    - For mocking `client.stream(...)` use an async context manager that yields an object with an `aiter_lines()` async generator, plus a `raise_for_status()` no-op. See unittest.mock patterns or build a small fake class inline (see test_llm_providers.py _FakeStream pattern).
  </action>
  <verify>
    <automated>cd backend && pytest tests/services/test_llamacpp_provider.py -x -v && pytest tests/ -x -q</automated>
  </verify>
  <done>
    - 4 new tests pass with descriptive names
    - Full backend suite remains green (220 prior + 4 new = 224 passing, no skips except pre-existing)
    - registry.PROVIDERS["llamacpp"] is a LlamaCppProvider instance at import time
    - llamacpp.py file exists, ~60-90 lines, no `model` field sent when sentinel is "(server-default)"
  </done>
</task>

<task type="auto">
  <name>Task 2: AuthSetupSheet — Llama.cpp panel (base_url + Testar conexão + status badge)</name>
  <files>
    frontend/src/components/research/AuthSetupSheet.tsx,
    frontend/src/api/research.ts
  </files>
  <action>
    1. Open `frontend/src/components/research/AuthSetupSheet.tsx`. Add a new derived flag near `isOllama` (line 87):
       ```ts
       const isLlamacpp = provider?.provider_id === "llamacpp";
       ```

    2. Add local component state for llama.cpp inputs (next to apiKey state):
       ```ts
       const [llamacppBaseUrl, setLlamacppBaseUrl] = useState("http://localhost:8080");
       const [llamacppHealth, setLlamacppHealth] =
         useState<{healthy: boolean; message: string} | null>(null);
       const [llamacppTesting, setLlamacppTesting] = useState(false);
       ```

    3. In `frontend/src/api/research.ts`, add a tiny helper (mirror existing health/credential mutation patterns) — `useTestProviderConnectionMutation` or a fetch-call wrapper that POSTs/GETs the existing `/api/research/providers/{provider_id}/health` endpoint with `{base_url}` (use whichever endpoint shape already exists in this file; if a generic health endpoint is not present, reuse `useStoreCredentialMutation` to persist `{base_url}` then refetch `useProvidersQuery`). Do NOT invent a new backend endpoint.

       Read frontend/src/api/research.ts first; pick the simplest existing primitive that posts a credential or queries health. Document the choice in a one-line comment.

    4. Add the Llama.cpp panel between the `isOllama` block and the API-key block. It must NOT render when `isOllama` or other branches are active. Mirror Ollama's structure (Heading + descriptive Text + input + button + status):
       ```tsx
       {isLlamacpp && (
         <Flex direction="column" gap="2">
           <Heading size="3">Servidor Llama.cpp local</Heading>
           <Text size="1" color="gray">
             Llama.cpp roda localmente e não precisa de chave de API. Informe a URL do servidor (default: http://localhost:8080) e teste a conexão.
           </Text>
           <TextField.Root
             placeholder="http://localhost:8080"
             value={llamacppBaseUrl}
             onChange={(e) => { setLlamacppBaseUrl(e.target.value); setLlamacppHealth(null); }}
           />
           <Button
             onClick={async () => {
               setLlamacppTesting(true);
               try {
                 // call the helper from step 3 with { provider: "llamacpp", base_url: llamacppBaseUrl }
                 const result = await /* helper */;
                 setLlamacppHealth(result);
               } finally {
                 setLlamacppTesting(false);
               }
             }}
             disabled={!llamacppBaseUrl.trim() || llamacppTesting}
             color="blue"
           >
             {llamacppTesting ? "Testando..." : "Testar conexão"}
           </Button>
           {llamacppHealth && (
             <Badge color={llamacppHealth.healthy ? "green" : "red"} size="2">
               {llamacppHealth.healthy ? "✓ conectado" : `✗ ${llamacppHealth.message}`}
             </Badge>
           )}
         </Flex>
       )}
       ```

    5. Update the API-key gating (line 222) so it ALSO hides for `isLlamacpp`:
       ```tsx
       {!isOllama && !isLlamacpp && (
       ```
       And the persistent status badge gating (line 136) similarly:
       ```tsx
       {!isOllama && !isLlamacpp && !isClaudeWithCli && provider && (
       ```

    6. Build the frontend (or run typecheck) to ensure TS compiles.

    Note: We are NOT adding model selection for llama.cpp — by design (per Etapa 4), llama-server serves whatever was launched. The base_url is the only config knob.
  </action>
  <verify>
    <automated>cd frontend && npm run build</automated>
  </verify>
  <done>
    - frontend builds with no TS errors
    - When `sheetOpenForProvider === "llamacpp"`: the panel renders with base_url field defaulting to http://localhost:8080, a "Testar conexão" button, and a status badge after a test
    - The API-key input and the persistent "Credencial salva" badge are HIDDEN for llamacpp (matching the Ollama pattern)
    - No new backend endpoint was introduced; the panel reuses existing api/research.ts primitives
  </done>
</task>

</tasks>

<verification>
- All 4 new backend unit tests pass
- Full backend suite passes (220 prior + 4 new, no regressions)
- Frontend `npm run build` passes with no TS errors
- registry.PROVIDERS contains "llamacpp"
- model_routing.py and research_runner.py are UNCHANGED (git diff confirms)
- AuthSetupSheet shows the Llama.cpp panel for `provider_id === "llamacpp"`
</verification>

<success_criteria>
- Atomic commit `feat(quick-260428-fjc): add Llama.cpp provider (llamacpp.py + registry + AuthSetupSheet)` (or split into backend+frontend if preferred — master plan says 1 commit, do that)
- Master plan section H entry "Etapa 5 (Llama.cpp): 1 commit, 4 testes" satisfied
- User can open the AuthSetupSheet for Llama.cpp, enter a base_url, click Testar conexão, and see ✓/✗ status
</success_criteria>

<output>
After completion, create `.planning/quick/260428-fjc-etapa-5-llama-cpp-provider-local-llamacp/260428-fjc-SUMMARY.md`
</output>
