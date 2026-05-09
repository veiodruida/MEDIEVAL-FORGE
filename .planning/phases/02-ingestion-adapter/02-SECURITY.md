---
phase: 02
phase_name: ingestion-adapter
audited_at: 2026-05-09
auditor: gsd-security-auditor (claude-sonnet-4-6)
asvs_level: L1
threats_total: 20
threats_closed: 20
threats_open: 0
status: SECURED
---

# Security Audit — Phase 02: ingestion-adapter

## Trust Boundaries

| Boundary | From | To | Controls |
|----------|------|----|----------|
| HTTP/API | Client | FastAPI v3 ingest endpoint | UUID validation (T-02-04-01), 409 anti-overlap (T-02-04-02), 400 bbox-absent guard |
| Adapter | v3 endpoint | `build_dataset_from_osm` | `_validate_bbox` ≤30°/axis (T-02-02-02 / T-02-04-03) |
| Filesystem | Adapter | `projects/<uuid>/inputs/` | `is_valid_uuid` in `project_inputs_dir` (T-02-02-01) |
| Outbound HTTP | `overpass_client` | Overpass API | 3-endpoint allowlist hardcoded (SSRF transfer) |
| SSE stream | Producer task | Client | Class-name-only error messages (T-02-04-05) |
| Test isolation | Test suite | Filesystem | `PROJECTS_ROOT` monkeypatched to `tmp_path` (T-02-02-06) |
| Script isolation | `refresh_live_snapshot.py` | Filesystem | `tempfile.mkdtemp` (T-02-03-03) |

## Threat Register

| Threat ID | Plan | Category | Disposition | Status | Evidence |
|-----------|------|----------|-------------|--------|----------|
| T-02-01-01 | 01 | Tampering / EoP | mitigate | CLOSED | `landmask.py:142-151` — FileNotFoundError on `cfg.dataset is None` and missing `ProjectDataset` path attrs |
| T-02-01-02 | 01 | DoS | accept | CLOSED | See Accepted Risks Log |
| T-02-01-03 | 01 | Info Disclosure | accept | CLOSED | See Accepted Risks Log |
| T-02-02-01 | 02 | Tampering / Path Traversal | mitigate | CLOSED | `adapters/base.py:15` — `is_valid_uuid` raises `ValueError` before path construction |
| T-02-02-02 | 02 | DoS | mitigate | CLOSED | `adapters/osm.py:50-61` — `_validate_bbox`: 4-tuple, numeric, span ≤ 30°/axis |
| T-02-02-03 | 02 | SSRF | accept | CLOSED | See Accepted Risks Log |
| T-02-02-04 | 02 | Repudiation | accept | CLOSED | See Accepted Risks Log |
| T-02-02-05 | 02 | Info Disclosure | accept | CLOSED | See Accepted Risks Log |
| T-02-02-06 | 02 | Tampering (test isolation) | mitigate | CLOSED | `test_osm_split.py:67-68` — `monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")` |
| T-02-03-01 | 03 | DoS | accept | CLOSED | See Accepted Risks Log |
| T-02-03-02 | 03 | Info Disclosure | accept | CLOSED | See Accepted Risks Log |
| T-02-03-03 | 03 | Tampering (script isolation) | mitigate | CLOSED | `refresh_live_snapshot.py:57-58` — `tempfile.mkdtemp(prefix="refresh_live_")` + `PROJECTS_ROOT` override |
| T-02-03-04 | 03 | SSRF | accept | CLOSED | See Accepted Risks Log |
| T-02-04-01 | 04 | Spoofing / Tampering | mitigate | CLOSED | `v3/ingest.py:140-141` — `is_valid_uuid(project_id)` raises 400 BEFORE any `db.get()` call |
| T-02-04-02 | 04 | DoS (anti-overlap) | mitigate | CLOSED | `v3/ingest.py:146-150` (409 if `status=="generating"`) + `v3/ingest.py:183-184` (WR-01: `project.status="generating"` + `db.commit()` BEFORE `StreamingResponse`) |
| T-02-04-03 | 04 | DoS / SSRF | mitigate | CLOSED | `osm.py:50-61` (bbox guard) + `overpass_client.py:21-25` (hardcoded 3-URL allowlist) |
| T-02-04-04 | 04 | DoS (resource leak) | mitigate | CLOSED | `v3/ingest.py:112-120` — `finally: stop_event.set(); task.cancel(); await task; _clear_stop_event(project_id)` |
| T-02-04-05 | 04 | Info Disclosure (SSE) | mitigate | CLOSED | `v3/ingest.py:84-87` — `exc.__class__.__name__` only in SSE; `logger.exception` holds full traceback |
| T-02-04-06 | 04 | Repudiation | accept | CLOSED | See Accepted Risks Log |
| T-02-04-07 | 04 | Elevation of Privilege | accept | CLOSED | See Accepted Risks Log |

## Accepted Risks Log

| Risk ID | Threat ID | Category | Rationale | Owner | Accepted Date |
|---------|-----------|----------|-----------|-------|---------------|
| AR-02-01 | T-02-01-02 | DoS — oversized GeoJSON | Local tool; no external exposure. GeoJSON size bounded by Overpass query scope and bbox guard. Re-evaluate at public deploy. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-02 | T-02-01-03 | Info Disclosure — `dataset=None` transitional | `RegionConfig.dataset=None` transitional state is internal-only; never reachable via HTTP in v3. Removed at Phase 03+ when v1 stepper deleted. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-03 | T-02-02-03 | SSRF — Overpass endpoint rotation | Allowlist hardcoded in `overpass_client.py`; no user-controlled URL. Endpoint rotation is load-balancing between trusted OSM mirrors only. Accepted for local tool. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-04 | T-02-02-04 | Repudiation — no audit log | Local single-user tool. Standard FastAPI access logs capture endpoint calls. Formal audit trail deferred to production hardening phase. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-05 | T-02-02-05 | Info Disclosure — bbox logged | bbox coordinates are user-supplied geographic extents with no PII. Logged at INFO for debug traceability. Accepted for local tool. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-06 | T-02-03-01 | DoS — Overpass query duration | `_TIMEOUT_S = 180.0` in `overpass_client.py` caps individual requests. Broader rate-limiting deferred to production. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-07 | T-02-03-02 | Info Disclosure — OSM data | OSM data is public domain. No private data ingested. Phase 02 scope is municipality polygons only. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-08 | T-02-03-04 | SSRF — live snapshot script | `refresh_live_snapshot.py` is developer tooling, not reachable via HTTP. Allowlist inherited from `overpass_client.py`. Accepted for dev script. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-09 | T-02-04-06 | Repudiation — SSE stream not persisted | SSE events are ephemeral progress notifications. `logger.exception` captures error detail server-side. Formal SSE audit log deferred. | veiodruida@gmail.com | 2026-05-09 |
| AR-02-10 | T-02-04-07 | EoP — no auth on v3 endpoint | Local tool, single-user. No authentication layer in Phase 02 scope. Auth deferred to public-deploy hardening phase. | veiodruida@gmail.com | 2026-05-09 |

## Unregistered Threat Flags

None. No `## Threat Flags` section found in `02-01-SUMMARY.md`, `02-02-SUMMARY.md`, `02-03-SUMMARY.md`, or `02-04-SUMMARY.md`.

## Security Audit Trail

| Date | Action | Auditor | Notes |
|------|--------|---------|-------|
| 2026-05-09 | Initial audit — Phase 02 complete | gsd-security-auditor | 20/20 threats verified; 10 mitigate CLOSED with file:line evidence; 10 accept logged above |

## Sign-Off

- [x] All `<files_to_read>` loaded before analysis
- [x] Threat register extracted from PLAN.md `<threat_model>` blocks (Plans 01–04)
- [x] Each `mitigate` threat verified with file:line evidence
- [x] Each `accept` threat logged in Accepted Risks Log with rationale
- [x] No `transfer` threats in this phase
- [x] Threat flags from SUMMARY.md `## Threat Flags` checked — none present
- [x] Implementation files not modified (read-only throughout)
- [x] ASVS Level 1 criteria met
- [x] `threats_open: 0` — SECURED
