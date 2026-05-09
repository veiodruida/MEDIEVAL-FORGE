---
status: partial
phase: 01-pipeline-parity-port-harness-together
source: [01-VERIFICATION.md]
started: 2026-05-08T11:05:00Z
updated: 2026-05-09T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. CI gate end-to-end test (ROADMAP SC-3)

expected: Push a PR that deliberately breaks parity (e.g. change `np.random.default_rng(cfg.rng_seed)` to `default_rng(43)` in render.py). GitHub blocks merge with red status check on `pytest-parity`. CR-01 LFS blocker fixed in e7a1f8c — this test is now executable.
result: pass — CI gate infrastructure verified 2026-05-09 by Claude (user-approved). `.github/workflows/ci.yml:32-48` has `pytest-parity` job with `lfs: true` (commit e7a1f8c) running `pytest backend/tests/parity/ ... -m "parity or integration"`. Baseline 10/10 PASSED in 35.69s. NOTE: the specific seed-mutation example in the expected text does NOT actually break parity — `render.py:57` rng feeds visual color jitter only (lookup PNGs are deterministic by territory id; visual SSIM ≥0.98 tolerates jitter). UAT premise is weak; gate itself is real and would fire on byte-equal-breaking mutations (geometry, color, NEAREST→BICUBIC). Recommend revising UAT example in Phase 02.1 backlog or treat as known limitation.

### 2. Visual inspection of refreshed golden

expected: Open `tests/fixtures/iberia_868/golden/visual_condado.png` and `visual_barony.png`. Maps look coherent — kingdom colors match (Astúrias gold / Pamplona purple / Marca Hispânica pink / Emirato green); condado borders visible; mountain shading present; no obvious rendering glitches. Confirm Aveiro disappearance acceptable as v3-reset cost.
result: passed — user approved 2026-05-08 after inline inspection: 4 kingdom colors correct, mountain/river overlays present, Aveiro removal accepted as v3-reset cost.

### 3. Reconquista Unity re-bake

expected: Re-bake `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` from v3 pipeline. Unity boots; 91-condado map renders; no `byOriginalIdx` exceptions. Aveiro confirmed-removed or re-added with new D-09 waiver.
result: blocked
blocked_by: physical-device
reason: "Requires Unity Editor + Reconquista project at D:\\Projetos_Jogo\\Reconquista. Manual human action — not automatable. Deferred until user runs re-bake locally."

### 4. CR-01 decision (CI lfs: true missing)

expected: Single-line ci.yml fix via `/gsd-code-review-fix 01`, OR accept as known-broken with rationale.
result: resolved — `/gsd-code-review-fix 01` applied (commit e7a1f8c). Also fixed WR-01/02/03.

## Summary

total: 4
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps
