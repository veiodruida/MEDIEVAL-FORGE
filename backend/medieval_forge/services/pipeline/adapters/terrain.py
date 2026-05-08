"""Terrain stub adapter (D-13 passthrough — Phase 02 reserves the slot, Phase 06/v3.1 wires it).

The 851-line services/ingest_terrain/ package STAYS UNTOUCHED in Phase 02.
This stub returns the vendored mountain_river_data.json Path so the v3 pipeline
can run end-to-end without DEM/HydroSHEDS/ridges work.
"""
from __future__ import annotations

from pathlib import Path

from medieval_forge.services.paths import is_valid_uuid

# Anchored to repo root (parents[5] from this file).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_VENDORED_MOUNTAIN_RIVER = _REPO_ROOT / "data" / "regions" / "iberia_868" / "inputs" / "mountain_river_data.json"


def build_terrain(project_id: str) -> Path:
    """D-13 stub: returns Path to vendored mountain_river_data.json.

    No DEM/HydroSHEDS/ridges work — the slot exists on ProjectDataset
    (`mountain_river_json: Path`); Phase 06 or v3.1 fills it for real.

    project_id is validated (T-PATH) but unused — the vendored file is
    project-independent in Phase 02.
    """
    if not is_valid_uuid(project_id):
        raise ValueError(f"invalid project_id: {project_id!r}")
    return _VENDORED_MOUNTAIN_RIVER


__all__ = ["build_terrain"]
