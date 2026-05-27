---
phase: 8
reviewers: [gemini, opencode]
reviewers_skipped: [claude, codex, coderabbit]
skip_reasons:
  claude: "running inside Claude Code session — skipped for reviewer independence"
  codex: "ChatGPT-account auth rejects gpt-5/gpt-5-codex/gpt-5.1-codex/qwen models — no compatible model available"
  coderabbit: "not installed"
reviewed_at: 2026-05-27T11:14:00Z
plans_reviewed:
  - 08-00-PLAN.md
  - 08-01-PLAN.md
  - 08-02-PLAN.md
  - 08-03a-PLAN.md
  - 08-03b-PLAN.md
  - 08-04-PLAN.md
  - 08-05-PLAN.md
  - 08-06a-PLAN.md
  - 08-06b-PLAN.md
  - 08-07-PLAN.md
  - 08-07c-PLAN.md
  - 08-08-PLAN.md
  - 08-09-PLAN.md
  - 08-10-PLAN.md
  - 08-11-PLAN.md
---

# Cross-AI Plan Review — Phase 8

## Gemini Review

# Implementation Plan Review: Phase 8 — border-vertex-editor

I have reviewed the implementation plans for **Phase 8: border-vertex-editor** (Plans 08-00 through 08-11). The following is my assessment of the plan quality, completeness, and risks.

## 1. Summary
The plan for Phase 8 is exceptionally comprehensive, providing a surgical and highly detailed roadmap for delivering a manual vector editor within a raster-heavy pipeline. It successfully navigates the complex intersection of interactive Konva rendering, Shapely geometry operations, and a version-controlled branching model. Most notably, it closes **BLOCKER-1** (the replay path) by formalizing the raster-vector-raster conversion within the DAG, ensuring user edits propagate to the final Unity export. The architectural decisions, such as the `EditorSyncBridge` and the `STAGE_TOKEN_OVERRIDES`, demonstrate deep alignment with the project's existing "Geometric Source of Truth" philosophy.

---

## 2. Strengths
- **Closed-Loop Integration:** The plan doesn't just build a UI; it wires the edits back into the pipeline via `manual_edit.compute()`. The use of `rasterio.features.shapes` for vectorization and `rasterize` for re-painting is the correct standard-stack choice for this project.
- **Branching Model Robustness:** The hybrid Branch+Snapshot model (D-10/D-12) avoids complex patch-replay logic by storing full blobs, significantly reducing the "replay bug" surface area while providing a rich sub-timeline for users.
- **Performance Discipline:** The use of Konva viewport culling (D-34) and RAF-throttled drag previews (Plan 08-05) targets 60fps early without premature optimization (like `sceneFunc` rewrites), following the Karpathy skill.
- **Topology & Shared-Vertex Coupling:** The "Shared vertex moves together" constraint (D-30) combined with server-side Shapely validation (D-26) guarantees topological integrity by construction, preventing the most common "broken border" bugs in map generation.
- **Nyquist Sampling Integrity:** The Wave 0 scaffold (08-00) ensures that every implementation task has an automated verification path from the start, maintaining the project's high testing standards.

---

## 3. Concerns

### [LOW] Raster-to-Vector Artifacts
- **Detail:** Re-rasterizing polygons back into the `int16` array in `manual_edit.compute()` (Plan 08-07c) may introduce sub-pixel aliasing or small "orphan" pixels if the `transform` isn't perfectly aligned with the original `voronoi` raster grid.
- **Mitigation:** Plan 08-07c uses an identity-equivalent affine `from_bounds(0, 0, W, H, W, H)`, which is correct. Ensure `rasterize` uses `all_touched=False` (default) to match standard rasterization semantics.

### [LOW] Snapshot Blob Size
- **Detail:** Each snapshot stores a full GeoJSON + Log. While estimated at ~100KB (A3), projects with thousands of edits across many branches could lead to a large SQLite DB file.
- **Mitigation:** The plan already uses `gzip` (D-12) and a 10MB safety limit. No immediate action needed, but worth monitoring in UAT.

---

## 4. Suggestions
- **Vertex ID Strategy:** Ensure that vertex IDs generated in the frontend (likely UUIDs) are stable enough for the `edit_log` but don't cause unnecessary token invalidation if they are regenerated during a simple session refresh. Using the vertex's initial `(lat, lon)` as part of a compound key might help if UUIDs aren't persisted.
- **Undo Labels:** Since `zundo` doesn't store metadata, consider the `undoLabels` stack mentioned in the existing `useEditorStore.ts` snippet to provide "Undo Split" instead of just "Undo" in the UI, enhancing the Game Designer's experience.
- **Snap Tolerance Visual:** In 08-11 (Task 3), specifically verify that the snap indicator (yellow circle) doesn't "jitter" when the user zooms in significantly (verifying Pitfall 7: scale-aware snap).

---

## 5. Risk Assessment: LOW
- **Justification:** The plan is technically sound, uses the correct libraries (Shapely, rasterio, zundo), and follows established project patterns. The most complex logic (the DAG cache extension and the replay path) is isolated in early backend waves (08-01, 08-02, 08-07c) with clear parity gates. The probability of breaking the canonical Iberia 868 output is low because the `manual_edit` stage defaults to a bit-identical identity pass-through.

**Phase 8 is ready for execution.**

---

## OpenCode Review

## Summary
The Phase 08 plans comprehensively cover the addition of branch management features, vertex and polygon editing capabilities, landmask editing, export functionality, and end-to-end testing to ensure a seamless user experience. The plans are detailed and methodical, with clear dependencies and objectives for each task.

## Strengths
- **Comprehensive Coverage**: Plans address all identified requirements (REQ-IDs), leaving no request unimplemented. Each plan aligns with its respective requirement, ensuring thorough feature development.
- **Testing Strategy**: Extensive unit tests, integration tests, integration parity checks, and user acceptance tests (UAT) are planned, indicating a robust verification process to ensure functionality and maintain existing parities.
- **Task Breakdown**: Tasks are clearly defined with expected outcomes, dependencies, and verification steps. This granularity helps in tracking progress and identifying issues early.
- **Security Considerations**: Threat models for each plan include potential attack vectors and mitigation strategies, ensuring security is a priority throughout the development process.

## Concerns
- **Human Verification Task (HIGH severity)**: The manual visual verification task is essential but inherently subjective. Providing clear guidelines and a check-off list helps in mitigating biases but could introduce human error.
- **Performance Testing Flakiness (MEDIUM severity)**: The 60fps drag performance test includes a tolerance mechanism (`test.fail()` only if median > 33 ms), but this may lead to inconsistent results. Adding visual confirmation and allowing manual overrides can improve the reliability of this test without sacrificing automation.

## Suggestions
- **Enhance Mocking in Unit Tests**: Some unit tests (e.g., sliders) heavily rely on mocking sequences. While necessary, increasing the depth of these mocks could add confidence in their accuracy.
- **Automated Playwright Test for Performance** (not currently feasible with flaky test criteria): Consider adding a manual confirmation flag as an optional step that can be skipped once confidence is established. This approach minimizes required human interactions without compromising on testing rigor.

## Risk Assessment
LOW — The plans follow a structured development lifecycle, ensuring all tasks are clearly defined and verifiable. While human-verified tasks introduce subjective elements, the verification process is well-documented and should reduce misinterpretation. Performance tests have clear tolerance mechanisms to account for variability, ensuring that major issues will be identified early.

---

## Consensus Summary

Both reviewers (Gemini, OpenCode) rate Phase 8 risk as **LOW** and deem the plans ready for execution. No HIGH-severity blockers were raised that would require a re-plan; all flagged concerns are mitigable during execution.

### Agreed Strengths
- **Comprehensive coverage** — every REQ-08-* ID and locked decision (D-01..D-37) traced to plan tasks (both reviewers).
- **Robust testing pyramid** — Wave 0 scaffolds + integration + parity + UAT layered correctly (both reviewers).
- **Clear task breakdown** — each task has explicit dependencies, acceptance criteria, and verification commands (both reviewers).
- **Security/threat modelling discipline** — STRIDE blocks per plan, attack surface minimised (OpenCode); architectural alignment with project invariants (Gemini).

### Agreed Concerns
None of the same severity. Reviewers raised orthogonal risks:
- Gemini flagged **geometric** edge cases (raster-vector roundtrip artifacts, snapshot blob growth) — both LOW with already-planned mitigations.
- OpenCode flagged **verification** edge cases (manual UAT subjectivity, 60fps flakiness) — HIGH/MEDIUM but addressable via checklist + manual override flag during execution.

### Divergent Views
- **Performance test confidence:** Gemini gives the 60fps Konva culling approach implicit confidence ("targets 60fps early without premature optimization"); OpenCode raises MEDIUM concern about Playwright frame-time flakiness. Recommendation: keep current `test.fail()` tolerance in 08-11 but add an optional manual-override flag for CI stability.
- **Human verification weight:** OpenCode rates manual UAT a HIGH risk; Gemini does not call it out. Phase 8 plans already mark Manual-Only Verifications in VALIDATION.md with explicit instructions — risk is procedural, not architectural.

### Actionable Improvements (optional, non-blocking)
1. **08-07c:** Add explicit assertion in unit test that `rasterize(all_touched=False)` is used (Gemini concern: raster-vector artifacts).
2. **08-04 / 08-09:** Optionally surface `undoLabels` stack so undo UI reads "Undo Split" vs "Undo" (Gemini suggestion).
3. **08-11 Task 3:** Add snap-indicator zoom test — confirm yellow snap circle does not jitter at high zoom (Gemini suggestion, ties to Pitfall 7).
4. **08-11 perf test:** Add `--allow-manual-override` flag for 60fps test to reduce CI flakiness (OpenCode suggestion).

None of these require a re-plan — incorporate during execution at the relevant task or defer to a follow-up todo.

---

## Reviewer Coverage Note

Only 2 of 5 candidate CLIs produced reviews:
- **claude** — skipped (running inside Claude Code; would not be independent)
- **codex** — failed (ChatGPT-account auth rejects every model tested: `gpt-5`, `gpt-5-codex`, `gpt-5.1-codex`, and the configured `qwen2.5-coder:14b` — needs auth/config fix outside this session)
- **coderabbit** — not installed

Gemini + OpenCode both reached LOW risk consensus. Adding codex/claude later via `/gsd-review` re-run would strengthen the signal but is not blocking.
