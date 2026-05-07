"""Session-scoped parity fixtures.

Per RESEARCH §5.a: the full Iberia 868 pipeline takes ~45 s; running it once
per test keeps CI manageable. `tmp_path_factory.mktemp` returns a sandboxed
path under pytest's tmp tree, auto-cleaned at session end.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.regions import REGIONS

# backend/tests/parity/conftest.py -> repo root (parents[3])
REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "iberia_868" / "golden"


@pytest.fixture(scope="session")
def pipeline_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the v3 pipeline once for the session and return its output dir."""
    out = tmp_path_factory.mktemp("iberia_868_actual")
    cfg = REGIONS["iberia_868"]()
    cfg.output_dir = str(out)
    run_pipeline(cfg)
    return out


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    """Path to the committed Reconquista golden fixtures."""
    return GOLDEN_DIR
