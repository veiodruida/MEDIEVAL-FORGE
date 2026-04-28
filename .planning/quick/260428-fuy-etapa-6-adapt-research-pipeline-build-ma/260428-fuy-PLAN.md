---
phase: quick-260428-fuy
plan: 01
type: tdd
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/llm/prompt.py
  - backend/medieval_forge/services/llm/schemas.py
  - backend/tests/unit/test_map_research_prompt.py
  - backend/tests/unit/test_barony_assignments_validation.py
autonomous: true
requirements:
  - HAZY-ETAPA-6
must_haves:
  truths:
    - "build_map_research_prompt(country, period_start, baronies) emits a prompt that lists every input barony with its id, name, lon, lat"
    - "The emitted prompt instructs the LLM to fill barony_assignments as {barony_id -> condado_id} using ONLY the provided barony ids"
    - "validate_barony_assignments raises ValueError when an assignment key is not among the input baronies"
    - "validate_barony_assignments raises ValueError when at least one input barony is left unassigned (strict mode — triggers run_with_retry self-correction)"
    - "validate_barony_assignments returns None silently when every input barony is assigned exactly once to a known condado"
    - "Existing MapResearchResult schema validator (assignments → known condado_id) continues to pass"
  artifacts:
    - path: backend/medieval_forge/services/llm/prompt.py
      provides: "build_map_research_prompt(country_name, period_start, baronies, *, period_end=None, bbox=None) -> str"
      contains: "def build_map_research_prompt"
    - path: backend/medieval_forge/services/llm/schemas.py
      provides: "validate_barony_assignments(result, input_baronies) helper alongside MapResearchResult"
      contains: "def validate_barony_assignments"
    - path: backend/tests/unit/test_map_research_prompt.py
      provides: "3 descriptive tests for build_map_research_prompt"
    - path: backend/tests/unit/test_barony_assignments_validation.py
      provides: "3 descriptive tests for validate_barony_assignments"
  key_links:
    - from: build_map_research_prompt
      to: MapResearchResult schema shape
      via: prompt mentions exact top-level keys (kingdoms, duchies, condados, barony_assignments)
      pattern: "barony_assignments"
    - from: validate_barony_assignments
      to: run_with_retry retry loop
      via: raising ValueError → retry.py treats as schema failure → re-prompts LLM
      pattern: "raise ValueError"
---

<objective>
Etapa 6 of master plan hazy-hatching-abelson: adapt the research pipeline so the LLM
receives a concrete list of pre-built baronies (from Etapa 2's baronies_builder) and
returns a `barony_assignments: dict[barony_id -> condado_id]` instead of inventing
barony coordinates. Add a self-consistency validator that re-prompts the LLM when
assignments are wrong/incomplete.

Purpose: This is the inversion the master plan calls for — baronies are the organic
permanent unit (from OSM), condados are dynamic political layers built FROM baronies.
The LLM only assigns; it does not invent geography.

Output:
- `build_map_research_prompt(country_name, period_start, baronies, *, period_end=None, bbox=None)` in prompt.py
- `validate_barony_assignments(result: MapResearchResult, input_baronies: list[dict]) -> None` in schemas.py
- 6 tests (3 RED prompt + 3 RED validator → GREEN) split into RED + GREEN commits

Out of scope (later etapas):
- Wiring into research_runner.py (Etapa 7 / territory_builder rebuild)
- territory_builder reconstruction (Etapa 7)
- AssignmentEditor frontend (Etapa 8)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

# Current code under change
@backend/medieval_forge/services/llm/prompt.py
@backend/medieval_forge/services/llm/schemas.py
@backend/medieval_forge/services/research_runner.py
@backend/medieval_forge/services/llm/retry.py
@backend/tests/unit/test_llm_schemas.py

# Master plan reference for Etapa 6 scope and intent
@C:/Users/veio_/.claude/plans/hazy-hatching-abelson.md

# User preference for descriptive tests
@C:/Users/veio_/.claude/projects/c--Users-veio--Documents-Unity-Projects-MEDIEVAL-FORGE/memory/feedback-tests-descriptive.md

<interfaces>
Existing schema (DO NOT change shape — only add a sibling helper):

```python
# backend/medieval_forge/services/llm/schemas.py (excerpt)
class MapCondado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    kingdom_id: str
    duchy_id: str

class MapResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdoms: dict[str, str]
    duchies: dict[str, Duchy]
    condados: list[MapCondado]
    barony_assignments: dict[str, str]  # barony_id -> condado_id

    @model_validator(mode="after")
    def _validate_barony_assignments_reference_existing_condados(self) -> "MapResearchResult":
        # Already enforces: every assignment VALUE (condado_id) is in condados[].
        # DOES NOT enforce: every assignment KEY is a real input barony, nor coverage.
        ...
```

Existing prompt builder (template to emulate — keep `build_research_prompt` untouched
for backwards compat with legacy ResearchResult callers; add new sibling function):

```python
# backend/medieval_forge/services/llm/prompt.py (excerpt)
def build_research_prompt(country_name, period_start, period_end, bbox=None) -> str: ...
```

Retry loop contract (drives the design — strict ValueError → re-prompt):

```python
# backend/medieval_forge/services/llm/retry.py (excerpt)
async def run_with_retry(provider, prompt_base, schema, credentials, queue, max_retries=3):
    # Catches (ValidationError, ValueError, JSONDecodeError) and re-prompts.
```

Input baronies shape (produced by Etapa 2 baronies_builder, GeoJSON FeatureCollection
properties — list of plain dicts the runner will pass in):

```python
# Each element:
{"id": "B_OSM_12345", "name": "Braga", "lon": -8.43, "lat": 41.55}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (RED): Write 6 failing tests — 3 for build_map_research_prompt, 3 for validate_barony_assignments</name>
  <files>
    backend/tests/unit/test_map_research_prompt.py,
    backend/tests/unit/test_barony_assignments_validation.py
  </files>
  <behavior>
    File 1 — `backend/tests/unit/test_map_research_prompt.py` (3 tests):

    1. `test_build_map_research_prompt_lists_every_input_barony_with_id_name_lon_lat`
       - Given: country="Iberia", period_start=868, baronies=3 explicit ones with
         ids "B_001"/"B_002"/"B_003", names "Braga"/"Porto"/"Coimbra",
         coords (-8.43, 41.55), (-8.61, 41.15), (-8.42, 40.21).
       - Assert: returned string contains every id, every name, and each numeric
         coord (formatted to at least 2 decimals). Use `"B_001" in prompt`,
         `"Braga" in prompt`, `"-8.43" in prompt`, `"41.55" in prompt`.

    2. `test_build_map_research_prompt_instructs_llm_to_emit_barony_assignments_dict_with_input_ids_only`
       - Given: same fixture as test 1.
       - Assert: prompt contains the literal token `"barony_assignments"`, contains
         the phrase "MUST be one of the barony_ids listed above" (or equivalent
         wording the implementer chooses — document the exact substring used in a
         comment), and contains the four allowed top-level keys
         ("kingdoms", "duchies", "condados", "barony_assignments") while NOT
         containing the legacy `"baronies"` top-level key (the new schema replaces it).

    3. `test_build_map_research_prompt_uses_period_start_year_and_optional_bbox_when_supplied`
       - Given: country="Iberia", period_start=868, period_end=1492,
         baronies=[{"id": "B_001", "name": "Braga", "lon": -8.43, "lat": 41.55}],
         bbox=(-9.5, 36.0, 3.3, 43.8).
       - Assert: "868" in prompt, "1492" in prompt (period_end is included when
         provided), "-9.5" and "43.8" both appear (bbox echoed).

    File 2 — `backend/tests/unit/test_barony_assignments_validation.py` (3 tests):

    Shared fixture: 3 input baronies B_001 / B_002 / B_003; result with 1 condado
    "C_BRAGA" + corresponding kingdom "K_PORT" + duchy "D_MINHO".

    4. `test_validate_barony_assignments_passes_when_every_input_barony_is_assigned_to_known_condado`
       - assignments = {"B_001": "C_BRAGA", "B_002": "C_BRAGA", "B_003": "C_BRAGA"}
       - Assert: returns None, no exception.

    5. `test_validate_barony_assignments_raises_when_assignment_key_is_not_an_input_barony_id`
       - assignments = {"B_001": "C_BRAGA", "B_002": "C_BRAGA", "B_999_GHOST": "C_BRAGA"}
       - input_baronies omits "B_999_GHOST".
       - Assert: pytest.raises(ValueError, match=r"B_999_GHOST"); error message
         must mention the offending id so run_with_retry's appended correction
         text steers the LLM.

    6. `test_validate_barony_assignments_raises_when_at_least_one_input_barony_is_unassigned`
       - assignments = {"B_001": "C_BRAGA"}  # B_002, B_003 missing
       - Assert: pytest.raises(ValueError, match=r"unassigned|B_002|B_003");
         message names the unassigned ids so the LLM can recover on retry.

    All 6 tests use explicit numeric/string fixtures (per feedback-tests-descriptive)
    — no opaque random data. Test names read as full English behavioral statements.
  </behavior>
  <action>
    Step 1: Create `backend/tests/unit/test_map_research_prompt.py` with the 3 tests
    above. Import `build_map_research_prompt` from
    `medieval_forge.services.llm.prompt` (does not exist yet — that's the point of RED).

    Step 2: Create `backend/tests/unit/test_barony_assignments_validation.py` with
    the 3 tests above. Import `validate_barony_assignments` and
    `MapResearchResult` from `medieval_forge.services.llm.schemas`.

    Step 3: Run `cd backend && python -m pytest tests/unit/test_map_research_prompt.py
    tests/unit/test_barony_assignments_validation.py -q` and confirm all 6 fail
    with ImportError or AttributeError (NOT a non-import error — that would mean
    the symbol exists prematurely).

    Step 4: Commit as `test(quick-260428-fuy): add 6 failing tests for build_map_research_prompt + validate_barony_assignments (RED)`.

    Constraints:
    - Use explicit literal coordinates and ids in fixtures, not parametrize loops.
    - Each test docstring (one line, optional) restates the behavior in plain English.
    - Do NOT touch prompt.py or schemas.py in this task — RED only.
    - Do NOT mock anything; these are pure functions.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/unit/test_map_research_prompt.py tests/unit/test_barony_assignments_validation.py -q 2>&1 | grep -E "6 (failed|errors?)"</automated>
  </verify>
  <done>
    Both test files exist; 6 tests collected; all 6 FAIL with ImportError /
    AttributeError indicating the production symbols do not yet exist.
    Commit "test(quick-260428-fuy): … (RED)" landed on branch.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (GREEN): Implement build_map_research_prompt + validate_barony_assignments — all 6 tests pass, 224 prior tests stay green</name>
  <files>
    backend/medieval_forge/services/llm/prompt.py,
    backend/medieval_forge/services/llm/schemas.py
  </files>
  <behavior>
    All 6 tests from Task 1 turn GREEN. Existing 224 tests remain GREEN
    (no breakage of legacy `build_research_prompt` callers, no breakage of
    `MapResearchResult` schema-level validator).
  </behavior>
  <action>
    Step 1: In `backend/medieval_forge/services/llm/prompt.py`, ADD a new function
    `build_map_research_prompt(country_name, period_start, baronies, *, period_end=None, bbox=None) -> str`.

    Implementation:
    - Reuse `SYSTEM_INSTRUCTIONS` constant.
    - Build a NEW `EXAMPLE_OUTPUT_MAP` string showing the 4-key MapResearchResult
      shape (kingdoms / duchies / condados WITHOUT coords / barony_assignments dict).
      Use 2-3 example baronies and 2 condados, all with id slugs that match the
      pattern actually used in the input list passed in (e.g. `B_001`, `C_BRAGA`).
    - Build a NEW `RULES_MAP` string. Critical rules (mirroring existing RULES style):
       1. TOP-LEVEL KEYS ALLOWED: exactly "kingdoms", "duchies", "condados",
          "barony_assignments". NOTHING ELSE. NO "baronies" key.
       2. condados objects have keys "id", "name", "kingdom_id", "duchy_id" — NO lon/lat.
       3. barony_assignments: object mapping <barony_id> → <condado_id>.
          Every key MUST be one of the barony_ids listed in the BARONIES section
          below — do NOT invent new ids. Every value MUST be one of the condado
          ids in your "condados" array.
       4. EVERY input barony MUST appear exactly once as a key in
          barony_assignments. Do not leave any unassigned.
    - Format the input baronies as a bulleted list:
      `- {id}: {name} (lon={lon:.2f}, lat={lat:.2f})\n` (use 2 decimals minimum so
      the test for "-8.43" / "41.55" matches verbatim).
    - Optionally include `geo_hint` block when bbox provided (mirror existing
      build_research_prompt style; ensure bbox numbers appear with the precision
      the test asserts — e.g. format `f"{lon_min:.2f}"` so `-9.5` becomes `-9.50`;
      adjust test substring to `"-9.50"` if needed, OR format with `{lon_min:g}` to
      preserve `-9.5` literally — pick whichever matches the test exactly).
    - Final TASK section includes country_name, period_start (and period_end if not None).

    Step 2: In `backend/medieval_forge/services/llm/schemas.py`, ADD a module-level
    function (NOT a method):

    ```python
    def validate_barony_assignments(
        result: "MapResearchResult",
        input_baronies: list[dict],
    ) -> None:
        """Strict cross-check between LLM assignments and the input barony list.

        Complements MapResearchResult's built-in validator (which only checks
        condado refs). This function checks the OTHER side: keys must match
        input baronies exactly. Strict mode — raises so run_with_retry re-prompts.
        """
        input_ids = {b["id"] for b in input_baronies}
        assigned_ids = set(result.barony_assignments.keys())

        unknown_keys = assigned_ids - input_ids
        if unknown_keys:
            raise ValueError(
                f"barony_assignments contain unknown barony id(s) not in the "
                f"input list: {sorted(unknown_keys)}; "
                f"valid input ids: {sorted(input_ids)}"
            )

        unassigned = input_ids - assigned_ids
        if unassigned:
            raise ValueError(
                f"barony_assignments are incomplete — the following input "
                f"baronies were left unassigned: {sorted(unassigned)}"
            )
    ```

    Step 3: Run the FULL backend test suite:
    `cd backend && python -m pytest tests -q -m "not slow and not requires_llamacpp"`.

    Expected: all prior 224 tests green + 6 new tests green = 230 passing.
    If any prior test fails, do NOT alter the prior test — fix the new code so
    the legacy contract is preserved (most likely: do not touch existing
    `build_research_prompt`, do not change `MapResearchResult` schema fields,
    only add the new helper function and the new prompt builder).

    Step 4: Commit as `feat(quick-260428-fuy): build_map_research_prompt + validate_barony_assignments (GREEN, 6 tests)`.

    Step 5: Update STATE.md "Quick Tasks Completed" with row:
    `260428-fuy | Etapa 6: adapt research pipeline — build_map_research_prompt + validate_barony_assignments | 2026-04-28 | <commit> | …`
    and "Last activity" / "Stopped at" lines. Commit STATE update as a docs commit
    (or fold into the GREEN commit if preferred — keep it 1 logical change).

    Constraints:
    - Do NOT touch research_runner.py (Etapa 7).
    - Do NOT touch territory_builder.py (Etapa 7).
    - Do NOT touch any frontend file.
    - Do NOT modify the existing `build_research_prompt` function or the existing
      `MapResearchResult` model_validator.
    - Keep `validate_barony_assignments` as a plain module-level function so it
      can be wrapped (in Etapa 7) by a `_ValidatingWrapper`-style adapter inside
      research_runner, mirroring the existing `validate_condados_self_consistency`
      pattern.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests -q -m "not slow and not requires_llamacpp" 2>&1 | tail -5</automated>
  </verify>
  <done>
    - All 6 new tests pass.
    - All 224 pre-existing tests still pass (test count is 230+ green, 0 fail).
    - `build_map_research_prompt` exists and is importable from
      `medieval_forge.services.llm.prompt`.
    - `validate_barony_assignments` exists and is importable from
      `medieval_forge.services.llm.schemas`.
    - GREEN commit landed; STATE.md updated.
  </done>
</task>

</tasks>

<verification>
Backend full suite green:

```
cd backend && python -m pytest tests -q -m "not slow and not requires_llamacpp"
```

Expected: ≥230 passing, 0 failing.

Spot-check the new symbols are importable:

```
cd backend && python -c "from medieval_forge.services.llm.prompt import build_map_research_prompt; from medieval_forge.services.llm.schemas import validate_barony_assignments; print('ok')"
```

Expected output: `ok`.
</verification>

<success_criteria>
- 2 commits on main: RED (6 failing tests) → GREEN (impl + tests pass).
- `build_map_research_prompt(country, period_start, baronies, *, period_end=None, bbox=None)` exists, returns a string that:
  - lists every input barony with id, name, lon, lat;
  - names the four allowed top-level keys including `barony_assignments`;
  - forbids the legacy `baronies` top-level key.
- `validate_barony_assignments(result, input_baronies)` exists and:
  - returns None for the happy path;
  - raises ValueError naming the offending barony id when an assignment key is not in the input list;
  - raises ValueError naming the unassigned ids when coverage is incomplete.
- Existing `build_research_prompt` and `MapResearchResult.model_validator` untouched.
- No frontend changes. No research_runner.py / territory_builder.py changes.
- STATE.md updated with the 260428-fuy row.
</success_criteria>

<output>
After completion, create `.planning/quick/260428-fuy-etapa-6-adapt-research-pipeline-build-ma/260428-fuy-SUMMARY.md` documenting:
- Symbols added (prompt builder + validator) and exact signatures.
- Test count delta (224 → 230).
- Commit hashes (RED + GREEN).
- Explicit note that wiring into research_runner is deferred to Etapa 7.
</output>
