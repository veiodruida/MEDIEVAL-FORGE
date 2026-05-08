---
status: partial
phase: 01-pipeline-parity-port-harness-together
source: [01-VERIFICATION.md]
started: 2026-05-08T11:05:00Z
updated: 2026-05-08T12:30:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. CI gate end-to-end test (ROADMAP SC-3)

expected: Push a PR that deliberately breaks parity (e.g. change `np.random.default_rng(cfg.rng_seed)` to `default_rng(43)` in render.py). GitHub blocks merge with red status check on `pytest-parity`. CR-01 LFS blocker fixed in e7a1f8c — this test is now executable.
result: [pending]

### 2. Visual inspection of refreshed golden

expected: Open `tests/fixtures/iberia_868/golden/visual_condado.png` and `visual_barony.png`. Maps look coherent — kingdom colors match (Astúrias gold / Pamplona purple / Marca Hispânica pink / Emirato green); condado borders visible; mountain shading present; no obvious rendering glitches. Confirm Aveiro disappearance acceptable as v3-reset cost.
result: passed — user approved 2026-05-08 after inline inspection: 4 kingdom colors correct, mountain/river overlays present, Aveiro removal accepted as v3-reset cost.

### 3. Reconquista Unity re-bake

expected: Re-bake `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` from v3 pipeline. Unity boots; 91-condado map renders; no `byOriginalIdx` exceptions. Aveiro confirmed-removed or re-added with new D-09 waiver.
result: [pending]

### 4. CR-01 decision (CI lfs: true missing)

expected: Single-line ci.yml fix via `/gsd-code-review-fix 01`, OR accept as known-broken with rationale.
result: resolved — `/gsd-code-review-fix 01` applied (commit e7a1f8c). Also fixed WR-01/02/03.

## Summary

total: 4
passed: 2
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
