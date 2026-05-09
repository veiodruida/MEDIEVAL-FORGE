---
phase: 01
reviewers: [gemini, codex, opencode]
reviewed_at: 2026-05-09T00:00:00Z
plans_reviewed:
  - 01-01-PLAN.md
  - 01-02-PLAN.md
  - 01-03-PLAN.md
self_skipped: claude
---

# Cross-AI Plan Review — Phase 01

> Note: Phase 01 is already executed and committed. This retroactive review surfaces gaps for Phase 02.1 backlog and informs future-phase planning. Run `/gsd-plan-phase 01 --reviews` is not applicable here; treat findings as informational.

## Gemini Review

# Implementation Plan Review: Phase 01 (Pipeline Parity)

## 1. Summary
The implementation plans for Phase 01 are exceptionally high-quality, demonstrating a rigorous commitment to the "verbatim port" strategy required for pixel-level parity. By decoupling environmental setup (`01-01`), algorithmic translation (`01-02`), and the final integration/gatekeeping (`01-03`), the plans minimize context pressure and provide clear audit trails. The use of a `PREFLIGHT.md` to resolve ground-truth ambiguities before a single line of code is ported is a standout engineering practice that significantly reduces the risk of "blind iteration" loops.

## 2. Strengths
*   **Decoupled Verification:** `Plan 01-01` forces an early resolution of the `original_idx` and `draw_names` unknowns. This prevents the "Nájera bug" from being baked into the port by assumption.
*   **Fidelity to Source:** The mapping of `inicio/map_generator.py` sections to specific submodules (e.g., `cleanup.py` handling all four median/smooth sub-stages) respects the original author's logic flow while providing a modern package structure.
*   **Determinism as a First-Class Citizen:** Promoting `rng_seed` to the `RegionConfig` and auditing for hardcoded `default_rng(42)` calls ensures that the parity tests will be stable across CI runs and developer environments.
*   **Efficiency in Testing:** Using a session-scoped fixture in `backend/tests/parity/conftest.py` is a crucial optimization, reducing a potential 9-minute test suite (12 files × 45s) down to ~1 minute.
*   **Surgical Deletion:** The import-graph-driven deletion plan in `01-03` prevents "ghost imports" and ensures that surviving v1 features (like the `edit` API) remain functional during the transition.

## 3. Concerns
*   **Font-Based SSIM Flakiness (LOW):** `render.py` (Task 7, Plan 01-02) uses a hardcoded Linux font path (`/usr/share/fonts/...`). While it includes a fallback to `ImageFont.load_default()`, different OS environments (Windows vs. CI) will render text differently.
    *   *Mitigation:* The preflight check in `Plan 01-01` suggests `draw_names = False` is likely for the golden fixtures, which renders this moot. If labels *are* required, vendoring a specific `.ttf` file in `data/fonts/` would be necessary.
*   **NPM Dependency for ES TopoJSON (MEDIUM):** `Plan 01-01 Task 2` relies on `npm pack` for Method A. If the environment lacks Node.js, it falls back to a GitHub raw URL. If the `master` branch on that external repo drifts before the fetch, parity is broken.
    *   *Mitigation:* Method A should be prioritized, or Method B should use a specific Git SHA in the URL to ensure immutability.
*   **Binary File Comparison Latency (LOW):** Comparing large GeoJSON files and high-res PNGs can be memory-intensive.
    *   *Mitigation:* The use of `tmp_path_factory` and `numpy.array_equal` is appropriate; local development machines should have enough RAM for the 30MB GeoJSON.

## 4. Suggestions
*   **Explicit Encoding for All I/O:** `Plan 01-02` correctly identifies the Windows `utf-8` bug for the ES TopoJSON. It is recommended to explicitly set `encoding="utf-8"` for *all* `json.load/dump` and `open()` calls in `landmask.py`, `lookup.py`, and `export.py` to avoid cross-platform encoding drifts.
*   **Diff-Mask Storage on Failure:** For the SSIM tests in `01-03-PLAN`, consider using `skimage.metrics.structural_similarity(..., full=True)` to save an actual SSIM difference map to the temp directory on failure. This provides much faster debugging than a simple score.
*   **Coordinate Precision:** Ensure `json.dump` in `export.py` uses a consistent `indent` or a specific float formatting if `pixel_center` ever produces non-integer floats (though the plan uses `int(xs.mean())`).

## 5. Risk Assessment
**Overall Risk: LOW**

The strategy is highly conservative and goal-oriented. The primary risk—failure to achieve 100% byte-parity—is mitigated by:
1.  **Isolation:** The v3 pipeline is built as a clean-room package.
2.  **Gold Standard:** The Reconquista Assets are the final arbiter, not the `inicio` script.
3.  **Strict Markers:** The `pytest-parity` marker prevents accidental regressions from unrelated unit test work.

The plan is ready for execution once the manual `PREFLIGHT.md` verdicts are recorded.

---

## Codex Review

## Plan 01-01 Review

### Summary
Plan 01-01 is a strong preflight/scaffold plan: it isolates unknowns before porting, locks fixture/input paths, and creates the package contract early. The biggest issue is that it formally narrows Phase 01 parity from the roadmap's 12-file contract to 10 files by deferring `terrain_lookup.png` and `terrain_types.json`. That may be technically justified by the research, but it conflicts with the stated Phase 01 success criteria unless the roadmap/contract is amended.

### Strengths
- Resolves the two parity-sensitive unknowns before implementation: `original_idx` and `draw_names`.
- Keeps `inicio/` read-only and moves territory data into an importable package path.
- Good separation between scaffolding and algorithm porting.
- Explicitly records provenance of fixtures, ES TopoJSON source, and LFS decision.
- Uses `@dataclass`, which matches the parity-first goal.
- Self-contained repo goal is well covered.

### Concerns
- **HIGH:** Deferring `terrain_lookup.png` and `terrain_types.json` contradicts Phase 01 success criteria and the 12-file Unity export contract. If accepted, the roadmap should be explicitly updated before execution.
- **HIGH:** Task 2 depends on network/npm/GitHub access to source ES TopoJSON. The plan says "auto," but this can fail offline or due to version drift.
- **MEDIUM:** `git lfs install` and LFS availability are assumed, but CI/developer clone behavior needs explicit validation.
- **MEDIUM:** Golden fixture count language is inconsistent: "11 deployed Reconquista files," "10 contract files + README," and "12 minus terrain deferred" may confuse implementers.
- **LOW:** Human visual inspection for `draw_names` is subjective; OCR or pixel/text-region check would be more reproducible.

### Suggestions
- Add an explicit Phase 01 contract amendment: either "Phase 01 parity is 10-file geometric parity; Phase 06 restores 12-file export parity" or require terrain generation now.
- Pin ES TopoJSON to a commit/package version and record checksum in `PREFLIGHT.md`.
- Add checksum verification for all copied golden/input files.
- Make `draw_names` verification more objective: compare known label-area pixels or run a simple image diff against a no-label render if available.
- Add a CI/LFS note: `git lfs pull` must run before parity, or add a test that fails clearly if the GeoJSON is an LFS pointer.

### Risk Assessment
**MEDIUM-HIGH.** The scaffold is sound, but the 10-file vs 12-file contract change is a phase-level risk, and ES TopoJSON/LFS provisioning can block execution.

---

## Plan 01-02 Review

### Summary
Plan 01-02 is thorough and correctly centered on a verbatim port, with good attention to deterministic behavior and known historical pitfalls. The main risk is that it mixes "verbatim port" with deliberate deviations: `cfg.rng_seed`, `cfg.draw_names`, `original_idx`, and 10-file output. Those deviations are justified, but they should be tracked as formal exceptions because they can undermine the auditability goal.

### Strengths
- Clear one-section-to-one-submodule mapping.
- Strong preservation of critical algorithm details: per-country KD-trees, sentinel values, median kernel sequence, NEAREST lookup upscale, independent 2x mask renders.
- Good standalone CLI smoke requirement.
- Explicitly avoids FastAPI dependency in the pipeline.
- Determinism requirement is concrete and testable.
- Keeps Phase 04 DAG/cache concerns out of scope.

### Concerns
- **HIGH:** Producing only 10 files means ROADMAP SC-1 and the 12-file Unity contract are not actually met as written.
- **HIGH:** "Verbatim" is weakened by multiple approved substitutions. Without a deviation ledger, later reviewers may not know what changed intentionally.
- **MEDIUM:** Smoke test checks file count, not exact filenames, schemas, image modes, dimensions, or JSON shape.
- **MEDIUM:** `pathlib.Path(args.out).resolve()` is mentioned in the threat model, but Plan 01-01's `__main__.py` shim does not include it. This is inconsistent.
- **MEDIUM:** Large end-to-end smoke may be slow and brittle during each task if earlier algorithm pieces are incomplete.
- **LOW:** Grep-based acceptance checks are useful but can pass despite behavior being wrong.

### Suggestions
- Add `DEVIATIONS_FROM_INICIO.md` or include a table in `01-02-SUMMARY.md`: `rng_seed`, `draw_names`, `territory data on cfg`, `original_idx per Q8`, terrain deferral.
- Strengthen Task 8 smoke checks:
  - Assert exact output filenames.
  - Assert expected dimensions for PNGs.
  - Assert lookup PNG image mode and JSON parseability.
  - Assert `mountain_river_data.json` copied unchanged.
- Decide whether CLI output path resolution belongs in Plan 01-01 or 01-02 and make both plans consistent.
- Add a tiny deterministic test comparing two complete output dirs, not only lookup PNGs.
- If 12-file parity remains required, port or rehome terrain lookup generation here instead of deferring.

### Risk Assessment
**MEDIUM-HIGH.** Algorithmic plan quality is high, but the phase-goal mismatch and "verbatim plus exceptions" tension create significant delivery risk.

---

## Plan 01-03 Review

### Summary
Plan 01-03 closes the phase cleanly: delete v1 generator code, add parity harness, require local green before CI flip, and make CI non-skippable. The sequencing is good. The key problem is again contractual: it declares ROADMAP SC-1 met with 10 tests covering 10 files, while the roadmap says lookup PNGs include `terrain_lookup.png` and JSONs include `terrain_types.json`.

### Strengths
- Good deletion discipline: import-graph-driven, deletes tests with production code, preserves known surviving modules.
- Correctly edits `main.py` in the same commit as deleting `api/generate.py`.
- Session-scoped parity fixture avoids repeated 45s pipeline runs.
- Local-green checkpoint before CI flip is the right control.
- CI flip is correctly last.
- Unit and integration tests cover basic pipeline API and FastAPI boot.

### Concerns
- **HIGH:** Claims ROADMAP SC-1 is met while excluding 2 of 12 contract files. This is a governance/acceptance mismatch.
- **HIGH:** Raising coverage from 60% to 85% may fail despite parity being green, especially after deleting tests and adding large untested pipeline code. This could block the phase for reasons unrelated to parity.
- **MEDIUM:** `pytest backend/tests/ -v -m "parity or integration or not slow"` may include unintended tests because `or not slow` selects almost everything not marked slow.
- **MEDIUM:** Deleting `api/generate.py` while leaving frontend calls to it intentionally broken is accepted, but there should be a visible tracking issue/Phase 03 dependency.
- **MEDIUM:** CI parity command includes integration tests. A flaky integration failure could be confused with parity failure.
- **LOW:** The parity diff image generation using `np.where(actual == golden, 0, 255)` can produce odd shapes for RGB images; acceptable for debugging, but not ideal.

### Suggestions
- Separate "parity required" and "integration required" CI jobs, or at least name/report them distinctly.
- Treat coverage bump as a separate risk. Add a pre-check before CI edit: `pytest backend/tests/unit/ --cov=medieval_forge --cov-fail-under=85` must already pass.
- Add a tracking note for frontend breakage caused by `/api/generate` deletion.
- Fix the success wording: "10-file Phase 01 parity gate" unless terrain files are restored.
- Add parity assertions that golden files do not include deferred terrain files, so the deferral stays explicit.

### Risk Assessment
**MEDIUM-HIGH.** The closeout mechanics are good, but CI coverage escalation and the 10-vs-12 contract gap can derail acceptance.

---

## Overall Assessment

The plans are well researched, sequenced, and pragmatic. They show strong awareness of parity pitfalls and keep the port auditable. The primary issue is not implementation detail; it is scope/contract drift. The project context says Phase 01 proves parity against the Reconquista exports and the 12-file Unity contract, but the plans intentionally ship a 10-file parity gate. That may be the right engineering choice given `inicio/map_generator.py`, but it must be made an explicit roadmap decision before execution.

### Overall Strengths
- Excellent dependency ordering: preflight → scaffold → port → harness/delete → CI gate.
- Strong preservation of historical algorithm pitfalls.
- Good use of local fixtures for deterministic CI.
- Sensible human checkpoints where evidence is needed.
- Surgical v1 deletion plan avoids broad cleanup risk.

### Overall Concerns
- **HIGH:** 10-file parity conflicts with the stated 12-file Phase 01 acceptance criteria.
- **HIGH:** Terrain lookup provenance is unresolved but pushed to Phase 06 without formally changing Phase 01.
- **MEDIUM:** LFS/npm/ES TopoJSON acquisition can block reproducibility.
- **MEDIUM:** Coverage gate jump to 85% may be unrelated to Phase 01's real goal and could become a distraction.
- **MEDIUM:** Multiple "verbatim port" exceptions need formal tracking.

### Recommended Changes Before Execution
- Add a decision record: "Phase 01 parity covers 10 files; terrain lookup deferred" or revise the plans to generate all 12 files.
- Pin ES TopoJSON source with version and checksum.
- Add a deviations ledger for all non-verbatim changes.
- Make coverage bump conditional on passing locally, or defer it if not required by the phase.
- Strengthen output smoke checks beyond file count.

### Overall Risk
**HIGH until the 10-file vs 12-file contract is resolved; MEDIUM after that.** The engineering plan is solid, but acceptance criteria ambiguity is a serious risk because a successful implementation could still fail the project's stated definition of done.

---

## OpenCode Review

# Phase 01 Plan Review: Pipeline Parity Port + Harness Together

## Summary

This is a comprehensive three-wave plan to port `inicio/map_generator.py` verbatim into a 9-submodule pipeline package, establish parity fixtures, delete the v1 generator stack, and lock CI gates. The plans are well-researched with deep references to inicio source code, existing pitfalls documented in JORNADA_CRIACAO_MAPA.md, and proper handling of non-negotiable CLAUDE.md rules. The main risks are around manual checkpoints (Task 1 and Task 3), potential input file schema mismatches, and the complexity of coordinating 17+ commits across three plans.

---

## Plan 01-01: Wave 0 Preflight & Scaffolding

### Strengths
- Preflight verification correctly identifies P-1 (original_idx) and Q10 (draw_names) as unknowns requiring manual inspection before port begins
- Territory data moved into package per D-13 with correct import path
- LFS configuration with fallback noted for 28 MB PT GeoJSON
- Package skeleton correctly uses @dataclass (not pydantic) per RESEARCH §9 Q1
- PREFLIGHT.md captures verdicts for downstream reference

### Concerns
| Severity | Issue | Details |
|----------|-------|---------|
| **HIGH** | Task 1 requires manual jq/visual inspection | The checkpoint `resume-signal: "approved"` blocks autonomous execution. If operator doesn't run the commands, plan stalls. No automated fallback if Reconquista path unavailable. |
| **MEDIUM** | ES TopoJSON sourcing not verified | Two methods proposed (npm pack or direct download) but neither verified against inicio's expected file structure. Could cause silent parity failures. |
| **MEDIUM** | LFS not guaranteed available | Fallback to direct commit exists but wasn't tested. 28 MB file in regular pack may bloat repo for subsequent clones. |
| **LOW** | No diff verification of territory_data.py | Task 4 verifies byte-identical but doesn't explicitly checkKINGDOMS/DUCHIES/CONDADOS values match inicio source |

### Suggestions
- Add a secondary verification: download ES TopoJSON and run `python -c "import json; data=json.load(f); assert 'municipalities' in data"` to validate schema before committing
- Include a stub test that fails fast if input JSON can't be parsed, preventing downstream parity test confusion

---

## Plan 01-02: Wave 1 Verbatim Port

### Strengths
- Excellent D-01 compliance: each inicio section maps cleanly to one submodule, function names/signatures/bodies verbatim
- All 7 CLAUDE.md non-negotiable rules handled:
  - Rule #1: Image.NEAREST in render.py
  - Rule #2: σ ∈ [3.0, 4.5] with per-mask reduction
  - Rule #3: per-country KD-trees (tp + te)
  - Rule #4: original_idx per PREFLIGHT Q8
  - Rule #5: sentinels -1 and 9999
  - Rule #6: 2x independent mask renders
  - Rule #7: cfg.rng_seed replaces hardcoded 42
- Good edge case handling: island_min_px scaling (P-11), border sampling every 3px (P-10), border-only-on-land (P-12)
- Session-scoped pipeline_output fixture (40-90s runtime) prevents 12x redundant pipeline runs in parity tests

### Concerns
| Severity | Issue | Details |
|----------|-------|---------|
| **HIGH** | Smoke test in Task 8 is advisory, not blocking | "Hard rule (Karpathy): the smoke run must produce 10 files before commit" but the verify block doesn't actually fail if smoke fails. Autonomy could ship broken pipeline. |
| **MEDIUM** | 8 sequential commits risk integration drift | If Task 4 (voronoi) has a bug, Tasks 5-8 may produce garbage that only fails at Task 8 verification. No intermediate sanity checks. |
| **MEDIUM** | RNG seed substitution across render.py needs verification | Two call sites (lines 537 and 904) must use cfg.rng_seed, but if any other `np.random.default_rng(42)` exists in ported code, determinism breaks silently. |
| **LOW** | P-1 fix depends on PREFLIGHT verdict | If Q8 verdict is wrong or PREFLIGHT.md is missing, Task 6's original_idx handling may be incorrect, causing JSON parity failure. |

### Suggestions
- Add `pytest backend/tests/unit/test_pipeline_smoke.py -v -m smoke` as an intermediate checkpoint after Task 4 to catch KD-tree issues early
- Pre-verify no `default_rng(42)` remains after port with: `grep -rn "default_rng(42)" backend/medieval_forge/services/pipeline/`
- Add explicit comment in export.py when original_idx IS emitted (per D-09 deployed-wins) to explain why this deviation from D-01 verbatim is justified

---

## Plan 01-03: Wave 2 Delete v1 + Parity Harness + CI Flip

### Strengths
- Import-graph driven deletion is precise: 5 production + 7 test files identified via backward trace from api/generate.py and services/generator.py
- main.py edit atomic with file deletion prevents broken-import intermediate state
- Parity harness correctly implements 10 parametrised tests (2 byte-equal + 4 SSIM + 4 JSON deep-equal), excluding terrain_lookup.png/terrain_types.json per P-2
- CI flip correctly placed as LAST commit per RESEARCH §7 to avoid gating in-flight commits
- Coverage gate raised to 85% as specified

### Concerns
| Severity | Issue | Details |
|----------|-------|---------|
| **HIGH** | Task 3 is a manual checkpoint requiring "approved" signal | This blocks autonomous execution. If parity fails, the plan doesn't specify how to triage or how many retry attempts are allowed before escalating. |
| **HIGH** | 14 files deleted in one commit | No granular rollback if something unexpected breaks (e.g., surviving consumer ImportError not caught by verification). |
| **MEDIUM** | No test for surviving import graph | Verification checks that deleted modules aren't imported, but doesn't verify surviving modules (voronoi.py, territory_builder.py, etc.) still import correctly after deletion. |
| **LOW** | P-2 deferral not validated at pipeline level | If someone later runs the pipeline expecting terrain_lookup.png, they'll get only 10 files with no warning in output. Could confuse users. |

### Suggestions
- Add explicit error message in run_pipeline output when files are missing: "Note: terrain_lookup.png and terrain_types.json deferred to Phase 06"
- Before Task 3 checkpoint, run a quick import sanity check: `python -c "import medieval_forge.services.voronoi; import medieval_forge.services.territory_builder; import medieval_forge.services.territories_geojson"` to confirm surviving modules still work
- Document in parity harness README that 10/12 files are covered, and what happens if someone adds terrain in Phase 06

---

## Risk Assessment

**Overall Risk Level: MEDIUM**

**Justification:**
- The plans are well-researched with 16 documented pitfalls from JORNADA_CRIACAO_MAPA.md
- D-01 verbatim port strategy is sound and auditable
- Session-scoped fixture prevents CI runtime bloat
- Strong verification at each wave boundary

**However:**
- Two manual checkpoints (Task 1 in 01-01, Task 3 in 01-03) break autonomy
- 28 MB input file and ES TopoJSON sourcing are external dependencies not verified until runtime
- 17+ commits across three plans create coordination complexity
- Deletion of 14 files in one atomic commit has blast radius risk

**Mitigations in place:**
- PREFLIGHT.md captures decisions for downstream reference
- CI flip placed last to avoid self-gating
- Golden fixtures committed before parity tests run
- Clear acceptance criteria for each task with automated verification commands

---

## Consensus Summary

### Agreed Strengths (mentioned by 2+ reviewers)

- **Decoupled wave structure** (01-01 preflight → 01-02 port → 01-03 delete/harness/CI). All 3 reviewers praise dependency ordering.
- **CLAUDE.md rule fidelity** — Rules 1-7 (NEAREST upscale, σ range, per-country KD-trees, original_idx, sentinels, 2x masks, rng_seed) preserved correctly.
- **Session-scoped pipeline fixture** — single ~45s pipeline run for all 10 parity tests is universally recognized as crucial CI optimization.
- **PREFLIGHT.md as evidence-first design** — both gemini and opencode call out resolving original_idx + draw_names before porting.
- **Surgical v1 deletion** — import-graph-driven, atomic with main.py edit, preserves surviving modules.
- **CI flip last** — placed at end of Plan 01-03 to avoid self-gating.

### Agreed Concerns (raised by 2+ reviewers — highest priority)

- **HIGH — 10-file vs 12-file contract gap** (codex × 3 plans, opencode LOW). ROADMAP SC-1 promises 12-file Unity contract; plans deliberately ship 10 files (terrain_lookup.png + terrain_types.json deferred to Phase 06). No formal roadmap amendment. Phase 01 closed as PASS but acceptance criteria ambiguous.
- **HIGH — Manual checkpoints break autonomy** (opencode HIGH × 2, codex MED). Task 1 in 01-01 + Task 3 in 01-03 require human "approved" signal. No automated fallback if operator unavailable; no retry policy on parity failure.
- **MEDIUM — ES TopoJSON sourcing fragility** (gemini MED, codex HIGH, opencode MED). npm pack OR GitHub raw URL — neither pinned to commit/version. Master-branch drift can silently break parity. No checksum verification.
- **MEDIUM — Smoke check too weak** (codex MED, opencode HIGH). Counts files only — does not assert filenames, dimensions, image modes, JSON shape. Bug could ship through.
- **MEDIUM — Verbatim port deviations not formally tracked** (codex HIGH, gemini implicit). `cfg.rng_seed`, `cfg.draw_names`, `original_idx`, 10-file output are all approved deviations but no DEVIATIONS_FROM_INICIO.md ledger.
- **MEDIUM — LFS assumption untested** (codex MED, opencode MED). `git lfs install` + clone behavior assumed; no failing test if GeoJSON arrives as LFS pointer.

### Divergent Views

- **Overall risk ratings spread widely**: Gemini LOW · OpenCode MEDIUM · Codex HIGH-until-contract-resolved. Codex weights the 12-vs-10 file contract gap as governance-blocking; gemini treats it as resolved by P-2 deferral; opencode acknowledges but moderates.
- **Coverage gate**: Codex flags raising 60% → 85% as risky-may-fail. Opencode names it as a strength. Gemini silent. (Real outcome: dev deferred to follow-up coverage-restoration plan; ci.yml currently gates at 60%.)
- **Encoding/UTF-8 hygiene**: Gemini explicitly recommends utf-8 everywhere (json.load/open). Codex/OpenCode silent. (Phase 02 code review WR-04 caught render.py omitting encoding — gemini's recommendation was correct.)
- **Manual checkpoints**: OpenCode flags as HIGH. Gemini calls them "sensible human checkpoints where evidence is needed" — opposite stance.

### Recommended Follow-ups for Phase 02.1 Backlog

1. Add deviation ledger: `01-DEVIATIONS-FROM-INICIO.md` listing all approved non-verbatim changes (rng_seed promotion, draw_names default, original_idx emission, 10-file contract).
2. Pin ES TopoJSON source: record git SHA + checksum in PREFLIGHT.md or input fixture README.
3. Strengthen smoke checks in any future Phase 04 parameter-studio work: assert exact filenames, dimensions, image modes, JSON shape — not just file count.
4. Resolve 12-vs-10 file contract: amend ROADMAP SC-1 or schedule terrain port in Phase 06 explicitly.
5. Tighten CI parity job: split parity from integration (codex MED), so flaky integration doesn't masquerade as parity failure.
6. Apply gemini's encoding-everywhere recommendation: audit remaining `json.load`/`open` calls in pipeline modules for missing `encoding='utf-8'` (already partially fixed by Phase 02 WR-04).

