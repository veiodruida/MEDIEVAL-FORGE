# Phase 1: Data Pipeline + Backend Scaffold - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 01-data-pipeline-backend-scaffold
**Areas discussed:** Repo & package structure, map_generator.py integration, Per-project data layout, Minimal frontend scope

---

## Repo & Package Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat monorepo | backend/ (Python package), frontend/ (Vite app), pyproject.toml at root | ✓ |
| Python-first layout | medieval_forge/ at root, frontend/ alongside | |
| src-layout | src/medieval_forge/ (Python), frontend/ alongside | |

**User's choice:** Flat monorepo
**Notes:** Clean separation, standard for FastAPI+Vite tools.

| Option | Description | Selected |
|--------|-------------|----------|
| backend/medieval_forge/static/ | Vite outDir directly into Python package, no copy step | ✓ |
| frontend/dist/ + copy step | Two-step build process | |

**User's choice:** Vite outDir → `backend/medieval_forge/static/` directly

| Option | Description | Selected |
|--------|-------------|----------|
| ~/.medieval-forge/ | DB + projects in user home dir, survives pip upgrades | ✓ |
| Current working directory | Data in ./medieval_forge_data/ | |
| XDG_DATA_HOME / platform-aware | Platform-correct paths, more complexity | |

**User's choice:** `~/.medieval-forge/` for all runtime data

---

## map_generator.py Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Copy into backend/medieval_forge/lib/ | Part of installed package, importable as medieval_forge.lib.map_generator | ✓ |
| Keep in inicio/, sys.path hack | Works locally, breaks after pip install | |
| Separate medieval-forge-core package | Over-engineered for a single file | |

**User's choice:** Copy into `backend/medieval_forge/lib/map_generator.py`
**Notes:** Verified `if __name__ == "__main__":` guard at line 941 — safely importable.

| Option | Description | Selected |
|--------|-------------|----------|
| Async function run_generation(project_id, config) | asyncio.to_thread(), returns file manifest | ✓ |
| Thin class GeneratorService | OOP wrapper | |
| Direct import at call site | No wrapper | |

**User's choice:** `async def run_generation(project_id: str, config: dict) -> dict`

---

## Per-Project Data Layout

| Option | Description | Selected |
|--------|-------------|----------|
| UUID | Collision-free, stable folder names | ✓ |
| Auto-increment integer ID | Simple but fragile on deletion | |
| Slug from project name | Human-readable but uniqueness complexity | |

**User's choice:** UUID as primary key and folder name

| Option | Description | Selected |
|--------|-------------|----------|
| Flat with named subdirs | raw/, generated/, exports/ | ✓ |
| Single flat dir | All files at project root | |
| Versioned snapshots | generated/v1/, v2/ etc. | |

**User's choice:** `raw/` + `generated/` + `exports/` subdirectories under `~/.medieval-forge/projects/{uuid}/`

---

## Minimal Frontend Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Functional project manager | Working SPA with project CRUD, trigger buttons, SSE log panel, PNG previews | ✓ |
| Bare API shell | Dev playground, no real UI | |
| Full app shell ready for Phase 2 | Nav + sidebar skeleton | |

**User's choice:** Functional project manager — routes: `/projects`, `/projects/new`, `/projects/:id`

| Option | Description | Selected |
|--------|-------------|----------|
| Inline log panel | Scrollable text area appending SSE messages | ✓ |
| Progress bar + status text | Requires percentage in SSE events | |
| Toast notifications only | Loses history when dismissed | |

**User's choice:** Inline scrollable log panel for SSE progress display

| Option | Description | Selected |
|--------|-------------|----------|
| Only Phase 1 routes | /projects, /projects/new, /projects/:id | ✓ |
| Full route skeleton now | All routes defined upfront with placeholders | |

**User's choice:** Only Phase 1 routes — later phases add their own

---

## Claude's Discretion

- Tailwind component styling and color choices
- SQLAlchemy model column naming conventions
- FastAPI router file organization
- Error response schema format
- Wikidata SPARQL query structure (within pagination constraint)
- OSM Overpass query format

## Deferred Ideas

None — discussion stayed within Phase 1 scope.
