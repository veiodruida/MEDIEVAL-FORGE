"""Unit tests for D-04 fail-fast input assertion in load_municipalities."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from medieval_forge.services.pipeline.contracts import ProjectDataset, RegionConfig
from medieval_forge.services.pipeline.landmask import load_municipalities


def _make_cfg_with_dataset(dataset: Optional[ProjectDataset]) -> RegionConfig:
    cfg = RegionConfig()
    cfg.dataset = dataset
    return cfg


def test_load_municipalities_raises_when_dataset_is_none() -> None:
    """D-04: cfg.dataset = None → FileNotFoundError naming the dataset attribute."""
    cfg = _make_cfg_with_dataset(None)
    with pytest.raises(FileNotFoundError, match="dataset"):
        load_municipalities(cfg)


def test_load_municipalities_raises_when_pt_geojson_missing(tmp_path: Path) -> None:
    """D-04: missing pt_geojson path → FileNotFoundError mentioning the field name."""
    es = tmp_path / "es.json";    es.write_text("{}")
    mr = tmp_path / "mr.json";    mr.write_text('{"mountains":{}, "rivers":{}}')
    ds = ProjectDataset(
        pt_geojson=tmp_path / "missing_pt.geojson",
        es_input=es,
        mountain_river_json=mr,
    )
    cfg = _make_cfg_with_dataset(ds)
    with pytest.raises(FileNotFoundError, match="pt_geojson"):
        load_municipalities(cfg)


def test_load_municipalities_raises_when_es_input_missing(tmp_path: Path) -> None:
    """D-04: missing es_input path → FileNotFoundError mentioning the field name."""
    pt = tmp_path / "pt.geojson"; pt.write_text('{"type":"FeatureCollection","features":[]}')
    mr = tmp_path / "mr.json";    mr.write_text('{"mountains":{}, "rivers":{}}')
    ds = ProjectDataset(
        pt_geojson=pt,
        es_input=tmp_path / "missing_es.json",
        mountain_river_json=mr,
    )
    cfg = _make_cfg_with_dataset(ds)
    with pytest.raises(FileNotFoundError, match="es_input"):
        load_municipalities(cfg)


def test_load_municipalities_raises_when_mountain_river_json_missing(tmp_path: Path) -> None:
    """D-04: missing mountain_river_json path → FileNotFoundError mentioning the field name."""
    pt = tmp_path / "pt.geojson"; pt.write_text('{"type":"FeatureCollection","features":[]}')
    es = tmp_path / "es.json";    es.write_text("{}")
    ds = ProjectDataset(
        pt_geojson=pt,
        es_input=es,
        mountain_river_json=tmp_path / "missing_mr.json",
    )
    cfg = _make_cfg_with_dataset(ds)
    with pytest.raises(FileNotFoundError, match="mountain_river_json"):
        load_municipalities(cfg)
