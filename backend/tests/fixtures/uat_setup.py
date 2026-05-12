"""UAT bootstrap helper for the Plan 03-08 Playwright spec.

Standalone CLI used by `frontend/playwright.config.ts` globalSetup. Runs
the iberia_868 pipeline once (cached on disk so subsequent invocations
are instant), creates a Project row in the SQLite database used by the
backend, then copies the 14 ARTIFACT_FILES into that project's
``output/`` directory via :func:`seed_phase01_artifacts`.

Caches the pipeline output under
``~/.medieval-forge/uat_cache/iberia_868/`` so re-running the suite does
not re-pay the ~45 s pipeline cost. Cache is keyed only by the presence
of all 14 ARTIFACT_FILES; if any are missing the directory is wiped and
regenerated.

Prints a single JSON line to stdout on success::

    {"project_id": "...", "name": "...", "country_qid": "...",
     "period_start": 868, "period_end": 868}

Errors go to stderr; exit code 1 on any failure.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import uuid
from pathlib import Path

# Ensure backend/ is on sys.path so this script works when invoked from any cwd.
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from medieval_forge.api.v3.artifacts import ARTIFACT_FILES  # noqa: E402
from medieval_forge.database import DATA_DIR, engine  # noqa: E402
from medieval_forge.models import Base, Project  # noqa: E402
from dataclasses import replace  # noqa: E402

from medieval_forge.services.pipeline import run_pipeline  # noqa: E402
from medieval_forge.services.pipeline.region_loader import load_region  # noqa: E402

from tests.fixtures.seed_phase01_artifacts import seed_phase01_artifacts  # noqa: E402

# Cache lives outside the repo to avoid polluting the fixture tree.
UAT_CACHE_DIR: Path = DATA_DIR / "uat_cache" / "iberia_868"


def _has_full_artifact_set(d: Path) -> bool:
    if not d.is_dir():
        return False
    return all((d / name).is_file() for name in ARTIFACT_FILES)


def _ensure_pipeline_output() -> Path:
    """Generate the 14-file artifact set into UAT_CACHE_DIR; idempotent."""
    if _has_full_artifact_set(UAT_CACHE_DIR):
        return UAT_CACHE_DIR

    if UAT_CACHE_DIR.exists():
        shutil.rmtree(UAT_CACHE_DIR)
    UAT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cfg = replace(load_region("iberia_868"), output_dir=str(UAT_CACHE_DIR))
    run_pipeline(cfg)

    if not _has_full_artifact_set(UAT_CACHE_DIR):
        missing = [n for n in ARTIFACT_FILES if not (UAT_CACHE_DIR / n).is_file()]
        raise RuntimeError(
            f"pipeline did not emit the full 14-file set; missing: {missing}"
        )
    return UAT_CACHE_DIR


async def _create_project_row() -> Project:
    """Create a fresh Project row with status='generated' for the UAT."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    # Make sure tables exist (matches the lifespan startup).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            name="UAT 03 Iberia 868",
            country_qid="ES",
            period_start=868,
            period_end=868,
            status="generated",
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


async def _amain() -> int:
    try:
        source_dir = _ensure_pipeline_output()
        project = await _create_project_row()
        seed_phase01_artifacts(project.id, source_dir)
    finally:
        await engine.dispose()

    sys.stdout.write(
        json.dumps(
            {
                "project_id": project.id,
                "name": project.name,
                "country_qid": project.country_qid,
                "period_start": project.period_start,
                "period_end": project.period_end,
            }
        )
        + "\n"
    )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.stderr.write("usage: uat_setup.py\n")
        return 2
    try:
        return asyncio.run(_amain())
    except Exception as exc:  # pragma: no cover — CLI failure path
        sys.stderr.write(f"uat_setup: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
