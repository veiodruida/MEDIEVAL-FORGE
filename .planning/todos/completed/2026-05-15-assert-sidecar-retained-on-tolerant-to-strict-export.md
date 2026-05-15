---
created: 2026-05-15T14:09:58.064Z
title: Assert sidecar retained on Tolerant→Strict export
area: testing
files:
  - backend/tests/e2e/test_research_overlay_iberia.py
  - backend/medieval_forge/services/research/overlay.py:63-92
  - backend/medieval_forge/services/export/schemas.py:69-87
---

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
