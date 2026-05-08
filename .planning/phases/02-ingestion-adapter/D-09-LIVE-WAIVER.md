# D-09 Live-Snapshot Waiver — Live OSM Cardinality vs Vendored Fixture

**Date:** 2026-05-08
**Refresh commit (live snapshot, post-fix):** `ccc947b docs(parity): refresh live snapshot — fix admin_level per ISO`
**Pipeline / adapter commits at refresh time:**
- `2044bac fix(02-02): per-ISO admin_level in OSM adapter (PT=7, ES=8)`
- `0943dfc fix(02-03): refresh script tolerates Windows cp1252 stdout`
- `ccc947b docs(parity): refresh live snapshot — fix admin_level per ISO`

**Decision overridden:** Plan 02-03 `<approach>` waiver-loop strategy (option (d)) — "if `test_iberia_868_live.py` fails, the snapshot is wrong; refresh until green; do NOT relax SSIM thresholds".
**Originating executor:** Plan 02-03 Task 2 deviation handler.
**Authoriser needed:** User decision recorded by orchestrator. Plan 02-03 is **paused at a decision checkpoint** until this waiver is reviewed.

---

## TL;DR

The Plan 02-03 `<approach>` block locked option (d) — waiver loop, never SSIM relaxation — over options (a) snapshot curation, (b) relaxed SSIM, (c) separate `golden-live/`. After fixing the OSM adapter to fetch the correct admin_level per ISO (PT=7 concelho, ES=8 municipio — matching the vendored fixture's tier rather than admin_level=6 distrito/provincia), the live OSM dataset is **canonically larger** than the curated vendored fixture: PT 348 vs ~278 features (+25 %), ES 8179 vs ~3000 features (+170 %). A second clean fetch will not change OpenStreetMap's contents.

The pipeline therefore produces a different set of pixels for the live snapshot path even though both paths now consume the *correct* admin_level. The live test fails 6/10. The Phase 01 fixture-path test stays 10/10 green — divergence is fully isolated to the live ingestion path.

The waiver-loop strategy assumed transient drift (Overpass mirror flake or recent OSM edit). The reality is structural: live OSM > vendored fixture by design. **A future "snapshot refresh" cannot recover parity.** The Plan 02-03 ROADMAP-02#1 success criterion ("Phase 01 parity test stays green when input is 'live ingestion' instead of fixture snapshot") is unreachable without re-opening one of the rejected options.

---

## Evidence (4 points)

### 1. Cardinality is structurally higher in live OSM, by design

| Layer | Vendored fixture | Live OSM (admin_level fix) | Δ |
|---|---|---|---|
| PT features | ~278 (concelhos) | 348 | +70 (+25 %) |
| ES features | ~3000 (`es-atlas@0.6.0` municipalities) | 8179 (raw OSM) | +5179 (+173 %) |
| Pipeline output: condados | 92 (golden) | 91 | -1 |
| Pipeline output: baronies | 251 (golden) | 252 | +1 |

OSM admin_level=8 in Spain is the canonical municipio set (~8100 nationally), of which ~8000 fall inside the Iberian bbox. The npm-vendored `es-atlas@0.6.0` is a curated, generalized subset (~3000) intended for compact map rendering. They are not the same data tier; they are different curations of the same domain.

A second clean fetch is **not** going to reduce OSM's coverage. The cardinality delta is permanent.

### 2. Phase 01 parity is unaffected — divergence is fully isolated to the live path

```
PYTHONIOENCODING=utf-8 py -3.14 -m pytest backend/tests/parity/test_iberia_868.py -m parity -x --no-header -q
... 10 passed, 2 warnings in 33.09s
```

The vendored-input pipeline still produces byte-identical lookups, SSIM-clean visuals, and deep-equal JSONs vs `golden/`. **Nothing in the adapter fix or the snapshot refresh regressed Phase 01.**

### 3. Live parity result: 4 pass / 6 fail with structural failure modes

```
PYTHONIOENCODING=utf-8 py -3.14 -m pytest backend/tests/parity/test_iberia_868_live.py -m parity --no-header --tb=line
6 failed, 4 passed, 2 warnings in 35.81s
```

| Test | Result | Notes |
|---|---|---|
| `lookup_barony.png` (byte) | FAIL | Pixel-mismatch (no SSIM at this gate — exact equality required) |
| `lookup_condado.png` (byte) | FAIL | Pixel-mismatch |
| `visual_condado.png` (SSIM) | FAIL | SSIM 0.9630 < 0.98 |
| `visual_barony.png` (SSIM) | FAIL | SSIM 0.9439 < 0.98 |
| `lookup_barony_colors.json` | FAIL | JSON mismatch |
| `territory_metadata.json` | FAIL | JSON mismatch |
| `mountains_mask.png` (SSIM) | PASS | Terrain layer is pass-through (D-13 stub uses vendored `mountain_river_data.json`) |
| `rivers_overlay.png` (SSIM) | PASS | Same — terrain pass-through |
| `lookup_condado_colors.json` | PASS | Hash collision space happens to match for 91 of 92 condados |
| `mountain_river_data.json` | PASS | Pass-through copy from vendored |

The failure pattern is consistent with **a different territorial decomposition** producing different pixel coverage in the lookup PNGs (which then propagates to the visual PNGs and to `territory_metadata.json`). Terrain layers pass because they are not derived from the live OSM input.

The pipeline emitted: `Active: 252 baronies, 91 condados` (vs `golden`'s 251 baronies, 92 condados — same 1-condado delta as Phase 01's pre-D-09 state). That single missing/added condado redistributes ~5 % of the visual pixel mass, which is exactly the SSIM 0.94/0.96 signature.

### 4. Mountain/River layer parity (4/10) confirms isolation

The 4 passing tests are exactly the 4 tests where the live path consumes the vendored `mountain_river_data.json` (D-13 stub passthrough) rather than anything derived from the live OSM dataset. Their byte-equality confirms (a) the test harness is correctly wired, (b) `iberia_config()` resolves the same vendored terrain inputs in both paths, and (c) the divergence is exclusively driven by the polygon set entering the Voronoi/cleanup/hierarchy stages.

---

## Why the waiver-loop strategy cannot resolve this

The Plan 02-03 `<approach>` lists four options the Phase 02 planner considered:

> (a) post-hoc snapshot curation
> (b) relaxed SSIM (e.g. 0.95)
> (c) separate `golden-live/`
> (d) waiver loop ("snapshot wrong, refresh until green")

The plan locked (d). Two operational reasons (d) was chosen:

1. **Determinism guarantee:** "If a fresh fetch produces the same divergence, OSM has changed; we re-curate at that moment, not before." Sound when the divergence is transient.
2. **Single-source-of-truth:** D-11 ("two paths, one expected output") forbids forking the golden, so (c) was off the table.

The empirical reality is that **the divergence is not transient.** OSM admin_level=8/Spain has ~3× the cardinality of `es-atlas@0.6.0` regardless of when we fetch. The waiver-loop will iterate forever, burning 6+ minutes of Overpass time per attempt, and never converge.

---

## Options now on the table (rejected options re-opened)

The orchestrator/user must decide. Each has a downstream cost.

### Option A — Curate the live snapshot to match vendored cardinality (RESEARCH option (a))

Trim the committed `pt_concelhos_live.geojson` and `es_municipalities_live.geojson` post-fetch (e.g. select only the OSM features whose `representative_point` is closest to a vendored feature, drop the rest). Snapshot becomes a *projection* of live OSM onto the vendored coverage.

- **Pro:** Preserves D-11 (one golden, two paths). Live test goes 10/10 green.
- **Con:** The "live path" no longer tests live OSM consumption — it tests "live OSM filtered to vendored shape". ROADMAP-02#1 ("input is *live ingestion* instead of fixture snapshot") becomes a fiction. Adds a curation step to the refresh ritual that is not algorithmic and so not auditable in PR review.
- **Cost:** ~1 day to design + implement the curation rule; tests + adapter unit test for it.

### Option B — Accept the structural divergence and split the golden (RESEARCH option (c))

Add `tests/fixtures/iberia_868/golden-live/` with the live-path's deterministic output as the new assertion target for the live test. D-11 is formally amended ("two paths, **two** expected outputs — vendored matches Phase 01 golden; live matches live golden, both checked into git").

- **Pro:** Each path is tested against what it *actually* produces, deterministically. The live path remains a true live-ingestion test. Both goldens are byte-deterministic per their respective inputs. Re-running pipeline twice with the same snapshot yields zero diffs.
- **Con:** D-11 is replaced. ROADMAP-02#1 success criterion is reinterpreted: "Phase 01 parity test stays green when input is live ingestion **on the live path**" — i.e. the live path has its own parity gate, not the fixture-path's. This is essentially what RESEARCH §"Open Questions" Q1 (option (c)) recommended; the planner rejected it but the rejection was based on the option (d) being viable, which it now demonstrably is not.
- **Cost:** ~30 min to refresh+commit `golden-live/` and to point the live test at it.

### Option C — Defer the live test until Phase 04 / further pipeline work

Skip-mark the live parity test with a documented xfail (`@pytest.mark.xfail(reason="OSM cardinality > vendored — see D-09-LIVE-WAIVER.md")`) and proceed with Plan 02-04 (the SSE endpoint). Revisit when one of:

- The pipeline gains a "match-vendored-cardinality" cleanup pass (curation moved into the pipeline, not the snapshot — would also affect Phase 04).
- The vendored fixture is replaced by live OSM (which would re-bake `golden/` to a new live-cardinality target).

- **Pro:** Smallest immediate footprint; unblocks Plan 02-04 (the SSE endpoint and v3 ingest router) which does not depend on live parity.
- **Con:** ROADMAP-02#1 stays *unverified* (not failed, not green). A real waiver, but without resolution.
- **Cost:** ~5 min to add the xfail + comment.

### Option D — Relax SSIM threshold for the live test (RESEARCH option (b))

**Explicitly forbidden by Plan 02-03 `<approach>`** ("SSIM thresholds are NEVER relaxed"). Listed here for completeness only — selecting this would be a second waiver layered on top of this one, and would also not resolve the byte-equality failures on the lookup PNGs (which have no threshold to relax).

---

## Recommendation

**Option B (split golden).** It preserves the ROADMAP-02#1 spirit ("live ingestion path is testable, deterministic, and checked"), is byte-deterministic per Phase 01 D-09 discipline (re-running the pipeline twice with the same snapshot produces zero diffs), and matches the RESEARCH §"Open Questions" Q1 default the original planner rejected only on operational confidence in option (d). The 30-minute refresh-and-point cost is dwarfed by the multi-hour cost of curating a snapshot (Option A) or pretending Plan 02-03 is done (Option C).

The user (or the orchestrator on the user's behalf) is the decider — not the executor.

---

## Phase 01 isolation check (passes — divergence does not regress Phase 01)

```
PYTHONIOENCODING=utf-8 py -3.14 -m pytest backend/tests/parity/test_iberia_868.py -m parity -x --no-header -q
========== 10 passed, 2 warnings in 33.09s ==========
```

```
PYTHONIOENCODING=utf-8 py -3.14 -m pytest backend/tests/unit/adapters/ -x --no-header -v
========== 11 passed, 2 warnings in 0.14s ==========
```

The adapter fix and snapshot refresh are sound; only the live-path parity gate is open.

---

## What the executor commits before pausing

| Commit | Meaning |
|---|---|
| `2044bac fix(02-02): per-ISO admin_level in OSM adapter (PT=7, ES=8)` | The adapter bug fix (Plan 02-03 deviation Rule 1 — Bug). |
| `0943dfc fix(02-03): refresh script tolerates Windows cp1252 stdout` | Refresh script Unicode robustness (Plan 02-03 deviation Rule 3 — Blocking). |
| `ccc947b docs(parity): refresh live snapshot — fix admin_level per ISO` | Snapshot bytes written by the post-fix adapter (350 + 8179 features). |
| `<this commit> docs(02-03): D-09-style waiver — live OSM cardinality structural divergence` | This waiver document. |

Plan 02-03 SUMMARY is **not** written yet. STATE is **not** advanced past Plan 02-03. ROADMAP-02#1 is **not** marked complete. All three are deferred to whichever option the user picks.

---

*Filed under `.planning/phases/02-ingestion-adapter/` because the waiver originated during Plan 02-03 Task 2's live-snapshot refresh (see `02-03-PLAN.md`).*
