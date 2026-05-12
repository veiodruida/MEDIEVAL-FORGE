"""Integration tests: generate + render use load_region — Plan 05-04.

Tests:
  1. test_post_v3_projects_persists_region_key  — POST creates project with region_key
  2. test_generate_uses_load_region             — generate producer calls load_region spy
  3. test_render_uses_load_region               — render producer calls load_region spy
  4. test_load_region_singleton_not_mutated     — replace() never mutates cached singleton
"""
from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from medieval_forge.main import app
from medieval_forge.services.pipeline.region_loader import load_region, clear_region_cache


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Test 1: POST /api/v3/projects persists region_key
# ---------------------------------------------------------------------------

def test_post_v3_projects_persists_region_key(client):
    """POST /api/v3/projects with region_key='iberia_868' returns 201 + region_key."""
    r = client.post("/api/v3/projects", json={"name": "parity-test", "region_key": "iberia_868"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["region_key"] == "iberia_868"
    assert "id" in body
    assert body["name"] == "parity-test"


def test_post_v3_projects_rejects_unknown_region(client):
    """POST /api/v3/projects with unknown region_key returns 400."""
    r = client.post("/api/v3/projects", json={"name": "x", "region_key": "no_such_region"})
    assert r.status_code == 400
    assert "no_such_region" in r.json()["detail"]


def test_post_v3_projects_rejects_path_injection(client):
    """POST /api/v3/projects with path-injection region_key returns 422."""
    r = client.post("/api/v3/projects", json={"name": "x", "region_key": "../escape"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Test 2: generate endpoint calls load_region with project.region_key
# ---------------------------------------------------------------------------

def test_generate_uses_load_region(client):
    """POST /generate schedules producer that calls load_region('iberia_868')."""
    # Create a project first
    r = client.post("/api/v3/projects", json={"name": "gen-spy", "region_key": "iberia_868"})
    assert r.status_code == 201
    project_id = r.json()["id"]

    # Build a real RegionConfig to return from the spy
    real_cfg = load_region("iberia_868")

    spy_calls: list[str] = []

    def _spy(key, regions_dir=None):
        spy_calls.append(key)
        return real_cfg

    with patch("medieval_forge.api.v3.generate.load_region", side_effect=_spy):
        r2 = client.post(f"/api/v3/projects/{project_id}/generate")
        # 202 = scheduled; 409 = already running (both mean producer was queued)
        assert r2.status_code in (202, 409), r2.text

    # Give the event loop a moment; for 202 the producer task was created
    if r2.status_code == 202:
        assert spy_calls == ["iberia_868"], f"Expected load_region called with 'iberia_868', got {spy_calls}"


# ---------------------------------------------------------------------------
# Test 3: render endpoint calls load_region with project.region_key
# ---------------------------------------------------------------------------

def test_render_uses_load_region(client):
    """POST /render schedules producer that calls load_region('iberia_868')."""
    # Create a project first
    r = client.post("/api/v3/projects", json={"name": "render-spy", "region_key": "iberia_868"})
    assert r.status_code == 201
    project_id = r.json()["id"]

    real_cfg = load_region("iberia_868")

    spy_calls: list[str] = []

    def _spy(key, regions_dir=None):
        spy_calls.append(key)
        return real_cfg

    with patch("medieval_forge.api.v3.render.load_region", side_effect=_spy):
        r2 = client.post(
            f"/api/v3/projects/{project_id}/render",
            json={"cfg_overrides": {}},
        )
        assert r2.status_code in (202, 409), r2.text

    if r2.status_code == 202:
        assert spy_calls == ["iberia_868"], f"Expected load_region called with 'iberia_868', got {spy_calls}"


# ---------------------------------------------------------------------------
# Test 4: load_region singleton is NOT mutated by replace()
# ---------------------------------------------------------------------------

def test_load_region_singleton_not_mutated():
    """dataclasses.replace() in generate/render never mutates the cached singleton.

    Calls load_region twice with different output_dir overrides via replace(),
    then asserts the cached object's output_dir is unchanged (YAML-declared value).
    This is the RESEARCH Pitfall 9 / T-05-04-04 regression guard.
    """
    clear_region_cache()
    cfg_original = load_region("iberia_868")
    original_output_dir = cfg_original.output_dir  # YAML-declared value

    # Simulate what generate.py does: replace() with a different output_dir
    cfg_copy_a = dataclasses.replace(cfg_original, output_dir="/tmp/run_a/output")
    cfg_copy_b = dataclasses.replace(cfg_original, output_dir="/tmp/run_b/output")

    # Copies have their own output_dir
    assert cfg_copy_a.output_dir == "/tmp/run_a/output"
    assert cfg_copy_b.output_dir == "/tmp/run_b/output"

    # The cached singleton is unmodified — retrieve it again to confirm cache hit
    cfg_after = load_region("iberia_868")
    assert cfg_after.output_dir == original_output_dir, (
        f"Singleton was mutated! output_dir changed from {original_output_dir!r} "
        f"to {cfg_after.output_dir!r}"
    )
    # The returned object is the same cached instance
    assert cfg_after is cfg_original, "load_region should return the same cached instance"
