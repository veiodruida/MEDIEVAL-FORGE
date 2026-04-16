"""Tests for GEN-01..04, T-PATH preview guard, T-DOS overlap guard."""
from __future__ import annotations

from pathlib import Path
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
        assert resp.status_code == 400, f"{bad}: {resp.status_code} — {resp.text}"
    # Path traversal: ASGI normalises these before they reach the route.
    # They are intercepted by the URL router (never reach our handler) — acceptable
    # since the whitelist guard at the route layer still blocks them if they do.
    for traversal in ["../../etc/passwd"]:
        resp = await client.get(f"/api/projects/{pid}/preview/{traversal}")
        assert resp.status_code in (400, 404, 422, 503), f"{traversal}: {resp.status_code}"
    # And: invalid UUID returns 400.
    resp = await client.get("/api/projects/not-a-uuid/preview/territories.png")
    assert resp.status_code == 400


@pytest.mark.slow
@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (slow integration with real map_generator)")
async def test_png_outputs(client, tmp_path):
    pass


@pytest.mark.slow
@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (GEN-04 performance assertion)")
async def test_generation_time(client, tmp_path):
    pass
