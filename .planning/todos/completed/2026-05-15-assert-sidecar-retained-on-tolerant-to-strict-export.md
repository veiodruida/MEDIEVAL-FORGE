---
created: 2026-05-15T14:09:58.064Z
resolved: 2026-05-15T14:15:00.000Z
resolution: noop-already-covered
title: Assert sidecar retained on Tolerant→Strict export
area: testing
files:
  - backend/tests/e2e/test_research_overlay_iberia.py:341-384
  - backend/medieval_forge/services/research/overlay.py:63-92
  - backend/medieval_forge/services/export/schemas.py:69-87
---

## Resolution (2026-05-15)

**No work needed.** `test_strict_zip_bound_emits_only_name_while_sidecar_retains_all_three_fields`
(commit 714b51d, lines 341-384) already asserts:

1. Sidecar still on disk after Strict re-export (line 381 `sidecar_path.read_text`)
2. All three fields unmodified in sidecar (lines 382-384 — name + kingdom_owner + historical_notes)
3. Zip contains `name` only (lines 372-378)

Test run 2026-05-15: PASSED in 6.04s.

Audit agent (`/gsd-plan-phase 07 --reviews`) misclassified this as "test exists but
doesn't verify sidecar retention". False positive — sidecar retention IS verified.



## Problem

Phase 07 REVIEWS finding #9 (Qwen3 downgrade-path) shipped a Tolerant→Strict
toggle test in commit 714b51d, but the test verifies zip-bound field emission
only. It does not assert that `research_overlay.json` (sidecar) remains on disk
after a re-export under Strict.

Per Qwen3 caveat: "If Q2 verdict flips Tolerant→Strict after data exists,
existing `research_overlay.json` with `kingdom_owner`/`historical_notes` will
be ignored, but the sidecar remains. No cleanup or versioning strategy for
obsolete sidecars defined."

Gap: regression risk if future refactor of `merge_overlay()` or export pipeline
inadvertently deletes/truncates the sidecar on Strict re-export. D-12 parity
test would not catch this (parity covers zero-overlay path).

## Solution

Add assertion to existing Strict/Tolerant test in
`test_research_overlay_iberia.py`:

1. Seed `research_overlay.json` with `name + kingdom_owner + historical_notes`.
2. Re-export project with `_ZIP_BOUND_FIELDS = strict` (only `name` emitted).
3. After export, assert `research_overlay.json` still exists on disk AND
   contains unmodified `kingdom_owner` + `historical_notes` payloads.
4. Verify zip contains `name` only (existing assertion).

Effort: ~15 min. Low risk. Inline with `/gsd-quick`.
