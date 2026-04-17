"""Tests for GEN-01..04, T-PATH preview guard, T-DOS overlap guard."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolated_projects_root(tmp_path, monkeypatch):
    from medieval_forge.services import paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")


def test_inject_territory_module_creates_sys_modules_entry():
    import importlib
    import sys

    from medieval_forge.services import generator

    name = "_mf_territory_test_unit"
    data = {
        "kingdoms": {"K1": {"name": "Kingdom One"}},
        "duchies": {"D1": {"name": "Duchy"}},
        "condados": {"C1": {"name": "County"}},
    }
    try:
        mod = generator._inject_territory_module(name, data)
        # importlib.import_module finds it (this is the call inside map_generator.load_territory_data).
        loaded = importlib.import_module(name)
        assert loaded is mod
        assert loaded.KINGDOMS == data["kingdoms"]
        assert loaded.DUCHIES == data["duchies"]
        assert loaded.CONDADOS == data["condados"]
    finally:
        generator._cleanup_territory_module(name)
    assert name not in sys.modules


async def _create_project(client, **overrides):
    payload = {
        "name": "gen-test",
        "country_qid": "Q29",
        "period_start": 800,
        "period_end": 1000,
    }
    payload.update(overrides)
    return (await client.post("/api/projects", json=payload)).json()


async def test_trigger_generation(client):
    """POST /generate returns 202 and flips status to 'generating'."""
    created = await _create_project(client)
    pid = created["id"]
    # Stub run_generation so the background task completes quickly without invoking real pipeline.
    async def fake_run(project_id, config):
        return {"territories.png": "generated/territories.png"}
    with patch("medieval_forge.api.generate.run_generation", side_effect=fake_run):
        resp = await client.post(
            f"/api/projects/{pid}/generate",
            json={"territory_data": {"kingdoms": {}, "duchies": {}, "condados": []}},
        )
        assert resp.status_code == 202, resp.text
        assert resp.json() == {"project_id": pid, "status": "generating"}


async def test_trigger_generation_rejects_when_already_generating(client):
    """T-DOS: 409 if project.status == 'generating'."""
    created = await _create_project(client)
    pid = created["id"]
    # Manually flip status to 'generating'.
    await client.patch(f"/api/projects/{pid}", json={"status": "generating"})
    resp = await client.post(
        f"/api/projects/{pid}/generate",
        json={"territory_data": {"kingdoms": {}, "duchies": {}, "condados": []}},
    )
    assert resp.status_code == 409
    assert "generating" in resp.json()["detail"].lower()


async def test_png_fileresponse(client, tmp_path):
    """GEN-03: GET /preview/{filename} returns the file with image/png content-type."""
    from medieval_forge.services.paths import ensure_project_dirs

    created = await _create_project(client)
    pid = created["id"]
    dirs = ensure_project_dirs(pid)
    # Drop a 1x1 PNG byte sequence (valid PNG signature) into generated/.
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (dirs["generated"] / "territories.png").write_bytes(png_bytes)
    resp = await client.get(f"/api/projects/{pid}/preview/territories.png")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == png_bytes


async def test_preview_rejects_non_whitelisted_filename(client):
    """T-PATH: filename not in whitelist -> 400 (not 404).

    Note: path traversal strings like ../../etc/passwd are normalized by the
    ASGI router before reaching our endpoint, so they may resolve to 404/503
    from the SPA catch-all. Only single-segment filenames not in the whitelist
    are reliably tested here.
    """
    created = await _create_project(client)
    pid = created["id"]
    # Single-segment non-whitelisted filenames hit our route and get 400.
    for bad in ["secrets.txt", "wat.png", "arbitrary.png"]:
        resp = await client.get(f"/api/projects/{pid}/preview/{bad}")
        assert resp.status_code == 400, f"{bad}: {resp.status_code} -- {resp.text}"
    # Path traversal: ASGI normalises/redirects these before they reach the route.
    # They are intercepted by the URL router (never reach our handler). The SPA
    # catch-all may serve index.html (200) or return 404/503 depending on whether
    # the frontend is built. In all cases the sensitive file is never read -- the
    # whitelist guard at the route layer provides defence in depth if a traversal
    # string somehow reaches it.
    for traversal in ["../../etc/passwd"]:
        resp = await client.get(f"/api/projects/{pid}/preview/{traversal}")
        # Any status is acceptable here -- what matters is the file is not returned.
        assert resp.status_code in (200, 400, 404, 422, 503), (
            f"{traversal}: unexpected {resp.status_code}"
        )
        # The response must NOT be a PNG (i.e. not the sensitive file).
        assert resp.headers.get("content-type", "").startswith("application/json") or \
               resp.headers.get("content-type", "").startswith("text/html"), \
               f"{traversal}: suspicious content-type {resp.headers.get('content-type')}"
    # And: invalid UUID returns 400.
    resp = await client.get("/api/projects/not-a-uuid/preview/territories.png")
    assert resp.status_code == 400


# ---------- SLOW: real map_generator integration ----------

def _minimal_territory_data() -> dict:
    """Synthetic minimal territory hierarchy matching map_generator's expected schema.

    KINGDOMS: {kingdom_id: kingdom_name_string}
    DUCHIES:  {duchy_id: (kingdom_id, duchy_name_string)}  -- tuple format required
    CONDADOS: list of (id, name, lon, lat, duchy_id, [(barony_name, lon, lat), ...])
    """
    return {
        "kingdoms": {
            "K_TEST": "Test Kingdom",
        },
        "duchies": {
            "D_TEST": ("K_TEST", "Test Duchy"),
        },
        "condados": [
            (
                "C_NORTH",
                "North County",
                -3.0, 41.0,
                "D_TEST",
                [("North Barony", -3.0, 41.0), ("Mid Barony", -3.5, 41.2)],
            ),
            (
                "C_SOUTH",
                "South County",
                -3.0, 39.0,
                "D_TEST",
                [("South Barony", -3.0, 39.0), ("Coast Barony", -3.2, 38.8)],
            ),
        ],
    }


def _write_minimal_geojson(path) -> str:
    """Write a minimal PT-format GeoJSON covering the test barony region.

    build_land_mask filters polygon points to cfg.lon_min-1 <= lo <= cfg.lon_max+1
    and cfg.lat_min-1 <= la <= cfg.lat_max+1 (default: lon [-14.2,9.2] lat [34.4,45.6]).
    Points outside these bounds are dropped before Pillow draws the polygon,
    so the polygon coords MUST be well inside the region bounds to retain >= 3 pts.

    We use a large rectangle at the 4 cardinal extremes of the barony KD-tree seeds
    so the land mask has a fully filled rectangle and the KD-tree can assign every
    pixel to a barony.
    """
    import json
    import pathlib
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        # Rectangle well inside default RegionConfig bounds
                        # (lon_min=-13.2 lon_max=8.2 lat_min=35.4 lat_max=44.6)
                        # so all 5 points survive the bound-filter in build_land_mask.
                        [-12.0, 36.0],
                        [7.0, 36.0],
                        [7.0, 44.0],
                        [-12.0, 44.0],
                        [-12.0, 36.0],
                    ]],
                },
                "properties": {"name": "test-region"},
            }
        ],
    }
    p = pathlib.Path(path)
    p.write_text(json.dumps(geojson))
    return str(p)


def _make_test_config(geojson_path: str) -> dict:
    """Config dict for run_generation: territory data + small map size + GeoJSON path."""
    return {
        "territory_data": _minimal_territory_data(),
        # Use a small map resolution so the pipeline runs quickly.
        "map_w": 192,
        "map_h": 108,
        "upscale": 1,
        "municipality_pt_geojson": geojson_path,
    }


@pytest.mark.slow
async def test_png_outputs(client, tmp_path):
    """GEN-02: real generator produces the headline PNG outputs."""
    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.generator import run_generation

    # Reuse the autouse _isolated_projects_root fake_root.
    fake_root = paths_mod.PROJECTS_ROOT
    created = await _create_project(client)
    pid = created["id"]

    geojson_path = _write_minimal_geojson(tmp_path / "test_region.geojson")
    config = _make_test_config(geojson_path)
    manifest = await run_generation(pid, config)

    gen_dir = fake_root / pid / "generated"
    # Files that must always exist (independent of optional mountain/river data).
    always_required = [
        "visual_condado.png",
        "lookup_condado.png",
        "lookup_condado_colors.json",
        "territory_metadata.json",
        "territories.png",  # alias for visual_condado.png
    ]
    for required in always_required:
        p = gen_dir / required
        assert p.exists(), f"missing required output: {required}"
        if required.endswith(".png"):
            assert p.stat().st_size > 100, f"{required} suspiciously small"
    # Manifest reports at least the required files.
    assert "territories.png" in manifest


@pytest.mark.slow
async def test_generation_time(client, tmp_path):
    """GEN-04: generation completes in <60s for the minimal example."""
    import time
    from medieval_forge.services.generator import run_generation

    created = await _create_project(client)
    pid = created["id"]

    geojson_path = _write_minimal_geojson(tmp_path / "test_region.geojson")
    config = _make_test_config(geojson_path)

    t0 = time.monotonic()
    await run_generation(pid, config)
    elapsed = time.monotonic() - t0

    assert elapsed < 60.0, f"generation took {elapsed:.1f}s, exceeds GEN-04 budget"
