"""Unit tests for build_terrain stub passthrough (D-13)."""
from __future__ import annotations

import inspect
import uuid

import pytest

from medieval_forge.services.pipeline.adapters import terrain as terrain_mod
from medieval_forge.services.pipeline.adapters.terrain import build_terrain


@pytest.fixture
def project_uuid() -> str:
    return str(uuid.uuid4())


def test_build_terrain_returns_vendored_mountain_river_json_path(project_uuid):
    """D-13: build_terrain returns the vendored mountain_river_data.json Path."""
    result = build_terrain(project_uuid)
    assert result.name == "mountain_river_data.json"
    parts = [p.replace("\\", "/") for p in result.parts]
    joined = "/".join(parts)
    assert "data/regions/iberia_868/inputs" in joined, joined


def test_build_terrain_returned_path_exists_on_disk(project_uuid):
    """D-13 + Phase 01 D-11: the vendored file must actually exist on disk."""
    result = build_terrain(project_uuid)
    assert result.exists(), f"vendored mountain_river_data.json missing: {result}"


def test_build_terrain_does_not_call_dem_or_hydrosheds():
    """D-13 stub passthrough: no imports from services/ingest_terrain/."""
    src = inspect.getsource(terrain_mod)
    # Forbidden: any import of ingest_terrain submodules.
    assert "from medieval_forge.services.ingest_terrain" not in src, (
        "D-13 violated: terrain stub should not import ingest_terrain"
    )
    assert "import ingest_terrain" not in src, "D-13 violated"
    # Forbidden: direct DEM/HydroSHEDS/ridges calls.
    for forbidden in ("dem.fetch_dem", "hydrosheds.fetch_basins", "ridges.derive_ridges"):
        assert forbidden not in src, f"D-13 violated: forbidden call {forbidden}"


def test_build_terrain_validates_project_id_is_uuid():
    """T-PATH: invalid project_id rejected even though the field is unused in stub."""
    with pytest.raises(ValueError, match="invalid project_id"):
        build_terrain("not-a-uuid")

    # Valid UUID accepted
    result = build_terrain(str(uuid.uuid4()))
    assert result.name == "mountain_river_data.json"
