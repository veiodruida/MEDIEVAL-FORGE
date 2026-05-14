---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 00
subsystem: research-gate
tags: [unity-loader, newtonsoft, jobject, q2-gate, overlay-contract]

# Dependency graph
requires:
  - phase: 07-llm-research-as-opt-in-metadata-layer
    provides: 07-RESEARCH.md §Pattern 5 + §Open Questions §2 (Wave 0 Q2 verification dependency)
provides:
  - Wave 0 Q2 verdict file `07-Q2-UNITY-LOADER-VERDICT.md` (VERDICT: Tolerant)
  - Cleared value of `_ZIP_BOUND_FIELDS = frozenset({"name", "kingdom_owner", "historical_notes"})` for Plan 05
  - First-hand evidence pointer to `Reconquista/Assets/Scripts/Simulation/MapLoader.cs:196` (JObject-based deserialization)
affects:
  - 07-05 (overlay.py merge_overlay implementation — uses `_ZIP_BOUND_FIELDS`)
  - 07-08 (zip-build merge wiring — depends on bound fields)
  - any future plan touching Reconquista JSON contract

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 GATE pattern: blocking verification file consumed by downstream plans' read_first lists"
    - "Verdict-as-source-of-truth: a single .md file flips a backend constant, preventing drift across plans"

key-files:
  created:
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-Q2-UNITY-LOADER-VERDICT.md
  modified: []

key-decisions:
  - "VERDICT Tolerant — Reconquista Unity loader (MapLoader.cs:196) uses JsonConvert.DeserializeObject<JObject>, not a POCO; unknown JSON keys are silently ignored"
  - "Canonical Reconquista source path is C:\\Users\\veio_\\Documents\\Unity_Projects\\Reconquista\\Assets\\Scripts\\ on this machine; the D:\\Projetos_Jogo\\... path referenced in CLAUDE.md/07-CONTEXT.md is stale and the verdict file documents this"
  - "Plan 05 cleared to set `_ZIP_BOUND_FIELDS = frozenset({\"name\", \"kingdom_owner\", \"historical_notes\"}) == _ALL_OVERLAY_FIELDS` (no field restriction at zip-build time)"

patterns-established:
  - "Q-gate verdict file: a .md with `## VERDICT: <Tolerant|Strict|Unverifiable-default-Strict>` line + Evidence + Plan-N instruction block, consumed verbatim by downstream plans"
  - "Defense-in-depth grep audit: cross-check the verdict with `MissingMemberHandling|JsonExtensionData` grep across the Unity Assets/Scripts tree (0 hits confirms Tolerant)"

requirements-completed: [V3-LLM-OPT-IN]

# Metrics
duration: ~20min (Task 1 source inspection + verdict authoring; Task 2 user verification)
completed: 2026-05-14
---

# Phase 07 Plan 00: Q2 Unity Loader Strictness Gate Summary

**Wave 0 Q2 GATE resolved: Reconquista Unity loader is Tolerant (`JsonConvert.DeserializeObject<JObject>` at `MapLoader.cs:196`), clearing all three overlay fields (`name`, `kingdom_owner`, `historical_notes`) for zip-build merge in Plan 05.**

## Performance

- **Duration:** ~20 min total wall-clock (Task 1 inspection + verdict authoring; Task 2 user verification)
- **Started:** 2026-05-14 (Task 1 commit `8075685`)
- **Completed:** 2026-05-14 (Task 2 user-approved)
- **Tasks:** 2 / 2
- **Files modified:** 1 (one new verdict file)

## Accomplishments

- Located the live Reconquista Unity source tree at `C:\Users\veio_\Documents\Unity_Projects\Reconquista\Assets\Scripts\` (CLAUDE.md's `D:\Projetos_Jogo\...` path is stale on this machine).
- Inspected `Simulation/MapLoader.cs` `ParseTerritoryMetadata` (lines 193–227) and confirmed:
  1. Deserialization target is `JObject`, not a POCO — no `MissingMemberHandling` flag exists to flip.
  2. Per-key reads use `c["key"]?.Value<T>() ?? default` (defensive null-conditional + fallback) for kingdoms, condados, and baronies.
  3. Grep across `Assets/Scripts/` for `MissingMemberHandling|JsonExtensionData` returned 0 hits.
- Authored `07-Q2-UNITY-LOADER-VERDICT.md` with VERDICT line, primary-source evidence (file path + line numbers + verbatim C# snippet), cross-reference to other JSON consumers, Plan 05 instruction block, and Rationale tying back to D-03 / D-04 / D-12 and RESEARCH §Pitfall 8.
- User (and orchestrator re-verification) confirmed the verdict; Plan 05 unblocked to ship `_ZIP_BOUND_FIELDS = frozenset({"name", "kingdom_owner", "historical_notes"})`.

## Task Commits

1. **Task 1: Read Reconquista Unity loader source and produce Q2 verdict** — `8075685` (docs)
2. **Task 2: User confirms Q2 verdict before Plan 05 lands merge_overlay** — no code commit; user typed `approved` after orchestrator re-grep at `MapLoader.cs:196` and `MissingMemberHandling|JsonExtensionData` (0 hits).

**Plan metadata:** this SUMMARY commit (docs).

## Files Created/Modified

- `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-Q2-UNITY-LOADER-VERDICT.md` — Q2 verdict file with VERDICT: Tolerant, MapLoader.cs:196 evidence, Plan 05 instruction setting `_ZIP_BOUND_FIELDS` to the full overlay-field set, and Rationale section.

## Decisions Made

- **VERDICT: Tolerant** — backed by JObject-based deserialization at `MapLoader.cs:196` and the per-key null-conditional read pattern at lines 212–218 (condados) / 237–240 (baronies) / 200–202 (kingdoms). NIT 1's "Unverifiable-default-Strict" conservative fallback was explicitly NOT taken — primary source was reachable and read first-hand.
- **Source tree path correction** — verdict file documents that the canonical Reconquista checkout on this machine is at `C:\Users\veio_\Documents\Unity_Projects\Reconquista\`, not the `D:\Projetos_Jogo\Reconquista\` path enumerated in CLAUDE.md and 07-CONTEXT.md. Future plans should treat the `C:\` path as ground truth.
- **`_ZIP_BOUND_FIELDS` value cleared for Plan 05** — `frozenset({"name", "kingdom_owner", "historical_notes"})`, equal to `_ALL_OVERLAY_FIELDS`. No field restriction at zip-build time; pattern 12 (UI-served-only fallback) is no longer needed for the zip path.

## Deviations from Plan

None — plan executed exactly as written. Task 1 produced the verdict on first attempt with primary-source evidence; Task 2 reached the human-verify checkpoint and the user approved.

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

- The plan's `read_first` enumerated `D:\Projetos_Jogo\Reconquista\Assets\Scripts\` but that drive is not the live source on this machine. Resolved without escalation by discovering the active checkout at `C:\Users\veio_\Documents\Unity_Projects\Reconquista\Assets\Scripts\` (verified by directory listing) and documenting the stale path in the verdict file's "Drive note" section. The user's NIT 1 retry guidance was therefore not triggered.

## User Setup Required

None — no external service configuration; no secrets; no environment variables. The verdict file is a planning artifact only.

## Next Phase Readiness

- Plan 05 (`backend/medieval_forge/services/research/overlay.py` merge_overlay) is unblocked with an unambiguous `_ZIP_BOUND_FIELDS` constant value.
- Plan 08 (zip-build merge wiring) inherits the same cleared constant via Plan 05.
- Documentation drift to address in a future doc-pass: CLAUDE.md and `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-CONTEXT.md` reference `D:\Projetos_Jogo\Reconquista\...`; the live source tree on this machine is `C:\Users\veio_\Documents\Unity_Projects\Reconquista\...`. Not in scope for this plan (Rule 4 — out-of-scope doc refactor), but logged here so the next CLAUDE.md update can correct the canonical path.

## Self-Check: PASSED

Verifications:
- `07-Q2-UNITY-LOADER-VERDICT.md` exists at `.planning/phases/07-llm-research-as-opt-in-metadata-layer/`. FOUND.
- `grep -E "^## VERDICT: (Tolerant|Strict|Unverifiable-default-Strict)$"` on the verdict file matches `## VERDICT: Tolerant`. FOUND.
- Task 1 commit `8075685` present in `git log --oneline -5`. FOUND.
- Verdict file contains literal `_ZIP_BOUND_FIELDS: frozenset[str] = frozenset({"name", "kingdom_owner", "historical_notes"})`. FOUND (line 100 of the verdict file).
- Orchestrator independently re-verified `MapLoader.cs:196` (`JsonConvert.DeserializeObject<JObject>`) and `MissingMemberHandling|JsonExtensionData` grep (0 hits). FOUND.

---
*Phase: 07-llm-research-as-opt-in-metadata-layer*
*Completed: 2026-05-14*
