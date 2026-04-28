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
            json={"territory_data": {
                      "kingdoms": {"k1": "K"},
                      "duchies": {"d1": ("k1", "D")},
                      "condados": [["c1", "C", -3.0, 40.0, "d1", [("B", -3.0, 40.0)]]],
                  },
                  "force_body_territory_data": True},
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

    The service layer recomputes the render bbox from territory centroids + 15%
    padding (via _compute_padded_bbox). For the minimal territory data
    (_minimal_territory_data), centroids are at lon -3.0..-3.5, lat 38.8..41.2,
    giving a padded bbox of roughly lon -3.58..-2.92, lat 38.44..41.56.

    build_land_mask filters polygon points to cfg.lon_min-1 <= lo <= cfg.lon_max+1.
    With the padded bbox that filter window is approximately lon -4.58..-1.92,
    lat 37.44..42.56. The GeoJSON polygon MUST have its vertices inside this
    window so that at least 3 points survive and Pillow can rasterise the polygon.

    We use a rectangle centred on the barony region with ~1° margin on each side
    so all 5 ring points survive the filter regardless of exact padding arithmetic.
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
                        # Rectangle centred on barony centroids (lon ~-3.25, lat ~40.0)
                        # with ~1° margin so all 5 points survive the bbox filter.
                        [-4.5, 37.5],
                        [-2.0, 37.5],
                        [-2.0, 42.5],
                        [-4.5, 42.5],
                        [-4.5, 37.5],
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
async def test_png_outputs(client):
    """GEN-02: real generator produces the headline PNG outputs."""
    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.generator import run_generation
    from medieval_forge.services.paths import ensure_project_dirs

    # Reuse the autouse _isolated_projects_root fake_root.
    fake_root = paths_mod.PROJECTS_ROOT
    created = await _create_project(client)
    pid = created["id"]

    dirs = ensure_project_dirs(pid)
    raw_geojson = dirs["raw"] / "municipalities.geojson"
    geojson_path = _write_minimal_geojson(raw_geojson)
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
async def test_generation_time(client):
    """GEN-04: generation completes in <60s for the minimal example."""
    import time
    from medieval_forge.services.generator import run_generation
    from medieval_forge.services.paths import ensure_project_dirs

    created = await _create_project(client)
    pid = created["id"]

    dirs = ensure_project_dirs(pid)
    raw_geojson = dirs["raw"] / "municipalities.geojson"
    geojson_path = _write_minimal_geojson(raw_geojson)
    config = _make_test_config(geojson_path)

    t0 = time.monotonic()
    await run_generation(pid, config)
    elapsed = time.monotonic() - t0

    assert elapsed < 60.0, f"generation took {elapsed:.1f}s, exceeds GEN-04 budget"


# ---------- Terrain lookup unit tests ----------

def test_terrain_lookup_has_multiple_types():
    """generate_terrain_lookup produces a non-black image with at least land + ocean colors."""
    import numpy as np
    from medieval_forge.lib.map_generator import generate_terrain_lookup, RegionConfig

    cfg = RegionConfig(map_w=64, map_h=64)

    # Land mask: left half = land, right half = ocean.
    land = np.zeros((64, 64), dtype=bool)
    land[:, :32] = True  # left 32 columns are land

    lookup, terrain_types = generate_terrain_lookup(land, cfg, mtn_mask=None)

    # Output shape must match land mask.
    assert lookup.shape == (64, 64, 3)

    # Must have at least 2 distinct RGB values (land + ocean).
    flat = lookup.reshape(-1, 3)
    unique_colors = set(map(tuple, flat))
    assert len(unique_colors) >= 2, f"Expected 2+ unique terrain colors, got {len(unique_colors)}: {unique_colors}"

    # Ocean pixels (right half) must be the ocean color.
    from medieval_forge.lib.map_generator import _TERRAIN_TYPES
    ocean_rgb = _TERRAIN_TYPES["ocean"]["rgb"]
    assert tuple(lookup[0, 63]) == ocean_rgb, "right-half pixel should be ocean color"

    # Land pixels (left half) must NOT be black (0,0,0).
    land_sample = lookup[:, :32].reshape(-1, 3)
    all_black = np.all(land_sample == 0, axis=1)
    assert not np.all(all_black), "All land pixels are black — terrain classification did not run"


def test_terrain_lookup_mountain_mask_applied():
    """Mountain pixels on land are painted with mountain color."""
    import numpy as np
    from medieval_forge.lib.map_generator import generate_terrain_lookup, RegionConfig, _TERRAIN_TYPES

    cfg = RegionConfig(map_w=64, map_h=64)

    # All land.
    land = np.ones((64, 64), dtype=bool)

    # Mountain in top-left 16x16 quadrant.
    mtn = np.zeros((64, 64), dtype=bool)
    mtn[:16, :16] = True

    lookup, terrain_types = generate_terrain_lookup(land, cfg, mtn_mask=mtn)

    mountain_rgb = _TERRAIN_TYPES["mountain"]["rgb"]
    # Every pixel in the mountain quadrant must be mountain color.
    for y in range(16):
        for x in range(16):
            assert tuple(lookup[y, x]) == mountain_rgb, (
                f"pixel ({y},{x}) should be mountain {mountain_rgb}, got {tuple(lookup[y, x])}"
            )


def test_terrain_types_json_structure():
    """terrain_types dict has exactly 4 canonical types with required game stat keys."""
    import numpy as np
    from medieval_forge.lib.map_generator import generate_terrain_lookup, RegionConfig

    cfg = RegionConfig(map_w=32, map_h=32)
    land = np.ones((32, 32), dtype=bool)
    _, terrain_types = generate_terrain_lookup(land, cfg)

    # Exactly 4 types: ocean, coast, plain, mountain (no synthetic hill/forest).
    assert len(terrain_types) == 4, (
        f"Expected exactly 4 terrain types (ocean, coast, plain, mountain), "
        f"got {len(terrain_types)}: {list(terrain_types.keys())}"
    )
    expected_type_names = {"ocean", "coast", "plain", "mountain"}
    actual_type_names = {v["type"] for v in terrain_types.values()}
    assert actual_type_names == expected_type_names, (
        f"Expected terrain types {expected_type_names}, got {actual_type_names}"
    )
    for key, entry in terrain_types.items():
        # Key format: "R,G,B"
        parts = key.split(",")
        assert len(parts) == 3, f"key {key!r} is not R,G,B format"
        assert all(0 <= int(p) <= 255 for p in parts), f"key {key!r} has out-of-range values"
        # Required fields
        assert "movement" in entry, f"terrain_types[{key}] missing 'movement'"
        assert "defense" in entry,  f"terrain_types[{key}] missing 'defense'"
        assert "attack" in entry,   f"terrain_types[{key}] missing 'attack'"


@pytest.mark.slow
async def test_terrain_lookup_files_produced(client, tmp_path):
    """Full pipeline: terrain_lookup.png and terrain_types.json are written and non-trivial."""
    import json as _json
    import numpy as np
    from PIL import Image as _Image
    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.generator import run_generation
    from medieval_forge.services.paths import ensure_project_dirs

    fake_root = paths_mod.PROJECTS_ROOT
    created = await _create_project(client)
    pid = created["id"]

    # Place the GeoJSON in the project's raw/ dir so _validate_municipalities passes.
    dirs = ensure_project_dirs(pid)
    raw_geojson = dirs["raw"] / "municipalities.geojson"
    _write_minimal_geojson(raw_geojson)
    config = _make_test_config(str(raw_geojson))
    await run_generation(pid, config)

    gen_dir = fake_root / pid / "generated"

    # terrain_lookup.png must exist and be non-trivial.
    tlookup = gen_dir / "terrain_lookup.png"
    assert tlookup.exists(), "terrain_lookup.png was not generated"
    img = np.array(_Image.open(str(tlookup)))
    unique_colors = set(map(tuple, img.reshape(-1, 3)))
    assert len(unique_colors) >= 2, (
        f"terrain_lookup.png is trivial: only {len(unique_colors)} unique color(s)"
    )

    # terrain_types.json must exist and have required structure.
    ttypes = gen_dir / "terrain_types.json"
    assert ttypes.exists(), "terrain_types.json was not generated"
    data = _json.loads(ttypes.read_text())
    assert len(data) == 4, f"terrain_types.json has {len(data)} entries — expected exactly 4 (ocean/coast/plain/mountain)"
    for key, entry in data.items():
        assert "movement" in entry and "defense" in entry and "attack" in entry, (
            f"terrain_types.json entry {key!r} missing game stat fields"
        )

    # terrain.png alias must point to the same content as terrain_lookup.png.
    terrain_alias = gen_dir / "terrain.png"
    assert terrain_alias.exists(), "terrain.png alias was not created"
    alias_colors = set(map(tuple, np.array(_Image.open(str(terrain_alias))).reshape(-1, 3)))
    assert alias_colors == unique_colors, "terrain.png and terrain_lookup.png have different content"
