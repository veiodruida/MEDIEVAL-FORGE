---
phase: 02-ingestion-adapter
fixed_at: 2026-05-09T00:00:00Z
review_path: .planning/phases/02-ingestion-adapter/02-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-05-09
**Source review:** `.planning/phases/02-ingestion-adapter/02-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (Critical: 0, Warning: 4)
- Fixed: 4
- Skipped: 0

Info findings (IN-01..IN-04) are out of scope for `fix_scope=critical_warning`
and are not addressed in this iteration. They remain documented in REVIEW.md
for follow-up phases.

## Fixed Issues

### WR-04: `mountain_river_data.json` opened without `encoding='utf-8'`

**Files modified:** `backend/medieval_forge/services/pipeline/render.py`
**Commit:** 718a86d
**Status:** fixed

**Applied fix:** Added `encoding='utf-8'` to both `open()` calls
(`render_mountains` ~line 200; `render_rivers` ~line 241) and prefixed each
with a Rule 3 verbatim-port deviation comment that mirrors the existing
pattern in `landmask.py:173-176`. Comment cites the same Windows cp1252
hazard (`UnicodeDecodeError` on accented mountain/river names like
"Peña de Francia"). Verified with Tier 1 re-read + Tier 2
`python -c "import ast; ast.parse(...)"`.

### WR-03: Bare `except:` in `render_map` font fallback

**Files modified:** `backend/medieval_forge/services/pipeline/render.py`
**Commit:** ca770af
**Status:** fixed

**Applied fix:** Replaced bare `except:` at `render.py:130` with
`except (OSError, IOError):`. Added a comment noting the narrowing from
inicio's verbatim-port `except:` so that `KeyboardInterrupt` and
`SystemExit` are no longer swallowed during long renders. This is the only
exception class `PIL.ImageFont.truetype` actually raises when a font file
cannot be opened. Verified with Tier 1 re-read + Tier 2 syntax check.

The hardcoded Linux font path `/usr/share/fonts/truetype/dejavu/...` at
`render.py:128-129` was intentionally NOT touched — that is IN-03 and out
of scope for this iteration.

### WR-02: Border features may be written twice; no `osm_id` dedupe

**Files modified:** `backend/medieval_forge/services/pipeline/adapters/osm.py`
**Commit:** 7491821
**Status:** fixed: requires human verification

**Applied fix:** Inserted an `osm_id` dedupe pass between the per-ISO fetch
loop and `_split_by_iso` (between lines 163 and 193 in the new file).
Implementation matches the REVIEW.md template:

- Iterates `combined_features`, tracking a `seen_ids` set.
- Features without an `osm_id` are kept (defensive — should not happen for
  OSM relations but guards against future fixture drift).
- Duplicates are counted, and a single SSE message
  (`Adapter: deduped N cross-border feature(s) by osm_id.`) is emitted only
  when the counter is non-zero, so the happy path stays quiet.

Reason for `requires human verification` flag: this is a logic change in
the cross-border feature pipeline (non-trivial state-handling). Tier 2
syntax check passes, but unit-test confirmation that PT/ES border-overlap
features are now deduped exactly once was deferred — adding such a test
requires extending the `synthetic_iberia_fc` fixture with a feature whose
representative_point falls inside both buffered country polygons (e.g. on
the Minho), which is a fixture change beyond fix_scope. Recommended
follow-up: add the suggested unit test in Phase 02.1 (live-ingestion
parity) where the synthetic fixture is already being revisited.

### WR-01: 409 anti-overlap gate never fires for v3 ingest

**Files modified:** `backend/medieval_forge/api/v3/ingest.py`
**Commit:** 9148b61
**Status:** fixed: requires human verification

**Applied fix:** After all input validations (UUID, project existence,
status==generating, bbox, iso_codes) but BEFORE returning the
`StreamingResponse`, the handler now writes:

```python
project.status = "generating"
await db.commit()
```

Placement chosen in the handler (not the producer) because
`_adapter_producer` runs inside `asyncio.create_task`, which would create a
race window between handler return and producer first-line execution. The
handler-side commit completes synchronously before the SSE response
streams its first byte, so a second concurrent `/ingest` call now reliably
hits the 409 gate that previously was a no-op (the original v3 producer
only set `"ingested"` / `"error_ingesting"` — never `"generating"`).

The producer continues to transition this status to `"ingested"` (success)
or `"error_ingesting"` (failure / cancellation) via `_set_status`,
matching the v1 `ingest_runner` pattern.

Sanity-checked existing tests in `test_v3_ingest.py` against the new
behaviour:
- `test_v3_ingest_returns_409_when_project_status_is_generating` — gate
  logic unchanged; still passes.
- `test_v3_ingest_streams_terminal_sentinel_and_updates_status_on_success`
  — final assertion is `status == "ingested"`; producer transitions from
  the new transient `"generating"` to `"ingested"` on success.
- `test_v3_ingest_emits_terminal_sentinel_even_when_adapter_raises` — same
  reasoning; producer transitions to `"error_ingesting"` on failure.

Reason for `requires human verification` flag: state-machine change with
concurrency implications. The fix is small and the existing tests cover
the visible status transitions, but two concurrent in-flight
`/ingest` requests under realistic load are not exercised by the unit
test suite, so empirical verification under the parity / UAT runs is
recommended before considering it closed.

Note (from review): REVIEW.md asserts the v1 `ingest_runner.py` flow sets
`status='generating'`. A grep of the v1 module shows it does NOT — neither
v1 nor v3 was setting it. The v3 fix here is the correct one regardless;
the v1 flow has the same latent issue but is out of Phase 02 scope.

## Skipped Issues

_None. All in-scope warnings were applied successfully._

---

_Fixed: 2026-05-09_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
