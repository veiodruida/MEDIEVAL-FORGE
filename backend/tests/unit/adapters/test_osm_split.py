"""Unit tests for build_dataset_from_osm + _split_by_iso (Plan 02 D-05, D-07, D-13)."""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from medieval_forge.services.pipeline.adapters.osm import (
    build_dataset_from_osm,
    _split_by_iso,
)
from medieval_forge.services.pipeline.contracts import ProjectDataset


# ---- _split_by_iso ----

def test_split_by_iso_routes_pt_features_to_pt_list_only(synthetic_iberia_fc):
    """Synthetic 6-feature FC → 2 PT, 3 ES, 1 dropped."""
    result = _split_by_iso(synthetic_iberia_fc, ["PT", "ES"])
    assert len(result["PT"]) == 2, [f["properties"]["name"] for f in result["PT"]]
    assert len(result["ES"]) == 3, [f["properties"]["name"] for f in result["ES"]]

    pt_names = {f["properties"]["name"] for f in result["PT"]}
    es_names = {f["properties"]["name"] for f in result["ES"]}
    assert pt_names == {"PT-1", "PT-2"}
    assert es_names == {"ES-1", "ES-2", "ES-3"}


def test_split_by_iso_drops_features_outside_all_polygons(synthetic_iberia_fc):
    """Atlantic feature (lon=-25, lat=40) must be dropped — not in PT or ES."""
    result = _split_by_iso(synthetic_iberia_fc, ["PT", "ES"])
    total_kept = len(result["PT"]) + len(result["ES"])
    assert total_kept == 5, f"expected 5 kept of 6 input, got {total_kept}"
    all_names = {f["properties"]["name"] for f in result["PT"] + result["ES"]}
    assert "ATLANTIC" not in all_names


def test_split_by_iso_handles_multipolygon_features(synthetic_multipolygon_pt_feature):
    """MultiPolygon centered in PT routes to PT list (representative_point works)."""
    fc = {"type": "FeatureCollection", "features": [synthetic_multipolygon_pt_feature]}
    result = _split_by_iso(fc, ["PT", "ES"])
    assert len(result["PT"]) == 1
    assert len(result["ES"]) == 0
    assert result["PT"][0]["properties"]["name"] == "PT-MP"


def test_split_by_iso_returns_empty_lists_for_unknown_iso(synthetic_iberia_fc):
    """Unknown ISO (e.g. "XX") → empty list, no exception."""
    result = _split_by_iso(synthetic_iberia_fc, ["XX"])
    assert result == {"XX": []}


# ---- build_dataset_from_osm ----

@pytest.fixture
def project_uuid() -> str:
    return str(uuid.uuid4())


def test_build_dataset_from_osm_writes_two_geojsons_to_inputs_dir(
    project_uuid, synthetic_iberia_fc, monkeypatch, tmp_path,
):
    """Adapter writes pt + es .geojson files under projects/<uuid>/inputs/ and returns ProjectDataset."""
    # Redirect PROJECTS_ROOT into tmp_path so we don't write into the real DATA_DIR.
    from medieval_forge.services import paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    # Monkey-patch fetch_municipalities to return the synthetic FC (no network).
    async def _fake_fetch(country_iso, queue, **kwargs):  # noqa: ARG001
        return synthetic_iberia_fc

    import medieval_forge.services.pipeline.adapters.osm as osm_mod
    monkeypatch.setattr(osm_mod, "fetch_municipalities", _fake_fetch)

    queue: asyncio.Queue = asyncio.Queue()
    bbox = (36.0, -9.5, 44.0, 4.3)  # (lat_min, lon_min, lat_max, lon_max)
    ds = asyncio.run(build_dataset_from_osm(project_uuid, bbox, ["PT", "ES"], queue))

    assert isinstance(ds, ProjectDataset)
    assert ds.pt_geojson.name == "pt_concelhos_live.geojson"
    assert ds.es_input.name == "es_municipalities_live.geojson"
    assert ds.pt_geojson.exists()
    assert ds.es_input.exists()
    assert str(ds.mountain_river_json).endswith("mountain_river_data.json")  # D-13

    # Verify counts in the written files
    pt_fc = json.loads(ds.pt_geojson.read_text(encoding="utf-8"))
    es_fc = json.loads(ds.es_input.read_text(encoding="utf-8"))
    assert len(pt_fc["features"]) == 2
    assert len(es_fc["features"]) == 3


def test_build_dataset_from_osm_validates_bbox_shape(project_uuid, monkeypatch, tmp_path):
    from medieval_forge.services import paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    queue: asyncio.Queue = asyncio.Queue()

    # 3-tuple → ValueError
    with pytest.raises(ValueError, match="bbox"):
        asyncio.run(build_dataset_from_osm(project_uuid, (1.0, 2.0, 3.0), ["PT", "ES"], queue))  # type: ignore[arg-type]

    # Non-numeric → ValueError
    with pytest.raises(ValueError, match="numeric"):
        asyncio.run(build_dataset_from_osm(project_uuid, ("a", "b", "c", "d"), ["PT", "ES"], queue))  # type: ignore[arg-type]

    # Span > 30° → ValueError
    with pytest.raises(ValueError, match="30"):
        asyncio.run(build_dataset_from_osm(project_uuid, (0.0, -50.0, 35.0, 0.0), ["PT", "ES"], queue))


def test_build_dataset_from_osm_validates_project_id_is_uuid(monkeypatch, tmp_path):
    from medieval_forge.services import paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    queue: asyncio.Queue = asyncio.Queue()
    bbox = (36.0, -9.5, 44.0, 4.3)
    with pytest.raises(ValueError, match="invalid project_id"):
        asyncio.run(build_dataset_from_osm("not-a-uuid", bbox, ["PT", "ES"], queue))
