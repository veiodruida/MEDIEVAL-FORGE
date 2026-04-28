---
phase: quick-260428-ewx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/llm/schemas.py
  - backend/tests/unit/test_llm_schemas.py
autonomous: true
requirements:
  - QUICK-260428-EWX (Etapa 3 hazy-hatching-abelson.md, seção H item 3 + G.1)
must_haves:
  truths:
    - "MapResearchResult class exists in schemas.py exporting kingdoms, duchies, condados (no coords), barony_assignments"
    - "MapResearchResult validates a payload where condados have only id/name/kingdom_id/duchy_id (no lon/lat)"
    - "MapResearchResult.barony_assignments accepts a dict[str, str] mapping barony_id -> condado_id"
    - "Cross-reference validator (model_validator mode='after') raises ValueError when a barony_assignments value points to a condado_id NOT present in condados[]"
    - "All 209 existing tests still pass — legacy ResearchResult / Condado / Barony schemas remain importable and behave as before"
  artifacts:
    - path: "backend/medieval_forge/services/llm/schemas.py"
      provides: "MapResearchResult + MapCondado (no-coords variant) added; legacy ResearchResult/Condado/Barony preserved"
      contains: "class MapResearchResult"
    - path: "backend/tests/unit/test_llm_schemas.py"
      provides: "New test cases covering MapResearchResult acceptance + cross-reference validator"
      contains: "MapResearchResult"
  key_links:
    - from: "MapResearchResult.barony_assignments"
      to: "MapResearchResult.condados[].id"
      via: "model_validator(mode='after')"
      pattern: "model_validator"
---

<objective>
Implement Etapa 3 of plan hazy-hatching-abelson.md (section H item 3, schema details in G.1):
add a new `MapResearchResult` Pydantic model that represents the CK3-style schema split where:
  - LLM no longer invents condado coordinates (centroids will come from baronies aggregation later)
  - LLM returns `barony_assignments: dict[str, str]` (barony_id -> condado_id) instead of inline baronies
Preserve the existing `ResearchResult` / `Condado` / `Barony` classes untouched so the current 209 tests keep passing. Add focused unit tests for the new model + a cross-reference Pydantic `model_validator` (mode='after') that fails when a barony is assigned to a non-existent condado.

Purpose: Unblocks Etapa 4+ (model routing, prompt rewrite, territory_builder reconstruction) which depend on the new schema shape.
Output: Updated schemas.py with new model + new tests; 1 atomic commit; 209 existing tests + ~6 new tests all green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md
@backend/medieval_forge/services/llm/schemas.py
@backend/tests/unit/test_llm_schemas.py

<interfaces>
<!-- Existing schemas.py exports (DO NOT BREAK) -->

```python
# Already in backend/medieval_forge/services/llm/schemas.py
class Barony(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    lon: float
    lat: float

class Duchy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdom_id: str
    name: str

class Condado(BaseModel):  # legacy — has coordinates
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    lon: float
    lat: float
    kingdom_id: str
    duchy_id: str

class ResearchResult(BaseModel):  # legacy
    model_config = ConfigDict(extra="forbid")
    kingdoms: dict[str, str]
    duchies: dict[str, Duchy]
    condados: list[Condado]
    baronies: dict[str, list[Barony]]

def parse_research_json(text: str) -> ResearchResult: ...
```

<!-- New shape to add (Etapa 3 — section G.1 of hazy-hatching-abelson.md) -->

```python
class MapCondado(BaseModel):
    """Condado as returned by the new map_research prompt — NO coords.
    Centroids will be computed later by territory_builder from member baronies."""
    model_config = ConfigDict(extra="forbid")
    id: str          # LLM-invented slug, e.g. "C_BRAGA"
    name: str        # Historical display name
    kingdom_id: str  # references MapResearchResult.kingdoms key
    duchy_id: str    # references MapResearchResult.duchies key

class MapResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdoms: dict[str, str]                # id -> display_name
    duchies: dict[str, Duchy]               # id -> Duchy
    condados: list[MapCondado]              # NO coords
    barony_assignments: dict[str, str]      # barony_id -> condado_id

    @model_validator(mode="after")
    def _validate_barony_assignments_reference_existing_condados(self) -> "MapResearchResult":
        condado_ids = {c.id for c in self.condados}
        unknown = {bid: cid for bid, cid in self.barony_assignments.items()
                   if cid not in condado_ids}
        if unknown:
            raise ValueError(
                f"barony_assignments reference unknown condado_id(s): {sorted(set(unknown.values()))}; "
                f"known condado ids: {sorted(condado_ids)}"
            )
        return self
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add MapResearchResult + MapCondado schemas (with cross-ref validator) and unit tests</name>
  <files>
    backend/medieval_forge/services/llm/schemas.py,
    backend/tests/unit/test_llm_schemas.py
  </files>
  <behavior>
    Tests to add to backend/tests/unit/test_llm_schemas.py (descriptive names + explicit numeric fixtures per project convention):

    1. `test_map_research_result_accepts_minimal_valid_payload_with_two_baronies_assigned_to_condado_braga`
       - Fixture: kingdoms={"k_leon":"León"},
                  duchies={"d_galicia":{"kingdom_id":"k_leon","name":"Galícia"}},
                  condados=[{"id":"C_BRAGA","name":"Braga","kingdom_id":"k_leon","duchy_id":"d_galicia"}],
                  barony_assignments={"B_001":"C_BRAGA","B_002":"C_BRAGA"}
       - Assert: model validates; result.condados[0].id == "C_BRAGA";
                 len(result.barony_assignments) == 2;
                 result.barony_assignments["B_001"] == "C_BRAGA"

    2. `test_map_condado_rejects_lon_lat_fields_because_coords_are_no_longer_part_of_the_new_schema`
       - Attempt MapCondado.model_validate({"id":"C_X","name":"X","kingdom_id":"k1","duchy_id":"d1","lon":-8.5,"lat":42.3})
       - Assert: ValidationError raised (extra='forbid' rejects lon/lat)

    3. `test_map_condado_requires_id_name_kingdom_id_and_duchy_id`
       - Three sub-cases: missing id, missing name, missing duchy_id → each raises ValidationError

    4. `test_map_research_result_barony_assignments_accepts_empty_dict_when_no_baronies_yet`
       - Fixture with barony_assignments={} and one condado → validates successfully

    5. `test_map_research_result_cross_reference_validator_raises_when_barony_assigned_to_unknown_condado_id`
       - Fixture: condados=[{"id":"C_BRAGA",...}],
                  barony_assignments={"B_001":"C_BRAGA","B_002":"C_TOLEDO"}  # C_TOLEDO NOT in condados
       - Assert: ValidationError raised; error message mentions "C_TOLEDO"

    6. `test_map_research_result_cross_reference_validator_passes_when_all_assignments_point_to_known_condados`
       - Fixture: condados=[{"id":"C_BRAGA",...},{"id":"C_PORTO",...}],
                  barony_assignments={"B_001":"C_BRAGA","B_002":"C_PORTO","B_003":"C_BRAGA"}
       - Assert: validates; len(result.condados) == 2

    7. `test_legacy_research_result_still_works_after_schema_split` (regression guard)
       - Reuse the existing _MINIMAL_VALID fixture and call ResearchResult.model_validate(_MINIMAL_VALID)
       - Assert: still passes (proves we did NOT break the legacy path)
  </behavior>
  <action>
    1. Edit `backend/medieval_forge/services/llm/schemas.py`:
       - Add `model_validator` to the pydantic import: `from pydantic import BaseModel, ConfigDict, ValidationError, model_validator`
       - Append (do NOT modify existing classes) two new classes:
         * `MapCondado` — same shape as `Condado` but WITHOUT `lon`/`lat` fields, `extra="forbid"`.
         * `MapResearchResult` — fields: `kingdoms: dict[str, str]`, `duchies: dict[str, Duchy]`, `condados: list[MapCondado]`, `barony_assignments: dict[str, str]`, `extra="forbid"`.
       - On `MapResearchResult` add a `@model_validator(mode="after")` method
         `_validate_barony_assignments_reference_existing_condados(self)` that builds
         `condado_ids = {c.id for c in self.condados}`, finds any
         `barony_assignments` value not in that set, and raises `ValueError(...)`
         listing the unknown condado_id(s). Return `self` on success.
       - Do NOT touch `Barony`, `Duchy`, `Condado`, `ResearchResult`, `parse_research_json`,
         or `_RESEARCH_RESULT_KEYS`. Etapa 4+ will refactor `parse_research_json`; Etapa 3 is purely additive.
       - Update the module docstring's second paragraph to note: "Etapa 3 (hazy-hatching-abelson.md): MapResearchResult added — LLM returns condados WITHOUT coords plus barony_assignments dict; legacy ResearchResult kept for backwards compatibility until Etapa 4 migrates callers."

    2. Edit `backend/tests/unit/test_llm_schemas.py`:
       - Extend the import line to also import `MapCondado` and `MapResearchResult` from `medieval_forge.services.llm.schemas`.
       - Append the 7 test functions described in <behavior> above. Use module-level constants for the fixtures (e.g. `_MAP_MINIMAL_VALID = {...}`) so each test reads cleanly. Numeric values (lon/lat in the negative test) must be explicit literals, not random/computed.

    3. Run the new tests in isolation first (RED on cross-ref test BEFORE writing the validator, then GREEN). Then run the full unit suite to confirm zero regressions.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/unit/test_llm_schemas.py -v</automated>
    <automated>cd backend && python -m pytest tests -q -m "not slow"</automated>
  </verify>
  <done>
    - `MapCondado` and `MapResearchResult` exported from `medieval_forge.services.llm.schemas`
    - All 7 new tests pass
    - All previously-passing tests in test_llm_schemas.py still pass (legacy regression guard green)
    - Full non-slow suite still reports 209+ passing (no regressions)
    - Single atomic commit: `feat(quick-260428-ewx): add MapResearchResult schema with barony_assignments + cross-ref validator (Etapa 3)`
  </done>
</task>

</tasks>

<verification>
1. `cd backend && python -m pytest tests/unit/test_llm_schemas.py -v` — all old + 7 new tests green.
2. `cd backend && python -m pytest tests -q -m "not slow"` — total ≥ 209 passing, 0 failed, 0 errors.
3. `python -c "from medieval_forge.services.llm.schemas import MapResearchResult, MapCondado, ResearchResult, Condado; print('ok')"` — both new and legacy symbols importable.
</verification>

<success_criteria>
- New `MapResearchResult` model accepts the documented payload shape (kingdoms, duchies, condados-without-coords, barony_assignments dict).
- Cross-reference invariant enforced via `@model_validator(mode='after')` raising `ValueError` with a message naming the unknown condado_id.
- Legacy `ResearchResult`/`Condado`/`Barony` schemas untouched and still validating their existing tests.
- 209 existing tests + 7 new tests all pass.
- One atomic commit on `main`.
</success_criteria>

<output>
After completion, append a one-line entry to STATE.md "Quick Tasks Completed" table:
| 260428-ewx | Etapa 3: schemas split — MapResearchResult + barony_assignments + cross-ref validator | 2026-04-28 | <commit> | [260428-ewx-etapa-3-schemas-split-mapresearchresult-](./quick/260428-ewx-etapa-3-schemas-split-mapresearchresult-/) |
</output>
