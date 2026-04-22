---
phase: quick/260422-hl9
plan: 01
subsystem: backend/services
tags: [encoding, utf-8, geojson, windows-compat, bug-fix]
dependency_graph:
  requires: []
  provides: [utf8-safe-geojson-writes]
  affects: [territories.geojson, baronies.geojson, condado_colors.json, barony_colors.json]
tech_stack:
  added: []
  patterns: [Path.write_text with encoding="utf-8", json.dumps with ensure_ascii=False]
key_files:
  modified:
    - backend/medieval_forge/services/territories_geojson.py
    - backend/medieval_forge/services/baronies_geojson.py
decisions:
  - "Use ensure_ascii=False + encoding='utf-8' on all GeoJSON writes — matches existing render_modern.py reference pattern"
metrics:
  duration: "5m"
  completed: "2026-04-22"
---

# Quick Task 260422-hl9: Fix UTF-8 Encoding Bug (write_text without encoding) Summary

**One-liner:** Added `ensure_ascii=False` + `encoding="utf-8"` to all four bare `write_text()` call sites in the services layer so non-ASCII names (e.g. "Córdoba") are stored as real UTF-8 bytes on disk instead of being silently re-encoded through cp1252 on Windows.

## What Was Done

Fixed the four bare `write_text()` calls identified in the audit:

1. `territories_geojson.py` line 130 — `territories.geojson` FeatureCollection write
2. `territories_geojson.py` line 246 — `condado_colors.json` sidecar write
3. `baronies_geojson.py` line 64 — `baronies.geojson` FeatureCollection write
4. `baronies_geojson.py` line 117 — `barony_colors.json` sidecar write

Each call was updated from:
```python
path.write_text(json.dumps(data))
```
to:
```python
path.write_text(
    json.dumps(data, ensure_ascii=False),
    encoding="utf-8",
)
```

This matches the established pattern in `render_modern.py:178-187`.

No `read_text()` calls required changes — all were already explicit (confirmed by audit and re-verified by automated script).

## Verification

Automated script walked all `.py` files under `backend/medieval_forge/services/`, found every `.write_text(` and `.read_text(` call, and confirmed `encoding` appears in each argument list.

Result: `OK: all write_text/read_text calls in services/ pass encoding`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary changes.

## Self-Check: PASSED

- `backend/medieval_forge/services/territories_geojson.py` — FOUND, encoding fixes confirmed at lines 130-133 and 246-249
- `backend/medieval_forge/services/baronies_geojson.py` — FOUND, encoding fixes confirmed at lines 64-67 and 117-120
- Commit `108a4d1` — FOUND
