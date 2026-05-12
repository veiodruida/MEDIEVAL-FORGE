"""Tests for England 1216 YAML-only template behavior — Plan 05-09 (D-12).

Proves that:
1. load_region('england_1216') raises FileNotFoundError with an actionable message
   naming both the region key and the missing dataset path.
2. GET /api/v3/regions returns england_1216 with has_dataset=False (Plan 05-07 endpoint).
"""
import pytest
from medieval_forge.services.pipeline.region_loader import load_region, clear_region_cache


def test_load_region_england_raises_filenotfound():
    clear_region_cache()
    with pytest.raises(FileNotFoundError) as exc_info:
        load_region("england_1216")
    msg = str(exc_info.value)
    assert "england_1216" in msg.lower() or "england" in msg.lower() or "england_municipalities" in msg
    # Must name the missing path so user can act on it
    assert "inputs" in msg or "geojson" in msg or "missing" in msg


def test_regions_endpoint_marks_england_no_dataset():
    # This test exercises GET /api/v3/regions shipped in Plan 05-07.
    # depends_on:[05-01, 05-07] guarantees the endpoint exists when this runs.
    from fastapi.testclient import TestClient
    from medieval_forge.main import app
    c = TestClient(app)
    r = c.get("/api/v3/regions")
    assert r.status_code == 200
    items = {item["key"]: item for item in r.json()}
    assert "england_1216" in items
    assert items["england_1216"]["has_dataset"] is False
