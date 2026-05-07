# Project: Medieval Forge — v3

## Name
Medieval Forge

## Vision
A local web tool for Game Designers that automates the creation of historically-accurate medieval maps for strategy games, faithfully reproducing the canonical 15-stage pipeline documented in `inicio/map_generator.py` and shipping a 12-file Unity export package per project.

## Value Proposition
A Game Designer goes from "country + historical period" to a validated, Unity-ready map package — driven entirely by geometry — without manual pixel editing or blind LLM iteration. LLM research is opt-in metadata only; the pipeline runs end-to-end with zero API calls.

## Constraints
- Python 3.11+ / FastAPI / SQLite (backend), React 19 + Vite 6 + Konva (frontend)
- pip-installable; single `medieval-forge start` CLI
- 12-file Unity export contract (see CLAUDE.md > v3 Pipeline Contract)
- Pixel parity with `D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/` for lookup PNGs; SSIM ≥ 0.98 for visual PNGs
- Determinism: `np.random.default_rng(42)` locked in `RegionConfig`

## Out of Scope (v3)
- Multi-language UI (PT-BR only for now)
- Vector border editor with manual point drag
- Heightmap import (SRTM) for paint-brush mountains
- Compound cross-stage undo for parameter studio (deferred from v1 Phase 4)
- Full historical research database for non-Iberian regions (Phase 05 ships geometry only; data deferred to v3.1)
- Kuwahara filter alternative to Gaussian-per-mask smoothing

## Key Decisions
| ID | Decision | Source |
|----|----------|--------|
| D-V3-01 | Archive v1.0 entirely; restart milestone v3 from roots | AskUserQuestion 2026-05-07 |
| D-V3-02 | Ignore the off-PC v2 attempt; do not reconcile | AskUserQuestion 2026-05-07 |
| D-V3-03 | Move `Skill/SKILL-karpathy.md` → `.claude/skills/karpathy/SKILL.md` (auto-discovery) | AskUserQuestion 2026-05-07 |
| D-V3-04 | Delete obsolete v1 routes/stores rather than namespace them | Karpathy #2/#3 — dead code is regression risk |
| D-V3-05 | Treat `inicio/map_generator.py` as gold-standard reference; `RegionConfig` is the only mutable input | Plano master |
| D-V3-06 | "Smooth Kurzweil" term resolved to Gaussian-blur-per-territory + winner-takes-all (σ ∈ [3.0, 4.5]) | `inicio/map_generator.py:469-483` |
| D-V3-07 | LLM research becomes opt-in sidecar (`research_overlay.json`); zero LLM in geometric path | Phase 07 contract |
