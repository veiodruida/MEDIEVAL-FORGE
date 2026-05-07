<!-- GSD:project-start source:PROJECT.md -->
## Project

**Medieval Forge — Milestone v3 ("Reset to Roots")**

Medieval Forge is a local web tool for Game Designers that automates the creation of historically-accurate medieval maps for strategy games. The v3 milestone resets the project to focus on faithfully reproducing the canonical 15-stage pipeline documented in `inicio/map_generator.py` (620 lines, fruit of 25 chat iterations) which produced the maps currently shipping in the Reconquista game.

**Core Value:** A Game Designer goes from "country + historical period" to a validated, Unity-ready map package without manual pixel editing — driven by geometry, with LLM as opt-in metadata layer (never required).

### Constraints

- **Tech Stack**: Python 3.11+ / FastAPI / SQLite (backend); React 19 + TypeScript + Vite 6 + Konva.js (frontend)
- **State**: Zustand v5 + zundo 2.3.0 `temporal` middleware; TanStack Query v5
- **Styling**: Tailwind CSS v4 (`@tailwindcss/vite`) + Radix UI Themes 3.x
- **Packaging**: pip-installable Python package; `medieval-forge start` CLI
- **Geometry**: scipy Voronoi + Shapely for boolean ops; GeoJSON storage
- **LLM**: opt-in only — pipeline runs end-to-end with zero LLM calls

> Full historical stack research (versions, gotchas, peer-dep analysis) is preserved in
> `.planning/v1-archive/STACK_RESEARCH.md` and is **not** required for daily v3 work.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## v3 Pipeline Contract

The v3 pipeline produces a **12-file Unity export** that must match the Reconquista game's
`Assets/StreamingAssets/Maps/` artifacts byte-for-byte (lookup PNGs) or SSIM ≥ 0.98 (visual PNGs).

**Output contract (12 files):**

| # | File | Resolution | Purpose |
|---|------|-----------|---------|
| 1 | `lookup_barony.png` | 1920×1080 | hit detection (barony) |
| 2 | `lookup_condado.png` | 1920×1080 | hit detection (condado) |
| 3 | `lookup_barony_colors.json` | — | RGB → barony id |
| 4 | `lookup_condado_colors.json` | — | RGB → condado id |
| 5 | `terrain_lookup.png` | 1920×1080 | terrain type per pixel |
| 6 | `terrain_types.json` | — | RGB → `{movement, defense, attack}` |
| 7 | `territory_metadata.json` | — | full hierarchy with `original_idx` |
| 8 | `visual_condado.png` | 3840×2160 | visual placeholder (condado) |
| 9 | `visual_barony.png` | 3840×2160 | visual placeholder (barony) |
| 10 | `mountains_mask.png` | 3840×2160 | white = impassable |
| 11 | `rivers_overlay.png` | 3840×2160 | transparent PNG overlay |
| 12 | `mountain_river_data.json` | — | geo coordinates of mountains/rivers |

**Canonical references (read-only, gold standard):**
- [inicio/map_generator.py](inicio/map_generator.py) — 620-line reference pipeline
- [inicio/licoes/JORNADA_CRIACAO_MAPA.md](inicio/licoes/JORNADA_CRIACAO_MAPA.md) — every decision and bug, documented
- [inicio/territory_data_v3.py](inicio/territory_data_v3.py) — curated territory data for Iberia 868
- `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\*` — ground truth for parity tests

**Non-negotiable rules (lessons paid for in hours of debugging):**

1. **NEAREST upscale only** — never BICUBIC/BILINEAR for lookup PNGs. BICUBIC spreads border colors and breaks Unity's `byOriginalIdx` shader.
2. **σ ∈ [3.0, 4.5]** for the per-territory Gaussian blur in the smoothing stage. Outside this range either fragments territories (too low) or merges unrelated ones (too high).
3. **KD-trees per country** — never a single global KD-tree across PT/ES boundary. Each country gets its own tree built from its own baronies; the PT/ES border polygon (38 points) routes municipalities to the correct tree.
4. **`original_idx` in every territory** — the metadata JSON must include `original_idx` for every condado/barony so Unity's `byOriginalIdx` lookup never throws on indices > 44 (Nájera bug).
5. **`ocean=-1` and `ignore=9999` in the median pass** — these sentinel values are part of the contract; the median filter must skip them, not blur them.
6. **2x masks are independent renders** — `mountains_mask.png` and `rivers_overlay.png` at 3840×2160 are rendered fresh, NOT upscaled from the 1x lookup. Upscaling masks introduces fractional pixels at boundaries that look wrong on the final map.
7. **`byOriginalIdx` on the Unity side** — the game uses `original_idx` as the canonical key; pipeline must guarantee its uniqueness and stability across re-runs.

> The `RegionConfig` pydantic model is the **only** mutable input to the pipeline. Anything else (boundary polygons, terrain rules, render constants) lives as data files under `data/regions/<region>.yaml`.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

- **Module layout** — `backend/medieval_forge/services/pipeline/` houses individually-callable submodules: `config.py`, `landmask.py`, `border.py`, `voronoi.py`, `cleanup.py`, `render.py`, `lookup.py`, `export.py`, `contracts.py`, plus `adapters/` for ingestion translation.
- **Single mutable input** — the only thing the user/UI changes is a `RegionConfig` pydantic instance. No `importlib.reload`, no `sys.modules` patching, no global state.
- **No LLM in the geometric path** — `RESEARCH-*` features populate a sidecar `research_overlay.json` that the export merges if present. The pipeline must produce a valid 12-file export with zero LLM calls.
- **Atomic commits per task** — each `/gsd-execute-phase` task produces ≤1 commit; messages follow `type(phase-plan): subject` convention used in v1 history.
- **Three-layer test pyramid** — every phase delivers (1) `tests/unit/` pytest + vitest, (2) `tests/parity/` non-skippable parity vs. Reconquista (≥85% backend / ≥80% frontend coverage in `v3/`), (3) `tests/uat/playwright/` Playwright UAT scenario for any UI surface.
- **Determinism** — `np.random.default_rng(42)` is locked in `RegionConfig`. Seed changes break parity tests.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

The v3 pipeline is a **directed acyclic graph** of 11 stages, each with a `version_token` so Phase 04 (parameter studio) can re-run only downstream stages on slider change:

```
land mask → border → barony assign (Voronoi+KD-tree per country)
         → median cleanup (8 passes: 11,11,9,9,7,7,5,5)
         → smooth (per-mask Gaussian σ ∈ [3.0, 4.5], winner-takes-all)
         → merge (<200px blob removal)
         → hierarchy (barony → condado → duchy → kingdom via constrained clustering)
         → render (paint + tier borders + 2x mask independent + NEAREST upscale + coast outline)
         → lookup (RGB hash deterministic)
         → metadata (territory_metadata.json with original_idx)
         → export (12-file Unity ZIP + manifest)
```

**Data flow:**
- Input: `ProjectDataset` contract (PT-equivalent GeoJSON, ES-equivalent GeoJSON/TopoJSON, optional mountain/river JSON, optional DEM raster)
- Stage caching: in-memory arrays per project, keyed by `(project_id, stage_name, version_token)`
- Output: 12-file ZIP matching the Unity contract above
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

- [karpathy-guidelines](.claude/skills/karpathy/SKILL.md) — Behavioral guidelines to reduce common LLM coding mistakes (think before coding, simplicity first, surgical changes, verifiable success). Auto-discovered from `.claude/skills/karpathy/`.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

## What v3 explicitly is NOT

These are **rejected designs** — if a future plan suggests any of them, push back:

- **No LLM-mandatory pipeline.** The v1.0 Phase 3 LLM dependency is gone; LLM is opt-in metadata only.
- **No stepper UI.** The 697-line `frontend/src/pages/ProjectDetail.tsx` stepper is being replaced (Phase 03) with a single-canvas Figma/Mapbox-style workspace.
- **No `sys.modules` patching.** `RegionConfig` is the only mutable input; no `importlib.reload` games.
- **No upscale interpolation.** Lookup PNGs use `Image.NEAREST`, never `BICUBIC` / `BILINEAR`.
- **No global Voronoi.** KD-trees are always per-country; the PT/ES border is data, not assumption.
- **No hand-rolled compound undo.** zundo `temporal` with `partialize` + `diff` is the contract; alternatives need a written justification.

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
