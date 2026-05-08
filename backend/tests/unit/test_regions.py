"""Unit tests for iberia_config() vendored-ProjectDataset construction (D-08)."""
from __future__ import annotations

from pathlib import Path

from medieval_forge.services.pipeline.contracts import ProjectDataset
from medieval_forge.services.pipeline.regions import iberia_config


def test_iberia_config_returns_vendored_project_dataset() -> None:
    """D-08: iberia_config() builds a ProjectDataset pointing at the vendored es-atlas + pt_concelhos."""
    cfg = iberia_config()

    assert cfg.dataset is not None
    assert isinstance(cfg.dataset, ProjectDataset)

    # All three vendored paths anchored under data/regions/iberia_868/inputs/
    assert "data" in str(cfg.dataset.pt_geojson).replace("\\", "/")
    assert "regions/iberia_868/inputs" in str(cfg.dataset.pt_geojson).replace("\\", "/")

    assert str(cfg.dataset.pt_geojson).endswith("pt_concelhos_wgs84.geojson")
    assert str(cfg.dataset.es_input).endswith("municipalities.json")  # Vendored TopoJSON has .json extension
    assert "es-atlas-pkg" in str(cfg.dataset.es_input).replace("\\", "/")
    assert str(cfg.dataset.mountain_river_json).endswith("mountain_river_data.json")
    assert cfg.dataset.dem_raster is None  # D-04: vendored config doesn't set DEM


def test_iberia_config_dataset_paths_exist_on_disk() -> None:
    """D-08 + Phase 01 D-11: vendored ProjectDataset paths point at files that exist."""
    cfg = iberia_config()

    assert Path(cfg.dataset.pt_geojson).exists(), f"missing: {cfg.dataset.pt_geojson}"
    assert Path(cfg.dataset.es_input).exists(),   f"missing: {cfg.dataset.es_input}"
    assert Path(cfg.dataset.mountain_river_json).exists(), f"missing: {cfg.dataset.mountain_river_json}"
