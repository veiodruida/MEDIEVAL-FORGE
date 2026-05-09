---
phase: 02
reviewers: [gemini, codex, opencode]
reviewed_at: 2026-05-09T00:00:00Z
plans_reviewed:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
self_skipped: claude
---

# Cross-AI Plan Review — Phase 02

> Note: Phase 02 is already executed and just completed code-review-fix (4 warnings resolved, commit `e575f76`). This retroactive review surfaces validation for the just-applied fixes and informs Phase 02.1 backlog. Treat findings as informational confirmation of code-review concerns and additional Phase 03+ planning input.

## Gemini Review

# Implementation Plan Review: Phase 02 — Ingestion Adapter

## 1. Summary
The Phase 02 implementation plans are exceptionally well-structured, demonstrating a deep understanding of both the legacy v1 codebase and the v3 requirements. The plans successfully establish a clean data contract (`ProjectDataset`) and a robust adapter layer while strictly adhering to the "wrap, don't rewrite" mandate. The technical decisions—especially the use of `representative_point()` for geographic partitioning and the "Waiver Loop" strategy for parity—show high engineering maturity. The sequencing correctly prioritizes contract stability (Plan 01) before building the adapter logic (Plan 02) and exposing it (Plan 04).

## 2. Strengths
*   **Seam Insertion Strategy:** Plan 01 correctly identifies the atomicity required for the `ProjectDataset` migration. Identifying all 9 callsites via grep prevents the silent `AttributeError` regressions that often plague such refactors.
*   **Geographic Robustness:** Using Shapely's `representative_point()` instead of `centroid` in `_split_by_iso` (Plan 02) is a critical win. It ensures that concave or L-shaped coastal municipalities (common in Portugal) are correctly assigned to the landmass rather than falling into the ocean or being misassigned.
*   **Parity Discipline:** The "Waiver Loop" strategy in Plan 03 (snapshot adaptations vs. golden mutations) is the correct way to handle external data drift without compromising the "deployed wins" v3 constraint.
*   **Security & Stability Guards:** The inclusion of bbox span limits (30° DoS guard), strict UUID validation, and per-project `stop_event` scoping shows a "production-first" mindset even for a local tool.
*   **FastAPI Best Practices:** Plan 04 correctly switches the ingest endpoint to `GET` to align with the browser's `EventSource` API and provides a clear idempotency justification.

## 3. Concerns
*   **Structural Parity Divergence (HIGH):** As noted in `STATE.md`, live OSM `admin_level=8` (ES) and `admin_level=7` (PT) have significantly higher cardinality and different vertex precision than the vendored `es-atlas` fixture.
    *   *Risk:* The Plan 03 assumption that the "Waiver Loop" will eventually converge to green may be mathematically impossible if the centroids shift enough to flip border pixels in the Voronoi stage.
    *   *Impact:* This could lead to a permanent `xfail` state for live parity, which is already reflected in the project's backlog (Phase 02.1).
*   **I/O Overhead in Sliders (LOW):** Plan 01 D-02 decides to carry `Path` objects rather than in-memory FeatureCollections.
    *   *Risk:* While good for determinism, this might introduce latency in Phase 04 when users move sliders for σ or median passes if the `landmask` stage is re-triggered frequently.
*   **Centroid Math Parity (MEDIUM):** In `decode_geojson_municipalities`, the plan calculates the centroid as the arithmetic mean of points.
    *   *Risk:* TopoJSON decoders sometimes use pre-calculated properties or different winding order logic.
    *   *Mitigation:* The plan already mandates reading the `decode_topojson_municipalities` source first, which mitigates this.

## 4. Suggestions
*   **Pre-emptive Cardinality Match:** In `adapters/osm.py`, consider adding an optional "limit" or "curation" hook that could prune live features to match the vendored fixture's count. This might help the "Waiver Loop" converge faster by eliminating "noise" municipalities added to OSM recently.
*   **Async File I/O:** Since the SSE endpoint is designed to be highly concurrent, consider using `anyio` or `aiofiles` for the `json.load`/`json.dump` calls in the adapter, especially for the ~30MB Spanish municipality GeoJSON, to avoid blocking the event loop.
*   **SSIM Visualizer:** For Plan 03, if a parity mismatch occurs, the automated saving of a `DIFF_*.png` is great. It might be helpful to also log the specific coordinates of the worst SSIM clusters to help the human developer decide if the drift is "acceptable detail" or a "logic bug."

## 5. Risk Assessment
**Overall Risk: LOW**

The architectural approach is sound. The only significant risk is **Parity Failure** (the inability for live ingestion to match the vendored golden), but the plans explicitly treat this as a "known unknown" and provide a structured "Waiver Loop" to handle it. By separating the contract migration (Plan 01) from the live data acquisition (Plan 02/03), the project ensures that the core pipeline remains stable even if the live data source is currently too "noisy" to achieve 100% pixel parity. The test coverage (unit, integration, and parity) is comprehensive and follows a logical pyramid.

---

## Codex Review

## Overall Summary

The Phase 02 plan set is unusually thorough: it captures the architectural seam (`ProjectDataset`), protects Phase 01 parity, wraps rather than rewrites ingestion, and keeps CI network-free. The main weakness is that Plan 02-03's stated live-parity contract is likely unrealistic and already contradicted by the later Phase 02.1 backlog note: live OSM and vendored inputs are structurally different sources, so "same golden, 20/20 passing" may be unreachable without curation or a revised contract. There are also some implementation-level risks around hardcoded repo-root path derivation, tests that monkeypatch the wrong module globals, SSE semantics, and status/locking behavior.

---

## Plan 02-01 Review

### Summary

Plan 02-01 is strong and correctly treats the `ProjectDataset` migration as an atomic contract change. It directly addresses the most dangerous failure mode: partial migration from flat `RegionConfig` fields to `cfg.dataset.*`. The scope is appropriate for an initial seam-insertion plan, though a few details should be tightened around dataclass typing, GeoJSON/TopoJSON detection, and fail-fast validation placement.

### Strengths

- Correctly makes `ProjectDataset` the single input port, matching D-01 and D-V3-05.
- Atomic migration across `contracts.py`, `regions.py`, `landmask.py`, `render.py`, and `__init__.py` is the right dependency boundary.
- Keeps `iberia_config()` semantically unchanged by pointing to vendored inputs.
- Adds GeoJSON ES support early, before live adapter output depends on it.
- Includes parity verification immediately after the migration.
- Good unit coverage for contract shape, vendored paths, and missing input failures.

### Concerns

- **MEDIUM:** `RegionConfig.dataset: "ProjectDataset" = field(default=None)` conflicts with "single mutable input" intent. If `dataset` is required conceptually, making it optional invites runtime-only failure. It is acceptable short-term, but should be explicit as a temporary compatibility concession.
- **MEDIUM:** Extension-only detection for ES format is brittle. A `.json` GeoJSON or `.geojson` TopoJSON would route incorrectly. The plan says extension sniffing is chosen for minimal branching, but a top-level key check would be safer with little complexity.
- **MEDIUM:** Fail-fast validation in `load_municipalities()` checks `mountain_river_json`, even though `load_municipalities()` does not consume it. This is defensible as a dataset integrity gate, but the function name/location becomes misleading.
- **LOW:** The objective says "9 grep-verified callsites" but the table totals 10 read occurrences when counting repeated `if` checks. The acceptance criteria soften this, but the wording may confuse executors.
- **LOW:** The suggested tests use semicolon-separated statements in Python snippets. That is harmless but not ideal style for project tests.
- **LOW:** `decode_geojson_municipalities` ignores holes and only uses exterior rings. This matches the intended TopoJSON shape, but should be verified against the actual `decode_topojson_municipalities`, not assumed.

### Suggestions

- Prefer format detection by content:
  - If top-level has `"type": "FeatureCollection"` → GeoJSON.
  - If top-level has `"type": "Topology"` or `"objects"` → TopoJSON.
- Add one unit test for `decode_geojson_municipalities` shape using a tiny Polygon and MultiPolygon fixture.
- Consider moving full dataset path validation into a helper such as `validate_project_dataset(cfg.dataset)` so `landmask.py` does not own terrain validation semantically.
- Make the `dataset=None` runtime failure message explicit: "legacy RegionConfig construction is no longer supported."
- Add grep acceptance for legacy field declarations as well as reads.

### Risk Assessment

**Risk: LOW-MEDIUM.** The migration is invasive but well-scoped and parity-gated. The biggest risk is subtle GeoJSON shape mismatch, which can be mitigated with a direct shape unit test.

---

## Plan 02-02 Review

### Summary

Plan 02-02 has the right high-level shape: a dedicated adapter package, no changes to v1 ingest code, and tests around partitioning. It appropriately separates OSM adapter logic from terrain stub logic. However, several implementation details are risky: hardcoded repository root via `parents[5]`, monkeypatching `PROJECTS_ROOT` through a module object that may not affect imported symbols, and a possible mismatch with the real `fetch_municipalities` signature and expected `country_iso` type.

### Strengths

- Respects "wrap, don't rewrite" by importing `fetch_municipalities`.
- Correctly identifies that existing clipping is a union filter, not a partition.
- Uses `representative_point()` rather than centroid, which is a robust improvement.
- Keeps terrain as a passthrough stub, matching D-13.
- Avoids new dependencies.
- Adds input validation for UUID and bbox before filesystem/network work.
- Test cases cover PT/ES split, dropped features, MultiPolygon, invalid ISO, bbox validation, and output writing.

### Concerns

- **HIGH:** `_REPO_ROOT = Path(__file__).resolve().parents[5]` is fragile and may be wrong depending on package layout. In this repo, from `backend/medieval_forge/services/pipeline/adapters/osm.py`, `parents[5]` likely resolves to `backend`, not repo root, so the vendored path may become `backend/data/...` instead of `data/...`.
- **HIGH:** Tests monkeypatch `medieval_forge.services.paths.PROJECTS_ROOT`, but `base.py` imports `project_dir` directly. If `project_dir` closes over a module constant, monkeypatching may work; if not, the test may write to the real project dir. This needs verification.
- **MEDIUM:** The plan's interface says `fetch_municipalities(country_iso: str)`, but research earlier mentioned `country_iso=["PT", "ES"]` in examples. The adapter passes `country_iso=iso_codes[0]` and `clip_iso_codes=iso_codes`; this may be correct, but the plan should verify the actual semantics of `fetch_municipalities`.
- **MEDIUM:** Bbox tuple ordering is `(lat_min, lon_min, lat_max, lon_max)`. Many geo APIs use `(lon_min, lat_min, lon_max, lat_max)`. The plan must confirm existing v1 conventions before locking this.
- **MEDIUM:** `_split_by_iso` silently assigns a feature to the first matching buffered country polygon. With a buffer, border/coastal features could match both. The first-match behavior should be documented in output metadata or counted as ambiguous.
- **MEDIUM:** `_split_by_iso` only handles Polygon/MultiPolygon and drops other geometry. Fine for municipalities, but malformed upstream data could silently reduce counts.
- **LOW:** Source-level tests checking for strings like `ingest_terrain` are brittle and can fail on comments/docstrings.
- **LOW:** The adapter writes fixed file names. Concurrent runs for the same project can overwrite each other unless the endpoint enforces locking reliably.

### Suggestions

- Replace `parents[5]` with a central path helper or derive from the same project/data root used by `regions.py`.
- Add a unit test asserting `_VENDORED_MOUNTAIN_RIVER.exists()` in both `osm.py` and `terrain.py`.
- In tests, monkeypatch the exact symbol used by the adapter, or inject a project root helper instead of relying on module-global mutation.
- Add split diagnostics:
  - total input features
  - PT count
  - ES count
  - dropped count
  - ambiguous count if multiple polygons contain the representative point
- Validate `iso_codes` includes exactly or at least `PT` and `ES`, then write an explicit error for unsupported regions because Phase 05 handles generalization.
- Confirm bbox ordering against `api/ingest.py` and `ingest_osm.py` before implementation.

### Risk Assessment

**Risk: MEDIUM.** The architecture is sound, but path derivation and test isolation are likely to cause implementation failures. The real-world partitioning logic also needs diagnostics to avoid silent bad snapshots.

---

## Plan 02-03 Review

### Summary

Plan 02-03 is the weakest plan because its acceptance target appears incompatible with the project's own empirical findings. It insists that live OSM snapshots must pass against the same golden outputs with no relaxed thresholds, but the roadmap already adds Phase 02.1 because that premise was found structurally false. The mechanics of no-network CI, snapshot refresh, and test mirroring are well-designed, but the success contract should be revised before implementation.

### Strengths

- Correctly forbids network calls in CI.
- Uses committed post-adapter GeoJSON snapshots, which keeps parity deterministic.
- Separates refresh script from test execution.
- Documents refresh ritual and avoids auto-commit.
- Reuses the same parity assertions as the fixture-path test.
- Makes failure loud and actionable when snapshots are missing.
- Adds SHA and feature-count summary documentation.

### Concerns

- **HIGH:** The plan's core premise conflicts with the provided Phase 02.1 context. The project already determined that live OSM and vendored fixtures are different upstream sources and structurally diverge. Therefore, "same golden, 20 passed" is likely unreachable.
- **HIGH:** "Waiver loop: refresh until green" does not solve structural divergence. If upstream source shape differs, repeated refreshes will not converge.
- **HIGH:** This plan claims to satisfy ROADMAP-02#1, but Phase 02.1 says ROADMAP-02#1 is unreachable as written and must be formally resolved later.
- **MEDIUM:** `autonomous: false` is appropriate, but the plan still has acceptance criteria that depend on external Overpass behavior and potentially huge committed GeoJSONs.
- **MEDIUM:** The refresh script monkeypatches `paths_mod.PROJECTS_ROOT`, but as in Plan 02-02, this may not affect already imported helpers depending on implementation.
- **MEDIUM:** The test imports and runs the full pipeline at session scope. If the snapshot files are very large, this may significantly increase parity suite runtime.
- **LOW:** `py -3.14 -c "import backend.tests.parity.test_iberia_868_live"` is probably not the correct import path unless `backend` is importable as a package.
- **LOW:** The README says "snapshot is wrong, not golden" too strongly given known source mismatch.

### Suggestions

- Reclassify this plan as blocked or superseded by Phase 02.1.
- Replace "live must equal same golden" with one of:
  - Split golden: `golden-live/` with explicit provenance.
  - Curated live snapshot that is intentionally transformed to match vendored cardinality.
  - Contract test for adapter shape/count sanity plus fixture parity remains the only pixel-parity gate.
  - Formal retirement of ROADMAP-02#1 with a replacement acceptance criterion.
- If keeping the test before Phase 02.1, mark it as `xfail(strict=True/False)` only with a documented decision, but that conflicts with current plan language.
- Add a preflight script that prints feature counts and cardinality deltas before running full parity.
- Store snapshot metadata in a sidecar JSON:
  - fetch date
  - Overpass mirror
  - iso counts
  - sha256
  - bbox
  - adapter version/git commit
- Avoid saying "refresh until green"; say "refresh detects drift; structural mismatch requires contract decision."

### Risk Assessment

**Risk: HIGH.** The plan is operationally detailed but targets an acceptance criterion already known to be invalid. Implementing it as written risks wasting time and creating a brittle or permanently failing parity gate.

---

## Plan 02-04 Review

### Summary

Plan 02-04 is a reasonable endpoint plan and cleanly isolates the v3 SSE route from the pipeline run. It mirrors existing v1 patterns and includes useful tests for guards and streaming behavior. The main concerns are around HTTP method semantics, project status locking, test compatibility with modern `httpx`, and whether the endpoint should set status to `generating` or another in-progress state before starting the adapter.

### Strengths

- Keeps v1 endpoint mounted, satisfying coexistence.
- Scope is correct: endpoint invokes adapter only, not `run_pipeline`.
- Good guard coverage: invalid UUID, missing project, generating project, missing bbox.
- Uses SSE cleanup with task cancellation and stop event.
- Emits terminal sentinel on success and error.
- Avoids terrain/Wikidata imports.
- Tests patch the adapter to avoid network calls.
- Derives ISO codes from project metadata rather than hardcoding in the endpoint.

### Concerns

- **HIGH:** The endpoint checks `project.status == "generating"` but does not set an in-progress status before starting. Two requests can pass the guard concurrently if status is `draft`, causing overlapping writes to `inputs/`.
- **HIGH:** Using `GET` for a mutating operation is semantically risky. The plan justifies this with EventSource, but the endpoint writes files and updates DB status. Browsers/proxies may retry or prefetch GETs. SSE often uses GET, but mutation should still be treated carefully.
- **MEDIUM:** The route returns 200 before adapter failure, with error only in SSE body. That is normal for SSE, but clients must be designed to handle it.
- **MEDIUM:** `httpx.AsyncClient(app=app, ...)` is removed/deprecated in newer httpx versions; tests may need `ASGITransport(app=app)`.
- **MEDIUM:** In-memory SQLite with async sessions may not share state across connections unless configured carefully. The test fixture may need `StaticPool` or a shared connection setup.
- **MEDIUM:** `clip_iso_codes_for_qid(project.country_qid)` may not accept combined values like `"Q29,Q45"` unless already proven. If it returns `None`, valid Iberia projects may get 400.
- **MEDIUM:** Cancel path sets status to `error_ingesting`, but a client disconnect may not mean ingestion failed if the adapter completed or is near completion. This could create misleading state.
- **LOW:** `_STOP_EVENTS` registry is local and not used to stop existing runs externally. It mainly supports cleanup, not overlap control.
- **LOW:** The plan says "terminal None sentinel emitted" but that sentinel is internal, not visible in SSE body. Tests should verify stream completion, not a literal sentinel.

### Suggestions

- Add an atomic status transition before returning the stream:
  - If status is in an active state, return 409.
  - Otherwise set `status = "ingesting"` or `"generating"` and commit before starting the producer.
- Consider using `POST /api/v3/projects/{id}/ingest` for mutation and a separate `GET` SSE stream, unless the frontend strongly requires EventSource-only GET.
- If staying with GET, add `Cache-Control: no-store` and document that the endpoint mutates state.
- Use `httpx.ASGITransport` in tests for compatibility.
- Configure in-memory SQLite tests with `StaticPool` or use the project's established database test fixture.
- Test concurrent requests explicitly once status locking is added.
- Add a test that valid project with unsupported `country_qid` returns 400.
- Add a test that v1 route remains present in `app.routes`.

### Risk Assessment

**Risk: MEDIUM.** Endpoint scope and tests are good, but lack of atomic in-progress locking is a real concurrency bug. HTTP GET mutation is also a design risk that should be deliberately accepted or changed.

---

## Cross-Plan Concerns

- **HIGH:** Phase 02 and Phase 02.1 conflict. Plans 02-03 and 02-04 say Phase 02 closes all success criteria, but Phase 02.1 says the original live parity criterion is deferred/unreachable.
- **HIGH:** Hardcoded repo-root discovery appears in multiple plans and is likely wrong. Centralize path resolution.
- **MEDIUM:** Several tests rely on monkeypatching module globals that may not affect imported symbols.
- **MEDIUM:** Committing very large live GeoJSON snapshots may bloat the repo and slow parity tests.
- **MEDIUM:** Status naming is inconsistent: `generating`, `ingested`, `error_ingesting`, while this phase is about ingesting, not generating.
- **LOW:** Some grep-based acceptance criteria may produce false positives/negatives due to comments and docstrings.

---

## Recommended Plan Changes Before Execution

- Mark Plan 02-03 as blocked pending Phase 02.1 contract decision.
- Add a central helper for repository/data paths; remove all `parents[5]` usage.
- Add atomic endpoint status transition to prevent concurrent v3 ingestion.
- Verify bbox ordering and `fetch_municipalities` signature before implementing Plan 02-02.
- Add direct unit tests for `decode_geojson_municipalities`.
- Replace brittle source-string tests with behavioral tests where possible.

---

## Overall Risk Assessment

**Overall Risk: MEDIUM-HIGH.**

Plans 02-01, 02-02, and 02-04 are mostly executable with targeted corrections. Plan 02-03 raises the phase risk substantially because it encodes a parity requirement already identified as structurally invalid. The safest path is to implement the contract and adapter pieces first, then reopen the live-parity contract formally before adding a hard CI gate.

---

## OpenCode Review

## Plan Review — Phase 02: Ingestion Adapter

---

### Plan 02-01 (ProjectDataset migration)

**Summary**
Atomic 5-file migration that replaces `RegionConfig`'s three legacy path strings with a `ProjectDataset` dataclass, adds a GeoJSON decoder branch to `landmask.py`, and wires `iberia_config()` to the vendored files. The approach is sound; the atomicity constraint is the right load-bearing design.

**Strengths**
- Atomic commit with fail-fast input assertion (D-04) prevents silent breakage
- Callsite table (9 occurrences across 3 files) is grep-verified, not guessed
- `decode_geojson_municipalities` output shape is pinned to `decode_topojson_municipalities` verbatim (same centroid math, same bbox filter)
- `iberia_config()` vendored path preserved semantically — Phase 01 parity path untouched

**Concerns**

- **MEDIUM — `msg is None` yielded to stream:** `_v3_sse_generator` in `api/ingest.py` (the v1 template Plan 04 mirrors) does `yield msg` after `if msg is None: break`. Plan 02-04's `_v3_sse_generator` may have this same bug if it yields the sentinel instead of just breaking. Verify the Plan 04 implementation explicitly skips yielding `None`.
- **LOW — Forward reference in `RegionConfig`:** `dataset: "ProjectDataset"` in `RegionConfig` references a class defined above it. Python resolves this at runtime, so it works — but `from __future__ import annotations` (Plan 02-04's test file has it) makes all annotations strings, which changes behavior. Ensure `contracts.py` does NOT have `annotations` import if you're relying on forward-ref resolution at construction time.

**Suggestions**
- Add `grep -rn "cfg\.mountain_river_json\|cfg\.municipality_pt_geojson\|cfg\.municipality_es_topojson" backend/medieval_forge/services/pipeline/` as a pre-commit hook or CI check to catch any stray legacy reads
- The `_VENDORED_MOUNTAIN_RIVER` path in `osm.py` (`parents[5]`) and `terrain.py` (`parents[5]`) is duplicated — consider extracting to `base.py` as a constant

---

### Plan 02-02 (Adapters subpackage)

**Summary**
Four-module `adapters/` subpackage with `build_dataset_from_osm` wrapping `fetch_municipalities` plus new split-by-ISO logic, a terrain stub, and 11 unit tests. Correctly uses `representative_point` (not `centroid`) for partition safety. `ingest_terrain/` and `ingest_wikidata/` are untouched.

**Strengths**
- `representative_point()` over `centroid()` is the right call for concave coastal polygons (Lisbon, Barcelona)
- `0.025°` buffer is explicitly documented as matching `ingest_osm._COUNTRY_BUFFER_DEG` — this prevents silent drift if the upstream constant changes
- `_validate_bbox` (30°/axis) provides a belt-and-suspenders DoS guard independent of the adapter's existing timeouts
- D-13 honored: `services/ingest_terrain/` is not imported anywhere in the subpackage (verified by source-level test)

**Concerns**

- **MEDIUM — Duplicate `_VENDORED_MOUNTAIN_RIVER` definition:** Identical `parents[5]` computation exists in both `osm.py` and `terrain.py`. If the file tree ever changes, both will break independently. Move to `base.py` or `contracts.py`.
- **MEDIUM — `iso_codes` must be `["PT", "ES"]` (hardcoded validation):** The guard `if "PT" not in iso_codes or "ES" not in iso_codes` is fine for Phase 02's Iberia scope, but if Phase 05 generalizes to other regions, this check will need relaxing. Worth a `TODO` or tracking issue.
- **LOW — `_COUNTRY_BUFFER_DEG` not exported:** The `0.025` constant is module-private. If `_split_by_iso` needs tuning later, there's no test-accessible constant. Not a blocker but a minor observability gap.

**Suggestions**
- Add a unit test for `_split_by_iso` with a feature whose `representative_point` falls on the PT/ES border (the "first match wins" logic at the partition step needs coverage for edge cases)
- Consider adding a `conftest.py` fixture that calls `build_dataset_from_osm` with a pre-built synthetic `ProjectDataset` so downstream plans can test the SSE endpoint without real network

---

### Plan 02-03 (Live parity test + snapshot)

**Summary**
Adds `test_iberia_868_live.py`, `refresh_live_snapshot.py`, and committed snapshot files. Two-path (vendored + live), one-golden structure is correct. The waiver loop strategy (not SSIM relaxation) is the right call given the Phase 01 D-09 precedent.

**Strengths**
- Waiver loop discipline is explicitly locked (no `0.95` threshold, no `@pytest.mark.xfail`) — this prevents drift from being papered over
- Refresh script uses a `tempfile.mkdtemp` `PROJECTS_ROOT` so local refreshes don't pollute developer data
- `scripts/refresh_live_snapshot.py --help` is verifiable in CI (Task 1), confirming the script is at least importable before the snapshot exists
- README documents the ritual clearly

**Concerns**

- **HIGH — Plan 02-01 is a hard dependency but listed as `depends_on: ["02-01"]` in the YAML frontmatter, not execution context:** The context includes `02-01-SUMMARY.md`, implying the executor reads it. This is fragile — if the summary doesn't exist yet, Plan 02-03 may proceed on stale assumptions. Consider adding an explicit `git log --oneline -1` smoke check in the `<read_first>` block.
- **HIGH — `autonomous: false` means the GSD executor won't auto-proceed past Task 2.** The checkpoint is the right call given the Overpass network dependency, but the resume-signal ("type 'snapshot committed and 10 parity tests pass'") requires manual intervention in every future GSD resume. This creates a stateful dependency that could stall if the context window resets before the user commits.
- **MEDIUM — bbox format mismatch between Task 1 (Plan 03) and Task 2 (Plan 02):** `IBERIA_BBOX = (36.0, -9.5, 44.0, 4.3)` is labeled `(lat_min, lon_min, lat_max, lon_max)` in the refresh script comment. `ingest_osm.fetch_municipalities` takes `bbox: tuple[float, float, float, float]`. If the OSM adapter's `_validate_bbox` and the Overpass query interpret the order differently, the refresh script could fetch the wrong bounding box. **Verify the exact `(lat, lon)` order in `ingest_osm.py:fetch_municipalities` before running the refresh.** If Overpass expects `(south, west, north, east)` but the script sends `(lat_min, lon_min, lat_max, lon_max)`, the order is correct — but this must be confirmed against the actual implementation.
- **MEDIUM — Phase 02.1 backlog item:** The plan correctly defers the live-parity contract ambiguity to Phase 02.1, but the current plan produces `test_iberia_868_live.py` that may hit the "unreachable as written" condition described in the roadmap. If the live snapshot always diverges from vendored, this test will permanently be in waiver-loop state. Worth an explicit acknowledgment that ROADMAP-02#1 may need to be retired, not just deferred.

**Suggestions**
- Before the human checkpoint, run `py -3.14 scripts/refresh_live_snapshot.py --help` in CI to at least verify the script is syntactically valid and the bbox format matches what `fetch_municipalities` expects
- Consider adding a `SKIP` marker option to the live test (commented out, with instructions) so Phase 02 can close without blocking on OSM availability — the snapshot can be refreshed in a follow-up patch
- Add the `sha256sum` of the snapshot files to the commit message body (not just the summary doc) for discoverability in `git log`

---

### Plan 02-04 (SSE endpoint)

**Summary**
New `/api/v3/projects/{id}/ingest` endpoint mirroring the v1 `_sse_generator` pattern. Correctly keeps the v1 endpoint mounted, adds UUID/404/409 guards, and wires `build_dataset_from_osm`. 6 unit tests cover the contract.

**Strengths**
- `asyncio.timeout(10.0)` in the error-path test (Test 6) is the right approach to surface zombie producer tasks — this is a common SSE footgun
- Per-(project_id, step) stop_event registry follows the `ingest_terrain/runner.py` pattern without importing it (correctly keeps `ingest_terrain/` untouched per D-13)
- Error path emits only `exc.__class__.__name__` to the client; full trace to logger (T-02-04-05 mitigation)
- Module-level `AsyncSessionLocal` global is the correct seam for the test monkeypatch strategy

**Concerns**

- **HIGH — `_v3_sse_generator` yields `msg` including the `None` sentinel check logic:** The pattern `while True: msg = await queue.get(); if msg is None: break; yield msg` is correct. But if the implementation yields before the `None` check, it will yield `None` as a string to the SSE stream, breaking the client. The plan action code shows the correct pattern — verify the executor doesn't accidentally refactor it.
- **MEDIUM — `async for chunk in r.aiter_text()` may lose SSE line delimiters:** `httpx.AsyncClient.aiter_text()` strips newlines by default in some versions. Consider `r.aiter_raw()` or `r.aiter_bytes()` with manual decoding to avoid SSE parsing issues in the test assertions. The plan's test uses `aiter_text()` — verify this produces the expected `"data: ..."` strings in the body string.
- **MEDIUM — `_adapter_producer` and `_set_status` both call `_set_status`:**
  - `_adapter_producer` calls `_set_status(project_id, "ingested", ...)` on success → puts "DONE" → puts `None`
  - `_set_status` is also called by the endpoint? No — looking at `trigger_v3_ingest`, it only calls `_v3_sse_generator`. So only the producer sets status. This is fine.
  
  But: on `CancelledError`, the producer calls `_set_status("error_ingesting")` AND the `finally` block still puts `None` to the queue. The `finally` block's `await queue.put(None)` happens after the `except asyncio.CancelledError` handler returns. The order is: `CancelledError` → handler sets status → handler returns → `finally` runs → `await queue.put(None)`. This is correct.
- **LOW — `_set_status` is called twice on success path:** `_adapter_producer` calls `_set_status("ingested")` then `await queue.put("DONE")`. The `finally` block puts `None`. No second status call. This is fine.

**Suggestions**
- Add a test for the `_clear_stop_event` call path — verify that after the SSE stream ends, `_STOP_EVENTS[(project_id, "osm")]` is empty. Currently only the happy/error paths are tested.
- Consider whether the endpoint should update `project.status = "ingesting"` at the start (before yielding), not just at the end. This provides a better UX for concurrent clients polling status.
- The `headers` dict in the `StreamingResponse` includes `X-Accel-Buffering: no` (nginx disable) and `Cache-Control: no-cache` — correct for SSE, but consider adding `Content-Type: text/event-stream; charset=utf-8` explicitly rather than relying on the `media_type` kwarg.

---

### Risk Assessment

**Overall: MEDIUM**

| Plan | Risk | Primary Driver |
|------|------|----------------|
| 02-01 | MEDIUM | Partial migration (9 callsites across 3 files); silent breakage if one is missed |
| 02-02 | LOW | Well-contained; duplicate constant is minor |
| 02-03 | HIGH (process) | `autonomous: false` checkpoint blocks automation; bbox format uncertainty could produce wrong snapshot |
| 02-04 | LOW | Correct pattern; SSE sentinel bug is preventable with careful code review |

**The biggest risks are process, not technical:**
1. **Plan 02-03's manual checkpoint** is a single-threaded dependency in an autonomous pipeline. If the user doesn't run the refresh script within the current context window, Phase 02 cannot close autonomously.
2. **bbox format mismatch** between the refresh script and `fetch_municipalities` could silently produce a wrong bounding box — this should be verified against the actual implementation before the snapshot is committed.
3. **Phase 02.1** (live-parity contract) may find that the waiver loop never converges, requiring a design decision that Plan 02-03 should not have to make.

---

## Consensus Summary

### Agreed Strengths (mentioned by 2+ reviewers)

- **`representative_point()` over `centroid`** for `_split_by_iso` partitioning — concave coastal polygons (Lisbon, Barcelona) handled correctly. All 3 reviewers explicitly call this out.
- **Wrap-don't-rewrite ingest discipline** — `fetch_municipalities` reused; `ingest_terrain/` + `ingest_wikidata/` untouched (D-13). All 3.
- **Atomic ProjectDataset migration** — single commit across 5 files; no partial state. All 3.
- **No-network CI parity** via committed snapshots + separate refresh script — gemini, codex, opencode.
- **bbox/UUID/30°-span DoS guards** — production-first mindset for local tool. Gemini, opencode.
- **PT/ES clipping buffer matches upstream constant** (`_COUNTRY_BUFFER_DEG = 0.025°`) — explicit comment prevents drift. Codex, opencode.
- **Phase 01 parity preserved** — `iberia_config()` semantically unchanged. Codex, opencode.

### Agreed Concerns (raised by 2+ reviewers — highest priority)

- **HIGH — Plan 02-03 live-parity contract structurally invalid** (gemini HIGH, codex HIGH × 3 mentions, opencode HIGH process). All 3 reviewers identify the live OSM vs vendored structural divergence; codex calls "same golden, 20/20 passing" mathematically unreachable. **Already deferred to Phase 02.1 and converted to xfail per recent commit `23cd5a1`** — review confirms this was correct.
- **HIGH — Plan 02-04 missing atomic in-progress lock** (codex HIGH, opencode silent in concerns but acknowledged). 409 gate doesn't fire because producer never sets `status="generating"` before kickoff. **Confirmed by Phase 02 code-review WR-01 and just fixed in commit `9148b61`**.
- **HIGH — Hardcoded `parents[5]` repo-root derivation** (codex HIGH × 2 plans, opencode MEDIUM). Fragile path math; centralized helper recommended. **Not yet fixed — flag for Phase 02.1 backlog or follow-up phase**.
- **MEDIUM — bbox tuple ordering verification** (codex MEDIUM, opencode MEDIUM). `(lat_min, lon_min, lat_max, lon_max)` vs Overpass `(south, west, north, east)` — needs empirical confirmation in `ingest_osm.fetch_municipalities`.
- **MEDIUM — Test monkeypatch fragility** (codex MEDIUM × 2, opencode silent). Tests patch `paths.PROJECTS_ROOT` but adapters import `project_dir` directly — may not affect imported symbols.
- **MEDIUM — Border-feature dedupe gap** (codex MEDIUM "first-match-wins on buffered polygons", opencode "test missing for border `_split_by_iso`"). **Confirmed by Phase 02 code-review WR-02 and just fixed in commit `7491821`**.
- **MEDIUM — TopoJSON/GeoJSON detection by extension only** (codex MEDIUM, gemini implicit). Top-level key check (`"type"`) more robust than file suffix.

### Divergent Views

- **Overall risk ratings spread**: Gemini LOW · OpenCode MEDIUM · Codex MEDIUM-HIGH. Same pattern as Phase 01 — Codex consistently most pessimistic, Gemini most optimistic.
- **GET vs POST for SSE endpoint**: Codex MEDIUM concern about GET semantics for mutating operation. Gemini explicitly praises GET as "FastAPI best practice for EventSource API". Direct disagreement.
- **`autonomous: false` on Plan 02-03**: Codex calls it "appropriate" but flags the embedded acceptance criteria. OpenCode flags it HIGH-process risk for context-window-reset stalls. Gemini silent.
- **Cardinality curation hook**: Gemini suggests adding optional limit/curation in adapter to help waiver loop converge. Codex argues structural divergence cannot be solved by curation, only by contract change. Opposing solutions.

### Validation of Recent Fixes

This review retroactively validates findings from `/gsd-code-review-fix 02` (commit `e575f76`):

| Code-review WR | Finding | Reviewers who flagged | Fix commit |
|---|---|---|---|
| WR-01 | 409 gate no-op (status never set to "generating") | Codex HIGH | `9148b61` |
| WR-02 | Border features double-fetched, no `osm_id` dedupe | Codex+OpenCode MEDIUM | `7491821` |
| WR-03 | Bare `except:` swallows signals | (not flagged in plan review — caught only at code level) | `ca770af` |
| WR-04 | `mountain_river_data.json` no `encoding='utf-8'` | (gemini phase-01 review recommended utf-8 everywhere) | `718a86d` |

3 of 4 code-review findings were predicted by plan-level reviewers, validating the cross-AI review process.

### Recommended Follow-ups for Phase 02.1 Backlog

1. **Centralize repo-root path resolution** — replace all `parents[5]` with single `data_root()` helper in `paths.py` (codex HIGH × 2, opencode MEDIUM).
2. **Verify bbox tuple ordering** — empirical test against `ingest_osm.fetch_municipalities` Overpass call (codex MEDIUM, opencode MEDIUM).
3. **TopoJSON/GeoJSON content-based detection** — top-level `"type"` key check instead of file extension (codex MEDIUM).
4. **Cardinality curation hook OR contract change** for live-parity — pick one (gemini suggests curation, codex argues contract). Phase 02.1 already opened for this decision.
5. **Test monkeypatch reliability audit** — review all `paths_mod.PROJECTS_ROOT` patches; switch to dependency-injection or fixture-injected helper if any are unreliable.
6. **`_split_by_iso` border edge-case test** — already partially addressed by WR-02 fix; explicit border-feature unit test still missing per opencode suggestion.
7. **Add `iso_codes` validation `TODO`** — current Phase 02 hardcodes PT/ES; flag for Phase 05 region generalization (opencode MEDIUM).

