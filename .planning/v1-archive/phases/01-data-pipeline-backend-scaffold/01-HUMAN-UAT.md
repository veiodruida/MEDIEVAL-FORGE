---
status: partial
phase: 01-data-pipeline-backend-scaffold
source: [01-VERIFICATION.md]
started: 2026-04-16T00:00:00Z
updated: 2026-04-16T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Full install + browser launch
expected: `medieval-forge start` opens the React SPA in the browser on port 8765; the project list page renders with no console errors
result: [pending]

### 2. Real Wikidata ingestion via SSE streaming
expected: Creating a project then clicking "Ingest" (Wikidata source) streams real progress events into the #ingest-log panel; municipalities.geojson is written to the project folder; project.status flips to "ingested"
result: [pending]

### 3. Map generation + PNG previews
expected: Clicking "Generate" starts background generation; status polling shows progress; three PNG images (terrain.png, territories.png, borders.png) appear in the browser once generation completes
result: [pending]

### 4. Unity ZIP download via browser trigger
expected: Clicking "Export ZIP" triggers a browser file download containing a ZIP with the 12 standardized Unity files including MANIFEST.json
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
