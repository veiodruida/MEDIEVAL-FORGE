"""Tests for EXPORT-01 (zip download) and EXPORT-02 (zip contents)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_projects_root(tmp_path, monkeypatch):
    from medieval_forge.services import paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")


async def _create_project(client, **overrides):
    payload = {
        "name": "exp-test",
        "country_qid": "Q29",
        "period_start": 800,
        "period_end": 1000,
    }
    payload.update(overrides)
    return (await client.post("/api/projects", json=payload)).json()


def _drop_fake_generated_files(generated_dir: Path) -> None:
    """Drop a small set of the 9 generator outputs so build_unity_zip has
    something real to work with — placeholders fill in the other slots."""
    generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "visual_condado.png").write_bytes(b"\x89PNG\r\n\x1a\nfake1")
    (generated_dir / "lookup_condado.png").write_bytes(b"\x89PNG\r\n\x1a\nfake2")
    (generated_dir / "lookup_condado_colors.json").write_text(json.dumps({"1": "rgb"}))
    (generated_dir / "territory_metadata.json").write_text(json.dumps({"k": "v"}))


async def test_build_unity_zip_assembles_12_files(client, tmp_path):
    from medieval_forge.services.export import (
        PLACEHOLDER_FILES,
        UNITY_ZIP_SPEC,
        build_unity_zip,
    )
    from medieval_forge.services.paths import ensure_project_dirs

    created = await _create_project(client)
    pid = created["id"]
    dirs = ensure_project_dirs(pid)
    _drop_fake_generated_files(dirs["generated"])

    zip_path = build_unity_zip(pid)

    assert zip_path.exists()
    assert zip_path.parent == dirs["exports"]
    assert zip_path.name.startswith(f"medieval-forge-{pid}-")
    assert zip_path.suffix == ".zip"

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # All 12 spec files PLUS MANIFEST.json.
        for fname in UNITY_ZIP_SPEC:
            assert fname in names, f"missing {fname}"
        assert "MANIFEST.json" in names

        manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
        assert manifest["project_id"] == pid
        assert manifest["spec_version"] == 1
        assert manifest["phase"] == 1
        manifest_files = {entry["name"]: entry for entry in manifest["files"]}

        # Files we dropped: source == "generated".
        for real in ["visual_condado.png", "lookup_condado.png",
                     "lookup_condado_colors.json", "territory_metadata.json"]:
            assert manifest_files[real]["source"] == "generated"

        # Files in PLACEHOLDER_FILES that we never created: source == "placeholder".
        for placeholder in PLACEHOLDER_FILES:
            assert manifest_files[placeholder]["source"] == "placeholder"


async def test_build_unity_zip_rejects_empty_generated_dir(client, tmp_path):
    from medieval_forge.services.export import build_unity_zip
    from medieval_forge.services.paths import ensure_project_dirs

    created = await _create_project(client)
    pid = created["id"]
    ensure_project_dirs(pid)  # creates empty generated/

    with pytest.raises(FileNotFoundError):
        build_unity_zip(pid)


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (api.export)")
async def test_zip_download(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (EXPORT-02 contents)")
async def test_zip_contents(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (T-PATH on download)")
async def test_download_invalid_uuid_returns_400(client):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (refuses pre-generated state)")
async def test_export_refuses_if_not_generated(client):
    pass
