---
phase: quick-260422-gts
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/services/test_llm_providers.py
autonomous: true
requirements:
  - QUICK-260422-GTS
must_haves:
  truths:
    - "Ollama provider test asserts grammar-constrained schema format (not 'json' string)"
    - "_VALID_PAYLOAD duchies field matches the Duchy pydantic model shape"
    - "All 5 tests in test_llm_providers.py pass"
  artifacts:
    - path: "backend/tests/services/test_llm_providers.py"
      provides: "Corrected unit tests for all LLM providers"
      contains: "test_ollama_provider_uses_grammar_constrained_format"
  key_links:
    - from: "test_llm_providers.py::_VALID_PAYLOAD"
      to: "backend/medieval_forge/services/llm/schemas.py::Duchy"
      via: "pydantic validation of ResearchResult"
      pattern: "kingdom_id.*name"
    - from: "test_ollama_provider_uses_grammar_constrained_format"
      to: "backend/medieval_forge/services/llm/ollama.py"
      via: "captured format kwarg from mocked chat call"
      pattern: "format.*model_json_schema"
---

<objective>
Fix two defects in `backend/tests/services/test_llm_providers.py` so the Ollama
unit test matches the current production behavior (grammar-constrained JSON
schema format) and `_VALID_PAYLOAD` produces a structurally valid
`ResearchResult` per the `Duchy` pydantic model.

Purpose: The Ollama provider was updated (commit 7081547) to pass
`format=schema.model_json_schema()` instead of `format="json"`, but the unit
test still asserts the old behavior. Additionally, the shared `_VALID_PAYLOAD`
has a wrong shape for `duchies` that breaks validation across all provider
tests.

Output: Corrected test file; `pytest backend/tests/services/test_llm_providers.py -v`
reports 5 passing tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@backend/tests/services/test_llm_providers.py
@backend/medieval_forge/services/llm/schemas.py
@backend/medieval_forge/services/llm/ollama.py

<interfaces>
<!-- From backend/medieval_forge/services/llm/schemas.py (expected) -->
```python
class Duchy(BaseModel):
    kingdom_id: str
    name: str
```
Payload shape for `duchies` must be: `{"<duchy_id>": {"kingdom_id": "<k>", "name": "<n>"}}`

<!-- From backend/medieval_forge/services/llm/ollama.py (post commit 7081547) -->
The Ollama provider calls `ollama.chat(...)` with
`format=ResearchResult.model_json_schema()`. The schema dict contains
`"title": "ResearchResult"` at its root.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix _VALID_PAYLOAD duchies shape</name>
  <files>backend/tests/services/test_llm_providers.py</files>
  <action>
    Locate `_VALID_PAYLOAD` at the top of the test module. Update the `duchies`
    field from the incorrect list form:
      "duchies": {"galicia": ["asturias", "Ducado de Galicia"]}
    to the correct dict form matching the `Duchy` pydantic model:
      "duchies": {"galicia": {"kingdom_id": "asturias", "name": "Ducado de Galicia"}}
    Do NOT change any other field in `_VALID_PAYLOAD`. This payload is shared by
    all provider tests (Claude, OpenAI, Gemini, Ollama), so this single edit
    fixes validation across the file.
  </action>
  <verify>
    <automated>cd backend && python -c "from medieval_forge.services.llm.schemas import ResearchResult; import json; ResearchResult.model_validate({'kingdoms': {}, 'duchies': {'galicia': {'kingdom_id': 'asturias', 'name': 'Ducado de Galicia'}}, 'counties': {}, 'settlements': {}, 'sources': []})"</automated>
  </verify>
  <done>_VALID_PAYLOAD["duchies"]["galicia"] is a dict with keys "kingdom_id" and "name"; no other field mutated.</done>
</task>

<task type="auto">
  <name>Task 2: Update Ollama format assertion to grammar-constrained schema</name>
  <files>backend/tests/services/test_llm_providers.py</files>
  <action>
    Find the test currently named `test_ollama_provider_uses_format_json_blocking`.

    1. Rename the function to `test_ollama_provider_uses_grammar_constrained_format`.
    2. Update its docstring to reflect that the Ollama provider passes a JSON
       schema dict as the `format` kwarg (grammar-constrained decoding) rather
       than the legacy string `"json"`.
    3. Replace the old assertion (which checked `_captured.get("format") == "json"`)
       with:
         - `assert isinstance(_captured.get("format"), dict)`
         - `assert _captured.get("format", {}).get("title") == "ResearchResult"`
    4. Leave the rest of the test body (mocking of `ollama.chat`, payload
       building, response parsing) unchanged.

    Rationale: commit 7081547 changed `ollama.py` to pass
    `format=ResearchResult.model_json_schema()`; the old string-equality check
    is now incorrect and always fails. The new assertions verify (a) the format
    is a schema dict and (b) it is the ResearchResult schema specifically.
  </action>
  <verify>
    <automated>cd backend && pytest tests/services/test_llm_providers.py -v</automated>
  </verify>
  <done>All 5 tests in test_llm_providers.py pass. The renamed test asserts format is a dict with title "ResearchResult".</done>
</task>

</tasks>

<verification>
Run the full provider test module and confirm zero failures:

```
cd backend && pytest tests/services/test_llm_providers.py -v
```

Expected: 5 passed. No test should reference `format == "json"` anymore.
</verification>

<success_criteria>
- `_VALID_PAYLOAD["duchies"]` uses the Duchy dict shape (`kingdom_id`, `name`).
- Test function renamed to `test_ollama_provider_uses_grammar_constrained_format`.
- Test asserts format is a dict whose `title` is `"ResearchResult"`.
- `pytest backend/tests/services/test_llm_providers.py -v` → 5 passed.
</success_criteria>

<output>
After completion, create `.planning/quick/260422-gts-fix-mocked-ollama-unit-test-correct-duch/260422-gts-SUMMARY.md`
</output>
