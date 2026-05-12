"""Tests for GET /api/v3/regions endpoint — Plan 05-07 (D-06).

Tests:
  - test_returns_iberia_and_france: both keys present with has_dataset=True
  - test_alphabetical_order: keys sorted alphabetically
  - test_nested_bounds_shape: each item's bounds is a nested dict with 4 numeric keys
  - test_has_dataset_false_when_inputs_missing: YAML pointing to non-existent paths
  - test_malformed_yaml_skipped: malformed YAML file does not 500 the endpoint
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from medieval_forge.main import app
from medieval_forge.api.v3 import regions as v3_regions_module


@pytest.fixture
def sync_client():
    """Synchronous TestClient — endpoint is sync (not async), no db dependency."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_regions_dir(monkeypatch, new_dir: Path):
    """Point the endpoint's _REGIONS_DIR to a tmp directory."""
    monkeypatch.setattr(v3_regions_module, "_REGIONS_DIR", new_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_returns_iberia_and_france(sync_client):
    """GET /api/v3/regions includes iberia_868 and france_1066 with has_dataset=True."""
    resp = sync_client.get("/api/v3/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    keys = {item["key"] for item in data}
    assert "iberia_868" in keys, f"iberia_868 missing from {keys}"
    assert "france_1066" in keys, f"france_1066 missing from {keys}"
    iberia = next(item for item in data if item["key"] == "iberia_868")
    france = next(item for item in data if item["key"] == "france_1066")
    assert iberia["has_dataset"] is True, "iberia_868 should have has_dataset=True"
    assert france["has_dataset"] is True, "france_1066 should have has_dataset=True"


def test_alphabetical_order(sync_client):
    """Response keys must be sorted alphabetically."""
    resp = sync_client.get("/api/v3/regions")
    assert resp.status_code == 200
    keys = [item["key"] for item in resp.json()]
    assert keys == sorted(keys), f"Keys not sorted: {keys}"


def test_nested_bounds_shape(sync_client):
    """Each item's 'bounds' must be a nested dict with 4 numeric (or None) keys."""
    resp = sync_client.get("/api/v3/regions")
    assert resp.status_code == 200
    for item in resp.json():
        bounds = item.get("bounds")
        assert isinstance(bounds, dict), f"bounds not dict for {item['key']}: {bounds}"
        for k in ("lon_min", "lon_max", "lat_min", "lat_max"):
            assert k in bounds, f"bounds missing key '{k}' for {item['key']}"
            val = bounds[k]
            assert val is None or isinstance(val, (int, float)), (
                f"bounds['{k}'] is not numeric for {item['key']}: {val!r}"
            )


def test_has_dataset_false_when_inputs_missing(monkeypatch, tmp_path):
    """has_dataset is False when YAML dataset paths do not exist on disk."""
    # Create a region YAML pointing to non-existent files
    region_dir = tmp_path / "missing_region"
    region_dir.mkdir()
    yaml_text = textwrap.dedent("""\
        display_name: Missing Region
        map_w: 1920
        map_h: 1080
        lon_min: -10.0
        lon_max: 4.0
        lat_min: 36.0
        lat_max: 44.0
        dataset:
          pt_geojson: inputs/pt.geojson
          es_input: inputs/es.geojson
          mountain_river_json: inputs/mountain_river_data.json
    """)
    (tmp_path / "missing_region.yaml").write_text(yaml_text, encoding="utf-8")
    # NOTE: inputs/ sub-directory is intentionally NOT created — files don't exist

    _patch_regions_dir(monkeypatch, tmp_path)

    with TestClient(app) as c:
        resp = c.get("/api/v3/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["key"] == "missing_region"
    assert data[0]["has_dataset"] is False


def test_malformed_yaml_skipped(monkeypatch, tmp_path):
    """A malformed YAML file must NOT cause a 500 — it is silently skipped."""
    # Write a valid YAML alongside a malformed one
    valid_yaml = textwrap.dedent("""\
        display_name: Good Region
        lon_min: -10.0
        lon_max: 4.0
        lat_min: 36.0
        lat_max: 44.0
    """)
    (tmp_path / "good_region.yaml").write_text(valid_yaml, encoding="utf-8")
    # Write deliberately broken YAML (unclosed bracket)
    (tmp_path / "bad_region.yaml").write_text(
        "display_name: Bad\nkingdoms: [unclosed\n", encoding="utf-8"
    )

    _patch_regions_dir(monkeypatch, tmp_path)

    with TestClient(app) as c:
        resp = c.get("/api/v3/regions")
    assert resp.status_code == 200
    data = resp.json()
    returned_keys = {item["key"] for item in data}
    assert "good_region" in returned_keys
    assert "bad_region" not in returned_keys, "Malformed YAML key must be skipped"
