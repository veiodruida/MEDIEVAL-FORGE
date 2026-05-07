# Backlog — v3.1 (deferred, not discarded)

Items captured during v3 planning that are deliberately deferred to v3.1 to keep the v3 milestone shippable. Promote with `/gsd-review-backlog` when v3 is in maintenance mode.

| # | Item | Why deferred | Source |
|---|------|--------------|--------|
| 1 | Full historical research database for France 1066 / England 1216 | Phase 05 ships geometry only; historical data is a research project, not a coding task | Plano master, Phase 05 DoD |
| 2 | Evaluate Kuwahara filter as alternative to Gaussian-per-mask smoothing | "Smooth Kurzweil" investigation; current Gaussian σ ∈ [3.0, 4.5] is good enough for v3 | Plano master, Context |
| 3 | Compound undo cross-stage (Ctrl+Z for parameter studio) | Inherited gap from v1 Phase 4; needs DAG version-token design first (Phase 04 builds the foundation but does not implement undo) | Plano master, Phase 04 risks |
| 4 | Vector border editor (drag points to manually refine borders) | Out of scope for v3; pipeline is geometry-driven, manual edits would compete with re-runs | Plano master, Bloco 6 |
| 5 | Heightmap import (SRTM) for mountain paint-brush | Phase 5 v1 was advanced canvas editing; v3 paint stays on terrain types only, no heightmap | Plano master, Bloco 6 |
| 6 | Multi-language UI (currently PT-BR) | Single-user local tool; i18n is premature optimization | Plano master, Bloco 6 |
