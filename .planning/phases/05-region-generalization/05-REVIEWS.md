---
phase: 05
reviewers: [gemini, codex, opencode]
reviewed_at: 2026-05-12T15:32:27Z
plans_reviewed:
  - 05-01-PLAN.md
  - 05-02-PLAN.md
  - 05-03-PLAN.md
  - 05-04-PLAN.md
  - 05-05-PLAN.md
  - 05-06-PLAN.md
  - 05-07-PLAN.md
  - 05-08-PLAN.md
  - 05-09-PLAN.md
  - 05-10-PLAN.md
  - 05-11-PLAN.md
  - 05-12-PLAN.md
---

# Cross-AI Plan Review — Phase 05 Region Generalization

## Gemini Review

# Phase 05 Implementation Plan Review — Region Generalization

This review analyzes the 12 execution plans for Phase 05, including the gap-closure plans (05-11 and 05-12) designed to reach the 12-file Unity contract and satisfy human verification requirements.

## 1. Summary
Phase 05 is an architecturally sound transition from a hard-coded single-region pipeline to a data-driven, multi-region platform. The implementation strategy rigorously adheres to the **"Structure → Migrate → Delete"** pattern (D-17), ensuring that byte-equal parity with the legacy Iberian system is never broken during the swap. The addition of plans 05-11 and 05-12 successfully closes the critical gaps identified in initial verification, specifically the 12-file export contract and the necessity for live UAT browser verification. The use of Pydantic for schema enforcement and strict path-traversal guards demonstrates a high standard of engineering and security.

## 2. Strengths
*   **Hard Parity Invariant:** The dependency chain (D-17) is perfectly ordered. `test_iberia_868_yaml.py` (05-03) establishes a non-skippable gate *before* the legacy code is purged (05-05), preventing any "silent" regressions during the refactor.
*   **Security by Design:** Path traversal risks are mitigated at multiple layers: regex validation of region keys, `pathlib.Path.relative_to` checks for dataset resolution, and Pydantic-level input validation for the `POST /api/v3/projects` endpoint.
*   **Contract Integrity:** Plan 05-11 specifically addresses the SC-3 gap by implementing `terrain_lookup.png` and `terrain_types.json`. By anchoring the 12-file list in a single constant (`EXPORT_FILE_CONTRACT`), the plan eliminates drift between the exporter and the E2E test suite.
*   **Deterministic Toy Generation:** `gen_toy_france.py` (05-06) uses jittered-grid Voronoi with a locked `rng_seed=42`, ensuring that the SC-3 "contract gate" is reproducible across different environments without requiring massive geographic datasets.
*   **Singleton Safety:** Explicit focus on **Pitfall 9** (Singleton Mutation) in Plan 05-04 via `dataclasses.replace` is a mature design choice that prevents concurrent request corruption in the cached loader.

## 3. Concerns
*   **Autogen Efficiency (MEDIUM):** As noted in `05-REVIEW.md` (WR-01), `_autogen_territories` reads the same file twice for single-country regions. While functional correctness is maintained via `original_idx` uniqueness, this produces ~80 condados for France instead of the intended ~40. Plans 05-11/12 correctly log this to `STATE.md` as out-of-scope, but it remains a technical debt item that may impact performance in Phase 06/07.
*   **Singleton Mutation in Tests (LOW):** `test_iberia_868_yaml.py` contains a direct mutation of the `load_region` result (Pitfall 9). While mitigated by the `clear_region_cache_between_tests` autouse fixture, it violates the phase's core mandate on immutability.
*   **Complex Startup in UAT (LOW):** Plan 05-12 relies on a `checkpoint:human-verify`. While necessary for visual sign-off, the complexity of background process management (killing PIDs, waiting for 200 OK) makes the local runner script sensitive to environment-specific `pkill` behavior.

## 4. Suggestions
*   **Tighten Autogen Bounds:** In Plan 05-06, the unit test `test_load_region_autogen` should assert `40 <= len(cfg.condados) <= 50`. Currently, it only checks `>= 40`, which allows the 80-condado doubling bug to pass undetected.
*   **Fix WR-02 Immediately:** Before closing Phase 05, the `test_iberia_868_yaml.py` fixture should be updated to use `replace(load_region(...), output_dir=...)`. Leaving a known Pitfall 9 violation in the *canonical parity gate* is a poor precedent for Phase 06.
*   **Accessibility Labels:** In Plan 05-08 (`NewProjectModal.tsx`), ensure `<Text as="label">` uses the `htmlFor` prop linked to the `TextField` ID. This is required for Playwright's `getByLabel` selector to work reliably and for proper screen reader support.

## 5. Risk Assessment
**Risk Level: LOW**

The phase is low-risk due to the exhaustive automated test coverage (Unit, Parity, and E2E) and the "golden set" comparison for Iberia. The most complex logic (the 11-stage pipeline) is already proven; Phase 05 merely changes the *injection source* of the configuration. The gap closure plans (11 and 12) have finalized the Unity contract requirements, leaving no known functional gaps before Phase 06.

**Approved for execution.**


---

## Codex Review

## Summary

Phase 05 is generally well-planned and has a strong migration strategy: externalize Iberia into YAML, prove parity before deleting legacy code, then extend the system to France/England through the same loader/API/UI path. The plan set is unusually thorough on security, test coverage, and sequencing. The main risks are implementation complexity in `region_loader.py`, possible over-scoping through frontend/UAT scaffolding in early waves, and the late terrain gap closure in 05-11, which does close SC-3 on paper but should be treated as a minimal contract implementation, not a real terrain system.

## Strengths

- **Good D-17 sequencing.** Plans 05-01 → 05-05 preserve the parity-gate-green invariant: loader first, YAML migration second, parity gate third, callsite swap fourth, deletion last.

- **Security is taken seriously.** `load_region()` validates `region_key`, uses `yaml.safe_load`, forbids unknown YAML keys, and guards dataset paths with `relative_to(region_root)`.

- **Pitfall 9 is correctly identified.** The plans repeatedly require `dataclasses.replace(load_region(...), ...)` before mutating per-run fields, which is necessary because the loader cache returns shared config objects.

- **Good coverage shape.** The phase includes unit tests for schema/cache/autogen, parity tests for Iberia, API tests for regions/projects, backend E2E for France export, frontend unit tests, and Playwright UAT.

- **05-11 closes the explicit SC-3 gap.** Moving `terrain_lookup.png` and `terrain_types.json` into `EXPORT_FILE_CONTRACT` and emitting them in `_write_outputs_to_disk` satisfies the ROADMAP’s “file contract IS” wording.

- **France/England scope is disciplined.** Empty territory arrays plus deterministic autogen respect the “geometry only, research deferred” boundary.

## Concerns

- **HIGH: `region_loader.py` is doing too much in 05-01.** It owns schema validation, path security, dataset resolution, cache behavior, territory conversion, GeoJSON parsing, autogen, and test scaffolding. That is a lot for the first wave and makes defects likely. D-03 autogen in particular is domain logic, not just config loading.

- **HIGH: 05-01 scaffolds too many future test files.** Creating placeholder tests across backend, frontend, and Playwright before the relevant code lands risks fake confidence and churn. It also weakens the signal of “pytest collection clean” because skipped placeholders can hide plan drift.

- **HIGH: Autogen double-read bug is real and should not be deferred casually.** Since `france_1066.yaml` intentionally points `pt_geojson` and `es_input` to the same file, `_autogen_territories` must dedupe paths. Otherwise France produces ~80 condados from ~40 features, which undermines the visual/UAT expectation and performance assumptions.

- **MEDIUM: 05-11 terrain implementation is contract-minimal.** A flat “plains everywhere on land, ocean sentinel elsewhere” satisfies the 12-file export contract, but it may create a misleading sense that terrain is implemented. The summary and docs must be explicit that this is a placeholder contract emitter.

- **MEDIUM: `OCEAN_RGB = (0,0,0)` collision guard may be too strict.** Guarding black against all visual colors can fail future legitimate palettes. It is acceptable for Phase 05, but this should be documented as an export sentinel constraint, not a general terrain rule.

- **MEDIUM: Plan 05-04 adds `POST /api/v3/projects` instead of extending existing project creation.** This resolves the open question, but it creates two creation paths. The plan should explicitly define which one the UI uses and whether legacy `/projects` remains supported long-term.

- **MEDIUM: `region_key` validation differs by layer.** Loader regex uses `^[a-z0-9_]+$`, while API uses length constraints too. Consider one shared helper or constant to avoid drift.

- **MEDIUM: Cache policy is explicit-only but still returns mutable singletons.** This is workable only if every consumer uses `replace()`. The remaining parity-test mutation found in review shows this rule is easy to violate.

- **LOW: Path anchor comments are brittle.** Repeated “parents[4], do not change” comments lock a fragile implementation. A shared `repo_root()` helper would be safer and less noisy.

- **LOW: 05-12 runner process cleanup on Windows is fragile.** The PowerShell process-kill filter may miss dev servers because `node` window titles are not reliable. It is acceptable for UAT helper scripts but not robust automation.

## Suggestions

- Split 05-01 internally: keep loader/schema/path/cache first, then add autogen as a focused second task with its own tests.

- Replace placeholder future tests with either real minimal contract tests or omit them until the implementation plan that owns them.

- Fix `_autogen_territories` path dedupe before UAT:
  ```python
  seen_paths: set[Path] = set()
  for geojson_path in (dataset.pt_geojson, dataset.es_input):
      if geojson_path in seen_paths:
          continue
      seen_paths.add(geojson_path)
  ```

- Tighten France autogen tests to assert a bounded count, e.g. `40 <= len(cfg.condados) <= 50`, not only `>= 40`.

- Fix `backend/tests/parity/test_iberia_868_yaml.py` to use `replace(load_region(...), output_dir=...)`.

- Create a shared path helper for region root discovery instead of repeating `parents[4]` in API modules.

- Make 05-11 comments explicit: terrain files are Phase 05 contract placeholders, richer terrain is deferred.

- In 05-10/05-11, ensure `EXPORT_FILE_CONTRACT` is the only source of truth and the export writer/test both import it.

- Add a test that verifies `load_region("france_1066")` is deterministic across `clear_region_cache()` calls, including generated `original_idx`, colors, and condado order.

- For 05-12, add a fallback note for Windows users if `pwsh` is unavailable: `powershell -ExecutionPolicy Bypass -File scripts/run_france_uat.ps1`.

## Risk Assessment

**Overall risk: MEDIUM.**

The architecture and sequencing are sound, and the plans directly address the major correctness risks: parity preservation, safe YAML loading, path traversal, mutable cached configs, and the 12-file export gap. Risk remains medium because the phase touches many layers at once, introduces a complex loader/autogen path, and relies on late gap closures for SC-3. The biggest practical risk is not security or parity; it is subtle data-shape drift in autogen/export behavior that passes tests but produces visually odd France output.


---

## OpenCode Review

## Phase 05 Plan Review

### Summary

Phase 05 ("region generalization") delivers a clean YAML-driven region loader, a new `POST /api/v3/projects` endpoint with strict validation, a `GET /api/v3/regions` discovery endpoint, three region templates (Iberia migrated, France toy, England YAML-only), a frontend `NewProjectModal` with Radix primitives, and a France 1066 E2E test. Plans 05-11/05-12 were added as gap closures after verification identified that the pipeline was producing 10 files instead of the 12-file Unity contract. The architecture is sound and security is handled well, but the retroactive scope expansion reveals a planning gap that should have been caught in the original 10-plan sequence.

---

### Strengths

- **Security is first-class.** `yaml.safe_load` enforced (no `yaml.load`), `^[a-z0-9_]+$` region key regex before any filesystem access, `relative_to(region_root)` traversal guard on dataset paths, pydantic `extra='forbid'` schema, and `Field(ge=3.0, le=4.5)` on `smooth_sigma` — all five security boundaries from RESEARCH T-05-01-01 through T-05-04-04 are covered. The threat model in each plan is accurate.
- **D-17 sequencing is the strongest part of this phase.** The 10-plan ordering (loader → YAML emit → YAML parity gate → callsite swap → delete → France toy → regions endpoint → frontend modal → England YAML → France E2E) enforces the parity-gate-stays-green invariant at the commit level. The rule "Plan 05-05 deletion cannot land before Plan 05-03 YAML parity gate" is explicit and enforced by the `depends_on` chain.
- **Explicit-only cache policy** (recommended in RESEARCH, adopted in D-15) avoids Windows mtime resolution flake (1-second FAT / 100ns NTFS with caching that masks back-to-back edits). The `dataclasses.replace()` immutability pattern in `generate.py` and `render.py` is consistent and correct.
- **`dataclasses.replace(cfg, ...)` everywhere** — the singleton-non-mutation contract (RESEARCH Pitfall 9) is applied uniformly across production callsites (05-04 Tasks 2-3), test fixtures (05-05 Task 2), and the France E2E test (05-10). The integration test `test_load_region_singleton_not_mutated` regression-guards this contract.
- **Path depth comment is permanent** — both `api/v3/projects.py` and `api/v3/regions.py` carry `parents[4] DO NOT change to parents[3]` comments anchoring the empirical fix. This prevents the regression from re-entering future work.
- **`EXPORT_FILE_CONTRACT` as single source of truth** (R-14, Plan 05-10/05-11) prevents silent drift. The tuple constant in `contracts.py` is imported by the E2E test — any rename now produces an import-time error rather than a silent test pass.
- **Autogen fallback is clean separation** — loader-side synthesis keeps the pipeline branch Iberia-agnostic. `original_idx` is required on every autogen condado (CLAUDE.md rule #4, Nájera bug guard), enforced in the generator loop and verified by `test_load_region_autogen`.

---

### Concerns

1. **[HIGH] Retroactive SC-3 gap — 05-11/05-12 scope creep.** The ROADMAP Phase 05 entry lists 10 plans; VERIFICATION identified that the pipeline produces 10 files, not 12, and added two gap-closure plans. The deferral was documented in a code comment (`EXPORT_FILE_CONTRACT_DEFERRED`) but this is not a ROADMAP-approved deviation. Plans 05-11/05-12 retroactively expand Phase 05 scope by ~20%. This is the right call (SC-3 wording "file contract IS" is unambiguous), but it should have been caught during Phase 05 planning, not post-verification. The root cause is that no plan in the original 10 explicitly verified the 12-file contract against `CLAUDE.md` — the E2E test in Plan 05-10 was written against a 10-file `_ALWAYS_PRESENT` set.

2. **[HIGH] WR-01: Autogen double-read produces ~80 condados for single-country regions.** `_autogen_territories` in `region_loader.py:389-411` iterates `(dataset.pt_geojson, dataset.es_input)` unconditionally. France 1066 and England 1216 YAMLs point both fields at the same file (documented single-country fallthrough). Every feature is appended twice, yielding ~80 condados instead of ~40. The unit test `test_load_region_autogen` asserts `>= 40` which passes for both 50 and 100, masking the regression. The code review correctly flags this. **Impact:** No CLAUDE.md rule is violated (`original_idx` uniqueness is preserved), but Voronoi seed collision produces spurious barony centroids and the E2E test's cardinality assertions (if any) could be wrong.

3. **[HIGH] WR-02: Parity test mutates `load_region()` singleton** (`test_iberia_868_yaml.py:42-44`). Direct `cfg.output_dir = str(out)` on the cached object — the exact pattern CLAUDE.md's Pitfall 9 / T-05-04-04 rule prohibits. The `clear_region_cache_between_tests` autouse hides the blast radius in CI, but this is a focus-area violation. Every other touchpoint in the phase uses `replace()` — the parity test is the outlier. Fix is a one-line change.

4. **[MEDIUM] Autogen condados: `pt_geojson == es_input` produces duplicate seeds.** When `france_1066.yaml` sets `pt_geojson: inputs/france_municipalities_toy.geojson` and `es_input: inputs/france_municipalities_toy.geojson`, the autogen reads the same file twice. The dedup loop at `_autogen_territories` uses `original_idx` dedup (which is always unique) but does NOT prevent the `representative_point` computation from running twice. Result: centroid coordinates for the same polygon appear twice in the seed list → Voronoi seeds are duplicated → more cells than intended.

5. **[MEDIUM] Plan 05-12 `checkpoint:human-verify` is architecturally inconsistent with automated CI.** The checkpoint asks the user to run `bash scripts/run_france_uat.sh` or `pwsh scripts/run_france_uat.ps1` locally. The resume signal is `approved`/`aprovado`. But Phase 04.1-05 Playwright specs are expected to run in CI (`npx playwright test --reporter=line`). If the user says `approved`, the spec has still never run in a CI headless browser session — only in the user's local headed session. The cross-regression check ("all prior Playwright specs stay green") requires running the full suite, which may not be what the user tested.

6. **[MEDIUM] `export.py` `EXPORT_FILE_CONTRACT` update vs `__init__.py` wire-up is split across Plans 05-10 and 05-11.** Plan 05-10 adds `EXPORT_FILE_CONTRACT` constant to `contracts.py` and imports it in the E2E test. Plan 05-11 edits `__init__.py` to wire the actual terrain writes and updates `contracts.py` to expand the tuple from 10→12. If Plan 05-10 commits before Plan 05-11, the constant would list 10 files but the actual pipeline would still be writing 10 — the E2E test would pass because the constant and the pipeline match. The gap would only surface when Plan 05-11 ships the terrain writes. This ordering risk exists within the gap-closure sequence.

7. **[MEDIUM] England's `load_region` error path depends on the template-only guard ordering.** Plan 05-09's `test_england_1216_missing_inputs.py` asserts that `load_region('england_1216')` raises `FileNotFoundError` containing "template-only". This depends on the `_autogen_territories` path NOT firing before the dataset existence check. The current code flow is: YAML parse → `_resolve` each dataset path → `FileNotFoundError` if any missing. Since England has empty `dataset.*` fields, `_resolve` is never called (all `None`), so the `all_unset` check fires. If future work changes the order (e.g., autogen before path resolution), the error message changes.

8. **[MEDIUM] `region_loader.py:350-360` no-op try/except** — catches exactly the exceptions the inner `_resolve` raises and re-raises unchanged. Harmless but misleading. This is INFO-02 in the code review.

9. **[LOW] England 1216 YAML's `pt_geojson: inputs/england_municipalities.geojson` points to a file that will never exist** (`inputs/` directory absent). The `all_unset` check in `load_region` catches this, but `_resolve` is never called because all three fields are `None` after the YAML is parsed... wait, no — England's YAML has all three dataset fields populated (`pt_geojson`, `es_input`, `mountain_river_json` all point to `inputs/...`). The YAML is not missing fields; the paths just point to non-existent files. So `_resolve` IS called, and `resolved.exists()` returns `False`, triggering `FileNotFoundError("template-only")`. This is correct, but it means the "template-only" error message is slightly misleading — England's dataset block is populated, the files just don't exist on disk.

10. **[LOW] `Select.Root` mixed controlled/uncontrolled mode** (`NewProjectModal.tsx:144-148`). `defaultValue="iberia_868"` and `value={regionKey}` both set — Radix uses the controlled `value`, making `defaultValue` dead. React DevTools warns. The initial value is already wired via `useEffect` at lines 42-46, so `defaultValue` is redundant.

11. **[LOW] `<Text as="label">` without `htmlFor`** (`NewProjectModal.tsx:120, 140`). Visual labels with no accessibility association. Playwright UAT already documents the consequence — spec uses placeholder-based selection. Fix is 2 lines per label.

---

### Suggestions

1. **Fix WR-01 (autogen double-read) before Phase 06 ships.** Add a `seen_paths: set[Path]` dedup in `_autogen_territories` (see code review fix) and tighten the unit test bound to `40 <= len(cfg.condados) <= 55` to catch regressions. Alternatively, route single-country regions (where `pt_geojson == es_input`) through a one-tree autogen path that skips the duplicate read.

2. **Fix WR-02 (parity test singleton mutation) in the same commit as any future work on `test_iberia_868_yaml.py`**. One-line `cfg = replace(load_region("iberia_868"), output_dir=str(out))` fix. This is consistent with every other test fixture in the phase.

3. **Run the France Playwright spec in a CI headless session** before Phase 06 begins, not just via the 05-12 checkpoint. The user's local headed session validates the visual surface; the CI headless run validates that the spec is reproducible without a display. These are complementary, not substitutes.

4. **Add `terrain_lookup.png` and `terrain_types.json` to the YAML parity test's parametrized file list** (in `test_iberia_868_yaml.py` or its golden file fixture) once Plan 05-11 ships. Today the parity test does NOT check these files because they were absent from the Phase 01 golden set. Plan 05-11 intentionally does not compare them (terrain is new output), but Phase 06 should add a structural-equal assertion for `terrain_types.json` to catch schema drift.

5. **Clarify in `data/regions/england_1216.yaml`** that the dataset fields point to intentionally-absent files (`inputs/england_municipalities.geojson`) and that `load_region` raises `FileNotFoundError` with "template-only" for this reason. A comment avoids confusion when a future developer reads the YAML and wonders why `has_dataset: false`.

6. **Remove `defaultValue="iberia_868"` from `Select.Root`** in `NewProjectModal.tsx:144`. The initial value is already set by the `useEffect` at lines 42-46 that calls `setRegionKey(defaultRegionKey(regions))`. Redundant `defaultValue` is dead code that causes React DevTools warnings.

7. **Add `htmlFor` to the two label elements** in `NewProjectModal.tsx:120, 140`. Wrap the inputs in `id` attributes and link them with `htmlFor`. This makes the Playwright spec more robust (can use `getByLabel` instead of placeholder-based selection) and fixes the accessibility violation.

8. **Replace `Toast.Root duration={Infinity}`** with a documented value (`duration={1000 * 60 * 60 * 24}`) per the code review fix, or remove `duration` entirely and rely on user-driven dismiss.

9. **Delete the unused `_make_toy_region_with_territories` helper** in `test_region_loader.py:100-141` — it's defined but never called and contains a duplicated `kingdoms:` YAML key.

10. **Delete `_make_on_stage` dead helper** in `render.py:94-99` — defined but never referenced; the producer inlines an equivalent closure.

11. **Remove the no-op try/except** in `region_loader.py:350-360` — let exceptions propagate naturally.

---

### Risk Assessment

| Risk | Likelihood | Impact | Overall |
|------|-----------|--------|---------|
| WR-01 autogen double-read propagates to Phase 06 validation | HIGH (already present) | MEDIUM (Voronoi seeds collide; original_idx preserved) | **MEDIUM** |
| WR-02 parity test singleton mutation breaks under concurrency | MEDIUM (CI has autouse cache clear; parallel pytest-xdist would fail) | HIGH (randomized output_dir across workers) | **HIGH** |
| Phase 06 re-validates Phase 05 gap-closure work (05-11 terrain) | LOW (terrain.py tested in 05-11 unit + e2e + smoke) | LOW | **LOW** |
| England "template-only" error message changes if autogen order changes | LOW | LOW | **LOW** |
| Playwright UAT not reproducible in CI headless (05-12 checkpoint only) | MEDIUM | MEDIUM | **MEDIUM** |
| `EXPORT_FILE_CONTRACT` constant and pipeline output drift (05-10→05-11 ordering) | LOW (05-11 depends on 05-10; constant and wire-up ship together) | HIGH | **MEDIUM** |

**Overall Phase 05 Risk: MEDIUM.**

The phase is well-structured, security is solid, and the core deliverables (YAML loader, `load_region`, region selection wire, France toy, frontend modal) are clean and correct. The two warnings (autogen double-read, parity test mutation) are live bugs, not hypothetical risks. Both are fixable in a single commit each. The SC-3 gap closure (05-11/05-12) is the right call but reveals that the original 10-plan sequence missed an end-to-end 12-file contract assertion — this should be remedied before Phase 06 begins, not deferred to Phase 06's validation work.


---

## Consensus Summary

All three reviewers approve Phase 05's architecture and sequencing. Risk verdicts: **Gemini LOW, Codex MEDIUM, OpenCode MEDIUM** — divergence driven by how much weight each places on live warnings (WR-01/WR-02) and 05-11/05-12 retroactive scope expansion.

### Agreed Strengths (2+ reviewers)

- **D-17 sequencing preserves Iberia parity invariant** — loader → YAML emit → parity gate → callsite swap → delete order is correct (Gemini, Codex, OpenCode).
- **Security posture is solid** — `yaml.safe_load`, `^[a-z0-9_]+$` region key regex, `relative_to(region_root)` path-traversal guard, pydantic `extra='forbid'`, `Field(ge=3.0, le=4.5)` on `smooth_sigma` (Gemini, Codex, OpenCode).
- **Pitfall 9 / singleton-non-mutation contract** explicitly enforced via `dataclasses.replace()` on production callsites (Gemini, Codex, OpenCode).
- **`EXPORT_FILE_CONTRACT` as single source of truth** prevents drift between exporter and E2E test (Gemini, Codex, OpenCode).
- **Deterministic France toy** — `rng_seed=42` Voronoi-from-grid keeps SC-3 reproducible (Gemini, OpenCode).

### Agreed Concerns (2+ reviewers) — highest priority

- **HIGH — WR-01: `_autogen_territories` double-read** (Gemini, Codex, OpenCode). `region_loader.py:389-411` iterates `(dataset.pt_geojson, dataset.es_input)` unconditionally; France/England point both fields at the same file, yielding ~80 condados instead of ~40. Unit test asserts `>= 40` which masks the regression. Fix: `seen_paths: set[Path]` dedup + tighten bound to `40 <= len(cfg.condados) <= 55`.
- **HIGH — WR-02: parity test mutates `load_region()` singleton** (Gemini, Codex, OpenCode). `test_iberia_868_yaml.py:42-44` does `cfg.output_dir = str(out)` on the cached object — exact Pitfall 9 pattern. `clear_region_cache_between_tests` hides blast radius; pytest-xdist parallel runs would break. One-line `replace()` fix.
- **MEDIUM — 05-11 terrain is contract-minimal placeholder, not a terrain system** (Codex, OpenCode). Flat `plains-everywhere-on-land + ocean sentinel` satisfies the 12-file Unity export contract but must be documented as a placeholder emitter so Phase 06/07 do not treat terrain as "done".
- **MEDIUM — `EXPORT_FILE_CONTRACT` ordering between 05-10 and 05-11** (Codex, OpenCode). The constant lives in `contracts.py`; if 05-10 ships with the 10-file tuple before 05-11 expands it to 12, the E2E test passes against the smaller contract. Both reviewers want the constant + wire-up to ship in a single commit.
- **MEDIUM — 05-12 platform-specific UAT runner fragility** (Codex, Gemini, OpenCode). Codex flags Windows `pwsh` not-installed fallback; Gemini flags `pkill` portability; OpenCode flags lack of CI headless reproducibility. All converge on: local `checkpoint:human-verify` is necessary but not sufficient — the spec also needs to run headless in CI before Phase 06.

### Divergent Views (worth investigating)

- **Codex flags 05-01 as over-scoped** (schema + path-security + dataset resolution + cache + territory conversion + GeoJSON parsing + autogen + scaffolding all in one wave). Suggests splitting autogen into its own task. Gemini and OpenCode do not raise this — they treat 05-01 as a coherent loader unit. Tie-breaker: 05-01 is already merged; the split is a deferred refactor candidate, not a Phase 05 blocker.
- **Codex flags two project-creation paths** (legacy `/projects` + new `POST /api/v3/projects`). Suggests defining which the UI uses long-term. OpenCode and Gemini do not raise this — they accept the parallel path as v3 scope. Worth a one-line note in PROJECT.md or a backlog item.
- **Overall risk verdict**: Gemini calls LOW citing exhaustive test coverage and proven pipeline; Codex and OpenCode call MEDIUM citing live WR-01/WR-02 warnings and scope drift. Treat MEDIUM as canonical — two live bugs are not "exhaustive coverage".

### Recommended Next Actions

1. **Before closing Phase 05**: fix WR-01 (autogen dedupe + tighter bound) and WR-02 (parity test `replace()`) in a single commit each. Both have one-line code review fixes.
2. **Before Phase 06 begins**: add `terrain_lookup.png` / `terrain_types.json` structural-equal assertion to the YAML parity test (currently absent from Phase 01 golden set).
3. **Before Phase 06 begins**: run France Playwright spec in CI headless mode in addition to the 05-12 local checkpoint — they validate complementary surfaces.
4. **Cleanup nits**: remove redundant `defaultValue` on `Select.Root`, add `htmlFor` to label elements, delete dead helpers (`_make_toy_region_with_territories`, `_make_on_stage`), remove no-op try/except at `region_loader.py:350-360`.

