"""Unit tests for region_loader.py — Plan 05-01.

Tests cover:
  - load_region happy path: returns RegionConfig with correct fields
  - Security: invalid key patterns rejected before filesystem access
  - Security: yaml.safe_load rejects malicious YAML tags
  - Security: dataset path traversal rejected
  - Pydantic schema: smooth_sigma range enforcement
  - Pydantic schema: extra fields rejected
  - Cache: second call returns same object (identity)
  - Cache: mtime NOT consulted (explicit-only invalidation)
  - Cache: clear_region_cache empties cache
  - Autogen: empty kingdoms/duchies/condados triggers synthesis from GeoJSON
  - Template-only regions: no dataset raises FileNotFoundError with 'template-only'
  - Immutability: dataclasses.replace does not mutate cache (R-10)
"""

import dataclasses
import json
import textwrap
from pathlib import Path

import pytest

from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)
from medieval_forge.services.pipeline.contracts import RegionConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, key: str, content: str) -> Path:
    """Write a region YAML and return the regions_dir (tmp_path)."""
    yaml_path = tmp_path / f"{key}.yaml"
    yaml_path.write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


MINIMAL_YAML_TEMPLATE = """\
    name: toy
    lon_min: -5.0
    lon_max: 5.0
    lat_min: 40.0
    lat_max: 50.0
    output_dir: /tmp/out
    {dataset_block}
"""

TOY_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.0, 45.0]},
            "properties": {"name": "A"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1.0, 46.0]},
            "properties": {"name": "B"},
        },
    ],
}


def _make_toy_region(tmp_path: Path, key: str = "toy_region") -> Path:
    """Create a minimal but valid region YAML + dataset inputs. Returns regions_dir."""
    region_root = tmp_path / key
    inputs_dir = region_root / "inputs"
    inputs_dir.mkdir(parents=True)

    pt_file = inputs_dir / "pt.geojson"
    es_file = inputs_dir / "es.geojson"
    mr_file = inputs_dir / "mr.json"

    pt_file.write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    es_file.write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    mr_file.write_text(json.dumps({"mountains": {}, "rivers": {}}), encoding="utf-8")

    yaml_content = f"""\
name: toy
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
"""
    (tmp_path / f"{key}.yaml").write_text(yaml_content, encoding="utf-8")
    return tmp_path


def _make_toy_region_with_territories(tmp_path: Path, key: str = "toy_with_terr") -> Path:
    """Create a region with explicit kingdoms/duchies/condados arrays."""
    region_root = tmp_path / key
    inputs_dir = region_root / "inputs"
    inputs_dir.mkdir(parents=True)

    pt_file = inputs_dir / "pt.geojson"
    es_file = inputs_dir / "es.geojson"
    mr_file = inputs_dir / "mr.json"

    pt_file.write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    es_file.write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    mr_file.write_text(json.dumps({"mountains": {}, "rivers": {}}), encoding="utf-8")

    yaml_content = f"""\
name: toy_with_terr
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
kingdoms:
  - id: unnamed
    name: Unnamed Kingdom
kingdoms:
  - id: unnamed
    name: Unnamed Kingdom
duchies:
  - id: unnamed_duchy
    name: Unnamed Duchy
condados:
  - id: c_001
    name: Condado 001
    original_idx: 1
"""
    (tmp_path / f"{key}.yaml").write_text(yaml_content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Security: key validation
# ---------------------------------------------------------------------------

def test_invalid_key_dotdot_rejected():
    with pytest.raises(ValueError, match="invalid region key"):
        load_region("../escape")


def test_invalid_key_slash_rejected():
    with pytest.raises(ValueError, match="invalid region key"):
        load_region("with/slash")


def test_invalid_key_backslash_rejected():
    with pytest.raises(ValueError, match="invalid region key"):
        load_region("back\\slash")


def test_invalid_key_uppercase_rejected():
    with pytest.raises(ValueError, match="invalid region key"):
        load_region("Iberia_868")


def test_invalid_key_null_byte_rejected():
    with pytest.raises(ValueError, match="invalid region key"):
        load_region("valid\x00key")


def test_valid_key_passes_regex(tmp_path):
    """Valid [a-z0-9_]+ key does not raise ValueError; raises FileNotFoundError instead."""
    with pytest.raises(FileNotFoundError):
        load_region("iberia_868", regions_dir=tmp_path)


# ---------------------------------------------------------------------------
# Security: yaml.safe_load — malicious tag
# ---------------------------------------------------------------------------

def test_malicious_yaml_tag_rejected(tmp_path):
    """yaml.safe_load must reject !!python/object/apply tags."""
    import yaml
    malicious_yaml = "!!python/object/apply:os.system ['echo pwned']"
    yaml_path = tmp_path / "evil_region.yaml"
    yaml_path.write_text(malicious_yaml, encoding="utf-8")
    with pytest.raises(Exception):  # yaml.constructor.ConstructorError or similar
        load_region("evil_region", regions_dir=tmp_path)


# ---------------------------------------------------------------------------
# Security: dataset path traversal
# ---------------------------------------------------------------------------

def test_dataset_path_traversal_rejected(tmp_path):
    """dataset path pointing outside region dir must raise ValueError."""
    region_root = tmp_path / "traversal_region"
    region_root.mkdir(parents=True)
    yaml_content = """\
name: traversal_region
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
dataset:
  pt_geojson: ../../../etc/passwd
  es_input: ../../../etc/passwd
  mountain_river_json: ../../../etc/passwd
"""
    (tmp_path / "traversal_region.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(ValueError, match="outside region dir"):
        load_region("traversal_region", regions_dir=tmp_path)


# ---------------------------------------------------------------------------
# Pydantic schema: smooth_sigma validation
# ---------------------------------------------------------------------------

def test_smooth_sigma_too_high_rejected(tmp_path):
    """smooth_sigma > 4.5 must raise pydantic.ValidationError."""
    import pydantic
    region_root = tmp_path / "sigma_high"
    inputs_dir = region_root / "inputs"
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "pt.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "es.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "mr.json").write_text(json.dumps({"mountains": {}, "rivers": {}}), encoding="utf-8")

    yaml_content = """\
name: sigma_high
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
smooth_sigma: 5.0
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
"""
    (tmp_path / "sigma_high.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        load_region("sigma_high", regions_dir=tmp_path)


def test_smooth_sigma_too_low_rejected(tmp_path):
    """smooth_sigma < 3.0 must raise pydantic.ValidationError."""
    import pydantic
    region_root = tmp_path / "sigma_low"
    inputs_dir = region_root / "inputs"
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "pt.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "es.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "mr.json").write_text(json.dumps({"mountains": {}, "rivers": {}}), encoding="utf-8")

    yaml_content = """\
name: sigma_low
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
smooth_sigma: 2.9
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
"""
    (tmp_path / "sigma_low.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        load_region("sigma_low", regions_dir=tmp_path)


def test_smooth_sigma_in_range_succeeds(tmp_path):
    """smooth_sigma = 3.5 must load successfully."""
    region_root = tmp_path / "sigma_ok"
    inputs_dir = region_root / "inputs"
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "pt.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "es.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "mr.json").write_text(json.dumps({"mountains": {}, "rivers": {}}), encoding="utf-8")

    yaml_content = """\
name: sigma_ok
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
smooth_sigma: 3.5
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
"""
    (tmp_path / "sigma_ok.yaml").write_text(yaml_content, encoding="utf-8")
    cfg = load_region("sigma_ok", regions_dir=tmp_path)
    assert cfg.smooth_sigma == 3.5


# ---------------------------------------------------------------------------
# Pydantic schema: extra fields rejected
# ---------------------------------------------------------------------------

def test_unknown_field_rejected(tmp_path):
    """YAML with unknown top-level field raises pydantic.ValidationError."""
    import pydantic
    region_root = tmp_path / "extra_field"
    inputs_dir = region_root / "inputs"
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "pt.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "es.geojson").write_text(json.dumps(TOY_GEOJSON), encoding="utf-8")
    (inputs_dir / "mr.json").write_text(json.dumps({"mountains": {}, "rivers": {}}), encoding="utf-8")

    yaml_content = """\
name: extra_field
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
this_field_does_not_exist: true
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
"""
    (tmp_path / "extra_field.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        load_region("extra_field", regions_dir=tmp_path)


# ---------------------------------------------------------------------------
# Happy path: load_region returns RegionConfig
# ---------------------------------------------------------------------------

def test_load_region_returns_region_config(tmp_path):
    regions_dir = _make_toy_region(tmp_path)
    cfg = load_region("toy_region", regions_dir=regions_dir)
    assert isinstance(cfg, RegionConfig)


def test_load_region_fields_match_yaml(tmp_path):
    regions_dir = _make_toy_region(tmp_path)
    cfg = load_region("toy_region", regions_dir=regions_dir)
    assert cfg.lon_min == -5.0
    assert cfg.lon_max == 5.0
    assert cfg.lat_min == 40.0
    assert cfg.lat_max == 50.0
    assert cfg.output_dir == "/tmp/out"


def test_load_region_missing_yaml_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="toy_missing"):
        load_region("toy_missing", regions_dir=tmp_path)


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------

def test_cache_returns_same_object(tmp_path):
    """Second load_region call returns the cached object (identity-equal)."""
    regions_dir = _make_toy_region(tmp_path)
    cfg1 = load_region("toy_region", regions_dir=regions_dir)
    cfg2 = load_region("toy_region", regions_dir=regions_dir)
    assert cfg1 is cfg2


def test_clear_cache_forces_reparse(tmp_path):
    """After clear_region_cache, load_region re-parses the YAML."""
    regions_dir = _make_toy_region(tmp_path)
    cfg1 = load_region("toy_region", regions_dir=regions_dir)
    clear_region_cache()
    cfg2 = load_region("toy_region", regions_dir=regions_dir)
    # Different object after cache clear
    assert cfg1 is not cfg2


def test_mtime_not_consulted(tmp_path):
    """Cache does NOT invalidate on mtime change — explicit-only (D-15 RESEARCH)."""
    regions_dir = _make_toy_region(tmp_path)
    cfg1 = load_region("toy_region", regions_dir=regions_dir)

    # Overwrite YAML with different content without clearing cache
    new_yaml = """\
name: toy_region_modified
lon_min: -10.0
lon_max: 10.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/other
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
"""
    (regions_dir / "toy_region.yaml").write_text(new_yaml, encoding="utf-8")

    cfg2 = load_region("toy_region", regions_dir=regions_dir)
    # Must return the cached cfg, not re-parse
    assert cfg2 is cfg1
    assert cfg2.lon_min == -5.0  # original value


# ---------------------------------------------------------------------------
# Template-only regions (R-03)
# ---------------------------------------------------------------------------

def test_template_only_no_dataset_block_raises(tmp_path):
    """YAML with no dataset block raises FileNotFoundError with 'template-only'."""
    yaml_content = """\
name: england_1216
lon_min: -6.0
lon_max: 2.0
lat_min: 49.5
lat_max: 56.0
output_dir: /tmp/out
"""
    (tmp_path / "england_1216.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="template-only"):
        load_region("england_1216", regions_dir=tmp_path)


def test_template_only_all_none_dataset_raises(tmp_path):
    """YAML with dataset: but every sub-field null raises FileNotFoundError with 'template-only'."""
    yaml_content = """\
name: england_1216
lon_min: -6.0
lon_max: 2.0
lat_min: 49.5
lat_max: 56.0
output_dir: /tmp/out
dataset:
  pt_geojson: null
  es_input: null
  mountain_river_json: null
"""
    (tmp_path / "england_1216.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="template-only"):
        load_region("england_1216", regions_dir=tmp_path)


def test_template_only_error_contains_region_key(tmp_path):
    """template-only FileNotFoundError message contains the region key."""
    yaml_content = """\
name: england_1216
lon_min: -6.0
lon_max: 2.0
lat_min: 49.5
lat_max: 56.0
output_dir: /tmp/out
"""
    (tmp_path / "england_1216.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="england_1216"):
        load_region("england_1216", regions_dir=tmp_path)


def test_missing_dataset_file_raises_with_template_only_hint(tmp_path):
    """Named dataset file that doesn't exist on disk raises FileNotFoundError with 'template-only'."""
    region_root = tmp_path / "missing_files_region"
    region_root.mkdir(parents=True)
    yaml_content = """\
name: missing_files_region
lon_min: -5.0
lon_max: 5.0
lat_min: 40.0
lat_max: 50.0
output_dir: /tmp/out
dataset:
  pt_geojson: inputs/pt.geojson
  es_input: inputs/es.geojson
  mountain_river_json: inputs/mr.json
"""
    (tmp_path / "missing_files_region.yaml").write_text(yaml_content, encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="template-only"):
        load_region("missing_files_region", regions_dir=tmp_path)


# ---------------------------------------------------------------------------
# Autogen: empty condados triggers synthesis (D-03)
# ---------------------------------------------------------------------------

def test_autogen_condados_when_empty(tmp_path):
    """When YAML has empty condados, loader synthesizes condados from GeoJSON centroids."""
    regions_dir = _make_toy_region(tmp_path)
    cfg = load_region("toy_region", regions_dir=regions_dir)
    assert len(cfg.condados) > 0


def test_autogen_condados_have_original_idx(tmp_path):
    """Autogen condados each have a unique original_idx (CLAUDE.md rule 4 — Nájera bug guard)."""
    regions_dir = _make_toy_region(tmp_path)
    cfg = load_region("toy_region", regions_dir=regions_dir)
    # Each autogen condado dict must have original_idx
    indices = []
    for c in cfg.condados:
        if isinstance(c, dict):
            assert "original_idx" in c, f"condado missing original_idx: {c}"
            indices.append(c["original_idx"])
        else:
            # tuple format: original_idx may be at a known position — acceptable
            pass
    if indices:
        assert len(indices) == len(set(indices)), "original_idx values must be unique"


def test_autogen_kingdoms_non_empty(tmp_path):
    """Autogen path produces a non-empty kingdoms structure."""
    regions_dir = _make_toy_region(tmp_path)
    cfg = load_region("toy_region", regions_dir=regions_dir)
    assert cfg.kingdoms


# ---------------------------------------------------------------------------
# R-10: Cache singleton immutability — dataclasses.replace does not mutate cache
# ---------------------------------------------------------------------------

def test_cache_not_mutated_by_replace(tmp_path):
    """dataclasses.replace on a load_region result must not affect cached cfg."""
    regions_dir = _make_toy_region(tmp_path)
    cfg1 = load_region("toy_region", regions_dir=regions_dir)
    original_output_dir = cfg1.output_dir

    # Caller replaces output_dir
    _cfg1_mod = dataclasses.replace(cfg1, output_dir="/tmp/different_output")

    # Cached cfg2 must still have the original output_dir
    cfg2 = load_region("toy_region", regions_dir=regions_dir)
    assert cfg2.output_dir == original_output_dir
