# v1 Deletion Candidates — Phase 00 Review

> **Policy (D-V3-04, applied conservatively):** delete obsolete v1 code rather than namespace it.
> But Phase 00 does NOT delete — it lists candidates for human review. Phase 02 (ingest adapter)
> and Phase 07 (LLM opt-in) reuse a lot of v1 services; deleting now risks breaking planned reuse.
>
> **Action required:** review this list with the user before Phase 03 (canvas redesign). Deletions
> happen as part of the phase that replaces the obsolete code, not Phase 00.

## Confirmed candidates (DELETE in Phase 03 or later)

| Path | Lines | Reason | Replaced by | Phase |
|------|-------|--------|-------------|-------|
| `frontend/src/pages/ProjectDetail.tsx` | 697 | v1 stepper UI; v3 uses single-canvas Figma-style workspace | New `frontend/src/v3/pages/ProjectWorkspace.tsx` | Phase 03 |
| `frontend/src/components/pipeline/Stepper.tsx` | ~? | Stepper component — only used by ProjectDetail | (nothing — no stepper in v3) | Phase 03 |
| `frontend/src/components/pipeline/StepCard.tsx` | ~? | Stepper card component | (nothing — no stepper in v3) | Phase 03 |
| `frontend/src/stores/usePipelineStore.ts` | ~? | Stepper state | (nothing — pipeline state lives in v3 ParameterPanel) | Phase 04 |

## Possible candidates (REVIEW before deletion)

| Path | Used by | Decision |
|------|---------|----------|
| `backend/medieval_forge/services/codex_runner.py` | `backend/medieval_forge/api/codex.py` (router); `backend/medieval_forge/main.py` (registers router); `models.py` (CodexCache uses produced payload); 5 test files (`test_codex_runner.py`, `test_codex_endpoints.py`, `test_codex_prompt.py`) | Tightly coupled to LLM-mandatory v1 pipeline. Delete in **Phase 07** when LLM moves to opt-in sidecar; tests + endpoints + cache table all go together. |
| `backend/medieval_forge/services/territory_builder.py` | v1 territories.geojson generator | Keep until Phase 02.2 v3 (geometry-first) ports the logic; then delete. |
| `backend/medieval_forge/services/territories_geojson.py` | v1 frontend adapter | Keep until Phase 02 wraps it in `pipeline/adapters/`; then maybe delete. |
| `backend/medieval_forge/lib/map_generator.py` (if exists) | v1 wrapper around `inicio/map_generator.py` | DO NOT DELETE — Phase 01 ports this to `services/pipeline/`. Phase 01 may delete the v1 wrapper after parity is proven. |

## DO NOT delete (reused by v3)

| Path | Why reused | Phase that uses it |
|------|------------|---------------------|
| `backend/medieval_forge/services/ingest_wikidata.py` | Wikidata SPARQL ingestion | Phase 02 (wraps it in adapter) |
| `backend/medieval_forge/services/ingest_osm.py` | OSM Overpass ingestion | Phase 02 |
| `backend/medieval_forge/services/overpass_client.py` | Shared 3-mirror Overpass client | Phase 02 |
| `backend/medieval_forge/services/ingest_terrain/` | DEM + ridges + HydroSHEDS pipeline | Phase 02 |
| `backend/medieval_forge/services/llm/` | Multi-provider LLM adapter (Claude/OpenAI/Gemini/Ollama/llamacpp/manual) | Phase 07 (opt-in) |
| `backend/medieval_forge/services/research_runner.py` | LLM research orchestration | Phase 07 (opt-in) |
| `backend/medieval_forge/services/research_cache.py` | SQLite cache for research | Phase 07 (opt-in) |
| `backend/medieval_forge/services/credential_store.py` | In-memory credential store | Phase 07 (opt-in) |
| `frontend/src/components/research/` | Research UI dialogs | Phase 07 (opt-in, moved to `v3/`) |
| `backend/medieval_forge/db.py` + `models.py` + `auth/` | Project CRUD foundation | All v3 phases |

## Greps captured during this Phase 00 task (for the record)

### codex_runner usage (`grep -rn "codex_runner\|from.*codex" backend/`)
```
backend/medieval_forge/api/codex.py:22:from ..services.codex_cache import compute_codex_cache_key, get_codex_cached
backend/medieval_forge/api/codex.py:23:from ..services.codex_runner import run_codex
backend/medieval_forge/api/codex.py:26:from ..services.llm.prompt import build_codex_prompt
backend/medieval_forge/api/codex.py:71:    Streams 'data: ...\n\n' events from run_codex, ending with 'data: DONE\n\n'.
backend/medieval_forge/main.py:54:from .api.codex import router as codex_router  # noqa: E402
backend/medieval_forge/models.py:87:    Holds the 12-category narrative payload produced by codex_runner.run_codex.
backend/medieval_forge/services/codex_runner.py:27:from .codex_cache import compute_codex_cache_key, get_codex_cached, set_codex_cached
backend/medieval_forge/services/codex_runner.py:31:from .llm.prompt import build_codex_prompt
backend/tests/api/test_codex_endpoints.py:159:    from medieval_forge.services.codex_cache import compute_codex_cache_key, set_codex_cached
backend/tests/services/test_codex_prompt.py:18,36,64:    from medieval_forge.services.llm.prompt import build_codex_prompt
backend/tests/services/test_codex_runner.py:1,90,117,137,140,168,186,190,224,242,245,262,285: codex_runner imports + run_codex calls
```

### ProjectDetail references (`grep -rn "ProjectDetail" frontend/src/`)
```
frontend/src/App.tsx:4:import { ProjectDetail } from './pages/ProjectDetail'
frontend/src/App.tsx:18:            <ProjectDetail />
frontend/src/components/ErrorBoundary.tsx:17: * Wraps ProjectDetail so a runtime throw inside the canvas subtree shows a
frontend/src/hooks/useCanvasArtifacts.ts:231:  // working (CanvasViewer.tsx, ProjectDetail.tsx). Use `as const` on the
frontend/src/pages/ProjectDetail.tsx:54:export function ProjectDetail()
frontend/src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx:10-26: ErrorBoundary shape tests
```

### Stepper / StepCard / usePipelineStore (`grep -rn "Stepper\|StepCard\|usePipelineStore" frontend/src/`)
```
frontend/src/components/pipeline/ProviderEffortPicker.tsx:3:import type { Effort } from '../../stores/usePipelineStore'
frontend/src/components/pipeline/StepCard.test.tsx (entire file uses StepCard)
frontend/src/components/pipeline/StepCard.tsx (StepCardProps interface + StepCard component)
frontend/src/components/pipeline/Stepper.test.tsx (test file)
frontend/src/components/pipeline/Stepper.tsx (Stepper component imports StepId/StepStatus from usePipelineStore)
```

### v3-reusable services (existence check)
```
backend/medieval_forge/services/ingest_osm.py             present
backend/medieval_forge/services/ingest_wikidata.py        present
backend/medieval_forge/services/overpass_client.py        present
backend/medieval_forge/services/llm/                      __init__.py, auth.py, base.py, claude.py, gemini.py, llamacpp.py, manual.py, model_routing.py, ollama.py
backend/medieval_forge/services/research_cache.py         present
backend/medieval_forge/services/research_runner.py        present
```

All Phase 02 / Phase 07 reuse targets exist on disk. Conservative deletion policy is justified.
