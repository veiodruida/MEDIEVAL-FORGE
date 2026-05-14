"""Plan 07-08 Task 1 — services/export/zip.py overlay merge integration.

Tests cover Pattern 11 + Pitfall 1 + Pitfall 2 + MANIFEST.research_overlay_applied:

  - Test 1: build_unity_zip writes MERGED territory_metadata.json when overlay exists.
  - Test 2: build_unity_zip writes RAW territory_metadata.json when overlay absent (D-12).
  - Test 3: pipeline output on disk is NEVER mutated by zip build (Pitfall 1).
  - Test 4: MANIFEST.research_overlay_applied is True when overlay present.
  - Test 5: MANIFEST.research_overlay_applied is False when overlay absent.

The fixture stubs the heavy 12-file pipeline output minimally: a real
territory_metadata.json plus the other 11 contract files as zero/placeholder
content sufficient for validate_export() to pass. We use a France 1066 toy
output snapshot for speed — fixture caches it module-scoped.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from medieval_forge.services.export import build_unity_zip
from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Module-scoped pipeline output — run France 1066 once, share across tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def france_pipeline_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run france_1066 pipeline once per module; return output directory."""
    out = tmp_path_factory.mktemp("france_1066_zip_overlay")
    clear_region_cache()
    cfg = replace(load_region("france_1066"), output_dir=str(out))
    run_pipeline(cfg)
    return out


@pytest.fixture
def project_with_pipeline_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    france_pipeline_output: Path,
) -> tuple[str, Path]:
    """Stage a project_dir with /output/ pre-populated by the France pipeline.

    Returns (project_id, project_dir). Monkeypatches PROJECTS_ROOT so
    project_dir() resolves under tmp_path.
    """
    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.export import zip as zip_mod

    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    # The export zip module imports project_dir + ensure_project_dirs at import
    # time; the monkeypatch above mutates the module-level attribute and the
    # imported functions resolve PROJECTS_ROOT dynamically, so this is enough.

    project_id = "11111111-2222-3333-4444-555555555555"
    pdir = paths_mod.project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    output_dir = pdir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy every file from the France pipeline output into output/.
    for src in france_pipeline_output.iterdir():
        if src.is_file():
            (output_dir / src.name).write_bytes(src.read_bytes())

    # exports/ directory required by build_unity_zip.
    (pdir / "exports").mkdir(parents=True, exist_ok=True)

    # Silence unused-import warning — module reference required.
    _ = zip_mod

    return project_id, pdir


# ---------------------------------------------------------------------------
# Helper — extract MANIFEST + territory_metadata from a built zip.
# ---------------------------------------------------------------------------


def _read_zip_payload(zip_path: Path) -> tuple[dict, dict]:
    """Return (territory_metadata, manifest) parsed from the zip."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        meta = json.loads(zf.read("territory_metadata.json").decode("utf-8"))
        manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
    return meta, manifest


# ---------------------------------------------------------------------------
# Test 1 — overlay present: merged metadata written to zip
# ---------------------------------------------------------------------------


def test_build_unity_zip_writes_merged_metadata_when_overlay_exists(
    project_with_pipeline_output: tuple[str, Path],
) -> None:
    project_id, pdir = project_with_pipeline_output

    raw_meta = json.loads((pdir / "output" / "territory_metadata.json").read_text(encoding="utf-8"))
    assert raw_meta["condados"], "fixture sanity: at least one condado"
    target_id = raw_meta["condados"][0]["id"]

    overlay_payload = {
        target_id: {
            "name": "Condado Merged via Zip",
            "kingdom_owner": "Reino Merged",
            "historical_notes": "Test note for zip merge.",
        }
    }
    (pdir / "research_overlay.json").write_text(
        json.dumps(overlay_payload), encoding="utf-8"
    )

    cfg = load_region("france_1066")
    zip_path = build_unity_zip(project_id, cfg=cfg, region_key="france_1066")

    meta_in_zip, _manifest = _read_zip_payload(zip_path)
    merged_condado = next(c for c in meta_in_zip["condados"] if c["id"] == target_id)
    assert merged_condado["name"] == "Condado Merged via Zip"
    assert merged_condado["kingdom_owner"] == "Reino Merged"
    assert merged_condado["historical_notes"] == "Test note for zip merge."


# ---------------------------------------------------------------------------
# Test 2 — overlay absent: raw metadata copied through (D-12 zero-LLM)
# ---------------------------------------------------------------------------


def test_build_unity_zip_writes_raw_metadata_when_overlay_absent(
    project_with_pipeline_output: tuple[str, Path],
) -> None:
    project_id, pdir = project_with_pipeline_output
    overlay_file = pdir / "research_overlay.json"
    assert not overlay_file.exists(), "fixture sanity: no overlay file"

    raw_text = (pdir / "output" / "territory_metadata.json").read_text(encoding="utf-8")
    raw_meta = json.loads(raw_text)

    cfg = load_region("france_1066")
    zip_path = build_unity_zip(project_id, cfg=cfg, region_key="france_1066")

    meta_in_zip, _manifest = _read_zip_payload(zip_path)
    # Deep-equal to raw on disk — D-12 invariant.
    assert meta_in_zip == raw_meta


# ---------------------------------------------------------------------------
# Test 3 — Pitfall 1: pipeline output on disk untouched by zip build
# ---------------------------------------------------------------------------


def test_pipeline_output_on_disk_is_never_mutated_by_zip_build(
    project_with_pipeline_output: tuple[str, Path],
) -> None:
    project_id, pdir = project_with_pipeline_output
    raw_meta_path = pdir / "output" / "territory_metadata.json"

    raw_meta = json.loads(raw_meta_path.read_text(encoding="utf-8"))
    target_id = raw_meta["condados"][0]["id"]
    overlay_payload = {
        target_id: {
            "name": "OverlayName",
            "kingdom_owner": "OverlayKingdom",
            "historical_notes": "OverlayNotes",
        }
    }
    (pdir / "research_overlay.json").write_text(
        json.dumps(overlay_payload), encoding="utf-8"
    )

    sha_before = hashlib.sha256(raw_meta_path.read_bytes()).hexdigest()
    cfg = load_region("france_1066")
    build_unity_zip(project_id, cfg=cfg, region_key="france_1066")
    sha_after = hashlib.sha256(raw_meta_path.read_bytes()).hexdigest()

    assert sha_before == sha_after, (
        "Pitfall 1 violated: build_unity_zip mutated pipeline output on disk."
    )


# ---------------------------------------------------------------------------
# Test 4 — MANIFEST.research_overlay_applied is True when overlay present
# ---------------------------------------------------------------------------


def test_manifest_records_research_overlay_applied_true_when_overlay_present(
    project_with_pipeline_output: tuple[str, Path],
) -> None:
    project_id, pdir = project_with_pipeline_output
    raw_meta = json.loads(
        (pdir / "output" / "territory_metadata.json").read_text(encoding="utf-8")
    )
    target_id = raw_meta["condados"][0]["id"]
    (pdir / "research_overlay.json").write_text(
        json.dumps({target_id: {"name": "X"}}), encoding="utf-8"
    )

    cfg = load_region("france_1066")
    zip_path = build_unity_zip(project_id, cfg=cfg, region_key="france_1066")
    _meta, manifest = _read_zip_payload(zip_path)
    assert manifest["research_overlay_applied"] is True


# ---------------------------------------------------------------------------
# Test 5 — MANIFEST.research_overlay_applied is False when overlay absent
# ---------------------------------------------------------------------------


def test_manifest_records_research_overlay_applied_false_when_overlay_absent(
    project_with_pipeline_output: tuple[str, Path],
) -> None:
    project_id, _pdir = project_with_pipeline_output
    cfg = load_region("france_1066")
    zip_path = build_unity_zip(project_id, cfg=cfg, region_key="france_1066")
    _meta, manifest = _read_zip_payload(zip_path)
    assert manifest["research_overlay_applied"] is False
