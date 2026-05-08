---
status: partial
phase: 01-pipeline-parity-port-harness-together
source: [01-VERIFICATION.md]
started: 2026-05-08T11:05:00Z
updated: 2026-05-08T11:05:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. CI gate end-to-end test (ROADMAP SC-3)

expected: Push a PR that deliberately breaks parity (e.g. change `np.random.default_rng(cfg.rng_seed)` to `default_rng(43)` in render.py). GitHub blocks merge with red status check on `pytest-parity`. Note: will currently FAIL on CR-01 (LFS pointer parse error) — fix CR-01 first.
result: [pending]

### 2. Visual inspection of refreshed golden

expected: Open `tests/fixtures/iberia_868/golden/visual_condado.png` and `visual_barony.png`. Maps look coherent — kingdom colors match (Astúrias gold / Pamplona purple / Marca Hispânica pink / Emirato green); condado borders visible; mountain shading present; no obvious rendering glitches. Confirm Aveiro disappearance acceptable as v3-reset cost.
result: [pending]

### 3. Reconquista Unity re-bake

expected: Re-bake `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` from v3 pipeline. Unity boots; 91-condado map renders; no `byOriginalIdx` exceptions. Aveiro confirmed-removed or re-added with new D-09 waiver.
result: [pending]

### 4. CR-01 decision (CI lfs: true missing)

expected: Single-line ci.yml fix via `/gsd-code-review-fix 01`, OR accept as known-broken with rationale.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
