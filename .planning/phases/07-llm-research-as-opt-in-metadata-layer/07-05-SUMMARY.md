---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 05
subsystem: backend / services-research + services-export
tags: [overlay, merge, schemas, pydantic, manifest, d-03, d-04, reviews-fix-1]
requirements: [V3-LLM-OPT-IN]
dependency_graph:
  requires: [00, 02]
  provides: [merge_overlay, ResearchOverlay, CondadoOverlayEntry, _ZIP_BOUND_FIELDS, _ALL_OVERLAY_FIELDS, load_overlay_if_exists, MANIFEST_SCHEMA_VERSION=3, CondadoEntrySchema.kingdom_owner, CondadoEntrySchema.historical_notes, ManifestSchema.research_overlay_applied]
  affects: [06 parity (still green), 08 build_unity_zip (consumer), 07b runner (consumer)]
tech_stack:
  added:
    - "services/research/ subpackage (new)"
  patterns:
    - "RootModel[dict[str, T]] for sidecar JSON top-level shape (mirrors LookupBaronyColorsSchema pattern)"
    - "copy.deepcopy at function top to enforce input-immutability contract"
    - "allowed_fields: frozenset[str] parameter for emission-vs-acceptance asymmetry"
key_files:
  created:
    - "backend/medieval_forge/services/research/__init__.py"
    - "backend/medieval_forge/services/research/overlay.py"
    - "backend/tests/unit/test_overlay_merge.py"
    - "backend/tests/unit/test_overlay_merge_strict_bound.py"
  modified:
    - "backend/medieval_forge/services/export/schemas.py"
    - "backend/tests/unit/test_export_schemas.py"
decisions:
  - "Q2 Tolerant verdict honored: _ZIP_BOUND_FIELDS == _ALL_OVERLAY_FIELDS — all three overlay fields safe to emit into Unity zip (MapLoader.cs JObject-tolerant per 07-Q2-UNITY-LOADER-VERDICT.md)"
  - "Schema kept BROADER than zip emission (REVIEWS fix #1): CondadoOverlayEntry always validates all three fields; allowed_fields parameter narrows emission, never acceptance — cache hits + reloads validate cleanly across verdict flips"
  - "Field(max_length=2048) on historical_notes enforced at pydantic boundary (T-07-05-05); validated at load_overlay_if_exists() before merge"
  - "merge_overlay() is the SINGLE source of truth — both Plan 08 build_unity_zip and Plan 08 artifact endpoint will import it"
  - "Drift between overlay.py constant and Q2 verdict file enforced by test_zip_bound_fields_matches_q2_verdict_file_value drift-guard test"
metrics:
  duration_minutes: 7
  tasks_completed: 3
  files_created: 4
  files_modified: 2
  tests_added: 20  # 5 schema + 10 overlay + 5 strict-bound
  completed_date: "2026-05-14"
---

# Phase 07 Plan 05: services/research overlay + export-schema extension Summary

merge_overlay() pure function and CondadoOverlayEntry pydantic shape landed; export schemas extended additively with two optional overlay fields and MANIFEST bumped 2→3 with research_overlay_applied: bool = False — Plan 08 can now consume both without further scaffolding, and Phase 06 parity stayed bit-identical (12/12).

## What was built

### Backend — services/research/ (new subpackage)

- **`overlay.py`** — three exported objects:
  - `CondadoOverlayEntry` — per-condado sidecar shape with `name: str | None`, `kingdom_owner: str | None`, `historical_notes: str | None = Field(default=None, max_length=2048)`. `ConfigDict(extra="forbid")` so a typo in user-edited overlay JSON fails loudly at load time (RESEARCH §Pitfall 8).
  - `ResearchOverlay(RootModel[dict[str, CondadoOverlayEntry]])` — top-level file shape.
  - `merge_overlay(metadata, overlay, allowed_fields=_ALL_OVERLAY_FIELDS) -> dict` — pure function. `copy.deepcopy(metadata)` at top guarantees input immutability; iterates condados; for each `condado["id"]` present in overlay, copies overlay fields ∩ allowed_fields with non-None values. Unknown condado_ids in overlay silently ignored. `original_idx` never touched (not in `_ALL_OVERLAY_FIELDS`).
  - `load_overlay_if_exists(path) -> dict | None` — returns None when file missing (D-12 zero-LLM guard); otherwise `json.loads` + `ResearchOverlay.model_validate` and returns the dict-shaped root. JSONDecodeError + ValidationError propagate intentionally — runner (Plan 07) decides how to surface.
  - `_ZIP_BOUND_FIELDS: frozenset[str] = frozenset({"name", "kingdom_owner", "historical_notes"})` — value copied verbatim from `07-Q2-UNITY-LOADER-VERDICT.md` (Tolerant verdict). Doc-comment block immediately above the constant documents the schema-vs-zip asymmetry contract per REVIEWS fix #1.
  - `_ALL_OVERLAY_FIELDS` — schema breadth, equal to `_ZIP_BOUND_FIELDS` under Tolerant verdict.

- **`__init__.py`** — re-exports the six public names.

### Backend — schemas.py extension (Phase 06 additive)

- `CondadoEntrySchema`: appended `kingdom_owner: str | None = None` and `historical_notes: str | None = None` after `original_idx`. `extra="forbid"` preserved — only the two documented overlay fields are accepted; truly-unknown extras still raise (Phase 06 test `test_territory_metadata_rejects_unknown_field_on_condado_via_extra_forbid` continues to pass).
- `MANIFEST_SCHEMA_VERSION: int` bumped 2 → 3 with explanatory comment block.
- `ManifestSchema`: appended `research_overlay_applied: bool = False` — Plan 08 will set True when build_unity_zip merged an overlay; default False preserves D-12 zero-LLM parity.

### Tests

- **`test_export_schemas.py`** — appended 5 cases:
  - kingdom_owner accept (extended schema)
  - historical_notes accept
  - extra='forbid' still rejects unknown fields beyond the documented two
  - MANIFEST_SCHEMA_VERSION is 3
  - research_overlay_applied default False + explicit True acceptance
- **`test_overlay_merge.py`** — 10 cases (8 plan-mandated + 2 bonus):
  - original_idx preservation
  - input-immutability (deepcopy invariant)
  - unknown condado_id silently ignored
  - all-3-fields merge
  - allowed_fields={"name"} drops the other two
  - load_overlay_if_exists returns None when absent
  - load_overlay_if_exists raises ValidationError on schema-invalid file
  - REVIEWS fix #1 Test 8 — historical_notes 2048/2049 boundary
  - bonus: None overlay value is no-op (invariant 4)
  - bonus: _ZIP_BOUND_FIELDS is a frozenset
- **`test_overlay_merge_strict_bound.py`** — 5 cases:
  - strict-verdict (allowed_fields={"name"}) drops kingdom_owner + historical_notes
  - tolerant-verdict (3-field) keeps all
  - _ZIP_BOUND_FIELDS ⊆ _ALL_OVERLAY_FIELDS containment
  - drift guard: cross-checks overlay.py constant against Q2 verdict file literal (regex match + eval)
  - REVIEWS fix #1 Test 5 — schema accepts all 3 but strict zip emits only name (asymmetry contract)

## How to verify

```bash
cd backend && pytest tests/unit/test_overlay_merge.py tests/unit/test_overlay_merge_strict_bound.py tests/unit/test_export_schemas.py -x -q
# 35 passed

cd backend && pytest tests/parity/test_iberia_868_yaml.py -x -q
# 12 passed (Phase 06 parity — schema extension is forward-compatible)

cd backend && python -c "from medieval_forge.services.research import merge_overlay, load_overlay_if_exists, ResearchOverlay, _ZIP_BOUND_FIELDS; print(_ZIP_BOUND_FIELDS)"
# frozenset({'kingdom_owner', 'historical_notes', 'name'})
```

## Deviations from Plan

None — plan executed exactly as written, including all REVIEWS fix #1 deltas (doc-comment block, `Field(max_length=2048)`, Test 5 + Test 8). The plan illustrated `CondadoEntrySchema` with `duchy: str | int` / `kingdom: str | int` / `pixel_center: list[int]`; the actual Phase 06 file uses `duchy: str` / `kingdom: str` / `pixel_center: tuple[int, int]`. The extension preserved the real Phase 06 types and only appended the two new Optional fields after `original_idx` — no breaking change.

## Authentication gates

None encountered.

## Known Stubs

None — `merge_overlay` is fully wired; `load_overlay_if_exists` is fully wired. Plan 08 will import both functions and call them at the two consumer boundaries (zip + artifact endpoint).

## Self-Check

- `backend/medieval_forge/services/research/__init__.py` — FOUND
- `backend/medieval_forge/services/research/overlay.py` — FOUND
- `backend/tests/unit/test_overlay_merge.py` — FOUND
- `backend/tests/unit/test_overlay_merge_strict_bound.py` — FOUND
- `backend/medieval_forge/services/export/schemas.py` — modified (MANIFEST=3, +2 overlay fields, +research_overlay_applied)
- `backend/tests/unit/test_export_schemas.py` — modified (5 new tests)
- Commits:
  - `94d40d4` — feat(07-05): extend export schemas
  - `580d054` — feat(07-05): add services/research/overlay.py
  - `ff4b75b` — test(07-05): add test_overlay_merge_strict_bound.py
- Test totals: 20 (schemas) + 10 (overlay) + 5 (strict-bound) = 35 unit, 12 parity = 47 green
- Q2 Tolerant verdict: honored — `_ZIP_BOUND_FIELDS` matches verdict file value (drift guard test 4 passes)
- REVIEWS fix #1: all three pieces present — doc-comment block, `Field(max_length=2048)`, Test 5 in strict-bound file

## Self-Check: PASSED
