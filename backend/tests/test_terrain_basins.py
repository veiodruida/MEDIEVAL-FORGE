"""Wave 0 RED tests for hydrosheds.fetch_basins (TDD: Task 0b).

These tests fail until Task 1 creates medieval_forge/services/ingest_terrain/hydrosheds.py.

Deviation from plan spec (Rule 3 auto-fix):
- stub_geopandas builds GeoDataFrame directly from the synthetic fixture using
  gpd.GeoDataFrame.from_features() instead of calling gpd.read_file() internally.
  Reason: monkeypatching gpd.read_file then calling gpd.read_file inside the stub
  causes infinite recursion (stub calls itself). Building from features avoids
  re-entering the patched function.
- Fixture path uses Path(__file__).parent / "fixtures" (absolute resolution) so the
  test works regardless of the working directory from which pytest is invoked.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import geopandas as gpd
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def stub_geopandas(monkeypatch):
    """Return a factory: call with empty=True to get an empty stub, otherwise 2 features."""
    def _factory(empty: bool = False):
        def _read_file(path, bbox=None, **kwargs):
            if empty:
                return gpd.GeoDataFrame(
                    columns=["HYBAS_ID", "NEXT_DOWN", "SUB_AREA", "geometry"],
                    geometry="geometry",
                    crs="EPSG:4326",
                )
            # Build GeoDataFrame from the synthetic fixture WITHOUT calling read_file
            # (avoids infinite recursion after monkeypatching).
            data = json.loads((FIXTURES_DIR / "hydrosheds_synthetic.geojson").read_text())
            return gpd.GeoDataFrame.from_features(
                data["features"],
                crs="EPSG:4326",
            )
        monkeypatch.setattr(gpd, "read_file", _read_file)
    return _factory


# ---------------------------------------------------------------------------
# 1. Returns a FeatureCollection with 2 features
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basins_returns_feature_collection(stub_geopandas):
    stub_geopandas()
    from medieval_forge.services.ingest_terrain.hydrosheds import fetch_basins

    q: asyncio.Queue = asyncio.Queue()
    result = await fetch_basins((-9.5, 36.0, 3.5, 44.0), q)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 2


# ---------------------------------------------------------------------------
# 2. Each feature has exactly {id, next_down, sub_area} with correct types
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basins_property_schema(stub_geopandas):
    stub_geopandas()
    from medieval_forge.services.ingest_terrain.hydrosheds import fetch_basins

    q: asyncio.Queue = asyncio.Queue()
    result = await fetch_basins((-9.5, 36.0, 3.5, 44.0), q)

    for feature in result["features"]:
        props = feature["properties"]
        assert set(props.keys()) == {"id", "next_down", "sub_area"}, (
            f"unexpected keys: {set(props.keys())}"
        )
        assert isinstance(props["id"], int), f"id must be int, got {type(props['id'])}"
        assert isinstance(props["next_down"], int), (
            f"next_down must be int, got {type(props['next_down'])}"
        )
        assert isinstance(props["sub_area"], float), (
            f"sub_area must be float, got {type(props['sub_area'])}"
        )


# ---------------------------------------------------------------------------
# 3. HYBAS_ID column is renamed to "id" in output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basins_renames_hybas_id_to_id(stub_geopandas):
    stub_geopandas()
    from medieval_forge.services.ingest_terrain.hydrosheds import fetch_basins

    q: asyncio.Queue = asyncio.Queue()
    result = await fetch_basins((-9.5, 36.0, 3.5, 44.0), q)

    for feature in result["features"]:
        props = feature["properties"]
        assert "id" in props, "output feature must have 'id' key"
        assert "HYBAS_ID" not in props, "output must NOT have raw 'HYBAS_ID' key"


# ---------------------------------------------------------------------------
# 4. Empty bbox case returns empty FeatureCollection (no error)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basins_empty_bbox_returns_empty_collection(stub_geopandas):
    stub_geopandas(empty=True)
    from medieval_forge.services.ingest_terrain.hydrosheds import fetch_basins

    q: asyncio.Queue = asyncio.Queue()
    result = await fetch_basins((0.0, 0.0, 0.001, 0.001), q)

    assert result == {"type": "FeatureCollection", "features": []}

    # Drain queue to check for "0 bacias" progress message.
    items: list[str] = []
    while not q.empty():
        items.append(q.get_nowait())
    assert any("0 bacias" in item for item in items), (
        f"expected '0 bacias' in queue, got: {items}"
    )


# ---------------------------------------------------------------------------
# 5. Successful run emits at least one SSE line containing "bacias"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basins_emits_progress_log(stub_geopandas):
    stub_geopandas()
    from medieval_forge.services.ingest_terrain.hydrosheds import fetch_basins

    q: asyncio.Queue = asyncio.Queue()
    await fetch_basins((-9.5, 36.0, 3.5, 44.0), q)

    items: list[str] = []
    while not q.empty():
        items.append(q.get_nowait())
    assert any("bacias" in item for item in items), (
        f"expected 'bacias' in SSE queue, got: {items}"
    )
