---
status: complete
phase: 06-export-contract-validation-gate
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md, 06-03-SUMMARY.md]
started: 2026-05-13T16:00:00Z
updated: 2026-05-13T16:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. Restart from scratch. Server boots without errors. Routes load. API responds — no crash, no import error.
result: pass
notes: uvicorn started cleanly; /api/projects responded; no import errors

### 2. v3 Export Route Registered
expected: POST /api/v3/projects/nonexistent-id/export returns HTTP 400/404/422, NOT route 404.
result: pass
notes: returned 400 {"detail":"project_id must be a valid UUID"} — route exists

### 3. Dry-Run Export Returns Validation Report
expected: POST /api/v3/projects/{id}/export?dry_run=true returns JSON with validation report and errors list.
result: pass
notes: old project (no original_idx, no terrain files) returned 422 + dry_run:true + 93 structured D-08 errors (SCHEMA_INVALID + MISSING_ORIGINAL_IDX). 422 on failure is by design (WR-01).

### 4. Full Export Returns 201 + Download Link
expected: Valid project export returns 201 with download_url; MANIFEST has validation_report.passed=true.
result: pass
notes: e2e test_iberia_passes_export_gate + test_france_1066_passes_export_gate both pass with 201 + MANIFEST schema_version=2 + validation_report.passed=true

### 5. Export Download Returns Valid Zip
expected: GET /api/v3/projects/{id}/export/download returns application/zip with 12 files + MANIFEST.json with sha256.
result: pass
notes: download endpoint unit test passes (5/5); e2e tests validate zip structure including per-file sha256 hashes

### 6. Broken Export Returns 422 with D-08 Error Envelope
expected: Broken pipeline output returns 422 with structured {code, severity, file, context, message} errors.
result: pass
notes: 7 broken fixture e2e tests pass — every D-08 code (SCHEMA_INVALID, COLOR_COLLISION, OCEAN_LEAK, TERRITORY_TOO_SMALL, MISSING_ORIGINAL_IDX, PIXEL_CENTER_OUT_OF_RANGE) triggers correct 422 envelope; aggregate test confirms multi-failure recording

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
