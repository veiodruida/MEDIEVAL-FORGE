# Phase 01: Pipeline parity (port + harness together) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 01-pipeline-parity-port-harness-together
**Areas discussed:** Port strategy, V1 code disposition, Parity fixtures, Territory data loading

---

## Port strategy

### Q1 — Port mode

| Option | Description | Selected |
|--------|-------------|----------|
| Verbatim first, refactor later | Submodules mirror inicio function names + signatures + bodies. Line-by-line audit possible. Refactor after parity green. | ✓ |
| Refactor as we port | Pipeline/Stage classes, pydantic RegionConfig, typed intermediates introduced during port. Parity bug attribution becomes hard. | |
| Verbatim port + thin pydantic RegionConfig only | Functions verbatim; only RegionConfig upgraded. Middle ground. | |

**User's choice:** Verbatim first, refactor later (recommended).
**Notes:** Phase 01's whole point is parity; mixing port + refactor blurs failure attribution.

### Q2 — Stage / version_token DAG abstraction

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to Phase 04 | Plain functions returning numpy arrays. Phase 04 wraps in Stage objects with version_token + cache. | ✓ |
| Build minimal Stage interface now | Stage(name, version_token, run(inputs)→outputs). No cache. Pre-builds DAG. | |
| Build full DAG with cache hooks now | Stage + version_token + (project_id, stage, version_token) cache + in-memory cache wired now. | |

**User's choice:** Defer to Phase 04 (recommended).
**Notes:** Karpathy — don't build infra for hypothetical use. Phase 04 owns the DAG when sliders need it.

### Q3 — Orchestrator location

| Option | Description | Selected |
|--------|-------------|----------|
| pipeline/__init__.py exports run_pipeline() | Single import surface mirrors inicio's generate_maps(). Submodules are implementation detail. | ✓ |
| pipeline/run.py with explicit Pipeline class | Pipeline(cfg).run(); stage list lives in run.py. Mount point for hooks. | |
| pipeline/__main__.py only — no library API | CLI-only, library use via subprocess. Wrong for Phase 03/04 in-process needs. | |

**User's choice:** pipeline/__init__.py exports run_pipeline() (recommended).

### Q4 — CLI region resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-coded registry: REGIONS = {"iberia_868": iberia_config} | Dict of name → factory. Phase 05 swaps for YAML. | ✓ |
| Already YAML: data/regions/iberia_868.yaml | Pre-build Phase 05's structure. Risk: parity could drift via YAML transform. | |
| argparse direct args (--lon-min, --lon-max, ...) | User passes 30+ RegionConfig fields. Useless. | |

**User's choice:** Hard-coded registry (recommended).
**Notes:** Phase 05 is the right home for YAML; Phase 01 only ships iberia_868 and parity needs the exact inicio config.

---

## V1 code disposition

### Q1 — v1 generator stack disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Clean delete in Phase 01 | Delete lib/map_generator.py, services/generator.py, api/generate.py + reachable v1 code. UI 404s acceptable per V1_DELETION_CANDIDATES.md. | ✓ |
| Keep v1 alive in parallel until Phase 03 | v3 pipeline/ next to v1 services/generator.py. Two sources of truth. | |
| Replace v1 internals (route /api/generate to v3) | Stepper UI accidentally drives v3 pipeline; mismatch in stage assumptions. | |

**User's choice:** Clean delete in Phase 01 (recommended).
**Notes:** Aligns D-V3-04 + Karpathy. services/generator.py uses banned sys.modules patching anyway.

### Q2 — v1 test files

| Option | Description | Selected |
|--------|-------------|----------|
| Delete tests for deleted code | Tests die with production code. New tests/parity/test_iberia_868.py replaces them. | ✓ |
| Keep all tests, mark @pytest.mark.skip | Skipped tests as v1 documentation. Karpathy red flag (zombie skip). | |
| Delete tests, archive under .planning/v1-archive/tests/ | Snapshot for forensic reference. | |

**User's choice:** Delete tests for deleted code (recommended).

### Q3 — Frontend after /api/generate deletion

| Option | Description | Selected |
|--------|-------------|----------|
| Leave frontend untouched, accept broken UI until Phase 03 | Phase 01 is backend parity; Phase 03 owns frontend rewrite. UI 404s contained. | ✓ |
| Phase 01 also deletes ProjectDetail.tsx + Stepper + usePipelineStore | Brings Phase 03 deletes forward. Scope creep. | |
| Phase 01 stubs the stepper UI with a 'v3 coming' placeholder | Throw-away artifact. | |

**User's choice:** Leave frontend untouched (recommended).

### Q4 — Other v1 stepper-adjacent backend files

| Option | Description | Selected |
|--------|-------------|----------|
| Delete only what services/generator.py and api/generate.py import | Surgical, import-graph-driven. Planning task #1 traces graph. | ✓ |
| Delete every v1 file flagged in V1_DELETION_CANDIDATES.md confirmed list | One sweep, bigger blast radius. | |
| Defer to Phase 03 sweep | Only delete what Phase 01 actively breaks. Most conservative, more dead code. | |

**User's choice:** Delete only what services/generator.py and api/generate.py import (recommended).

---

## Parity fixtures

### Q1 — Source of truth

| Option | Description | Selected |
|--------|-------------|----------|
| Reconquista's deployed files | tests/fixtures/iberia_868/ contains snapshot from D:/Projetos_Jogo/Reconquista/.... Unity-readable contract wins over algorithm reference. | ✓ |
| Fresh inicio/map_generator.py output | Run inicio at fixture-creation time. Risk: if Reconquista files were tweaked or come from older inicio, parity won't match game. | |
| Both — dual-baseline test | Fail if either diverges. Forces inicio + Reconquista in sync; brittle if they already differ. | |

**User's choice:** Reconquista's deployed files (recommended).

### Q2 — Fixture location

| Option | Description | Selected |
|--------|-------------|----------|
| Commit into tests/fixtures/iberia_868/ in-repo | One-time ~3-10MB commit. CI portable. Updates explicit in PR review. | ✓ |
| Re-run inicio/map_generator.py at test setup | Slow (1-2 min); inicio Linux-font deps risky on CI. | |
| git LFS / DVC | Avoids history bloat; LFS bandwidth + CI setup overhead. Overkill for one snapshot. | |
| Hardcoded D:/Projetos_Jogo/Reconquista/... path | Breaks Linux/macOS CI immediately. | |

**User's choice:** Commit into tests/fixtures/iberia_868/ in-repo (recommended).

### Q3 — Pipeline inputs location

| Option | Description | Selected |
|--------|-------------|----------|
| Commit into data/regions/iberia_868/inputs/ alongside fixtures | Fully self-contained: clone, install, pytest. ~7-12MB total inputs. | ✓ |
| Symlink/copy from inicio at conftest time | Smaller repo; breaks CI without source paths. | |
| Download from a release asset / external URL | Network dependency in CI; slower. | |

**User's choice:** Commit into data/regions/iberia_868/inputs/ (recommended).

### Q4 — Comparison rules

| Option | Description | Selected |
|--------|-------------|----------|
| Pixel-perfect lookup PNGs + SSIM ≥0.98 visual + JSON deep-equal | Exactly the ROADMAP success criterion. numpy.array_equal + skimage.SSIM + sorted-key JSON. | ✓ |
| Hash-based: sha256 every output | Fast, no skimage dep. Too strict for visual PNGs (font rendering, libpng version). | |
| Tolerance bands per file type via tests/parity/tolerances.yaml | Most flexible, more code; useful for Phase 06+. | |

**User's choice:** Pixel-perfect + SSIM ≥0.98 + JSON deep-equal (recommended).

---

## Territory data loading

### Q1 — Loader strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Static Python import from in-repo module | Move inicio/territory_data_v3.py → backend/medieval_forge/data/regions/iberia_868/territory_data.py. No reload. Phase 05 converts to YAML. | ✓ |
| Convert to YAML now (Phase 05 forward-loading) | data/regions/iberia_868/territories.yaml + pydantic schemas. Risk: tuple↔struct conversion = parity drift surface. | |
| Keep at module-load level, no reload | Just delete the importlib.reload line. Quickest. Risk: hidden PYTHONPATH dependency. | |

**User's choice:** Static Python import from in-repo module (recommended).

### Q2 — Storage on RegionConfig

| Option | Description | Selected |
|--------|-------------|----------|
| RegionConfig fields: kingdoms, duchies, condados | cfg.kingdoms/duchies/condados. setup_baronies(cfg). Single arg. Reinforces D-V3-05. | ✓ |
| Separate ProjectDataset contract (forward-load Phase 02) | Splits config (sliders) from data (geographic facts). More types upfront. | |
| Loaded inside generate_maps(), not stored on RegionConfig | RegionConfig only holds paths. Phase 04 reload semantics awkward. | |

**User's choice:** RegionConfig fields directly (recommended).

---

## Claude's Discretion

The user explicitly deferred these to Claude (planning/implementation):

- RegionConfig as `@dataclass` (mirror inicio) vs pydantic `BaseModel`
- Exact submodule split inside `cleanup.py` (4 sub-stages: median + fragment + smooth + merge)
- Final repo path for territory data module (backend/medieval_forge/data/... vs repo-root data/...)
- conftest.py fixture wiring (session-scoped vs function-scoped, tmp_path layout)
- Whether `tests/parity/test_iberia_868.py` is one fat test or 12 narrow tests sharing a session fixture
- CI parity-gate flip mechanics (which task in the phase makes it non-skippable)

## Deferred Ideas

(Captured for post-Phase-01 / future phases — see CONTEXT.md `<deferred>` section.)

- Stage abstraction with `version_token` + in-memory stage cache → Phase 04
- Region YAML loader + Pydantic territory schemas → Phase 05
- Per-file tolerance YAML for parity → Phase 06
- Frontend stepper UI cleanup → Phase 03
- Mid-port refactor of cleanup.py sub-stages → Claude's discretion later
- RegionConfig dataclass → pydantic migration → Claude's discretion during planning
- CI parity baseline-refresh tooling → manual rsync in README for now
- inicio sync watchdog (automated drift check) → Phase 06 lint job candidate
