---
phase: 02-ingestion-adapter
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - backend/medieval_forge/api/v3/__init__.py
  - backend/medieval_forge/api/v3/ingest.py
  - backend/medieval_forge/main.py
  - backend/medieval_forge/services/pipeline/__init__.py
  - backend/medieval_forge/services/pipeline/adapters/__init__.py
  - backend/medieval_forge/services/pipeline/adapters/base.py
  - backend/medieval_forge/services/pipeline/adapters/osm.py
  - backend/medieval_forge/services/pipeline/adapters/terrain.py
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/landmask.py
  - backend/medieval_forge/services/pipeline/regions.py
  - backend/medieval_forge/services/pipeline/render.py
  - backend/medieval_forge/services/ingest_osm.py
  - backend/tests/parity/test_iberia_868_live.py
  - backend/tests/unit/adapters/__init__.py
  - backend/tests/unit/adapters/conftest.py
  - backend/tests/unit/adapters/test_osm_split.py
  - backend/tests/unit/adapters/test_terrain_passthrough.py
  - backend/tests/unit/api/__init__.py
  - backend/tests/unit/api/test_v3_ingest.py
  - backend/tests/unit/test_contracts.py
  - backend/tests/unit/test_landmask_input_assert.py
  - backend/tests/unit/test_regions.py
  - scripts/refresh_live_snapshot.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-08
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

The Phase 02 ingestion-adapter scope ports the OSM municipality fetcher into a
`ProjectDataset` contract, adds a `/api/v3/projects/{id}/ingest` SSE endpoint,
and stubs the terrain branch as a vendored passthrough (D-13). The
implementation is clean and the unit-test coverage on `_split_by_iso`, the
D-04 fail-fast assert, and the v3 SSE flow is solid.

Four warnings are worth addressing before Phase 03:

1. The `T-02-04-02` 409 anti-overlap check is **structurally a no-op** for the
   v3 ingest path — the producer never sets `status="generating"`, so two
   concurrent v3 calls both pass the gate and race on the inputs/ writes.
2. Per-ISO Overpass calls combined with a 0.025 deg country buffer can cause
   **border features to be fetched twice**, and `_split_by_iso` does not
   dedupe by `osm_id`, so a single border municipality may end up written
   twice into `pt_concelhos_live.geojson`.
3. `render.py` has a bare `except:` that swallows `KeyboardInterrupt` /
   `SystemExit` (verbatim port from `inicio`, but worth pinning).
4. `render.py` opens `mountain_river_data.json` twice without
   `encoding='utf-8'`, the same Windows cp1252 hazard `landmask.py` already
   fixed (Rule 3 deviation noted there).

The Critical bucket is empty. No injection vectors, no hardcoded secrets, no
auth bypasses, no path traversal risks (all FS access goes through
`is_valid_uuid` + `project_inputs_dir`). Bbox is range-checked
(`_validate_bbox`); the SSE error path emits exception class names only
(T-02-04-05).

## Warnings

### WR-01: 409 anti-overlap gate never fires for v3 ingest

**File:** `backend/medieval_forge/api/v3/ingest.py:146-150` (handler) +
`backend/medieval_forge/api/v3/ingest.py:60-93` (producer)

**Issue:** The handler raises 409 if `project.status == "generating"`, citing
`T-02-04-02 (DoS — anti-overlap)`. But `_adapter_producer` never sets the
project status to `"generating"` at start — it only writes `"ingested"` on
success or `"error_ingesting"` on failure (lines 75 and 81/89). A project in
`draft` (the default after creation) or `ingested` (after a previous run) is
not gated at all. Two concurrent calls to `/api/v3/projects/{pid}/ingest`
both pass the 409 check, both invoke `build_dataset_from_osm`, and both write
to the same `projects/<uuid>/inputs/pt_concelhos_live.geojson` (and
`es_municipalities_live.geojson`). `_write_geojson_atomic` makes each
individual write atomic, but cross-file consistency is not preserved — and
the OSM fetch is a real-world DoS / cost amplification surface.

The unit test `test_v3_ingest_returns_409_when_project_status_is_generating`
sets status manually, so it doesn't catch the mismatch between the gate and
the producer.

Note: the v1 `api/ingest.py` flow (out of scope for this review) does set
`status='generating'` in `services/ingest_runner.py`. The v3 producer here
diverges from that pattern without a documented reason.

**Fix:** Mark the project as in-progress before kicking off the producer.
Either inside the handler, immediately after the 409 check passes:

```python
# After all validations, before scheduling the producer task:
project.status = "generating"
await db.commit()
return StreamingResponse(...)
```

Or as the first action inside `_adapter_producer` (using `session_factory`),
matching the v1 `_set_status` pattern. Either way, the gate now actually
prevents overlap.

If the design intentionally allows concurrent ingests for v3 (e.g. multiple
adapters in parallel for one project), then remove the 409 gate and the
`T-02-04-02` claim from the docstring — silent no-ops are worse than
honestly-absent guards.

### WR-02: Border features may be written twice; no `osm_id` dedupe

**File:** `backend/medieval_forge/services/pipeline/adapters/osm.py:142-174`

**Issue:** `build_dataset_from_osm` calls `fetch_municipalities` once per ISO
(lines 142-163) with `clip_iso_codes=[iso]`. Each per-ISO call applies
`_clip_features_to_countries` against that ISO's Natural Earth polygon
buffered by `_COUNTRY_BUFFER_DEG = 0.025` (≈2.7 km, see `ingest_osm.py:115`).
A municipality whose `representative_point` falls inside both the buffered
PT polygon AND the buffered ES polygon — i.e. inside the ~5 km overlap band
along the actual PT/ES border — survives BOTH per-ISO fetches and ends up in
`combined_features` twice with the same `osm_id`.

`_split_by_iso` (line 64-106) then routes each occurrence by
`representative_point`, first-match-wins on the `polys` list. Both
occurrences route to whichever ISO appears first in `iso_codes` — i.e. PT in
`["PT", "ES"]`. Net effect: `pt_concelhos_live.geojson` gets the same border
feature twice.

This is hard to spot because:
- `_split_by_iso`'s unit tests use a synthetic FC where every feature lives
  far from the border (`test_osm_split.py:19-46`).
- The live-parity test is currently `xfail` (Phase 02.1 deferral, see
  `D-09-LIVE-WAIVER.md`), so a duplicate-feature symptom would not surface
  in CI today.
- `iberia_868` happens to have a 38-point border polygon that routes
  municipalities downstream via per-country KD-trees (CLAUDE.md rule #3),
  so duplicates may be silently absorbed by the rasterizer — but they
  inflate the GeoJSON byte budget and break the eventual byte-for-byte
  parity contract that Phase 02.1 is meant to restore.

**Fix:** Dedupe `combined_features` by `osm_id` before passing it to
`_split_by_iso`. `_relation_to_geojson_feature` already populates
`feat["properties"]["osm_id"]` (`ingest_osm.py:235`):

```python
# In build_dataset_from_osm, after the per-ISO loop, before _split_by_iso:
seen_ids: set = set()
deduped_features: list[dict[str, Any]] = []
duplicates = 0
for feat in combined_features:
    oid = feat.get("properties", {}).get("osm_id")
    if oid is None:
        # No id — keep (defensive; shouldn't happen for OSM relations)
        deduped_features.append(feat)
        continue
    if oid in seen_ids:
        duplicates += 1
        continue
    seen_ids.add(oid)
    deduped_features.append(feat)
if duplicates:
    await queue.put(
        f"data: Adapter: deduped {duplicates} cross-border feature(s) by osm_id.\n\n"
    )
combined_fc = {"type": "FeatureCollection", "features": deduped_features}
```

Add a unit test that places a feature centroid inside both buffered polygons
(e.g. on the Spanish-Portuguese Minho border) and asserts the dedupe counter.

### WR-03: Bare `except:` in `render_map` font fallback

**File:** `backend/medieval_forge/services/pipeline/render.py:128-131`

**Issue:**

```python
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
    font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
except:  # bare
    font = font_sm = ImageFont.load_default()
```

A bare `except:` swallows `KeyboardInterrupt` and `SystemExit`, masking
Ctrl-C and `os._exit` shutdown signals during long renders. Defensible as a
verbatim port from `inicio` (the file header acknowledges the §9 verbatim
contract), but the project-wide convention elsewhere uses
`except Exception:` or named exceptions (see `osm.py:98`,
`ingest_osm.py:152`).

Impact is low because this branch only fires when `cfg.draw_names=True`,
which the default config sets to `False` (see `regions.py:79` and
PREFLIGHT.md Q10). Still, a single targeted change keeps the verbatim-port
spirit while removing the signal-swallowing footgun.

**Fix:**

```python
except (OSError, IOError):
    font = font_sm = ImageFont.load_default()
```

`PIL.ImageFont.truetype` raises `OSError` when a font file can't be opened;
this is the only failure mode the fallback is actually trying to handle.

### WR-04: `mountain_river_data.json` opened without `encoding='utf-8'`

**File:** `backend/medieval_forge/services/pipeline/render.py:196` and
`backend/medieval_forge/services/pipeline/render.py:233`

**Issue:** Both `render_mountains` and `render_rivers` open the
mountain/river JSON without an explicit encoding:

```python
with open(mr_path, 'r') as f:
    data = json.load(f)
```

This is the exact Windows cp1252 hazard `landmask.py:173-178` already
documented and fixed (Rule 3 verbatim-port deviation: "inicio:256 omits
encoding='utf-8', relying on POSIX UTF-8 default. On Windows cp1252 raises
UnicodeDecodeError on byte 0x8d"). If the vendored `mountain_river_data.json`
contains accented mountain names ("Sierra de Guadarrama", "Peña de Francia",
etc.) on a non-UTF-8 byte, Windows users will hit the same class of bug —
`UnicodeDecodeError` — for the same reason.

The inconsistency is the smell: `landmask.py` fixed it; `render.py` left it.

**Fix:** Apply the same pattern as `landmask.py`:

```python
with open(mr_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
```

at both `render.py:196` (render_mountains) and `render.py:233`
(render_rivers). Mention the same Rule 3 deviation comment for traceability.

## Info

### IN-01: Defensive `cfg = RegionConfig()` is misleading

**File:** `backend/medieval_forge/services/pipeline/__init__.py:58-59`

**Issue:** `run_pipeline` opens with `if cfg is None: cfg = RegionConfig()`,
but a fresh `RegionConfig()` has `dataset=None`, which then fails
`load_municipalities`'s D-04 fail-fast assert with a
`FileNotFoundError("RegionConfig.dataset is None")` ten lines later. The
default-construction path is unreachable in practice; the `if cfg is None`
guard suggests it works.

**Fix:** Either drop the guard and type `cfg: RegionConfig` (no Optional),
or raise `ValueError("run_pipeline requires a configured RegionConfig")`
immediately on `cfg is None`. The current code is misleading.

### IN-02: Logger naming convention drift

**File:** `backend/medieval_forge/services/pipeline/adapters/osm.py:23`
vs. `backend/medieval_forge/api/v3/ingest.py:28`

**Issue:** `osm.py` uses `log = logging.getLogger(__name__)`; `ingest.py`
uses `logger = logging.getLogger(__name__)`. Both Python idioms are valid;
the project should pick one. Most files in the repo (e.g. `ingest_osm.py`,
v1 services) use `log`. The Phase 02 v3 router introduces `logger`.

**Fix:** Rename `logger` → `log` in `api/v3/ingest.py` for consistency with
the rest of the backend (cheaper change than the inverse).

### IN-03: Hardcoded Linux font path

**File:** `backend/medieval_forge/services/pipeline/render.py:128-129`

**Issue:** `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` will
never resolve on Windows or macOS, forcing the bare-except fallback (see
WR-03) on every non-Linux dev box. Low impact because `cfg.draw_names`
defaults to `False`, but if Phase 04 surfaces a UI toggle for names, every
non-Linux developer silently gets `ImageFont.load_default()` (8px bitmap).

**Fix (deferred):** When a follow-up phase actually exposes `draw_names`,
ship a vendored TTF under `data/fonts/` and resolve the path via
`Path(__file__).resolve().parents[N] / "data" / "fonts" / "..."`. Out of
scope for Phase 02; flag for Phase 04 backlog.

### IN-04: `print` statements in pipeline orchestrator

**File:** `backend/medieval_forge/services/pipeline/__init__.py:63-182`

**Issue:** The orchestrator prints progress to stdout (`print(f"[1] Loading
territory data...")` etc.). Verbatim port from `inicio` (this is acknowledged
in the file header and matches the original 620-line script's behavior), but
when `run_pipeline` is called from the v3 SSE endpoint or from
`scripts/refresh_live_snapshot.py`, these prints bypass the `queue` SSE
channel and dump straight to the server stdout.

Functionally harmless today (the SSE channel is fed by the adapter and the
underlying `fetch_municipalities`, not the pipeline orchestrator — Phase 02
scope is adapter-only per `api/v3/ingest.py:6-7`). Worth tracking for
Phase 03 when `run_pipeline` is wired into the SSE flow: the prints should
become `await queue.put(f"data: ...\n\n")` calls or be replaced with
structured logging.

**Fix (deferred):** Phase 03/04 — convert `print(...)` statements to
SSE-aware progress messages, threading `queue` through `run_pipeline`. No
action required this phase.

---

_Reviewed: 2026-05-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
