"""Unit tests for ProjectDataset and RegionConfig contract shape (Phase 02 D-01..D-04)."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from medieval_forge.services.pipeline.contracts import ProjectDataset, RegionConfig


def test_project_dataset_required_fields_are_paths(tmp_path: Path) -> None:
    """D-04: pt_geojson, es_input, mountain_river_json are the three required Path fields."""
    pt = tmp_path / "pt.geojson"; pt.write_text("{}")
    es = tmp_path / "es.json";    es.write_text("{}")
    mr = tmp_path / "mr.json";    mr.write_text("{}")

    ds = ProjectDataset(pt_geojson=pt, es_input=es, mountain_river_json=mr)

    assert ds.pt_geojson == pt
    assert ds.es_input == es
    assert ds.mountain_river_json == mr
    assert ds.dem_raster is None  # D-04: optional, default None


def test_project_dataset_optional_dem_raster_defaults_none(tmp_path: Path) -> None:
    """D-04: dem_raster defaults to None when omitted; accepts Path when provided."""
    pt = tmp_path / "pt.geojson"; pt.write_text("{}")
    es = tmp_path / "es.json";    es.write_text("{}")
    mr = tmp_path / "mr.json";    mr.write_text("{}")
    dem = tmp_path / "dem.tif";   dem.write_bytes(b"")

    ds_no_dem = ProjectDataset(pt, es, mr)
    ds_w_dem = ProjectDataset(pt, es, mr, dem_raster=dem)

    assert ds_no_dem.dem_raster is None
    assert ds_w_dem.dem_raster == dem


def test_region_config_no_longer_has_legacy_path_fields() -> None:
    """D-01: the three legacy fields are removed; cfg.dataset replaces them."""
    field_names = {f.name for f in fields(RegionConfig)}

    # D-01: removed
    assert "municipality_pt_geojson" not in field_names
    assert "municipality_es_topojson" not in field_names
    assert "mountain_river_json" not in field_names

    # D-01: replacement is the dataset port
    assert "dataset" in field_names
