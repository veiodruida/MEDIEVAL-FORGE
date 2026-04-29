"""Tests for GEO-07 ridge derivation pipeline (Plan 02.1-05).

Calibration record (Wave 0 probe against backend/tests/fixtures/synthetic_dem.tif):
  z.std ≈ 367, lap_raw range: -7.9..58.1, slope range: 0..90°
  slope>30 AND lap_raw>0.002: 840 mask cells, 2 skeleton components, 2 polygons
  polygon areas ≈ 4.2e-2 deg² >> min_deg2=4.06e-4 (5e6m²/111000²)
  => RESEARCH.md thresholds are valid for the synthetic DEM; unnormalized laplacian used.
  Both gaussian centers (row25,col25)→(lon≈0.255,lat≈0.745) and
  (row75,col75)→(lon≈0.755,lat≈0.245) fall inside their respective ridge polygons.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest
import rasterio
import rasterio.transform

from medieval_forge.services.ingest_terrain.ridges import derive_ridges, THRESHOLDS  # noqa: F401

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SYNTHETIC_DEM = FIXTURES_DIR / "synthetic_dem.tif"


# ---------------------------------------------------------------------------
# Helper: resolve world coords from pixel row/col in synthetic DEM
# ---------------------------------------------------------------------------

def _pixel_to_world(row: int, col: int) -> tuple[float, float]:
    with rasterio.open(SYNTHETIC_DEM) as src:
        lon, lat = rasterio.transform.xy(src.transform, row, col)
    return float(lon), float(lat)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_derive_ridges_returns_feature_collection():
    """derive_ridges returns a valid GeoJSON FeatureCollection with >=2 features."""
    result = derive_ridges(SYNTHETIC_DEM, sensitivity="med")
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) >= 2


def test_derive_ridges_synthetic_covers_both_gaussians():
    """Each gaussian peak center is covered by at least one ridge polygon."""
    from shapely.geometry import Point, shape as shp_shape

    result = derive_ridges(SYNTHETIC_DEM, sensitivity="med")

    # Convert pixel centers to world coords
    lon25, lat25 = _pixel_to_world(25, 25)  # first peak
    lon75, lat75 = _pixel_to_world(75, 75)  # second peak

    p1 = Point(lon25, lat25)
    p2 = Point(lon75, lat75)

    def _multipolygon_geom(feature):
        """Return the MultiPolygon component from a GeometryCollection feature."""
        gc = shp_shape(feature["geometry"])
        return gc.geoms[0]  # first geometry is MultiPolygon or Polygon

    ridge_geoms = [_multipolygon_geom(f) for f in result["features"]]

    p1_covered = any(g.contains(p1) or g.intersects(p1.buffer(0.02)) for g in ridge_geoms)
    p2_covered = any(g.contains(p2) or g.intersects(p2.buffer(0.02)) for g in ridge_geoms)

    assert p1_covered, f"Gaussian center at ({lon25:.3f},{lat25:.3f}) not covered by any ridge polygon"
    assert p2_covered, f"Gaussian center at ({lon75:.3f},{lat75:.3f}) not covered by any ridge polygon"


def test_derive_ridges_property_schema():
    """Each ridge feature has exactly the required property keys with correct types."""
    result = derive_ridges(SYNTHETIC_DEM, sensitivity="med")
    required_keys = {"id", "name", "elev_min", "elev_max", "elev_mean", "peak_count", "basin_ids"}

    for feat in result["features"]:
        props = feat["properties"]
        assert set(props.keys()) == required_keys, f"Unexpected keys: {set(props.keys())}"
        assert isinstance(props["id"], str)
        assert len(props["id"]) == 12
        assert isinstance(props["elev_min"], float)
        assert isinstance(props["elev_max"], float)
        assert isinstance(props["elev_mean"], float)
        assert isinstance(props["peak_count"], int)
        assert isinstance(props["basin_ids"], list)


def test_derive_ridges_id_is_deterministic_across_runs():
    """IDs are identical across two independent calls (Pitfall 7 — string-format hashing)."""
    ids_run1 = {f["properties"]["id"] for f in derive_ridges(SYNTHETIC_DEM, sensitivity="med")["features"]}
    ids_run2 = {f["properties"]["id"] for f in derive_ridges(SYNTHETIC_DEM, sensitivity="med")["features"]}
    assert ids_run1 == ids_run2, "Ridge IDs differ across runs — non-deterministic hashing detected"


def test_derive_ridges_id_format_is_sha1_truncated():
    """Each ridge id matches the regex ^[0-9a-f]{12}$ (SHA1 truncated to 12 hex chars)."""
    pattern = re.compile(r"^[0-9a-f]{12}$")
    result = derive_ridges(SYNTHETIC_DEM, sensitivity="med")
    for feat in result["features"]:
        rid = feat["properties"]["id"]
        assert pattern.match(rid), f"ID {rid!r} does not match ^[0-9a-f]{{12}}$"


def test_derive_ridges_geometry_is_geometry_collection():
    """Each feature.geometry is a GeometryCollection with [MultiPolygon-ish, LineString-ish]."""
    result = derive_ridges(SYNTHETIC_DEM, sensitivity="med")
    for feat in result["features"]:
        geom = feat["geometry"]
        assert geom["type"] == "GeometryCollection", f"Expected GeometryCollection, got {geom['type']}"
        geoms = geom["geometries"]
        assert len(geoms) >= 2, "Expected at least 2 sub-geometries"
        assert geoms[0]["type"] in {"MultiPolygon", "Polygon"}, f"First sub-geom should be (Multi)Polygon; got {geoms[0]['type']}"
        assert geoms[1]["type"] in {"LineString", "MultiLineString"}, f"Second sub-geom should be LineString; got {geoms[1]['type']}"


def test_derive_ridges_sensitivity_high_without_whitebox_returns_412():
    """sensitivity='high' without whitebox installed triggers 412-like SSE message via runner."""
    import asyncio
    from unittest.mock import patch

    # Monkeypatch whitebox as absent
    with patch.dict(sys.modules, {"whitebox": None}):
        queue: asyncio.Queue = asyncio.Queue()

        async def _run():
            from medieval_forge.services.ingest_terrain.runner import run_terrain_ridges
            # We need a dem_path that exists; use synthetic DEM but in a fake project dir
            # The runner checks for raw/dem.tif — use tmp dir workaround via direct call
            # Test the underlying derive_ridges raises RuntimeError for high without whitebox
            with pytest.raises((RuntimeError, ImportError)):
                from medieval_forge.services.ingest_terrain.ridges import (
                    _check_high_quality_available,
                )
                _check_high_quality_available()

        asyncio.get_event_loop().run_until_complete(_run())

    # Also verify the SSE path: mock run_terrain_ridges queue message
    async def _run_sse():
        import tempfile
        import shutil
        from pathlib import Path
        from medieval_forge.services import paths as mf_paths

        with tempfile.TemporaryDirectory() as tmpdir:
            # Monkeypatch PROJECTS_ROOT and set up project dir
            import uuid
            pid = str(uuid.uuid4())
            old_root = mf_paths.PROJECTS_ROOT
            mf_paths.PROJECTS_ROOT = Path(tmpdir)
            dirs = mf_paths.ensure_project_dirs(pid)
            shutil.copy(str(SYNTHETIC_DEM), str(dirs["raw"] / "dem.tif"))

            try:
                with patch.dict(sys.modules, {"whitebox": None}):
                    from medieval_forge.services.ingest_terrain.runner import run_terrain_ridges
                    q: asyncio.Queue = asyncio.Queue()
                    await run_terrain_ridges(pid, q, sensitivity="high")

                messages = []
                while not q.empty():
                    msg = q.get_nowait()
                    if msg is not None:
                        messages.append(msg)

                all_text = " ".join(messages)
                assert "412" in all_text or "high-quality" in all_text, (
                    f"Expected 412 or high-quality in SSE messages; got: {messages}"
                )
            finally:
                mf_paths.PROJECTS_ROOT = old_root

    asyncio.get_event_loop().run_until_complete(_run_sse())
